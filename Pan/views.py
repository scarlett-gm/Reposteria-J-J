from django.shortcuts import render, redirect
from decimal import Decimal
from .models import (
    CompraInsumo, ProductoProveedor, Producto, Proveedor, Insumo,
    Vendedor, Venta, DetalleVenta, Produccion, ProductoInsumo
)
from django.utils import timezone
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.db import transaction
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncDate
import json

def listar_productos(request):
    productos = Producto.objects.all()
    return render(request, 'listar_productos.html', {'productos': productos})

def home(request):
    return render(request, 'base.html')

def ventas(request):
    vendedores = Vendedor.objects.order_by('nombre')
    productos = Producto.objects.order_by('nombre')

    if request.method == 'POST':
        vendedor_id = request.POST.get('vendedor')
        producto_ids = request.POST.getlist('producto_id')
        cantidades = request.POST.getlist('cantidad')

        if not vendedor_id:
            return render(request, 'ventas.html', {
                'vendedores': vendedores,
                'productos': productos,
                'error': 'Seleccione un vendedor.'
            })

        # Construir diccionario con la cantidad requerida por producto (sumar filas duplicadas)
        required = {}
        for i, pid in enumerate(producto_ids):
            if not pid:
                continue
            try:
                qty = int(cantidades[i]) if i < len(cantidades) and cantidades[i] else 0
            except Exception:
                qty = 0
            if qty <= 0:
                continue
            required[pid] = required.get(pid, 0) + qty

        if not required:
            return render(request, 'ventas.html', {
                'vendedores': vendedores,
                'productos': productos,
                'error': 'Agregue al menos un producto con cantidad válida.'
            })

        # Validar stock antes de crear la venta (y usar bloqueo para concurrencia)
        with transaction.atomic():
            productos_objs = Producto.objects.select_for_update().filter(pk__in=required.keys())
            prod_map = {p.id: p for p in productos_objs}

            insuficientes = []
            for pid, qty in required.items():
                p = prod_map.get(int(pid))
                disponible = Decimal(p.stock or 0) if p else Decimal('0')
                if disponible < Decimal(qty):
                    insuficientes.append({
                        'producto_id': pid,
                        'nombre': p.nombre if p else f'ID {pid}',
                        'disponible': float(disponible),
                        'requerido': qty
                    })

            if insuficientes:
                # Si falta stock en al menos un producto, cancelar todo y avisar
                return render(request, 'ventas.html', {
                    'vendedores': vendedores,
                    'productos': productos,
                    'error': 'Stock insuficiente para completar la venta. No se realizó ningún registro.',
                    'insuficientes': insuficientes
                })

            # Todo OK: crear Venta y DetalleVenta, y actualizar stock (ya tenemos bloqueo)
            # usar hora local Centroamérica (UTC-6) al crear la venta
            venta = Venta.objects.create(vendedor_id=vendedor_id, fecha_hora=timezone.now())

            for pid, qty in required.items():
                DetalleVenta.objects.create(venta=venta, producto_id=pid, cantidad=qty)
                p = prod_map.get(int(pid))
                if p:
                    p.stock = (p.stock or Decimal('0')) - Decimal(qty)
                    p.save(update_fields=['stock'])

        return redirect('ventas')

    return render(request, 'ventas.html', {
        'vendedores': vendedores,
        'productos': productos,
    })

def dashboard(request):
    range_param = request.GET.get('range', 'Hoy')
    today = timezone.localdate()

    if range_param == '7':
        start_date_sel = today - timedelta(days=6)
        detalles_qs = DetalleVenta.objects.filter(venta__fecha_hora__date__gte=start_date_sel)
    else:
        detalles_qs = DetalleVenta.objects.filter(venta__fecha_hora__date=today)

    line_total = ExpressionWrapper(
        F('cantidad') * F('producto__precio_venta'),
        output_field=DecimalField(max_digits=18, decimal_places=2)
    )

    agg = detalles_qs.aggregate(ingresos_total=Sum(line_total), unidades_vendidas=Sum('cantidad'))
    ingresos_total = agg['ingresos_total'] or Decimal('0.00')
    unidades_vendidas = agg['unidades_vendidas'] or 0

    start_7 = today - timedelta(days=6)
    detalles_7 = DetalleVenta.objects.filter(venta__fecha_hora__date__gte=start_7)
    diarios_qs = detalles_7.annotate(dia=TruncDate('venta__fecha_hora')).values('dia').annotate(
        ingreso_dia=Sum(line_total)
    ).order_by('dia')
    diarios_map = {item['dia']: (item['ingreso_dia'] or Decimal('0.00')) for item in diarios_qs}

    labels = []
    values = []
    for i in range(7):
        d = start_7 + timedelta(days=i)
        labels.append(d.strftime('%Y-%m-%d'))
        values.append(float(diarios_map.get(d, Decimal('0.00'))))
    ingresos_last7_total = sum(values)

    top_qs = detalles_qs.values('producto__id', 'producto__nombre').annotate(total_vendidos=Sum('cantidad')).order_by('-total_vendidos')[:4]
    top_sellers = [{'producto_id': it['producto__id'], 'nombre': it['producto__nombre'], 'vendidos': it['total_vendidos'] or 0} for it in top_qs]

    low_stock_qs = Insumo.objects.filter(stock__lt=Decimal('10')).order_by('stock')
    low_stock_count = low_stock_qs.count()
    low_stock_items = list(low_stock_qs[:4])

    detalles_today = DetalleVenta.objects.filter(venta__fecha_hora__date=today)
    ventas_vendedores_qs = detalles_today.values(
        'venta__vendedor__id', 'venta__vendedor__nombre'
    ).annotate(
        total_unidades=Sum('cantidad'),
        ingreso_total=Sum(line_total)
    ).order_by('-ingreso_total')

    ventas_vendedores_hoy = [
        {
            'vendedor_id': it.get('venta__vendedor__id'),
            'vendedor': it.get('venta__vendedor__nombre') or '',
            'unidades': it.get('total_unidades') or 0,
            'ingreso': it.get('ingreso_total') or Decimal('0.00'),
        }
        for it in ventas_vendedores_qs
    ]

    context = {
        'ingresos_total': ingresos_total,
        'unidades_vendidas': unidades_vendidas,
        'range_selected': range_param,
        'low_stock_count': low_stock_count,
        'low_stock_items': low_stock_items,
        'top_sellers': top_sellers,
        'ingresos_last7_total': ingresos_last7_total,
        'sales_chart_labels_json': json.dumps(labels),
        'sales_chart_values_json': json.dumps(values),
        'ventas_vendedores_hoy': ventas_vendedores_hoy,
    }
    return render(request, 'dashboard.html', context)

def Compras(request):
    """
    Muestra página de Compras con tablas. Anota 'total' = cantidad * precio_unitario
    para compras de insumos y compras de productos.
    También procesa los formularios POST para registrar Compras de Insumos o Productos.
    """
    # --- Procesar POST (compra de insumos o compra de productos) ---
    if request.method == 'POST':
        fecha_str = request.POST.get('fecha')
        # parsear fecha (input type="date")
        if fecha_str:
            try:
                fecha_date = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                now_local = timezone.localtime()
                fecha_dt = timezone.make_aware(datetime.combine(fecha_date, now_local.time()))
            except Exception:
                fecha_dt = timezone.now()
        else:
            fecha_dt = timezone.now()

        # Comprar Insumos
        insumo_ids = request.POST.getlist('insumo_id')
        if insumo_ids and any(i for i in insumo_ids):
            proveedor_id = request.POST.get('proveedor')
            cantidades = request.POST.getlist('cantidad')
            precios = request.POST.getlist('precio_unitario')

            with transaction.atomic():
                for i, insumo_id in enumerate(insumo_ids):
                    if not insumo_id:
                        continue
                    try:
                        cantidad = Decimal(cantidades[i]) if i < len(cantidades) and cantidades[i] else Decimal('0')
                        precio = Decimal(precios[i]) if i < len(precios) and precios[i] else Decimal('0')
                    except Exception:
                        continue

                    CompraInsumo.objects.create(
                        proveedor_id=proveedor_id,
                        insumo_id=insumo_id,
                        cantidad=cantidad,
                        precio_unitario=precio,
                        fecha=fecha_dt
                    )

                    # actualizar stock de insumo
                    try:
                        insumo_obj = Insumo.objects.select_for_update().get(pk=insumo_id)
                        insumo_obj.stock = (insumo_obj.stock or Decimal('0')) + cantidad
                        insumo_obj.save(update_fields=['stock'])
                    except Insumo.DoesNotExist:
                        pass

            return redirect('Compras')

        # Comprar Productos/Bebidas
        producto_ids = request.POST.getlist('producto_id')
        if producto_ids and any(p for p in producto_ids):
            proveedor_id = request.POST.get('proveedor')
            cantidades = request.POST.getlist('cantidad')
            precios = request.POST.getlist('precio_unitario')

            with transaction.atomic():
                for i, producto_id in enumerate(producto_ids):
                    if not producto_id:
                        continue
                    try:
                        cantidad = Decimal(cantidades[i]) if i < len(cantidades) and cantidades[i] else Decimal('0')
                        precio = Decimal(precios[i]) if i < len(precios) and precios[i] else Decimal('0')
                    except Exception:
                        continue

                    ProductoProveedor.objects.create(
                        proveedor_id=proveedor_id,
                        producto_id=producto_id,
                        cantidad=cantidad,
                        precio_unitario=precio,
                        fecha=fecha_dt
                    )

                    # actualizar stock del producto
                    try:
                        producto_obj = Producto.objects.select_for_update().get(pk=producto_id)
                        producto_obj.stock = (producto_obj.stock or Decimal('0')) + cantidad
                        producto_obj.save(update_fields=['stock'])
                    except Producto.DoesNotExist:
                        pass

            return redirect('Compras')

    # --- GET: preparar datos para mostrar las tablas y selects ---
    line_total_expr = ExpressionWrapper(
        F('cantidad') * F('precio_unitario'),
        output_field=DecimalField(max_digits=18, decimal_places=2)
    )

    compras_insumos = CompraInsumo.objects.select_related('proveedor', 'insumo') \
        .annotate(total=line_total_expr) \
        .order_by('-fecha')[:200]

    compras_productos = ProductoProveedor.objects.select_related('proveedor', 'producto') \
        .annotate(total=line_total_expr) \
        .order_by('-fecha')[:200]

    # proveedores e items para los selects (si tu template los usa)
    proveedores_insumos = Proveedor.objects.filter(tipo_proveedor='INSUMOS').order_by('nombre')
    proveedores_bebidas = Proveedor.objects.filter(tipo_proveedor='BEBIDAS').order_by('nombre')
    insumos = Insumo.objects.order_by('nombre')
    productos_bebida = Producto.objects.filter(tipo_producto='BEBIDA').order_by('nombre')

    return render(request, 'Compras.html', {
        'compras_insumos': compras_insumos,
        'compras_productos': compras_productos,
        'proveedores_insumos': proveedores_insumos,
        'proveedores_bebidas': proveedores_bebidas,
        'insumos': insumos,
        'productos_bebida': productos_bebida,
    })

def produccion(request):
    productos_pan = Producto.objects.filter(tipo_producto='PAN').prefetch_related('productoinsumo_set__insumo').order_by('nombre')

    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad_raw = request.POST.get('cantidad')
        fecha_str = request.POST.get('fecha_hora')

        try:
            cantidad = int(cantidad_raw)
        except (TypeError, ValueError):
            cantidad = 0

        # validar que la cantidad sea >= 1
        if not producto_id or cantidad < 1:
            return render(request, 'produccion.html', {
                'productos_pan': productos_pan,
                'error': 'La cantidad debe ser al menos 1.',
                'selected_product_id': int(producto_id) if producto_id else None,
                'cantidad_inicial': cantidad_raw or ''
            })

        if fecha_str:
            try:
                dt = datetime.strptime(fecha_str, '%Y-%m-%dT%H:%M')
                fecha_dt = timezone.make_aware(dt)
            except Exception:
                fecha_dt = timezone.now()
        else:
            fecha_dt = timezone.now()

        producto_insumos = ProductoInsumo.objects.filter(producto_id=producto_id).select_related('insumo')
        required = {}
        for pi in producto_insumos:
            uso = Decimal(pi.cantidad_utilizada or 0)
            total_consumo = uso * Decimal(cantidad)
            if total_consumo > 0:
                required[pi.insumo_id] = {'insumo_id': pi.insumo_id, 'insumo_nombre': pi.insumo.nombre, 'requerido': total_consumo}

        with transaction.atomic():
            if required:
                insumo_objs = Insumo.objects.select_for_update().filter(pk__in=list(required.keys()))
                insuff = []
                insumo_map = {i.id: i for i in insumo_objs}
                for iid, info in required.items():
                    insumo_obj = insumo_map.get(iid)
                    disponible = Decimal(insumo_obj.stock or 0) if insumo_obj else Decimal('0')
                    if disponible < info['requerido']:
                        insuff.append({'nombre': info['insumo_nombre'], 'disponible': float(disponible), 'requerido': float(info['requerido'])})

                if insuff:
                    return render(request, 'produccion.html', {'productos_pan': productos_pan, 'error': 'Stock insuficiente para iniciar la producción.', 'insuficientes': insuff, 'selected_product_id': int(producto_id), 'cantidad_inicial': cantidad})

            prod_record = Produccion.objects.create(producto_id=producto_id, cantidad=cantidad, fecha_hora=fecha_dt)

            try:
                producto_obj = Producto.objects.select_for_update().get(pk=producto_id)
                producto_obj.stock = (producto_obj.stock or Decimal('0')) + Decimal(cantidad)
                producto_obj.save(update_fields=['stock'])
            except Producto.DoesNotExist:
                pass

            for iid, info in required.items():
                try:
                    insumo_obj = Insumo.objects.select_for_update().get(pk=iid)
                    insumo_obj.stock = (insumo_obj.stock or Decimal('0')) - Decimal(info['requerido'])
                    insumo_obj.save(update_fields=['stock'])
                except Insumo.DoesNotExist:
                    continue

        return redirect('produccion')

    # --- Preparar lista de las últimas 10 producciones con coste calculado ---
    producciones_qs = Produccion.objects.select_related('producto').order_by('-fecha_hora')[:10]
    # obtener todos los product_ids presentes y traer sus recetas
    product_ids = [p.producto_id for p in producciones_qs]
    receta_qs = ProductoInsumo.objects.filter(producto_id__in=product_ids).select_related('insumo')
    receta_map = {}
    for pi in receta_qs:
        receta_map.setdefault(pi.producto_id, []).append(pi)

    producciones_recientes = []
    for prod in producciones_qs:
        # Coste total calculado como: cantidad_producida * producto.costo
        producto_obj = prod.producto
        precio_producto = Decimal(getattr(producto_obj, 'costo', 0) or 0)
        try:
            costo_total = Decimal(prod.cantidad) * precio_producto
        except Exception:
            costo_total = Decimal('0')

        producciones_recientes.append({
            'fecha': prod.fecha_hora,
            'producto_nombre': prod.producto.nombre if prod.producto else '',
            'cantidad': prod.cantidad,
            'costo_total': costo_total,
        })

    return render(request, 'produccion.html', {'productos_pan': productos_pan, 'producciones_recientes': producciones_recientes})

from django.shortcuts import render, redirect
from decimal import Decimal
from .models import CompraInsumo, ProductoProveedor, Producto, Proveedor, Insumo, Vendedor, Venta, DetalleVenta, Produccion, ProductoInsumo
from django.utils import timezone
from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncDate
import json

def listar_productos(request):
    productos = Producto.objects.all()  # Traemos todos los productos
    return render(request, 'listar_productos.html', {'productos': productos})


def home(request):
    return render(request, 'base.html')

def ventas(request):
    """
    GET: muestra formulario de venta con vendedores y productos.
    POST: crea Venta + DetalleVenta(s) y actualiza stock de Producto.
    """
    if request.method == 'POST':
        vendedor_id = request.POST.get('vendedor')
        producto_ids = request.POST.getlist('producto_id')
        cantidades = request.POST.getlist('cantidad')

        # validar mínimamente
        if not vendedor_id or not producto_ids:
            return redirect('ventas')

        with transaction.atomic():
            # crear cabecera de venta
            venta = Venta.objects.create(vendedor_id=vendedor_id)

            for i, prod_id in enumerate(producto_ids):
                if not prod_id:
                    continue
                try:
                    cantidad = int(cantidades[i]) if i < len(cantidades) and cantidades[i] else 0
                except Exception:
                    cantidad = 0
                if cantidad <= 0:
                    continue

                # crear detalle de venta
                DetalleVenta.objects.create(
                    venta=venta,
                    producto_id=prod_id,
                    cantidad=cantidad,
                )

                # restar stock del producto (bloqueo para concurrencia)
                try:
                    producto_obj = Producto.objects.select_for_update().get(pk=prod_id)
                    producto_obj.stock = (producto_obj.stock or Decimal('0')) - Decimal(cantidad)
                    producto_obj.save(update_fields=['stock'])
                except Producto.DoesNotExist:
                    # si no existe, continuar; podrías loguear el error
                    continue

        return redirect('ventas')  # o redirigir a una vista de recibo

    # GET
    vendedores = Vendedor.objects.order_by('nombre')
    productos = Producto.objects.order_by('nombre')
    return render(request, 'ventas.html', {
        'vendedores': vendedores,
        'productos': productos,
    })

def dashboard(request):
    """
    Muestra dashboard. Calcula total de ventas según rango seleccionado (Hoy o últimos 7 días).
    También construye datos diarios de ingresos para los últimos 7 días (para la gráfica y el total).
    """
    range_param = request.GET.get('range', 'Hoy')  # 'Hoy' or '7' (últimos 7 días)
    today = timezone.localdate()

    # queryset para el rango seleccionado (para KPI "Total de ventas" y "Productos vendidos")
    if range_param == '7':
        start_date_sel = today - timedelta(days=6)
        detalles_qs = DetalleVenta.objects.filter(venta__fecha_hora__date__gte=start_date_sel)
    else:
        detalles_qs = DetalleVenta.objects.filter(venta__fecha_hora__date=today)

    # Expresión: cantidad * producto.precio_venta
    line_total = ExpressionWrapper(
        F('cantidad') * F('producto__precio_venta'),
        output_field=DecimalField(max_digits=18, decimal_places=2)
    )

    agg = detalles_qs.aggregate(
        ingresos_total=Sum(line_total),
        unidades_vendidas=Sum('cantidad')
    )

    ingresos_total = agg['ingresos_total'] or Decimal('0.00')
    unidades_vendidas = agg['unidades_vendidas'] or 0

    # --- Datos para últimos 7 días (gráfica y total de 7 días) ---
    start_7 = today - timedelta(days=6)
    detalles_7 = DetalleVenta.objects.filter(venta__fecha_hora__date__gte=start_7)

    # Agrupar por fecha y sumar ingreso por día
    diarios_qs = detalles_7.annotate(dia=TruncDate('venta__fecha_hora')).values('dia').annotate(
        ingreso_dia=Sum(line_total)
    ).order_by('dia')

    # Mapea resultados por fecha para rellenar todos los días
    diarios_map = {item['dia']: (item['ingreso_dia'] or Decimal('0.00')) for item in diarios_qs}

    labels = []
    values = []
    for i in range(7):
        d = start_7 + timedelta(days=i)
        labels.append(d.strftime('%Y-%m-%d'))  # formato ISO para la gráfica; puedes ajustar formato
        values.append(float(diarios_map.get(d, Decimal('0.00'))))

    ingresos_last7_total = sum(values)

    # Top vendidos: agrupar por producto y sumar cantidades en el rango seleccionado
    top_qs = detalles_qs.values('producto__id', 'producto__nombre').annotate(
        total_vendidos=Sum('cantidad')
    ).order_by('-total_vendidos')[:4]

    top_sellers = [
        {
            'producto_id': item['producto__id'],
            'nombre': item['producto__nombre'],
            'vendidos': item['total_vendidos'] or 0
        }
        for item in top_qs
    ]

    # Insumos con bajo stock (< 10)
    low_stock_qs = Insumo.objects.filter(stock__lt=Decimal('10')).order_by('stock')
    low_stock_count = low_stock_qs.count()
    low_stock_items = list(low_stock_qs[:4])  # máximo 4 para alertas

    # --- Ventas de Hoy: agrupar por venta y calcular ingreso por venta ---
    detalles_today = DetalleVenta.objects.filter(venta__fecha_hora__date=today)
    ventas_hoy_qs = detalles_today.values('venta_id', 'venta__vendedor__nombre').annotate(
        ingreso_venta=Sum(line_total)
    ).order_by('-ingreso_venta')

    ventas_hoy = [
        {
            'venta_id': item['venta_id'],
            'vendedor': item['venta__vendedor__nombre'] or '',
            'ingreso': item['ingreso_venta'] or Decimal('0.00')
        }
        for item in ventas_hoy_qs
    ]

    context = {
        'ingresos_total': ingresos_total,
        'unidades_vendidas': unidades_vendidas,
        'range_selected': range_param,
        'low_stock_count': low_stock_count,
        'low_stock_items': low_stock_items,
        'top_sellers': top_sellers,
        # datos para la vista de 7 días / gráfica
        'ingresos_last7_total': ingresos_last7_total,
        'sales_chart_labels_json': json.dumps(labels),
        'sales_chart_values_json': json.dumps(values),
        # ventas hoy
        'ventas_hoy': ventas_hoy,
    }
    return render(request, 'dashboard.html', context)

def Compras(request):
    """
    GET: muestra formularios y tablas (compras de insumos y compras de productos).
    POST: procesa ya sea el formulario de insumos (insumo_id...) o el de productos (producto_id...).
    """
    if request.method == 'POST':
        # --- parse fecha enviada por el formulario (input type="date") ---
        fecha_str = request.POST.get('fecha')
        if fecha_str:
            try:
                fecha_date = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                now_local = timezone.localtime()
                fecha_dt = timezone.make_aware(datetime.combine(fecha_date, now_local.time()))
            except Exception:
                fecha_dt = timezone.now()
        else:
            fecha_dt = timezone.now()

        # Procesar compra de insumos (crear registros y actualizar stock de Insumo)
        if request.POST.getlist('insumo_id'):
            proveedor_id = request.POST.get('proveedor')
            insumo_ids = request.POST.getlist('insumo_id')
            cantidades = request.POST.getlist('cantidad')
            precios = request.POST.getlist('precio_unitario')

            # usar transacción para asegurar consistencia al actualizar stock
            with transaction.atomic():
                for i, insumo_id in enumerate(insumo_ids):
                    if not insumo_id:
                        continue
                    try:
                        cantidad = Decimal(cantidades[i]) if i < len(cantidades) and cantidades[i] else Decimal('0')
                        precio = Decimal(precios[i]) if i < len(precios) and precios[i] else Decimal('0')
                    except Exception:
                        continue

                    # crear registro de compra
                    CompraInsumo.objects.create(
                        proveedor_id=proveedor_id,
                        insumo_id=insumo_id,
                        cantidad=cantidad,
                        precio_unitario=precio,
                        fecha=fecha_dt,
                    )

                    # actualizar stock del insumo (uso select_for_update para bloqueo de fila)
                    try:
                        insumo_obj = Insumo.objects.select_for_update().get(pk=insumo_id)
                        insumo_obj.stock = (insumo_obj.stock or Decimal('0')) + cantidad
                        insumo_obj.save(update_fields=['stock'])
                    except Insumo.DoesNotExist:
                        # si no existe el insumo, continuar (puedes registrar un log aquí)
                        continue
            return redirect('Compras')
 
        # Procesar compra de productos/bebidas (crear registros y actualizar stock de Producto)
        if request.POST.getlist('producto_id'):
            proveedor_id = request.POST.get('proveedor')
            producto_ids = request.POST.getlist('producto_id')
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
                        fecha=fecha_dt,
                    )

                    # actualizar stock del producto
                    try:
                        producto_obj = Producto.objects.select_for_update().get(pk=producto_id)
                        producto_obj.stock = (producto_obj.stock or Decimal('0')) + cantidad
                        producto_obj.save(update_fields=['stock'])
                    except Producto.DoesNotExist:
                        continue
            return redirect('Compras')
 
    # Consultas para mostrar en la página
    compras_insumos = CompraInsumo.objects.select_related('proveedor', 'insumo').order_by('-fecha')[:200]
    compras_productos = ProductoProveedor.objects.select_related('proveedor', 'producto').order_by('-fecha')[:200]

    # Proveedores filtrados por tipo
    proveedores_insumos = Proveedor.objects.filter(tipo_proveedor='INSUMOS').order_by('nombre')
    proveedores_bebidas = Proveedor.objects.filter(tipo_proveedor='BEBIDAS').order_by('nombre')

    # Lista de insumos y productos (solo bebidas)
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
    """
    GET: mostrar formulario con productos tipo PAN y sus insumos (ProductoInsumo).
    POST: crear Produccion, aumentar stock del Producto por la cantidad producida
    y disminuir stock de Insumo según la receta (ProductoInsumo).
    Antes de crear, valida que haya stock suficiente de cada insumo; si no, cancela y muestra mensaje.
    """
    # GET data share (usado también en re-render en caso de error)
    productos_pan = Producto.objects.filter(tipo_producto='PAN').prefetch_related('productoinsumo_set__insumo').order_by('nombre')

    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad_raw = request.POST.get('cantidad')
        fecha_str = request.POST.get('fecha_hora')  # formato datetime-local: 'YYYY-MM-DDTHH:MM'

        try:
            cantidad = int(cantidad_raw)
        except Exception:
            cantidad = 0

        # parsear fecha_hora
        if fecha_str:
            try:
                dt = datetime.strptime(fecha_str, '%Y-%m-%dT%H:%M')
                fecha_dt = timezone.make_aware(dt)
            except Exception:
                fecha_dt = timezone.now()
        else:
            fecha_dt = timezone.now()

        if not producto_id or cantidad <= 0:
            return render(request, 'produccion.html', {
                'productos_pan': productos_pan,
                'error': 'Producto o cantidad inválida.',
                'selected_product_id': int(producto_id) if producto_id else None,
                'cantidad_inicial': cantidad,
            })

        # calcular consumo total requerido por insumo
        producto_insumos = ProductoInsumo.objects.filter(producto_id=producto_id).select_related('insumo')
        required = {}
        for pi in producto_insumos:
            try:
                uso = Decimal(pi.cantidad_utilizada or 0)
            except Exception:
                uso = Decimal('0')
            total_consumo = uso * Decimal(cantidad)
            if total_consumo > 0:
                required[pi.insumo_id] = {
                    'insumo_id': pi.insumo_id,
                    'insumo_nombre': pi.insumo.nombre,
                    'requerido': total_consumo
                }

        with transaction.atomic():
            # bloquear filas de insumos implicados y comprobar disponibilidad
            if required:
                insumo_objs = Insumo.objects.select_for_update().filter(pk__in=list(required.keys()))
                insuff = []
                insumo_map = {i.id: i for i in insumo_objs}
                for iid, info in required.items():
                    insumo_obj = insumo_map.get(iid)
                    disponible = Decimal(insumo_obj.stock or 0) if insumo_obj else Decimal('0')
                    if disponible < info['requerido']:
                        insuff.append({
                            'nombre': info['insumo_nombre'],
                            'disponible': float(disponible),
                            'requerido': float(info['requerido'])
                        })

                if insuff:
                    # hay faltantes -> no realizar producción, mostrar mensaje
                    return render(request, 'produccion.html', {
                        'productos_pan': productos_pan,
                        'error': 'Stock insuficiente para iniciar la producción. Ver detalles.',
                        'insuficientes': insuff,
                        'selected_product_id': int(producto_id),
                        'cantidad_inicial': cantidad,
                    })

            # todo ok -> crear Produccion, actualizar stock producto e insumos
            prod_record = Produccion.objects.create(
                producto_id=producto_id,
                cantidad=cantidad,
                fecha_hora=fecha_dt
            )

            # actualizar stock del producto
            try:
                producto_obj = Producto.objects.select_for_update().get(pk=producto_id)
                producto_obj.stock = (producto_obj.stock or Decimal('0')) + Decimal(cantidad)
                producto_obj.save(update_fields=['stock'])
            except Producto.DoesNotExist:
                pass

            # restar insumos
            for iid, info in required.items():
                try:
                    insumo_obj = Insumo.objects.select_for_update().get(pk=iid)
                    insumo_obj.stock = (insumo_obj.stock or Decimal('0')) - Decimal(info['requerido'])
                    insumo_obj.save(update_fields=['stock'])
                except Insumo.DoesNotExist:
                    # si no existe, continuar
                    continue

        return redirect('produccion')

    # GET
    return render(request, 'produccion.html', {
        'productos_pan': productos_pan,
    })
# Create your views here.

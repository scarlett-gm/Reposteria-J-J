from django.shortcuts import render, get_object_or_404
from .models import Producto, Insumo, Venta, Produccion

def lista_productos(request):
    productos = Producto.objects.all()
    return render(request, "productos/lista.html", {"productos": productos})

def detalle_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    return render(request, "productos/detalle.html", {"producto": producto})

def lista_insumos(request):
    insumos = Insumo.objects.all()
    return render(request, "insumos/lista.html", {"insumos": insumos})

def lista_ventas(request):
    ventas = Venta.objects.all().prefetch_related("detalles__producto")
    return render(request, "ventas/lista.html", {"ventas": ventas})

def lista_producciones(request):
    producciones = Produccion.objects.select_related("producto").all()
    return render(request, "produccion/lista.html", {"producciones": producciones})

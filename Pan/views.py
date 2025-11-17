from django.shortcuts import render

def home(request):
    return render(request, 'base.html')

def ventas(request):
    return render(request, 'ventas.html')

def dashboard(request):
    return render(request, 'dashboard.html')

def Compras(request):
    return render(request, 'Compras.html')

def produccion(request):
    return render(request, 'produccion.html')
# Create your views here.

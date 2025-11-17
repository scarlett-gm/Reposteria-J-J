from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # URL vacía -> dashboard
    path('dashboard/', views.dashboard, name='dashboard'),  # Ruta explícita para dashboard
    path('ventas/', views.ventas, name='ventas'),  # Nueva ruta para ventas
    path('compras/', views.Compras, name='Compras'),
    path('produccion/', views.produccion, name='produccion'),  # Ruta de producción (temporalmente apunta a home)
]

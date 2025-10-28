from django.db import models

# ------------------------------
# MODELOS PRINCIPALES
# ------------------------------

class Proveedor(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=200)
    telefono = models.CharField(max_length=20)
    tipo_proveedor = models.CharField(max_length=50, choices=[
        ('INSUMOS', 'Insumos'),
        ('BEBIDAS', 'Bebidas')
    ])

    def __str__(self):
        return self.nombre


class Insumo(models.Model):
    nombre = models.CharField(max_length=100)
    stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coste = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    TIPO_CHOICES = [
        ('PAN', 'Pan'),
        ('BEBIDA', 'Bebida')
    ]

    nombre = models.CharField(max_length=100)
    tipo_producto = models.CharField(max_length=10, choices=TIPO_CHOICES)
    costo = models.DecimalField(max_digits=10, decimal_places=2)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.nombre} ({self.tipo_producto})"


# ------------------------------
# RELACIONES ESPECIALES
# ------------------------------

# Relación Producto (Pan) - Insumo, con cantidad específica usada
class ProductoInsumo(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, limit_choices_to={'tipo_producto': 'PAN'})
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad_utilizada = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.producto} usa {self.cantidad_utilizada} de {self.insumo}"


# Relación Producto (Bebida) - Proveedor
class ProductoProveedor(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, limit_choices_to={'tipo_producto': 'BEBIDA'})
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.proveedor} provee {self.producto}"


# Compra de insumos
class CompraInsumo(models.Model):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, limit_choices_to={'tipo_proveedor': 'INSUMOS'})
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Compra de {self.cantidad} {self.insumo} a {self.proveedor}"


# Producción (solo aplica a productos tipo Pan)
class Produccion(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, limit_choices_to={'tipo_producto': 'PAN'})
    fecha_hora = models.DateTimeField(auto_now_add=True)
    cantidad = models.PositiveIntegerField()

    def __str__(self):
        return f"Producción de {self.cantidad} {self.producto}"


# Vendedor
class Vendedor(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


# Venta
class Venta(models.Model):
    vendedor = models.ForeignKey(Vendedor, on_delete=models.CASCADE)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Venta #{self.id} - {self.fecha_hora.strftime('%d/%m/%Y')}"


# Productos vendidos en una venta (detalle)
class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.cantidad} x {self.producto}"

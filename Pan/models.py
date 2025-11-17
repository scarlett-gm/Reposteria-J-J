from django.db import models

class Proveedor(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=200)
    telefono = models.CharField(max_length=20)
    tipo_proveedor = models.CharField(max_length=50, choices=[('INSUMOS', 'INSUMOS'), ('BEBIDAS', 'BEBIDAS')])

    class Meta:
        db_table = 'Proveedor'
        managed = False

class Insumo(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coste = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'Insumo'
        managed = False

class Producto(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    tipo_producto = models.CharField(max_length=10, choices=[('PAN', 'PAN'), ('BEBIDA', 'BEBIDA')])
    costo = models.DecimalField(max_digits=10, decimal_places=2)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = 'Producto'
        managed = False

class ProductoInsumo(models.Model):
    id = models.AutoField(primary_key=True)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad_utilizada = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'ProductoInsumo'
        managed = False

class CompraInsumo(models.Model):
    id = models.AutoField(primary_key=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE)
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField()  # ahora se asigna desde la vista

    class Meta:
        db_table = 'CompraInsumo'
        managed = False

class ProductoProveedor(models.Model):
    id = models.AutoField(primary_key=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField()  # ahora se asigna desde la vista

    class Meta:
        db_table = 'ProductoProveedor'
        managed = False

class Produccion(models.Model):
    id = models.AutoField(primary_key=True)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    # permitimos asignar la fecha desde el formulario
    fecha_hora = models.DateTimeField()
    cantidad = models.IntegerField()

    class Meta:
        db_table = 'Produccion'
        managed = False

class Vendedor(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = 'Vendedor'
        managed = False

class Venta(models.Model):
    id = models.AutoField(primary_key=True)
    vendedor = models.ForeignKey(Vendedor, on_delete=models.CASCADE)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'Venta'
        managed = False

class DetalleVenta(models.Model):
    id = models.AutoField(primary_key=True)
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.IntegerField()

    class Meta:
        db_table = 'DetalleVenta'
        managed = False
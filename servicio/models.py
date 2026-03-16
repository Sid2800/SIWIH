from django.db import models
from django.contrib.auth.models import User
from ubicacion.models import Sector


# Create your models here.
class Zona(models.Model):
    codigo = models.AutoField(
        verbose_name="id",
        primary_key=True
    )
    nombre_zona = models.CharField(max_length=60, verbose_name="Nombre Zona")
    estado = models.BooleanField(default=True) 

    class Meta:
        verbose_name = "Zona"
        verbose_name_plural = "Zonas"
        ordering = ["codigo",]  

    def __str__(self):
        return self.nombre_zona
    

class Servicio(models.Model):
    nombre_servicio = models.CharField(max_length=60, verbose_name="Nombre Servicio")
    nombre_corto = models.CharField(max_length=10, verbose_name="Nombre Corto Servicio", default="NA")
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=[(1, "Activo"), (2, "Inactivo")],
        default=1
    )
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='servicios_creados')  # Corregido related_name
    fecha_modificado = models.DateTimeField(verbose_name="Editado", auto_now=True)
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='servicios_modificados')  # Corregido related_name

    class Meta:
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"
        ordering = ["nombre_servicio",]  

    def __str__(self):
        return self.nombre_servicio


class Sala(models.Model):
    nombre_sala = models.CharField(max_length=60, verbose_name="Nombre Sala")
    nombre_corto_sala = models.CharField(max_length=20, unique=True, blank=True, null=True)
    
    SEXO_CHOICES = [
        (0, "Indiferente"),
        (1, "Masculino"),
        (2, "Femenino"),
    ]
    sexo_esperado = models.SmallIntegerField(
        verbose_name="Sexo Esperado",
        choices=SEXO_CHOICES,
        default=1
    )

    edad_minima_meses = models.PositiveIntegerField(
        verbose_name="Edad Mínima (meses)",
        null=True, blank=True
    )
    
    edad_maxima_meses = models.PositiveIntegerField(
        verbose_name="Edad Máxima (meses)",
        null=True, blank=True
    )

    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=[(1, "Activo"), (2, "Inactivo")],
        default=1
    )
    
    servicio = models.ForeignKey(
        'Servicio',  # Usa el nombre de la clase como string si la referencia circular es un problema
        on_delete=models.PROTECT,
        related_name="salas_servicio"
    )
    
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='salas_creadas')  # Corregido related_name
    fecha_modificado = models.DateTimeField(verbose_name="Fecha Editado", auto_now=True)
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='salas_modificadas')  # Corregido related_name

    class Meta:
        verbose_name = "Sala"
        verbose_name_plural = "Salas"
        ordering = ["nombre_sala",]  

    def __str__(self):
        return f"{self.nombre_sala} | {self.servicio.nombre_corto}"


class Cama(models.Model):
    numero_cama = models.IntegerField(verbose_name="Número de Cama", primary_key=True)
    
    ESTADO_CAMAS = [
        (1, "Disponible"),
        (2, "Ocupada"),
        (3, "En Mantenimiento"),
    ]
    estado = models.IntegerField(
        verbose_name="Estado de la Cama",
        choices=ESTADO_CAMAS,
        default=1
    )
    
    sala = models.ForeignKey(
        Sala,  # Relación con el modelo Sala
        on_delete=models.PROTECT,
        related_name="camas_sala"
    )

    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='camas_creadas')  # Corregido related_name
    fecha_modificado = models.DateTimeField(verbose_name="Fecha Editado", auto_now=True)
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='camas_modificadas')  # Corregido related_name

    class Meta:
        verbose_name = "Cama"
        verbose_name_plural = "Camas"
        ordering = ["numero_cama",]  

    def __str__(self):
        return f"Cama {self.numero_cama} - {self.sala.nombre_sala}"


class Especialidad(models.Model):
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name='especialidades')
    nombre_especialidad = models.CharField(max_length=100, unique=True)
    nombre_corto_especialidad = models.CharField(max_length=20, unique=True, blank=True, null=True)

    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=[(1, "Activo"), (2, "Inactivo")],
        default=1
    )

    def __str__(self):
        return f"{self.nombre_especialidad} ({self.servicio.nombre_servicio})"

    class Meta:
        verbose_name = "Especialidad"
        verbose_name_plural = "Especialidades"
        ordering = ['nombre_especialidad']


class ServiciosAux(models.Model):
    nombre_servicio_a = models.CharField(max_length=100, unique=True)
    nombre_corto_servicio_a = models.CharField(max_length=20, unique=True, blank=True, null=True)
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=[(1, "Activo"), (2, "Inactivo")],
        default=1
    )

    def __str__(self):
        return f"{self.nombre_servicio_a})"

    class Meta:
        verbose_name = "Servicio Auxiliar"
        verbose_name_plural = "Servicios Auxiliares"
        ordering = ['nombre_servicio_a']

# REFERENCIA
class Proveedor_salud(models.Model):
    nombre_proveedor_salud = models.CharField(
        verbose_name="Nombre del proveedor de salud",
        max_length=30,
        unique=True,
        null=False,
        blank=False
    )
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=[(1, "Activo"), (2, "Inactivo")],
        default=1
    )

    def __str__(self):
        return f"{self.nombre_proveedor_salud}"

    class Meta:
        verbose_name = "Proveedor de salud"
        verbose_name_plural = "Proveedores de salud"
        ordering = ['nombre_proveedor_salud']

class Nivel_complejidad_institucional(models.Model):
    nivel_complejidad = models.SmallIntegerField(
        verbose_name="Nivel de complejidad",
        unique=False
    )
    siglas = models.CharField(
        verbose_name="Siglas del nivel de complejidad",
        max_length=30,
        unique=True,
        null=True,
        blank=True
    )
    detalle_nivel_complejidad = models.CharField(
        verbose_name="Detalle del nivel de complejidad",
        max_length=100,
        unique=True,
        null=False,
        blank=False
    )
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=[(1, "Activo"), (2, "Inactivo")],
        default=1
    )

    def __str__(self):
        return f"{self.detalle_nivel_complejidad}"

    class Meta:
        verbose_name = "Nivel de complejidad institucional"
        verbose_name_plural = "Niveles de complejidad institucional"
        ordering = ['nivel_complejidad']

class Region_salud(models.Model):
    codigo = models.PositiveSmallIntegerField(unique=True)
    nombre_region_salud = models.CharField(
        verbose_name="Nombre de la region de salud",
        max_length=50,
        unique=True,
        null=False,
        blank=False
    )
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=[(1, "Activo"), (2, "Inactivo")],
        default=1
    )

    def __str__(self):
        return f"#-{self.codigo}- {self.nombre_region_salud}"

    class Meta:
        verbose_name = "Region Sanitaria salud"
        verbose_name_plural = "Region Sanitaria salud"
        ordering = ['nombre_region_salud']

class Gestor(models.Model):
    nombre_gestor = models.CharField(
        verbose_name="Nombre del gestor",
        max_length=30,
        unique=True,
        null=False,
        blank=False
    )
    detalle_gestor = models.CharField(
        verbose_name="Detalle del gestor",
        max_length=100,
        unique=True,
        null=True,
        blank=True
    )
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=[(1, "Activo"), (2, "Inactivo")],
        default=1
    )

    def __str__(self):
        return f"{self.nombre_gestor}"

    class Meta:
        verbose_name = "Gestor"
        verbose_name_plural = "Gestores"
        ordering = ['nombre_gestor']

class Institucion_salud(models.Model):
    codigo_sesal = models.IntegerField(
        verbose_name="Codigo SESAL",
        unique=True,
        null=True,
        blank=True
    )
    nombre_institucion_salud = models.CharField(
        verbose_name="Nombre de la institucion de salud",
        max_length=50,
        unique=False,
        null=False,
        blank=False
    )
    proveedor_salud = models.ForeignKey(
        Proveedor_salud,
        on_delete=models.PROTECT,
        related_name='proveedores'
    )
    nivel_complejidad_institucional = models.ForeignKey(
        Nivel_complejidad_institucional,
        on_delete=models.PROTECT,
        related_name='niveles'
    )
    region_salud = models.ForeignKey(
        Region_salud,
        on_delete=models.PROTECT,
        related_name='regiones'
    )
    gestor = models.ForeignKey(
        Gestor,
        on_delete=models.PROTECT,
        related_name='gestores',
        null=True,
        blank=True
    )
    nivel_atencion = models.SmallIntegerField(
        verbose_name="Nivel de atencion",
        choices=[
            (1, "Primer nivel"),
            (2, "Segundo nivel"),
            (3, "Otros")  # Ajusté esta opción
        ],
        default=1
    )
    centralizado = models.BooleanField(
        verbose_name="Centralizado",
        choices=[(True, "SI"), (False, "NO")],
        default=True
    )
    telefono = models.CharField(
        verbose_name="Telefono",
        null=True,
        blank=True,
        max_length=12
    )
    direccion = models.ForeignKey(
        Sector,
        on_delete=models.PROTECT,
        related_name='instituciones_salud',
        null=True
    )
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=[(1, "Activo"), (2, "Inactivo")],
        default=1
    )

    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='instituciones_creadas')  # Corregido related_name
    fecha_modificado = models.DateTimeField(verbose_name="Fecha Editado", auto_now=True)
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='instituciones_modificadas')

    def __str__(self):
        return f"{self.region_salud.codigo}- {self.nivel_complejidad_institucional.siglas}- {self.nombre_institucion_salud} "

    class Meta:
        verbose_name = "Institucion de salud"
        verbose_name_plural = "Instituciones de salud"
        ordering = ['nombre_institucion_salud']


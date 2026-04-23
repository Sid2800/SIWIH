from django.db import models
from django.contrib.auth.models import User
from ubicacion.models import Sector
from django.db.models import Q
from core.constants.choices_constants import (
    TipoUnidad,
    EstadoRegistro,
    EstadoCama,
    NivelAtencion,
)
from django.core.exceptions import ValidationError


# Create your models here.
class Zona(models.Model):
    codigo = models.AutoField(verbose_name="id", primary_key=True)
    nombre_zona = models.CharField(max_length=60, verbose_name="Nombre Zona")
    estado = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Zona"
        verbose_name_plural = "Zonas"
        ordering = [
            "codigo",
        ]

    def __str__(self):
        return self.nombre_zona


class Servicio(models.Model):
    nombre_servicio = models.CharField(max_length=60, verbose_name="Nombre Servicio")
    nombre_corto = models.CharField(
        max_length=10, verbose_name="Nombre Corto Servicio", default="NA"
    )
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO,
    )
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="servicios_creados"
    )  # Corregido related_name
    fecha_modificado = models.DateTimeField(verbose_name="Editado", auto_now=True)
    modificado_por = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="servicios_modificados"
    )  # Corregido related_name

    class Meta:
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"
        ordering = [
            "nombre_servicio",
        ]

    def __str__(self):
        return self.nombre_servicio


class Sala(models.Model):
    nombre_sala = models.CharField(max_length=60, verbose_name="Nombre Sala")
    nombre_corto_sala = models.CharField(
        max_length=20, unique=True, blank=True, null=True
    )

    SEXO_CHOICES = [
        (0, "Indiferente"),
        (1, "Masculino"),
        (2, "Femenino"),
    ]
    sexo_esperado = models.SmallIntegerField(
        verbose_name="Sexo Esperado", choices=SEXO_CHOICES, default=1
    )

    edad_minima_meses = models.PositiveIntegerField(
        verbose_name="Edad Mínima (meses)", null=True, blank=True
    )

    edad_maxima_meses = models.PositiveIntegerField(
        verbose_name="Edad Máxima (meses)", null=True, blank=True
    )

    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO,
    )

    servicio = models.ForeignKey(
        "Servicio",  # Usa el nombre de la clase como string si la referencia circular es un problema
        on_delete=models.PROTECT,
        related_name="salas_servicio",
    )

    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="salas_creadas"
    )  # Corregido related_name
    fecha_modificado = models.DateTimeField(verbose_name="Fecha Editado", auto_now=True)
    modificado_por = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="salas_modificadas"
    )  # Corregido related_name

    class Meta:
        verbose_name = "Sala"
        verbose_name_plural = "Salas"
        ordering = [
            "nombre_sala",
        ]

    def __str__(self):
        return f"{self.nombre_sala} | {self.servicio.nombre_corto}"


class Cubiculo(models.Model):
    numero = models.PositiveIntegerField(verbose_name="Numero de Cubiculo")

    nombre_cubiculo = models.CharField(max_length=100, verbose_name="Nombre Cubiculo")

    sala = models.ForeignKey(Sala, on_delete=models.PROTECT, related_name="cubiculos")

    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO,
    )

    class Meta:
        verbose_name = "Cubiculo"
        verbose_name_plural = "Cubiculos"
        ordering = ["sala", "numero"]
        unique_together = ("sala", "numero")

    def __str__(self):
        return f"#{self.numero} {self.nombre_cubiculo}"


class Cama(models.Model):
    numero_cama = models.IntegerField(verbose_name="Número de Cama", primary_key=True)

    estado = models.IntegerField(
        verbose_name="Estado de la Cama",
        choices=EstadoCama.choices,
        default=EstadoCama.DISPONIBLE,
    )

    sala = models.ForeignKey(
        Sala,  # Relación con el modelo Sala
        on_delete=models.PROTECT,
        related_name="camas_sala",
    )

    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="camas_creadas"
    )  # Corregido related_name
    fecha_modificado = models.DateTimeField(verbose_name="Fecha Editado", auto_now=True)
    modificado_por = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="camas_modificadas"
    )  # Corregido related_name
    cubiculo = models.ForeignKey(
        Cubiculo, on_delete=models.PROTECT, related_name="camas", null=True, blank=True
    )

    class Meta:
        verbose_name = "Cama"
        verbose_name_plural = "Camas"
        ordering = [
            "numero_cama",
        ]

    def __str__(self):
        return f"Cama {self.numero_cama} - {self.sala.nombre_sala}"


class Area_atencion(models.Model):
    servicio = models.ForeignKey(
        Servicio, on_delete=models.PROTECT, related_name="servicio_Area_atencion"
    )
    nombre_area_atencion = models.CharField(max_length=100, unique=True)
    nombre_corto_area_atencion = models.CharField(
        max_length=20, unique=True, blank=True, null=True
    )

    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO,
    )

    def __str__(self):
        return f"{self.nombre_area_atencion} ({self.servicio.nombre_servicio})"

    class Meta:
        verbose_name = "Area atencion"
        verbose_name_plural = "Areas atencion"
        ordering = ["nombre_area_atencion"]


class ServiciosAux(models.Model):
    nombre_servicio_a = models.CharField(max_length=100, unique=True)
    nombre_corto_servicio_a = models.CharField(
        max_length=20, unique=True, blank=True, null=True
    )
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO,
    )

    def __str__(self):
        return f"{self.nombre_servicio_a})"

    class Meta:
        verbose_name = "Servicio Auxiliar"
        verbose_name_plural = "Servicios Auxiliares"
        ordering = ["nombre_servicio_a"]


# lugares no clinicos


class Unidad(models.Model):
    nombre_unidad = models.CharField(max_length=100, unique=True)
    nombre_corto_unidad = models.CharField(
        max_length=20, unique=True, blank=True, null=True
    )
    tipo = models.PositiveSmallIntegerField(
        choices=TipoUnidad.choices, default=TipoUnidad.CLINICA
    )
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO,
    )
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="unidades_creadas"
    )
    fecha_modificado = models.DateTimeField(verbose_name="Fecha Editado", auto_now=True)
    modificado_por = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="unidades_modificadas"
    )

    def __str__(self):
        return f"{self.nombre_unidad}"


# REFERENCIA
class Proveedor_salud(models.Model):
    nombre_proveedor_salud = models.CharField(
        verbose_name="Nombre del proveedor de salud",
        max_length=30,
        unique=True,
        null=False,
        blank=False,
    )
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO,
    )

    def __str__(self):
        return f"{self.nombre_proveedor_salud}"

    class Meta:
        verbose_name = "Proveedor de salud"
        verbose_name_plural = "Proveedores de salud"
        ordering = ["nombre_proveedor_salud"]


class Nivel_complejidad_institucional(models.Model):
    nivel_complejidad = models.SmallIntegerField(
        verbose_name="Nivel de complejidad", unique=False
    )
    siglas = models.CharField(
        verbose_name="Siglas del nivel de complejidad",
        max_length=30,
        unique=True,
        null=True,
        blank=True,
    )
    detalle_nivel_complejidad = models.CharField(
        verbose_name="Detalle del nivel de complejidad",
        max_length=100,
        unique=True,
        null=False,
        blank=False,
    )
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO,
    )

    def __str__(self):
        return f"{self.detalle_nivel_complejidad}"

    class Meta:
        verbose_name = "Nivel de complejidad institucional"
        verbose_name_plural = "Niveles de complejidad institucional"
        ordering = ["nivel_complejidad"]


class Region_salud(models.Model):
    codigo = models.PositiveSmallIntegerField(unique=True)
    nombre_region_salud = models.CharField(
        verbose_name="Nombre de la region de salud",
        max_length=50,
        unique=True,
        null=False,
        blank=False,
    )
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO,
    )

    def __str__(self):
        return f"#-{self.codigo}- {self.nombre_region_salud}"

    class Meta:
        verbose_name = "Region Sanitaria salud"
        verbose_name_plural = "Region Sanitaria salud"
        ordering = ["nombre_region_salud"]


class Gestor(models.Model):
    nombre_gestor = models.CharField(
        verbose_name="Nombre del gestor",
        max_length=30,
        unique=True,
        null=False,
        blank=False,
    )
    detalle_gestor = models.CharField(
        verbose_name="Detalle del gestor",
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO,
    )

    def __str__(self):
        return f"{self.nombre_gestor}"

    class Meta:
        verbose_name = "Gestor"
        verbose_name_plural = "Gestores"
        ordering = ["nombre_gestor"]


class Institucion_salud(models.Model):
    codigo_sesal = models.IntegerField(
        verbose_name="Codigo SESAL", unique=True, null=True, blank=True
    )
    nombre_institucion_salud = models.CharField(
        verbose_name="Nombre de la institucion de salud",
        max_length=50,
        unique=False,
        null=False,
        blank=False,
    )
    proveedor_salud = models.ForeignKey(
        Proveedor_salud, on_delete=models.PROTECT, related_name="proveedores"
    )
    nivel_complejidad_institucional = models.ForeignKey(
        Nivel_complejidad_institucional,
        on_delete=models.PROTECT,
        related_name="niveles",
    )
    region_salud = models.ForeignKey(
        Region_salud, on_delete=models.PROTECT, related_name="regiones"
    )
    gestor = models.ForeignKey(
        Gestor, on_delete=models.PROTECT, related_name="gestores", null=True, blank=True
    )
    nivel_atencion = models.SmallIntegerField(
        verbose_name="Nivel de atencion",
        choices=NivelAtencion.choices,
        default=NivelAtencion.PRIMER_NIVEL,
    )
    centralizado = models.BooleanField(
        verbose_name="Centralizado", choices=[(True, "SI"), (False, "NO")], default=True
    )
    telefono = models.CharField(
        verbose_name="Telefono", null=True, blank=True, max_length=12
    )
    direccion = models.ForeignKey(
        Sector, on_delete=models.PROTECT, related_name="instituciones_salud", null=True
    )
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO,
    )
    es_unidad_clinica = models.BooleanField(default=False)
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="instituciones_creadas"
    )  # Corregido related_name
    fecha_modificado = models.DateTimeField(verbose_name="Fecha Editado", auto_now=True)
    modificado_por = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="instituciones_modificadas"
    )

    def __str__(self):
        return f"{self.region_salud.codigo}- {self.nivel_complejidad_institucional.siglas}- {self.nombre_institucion_salud} "

    class Meta:
        verbose_name = "Institucion de salud"
        verbose_name_plural = "Instituciones de salud"
        ordering = ["nombre_institucion_salud"]


class Unidad_clinica(models.Model):
    # es un catalogo de ubicaciones pobibles a nuivel clinico
    area_atencion = models.ForeignKey(
        Area_atencion, on_delete=models.PROTECT, null=True, blank=True
    )
    sala = models.ForeignKey(Sala, on_delete=models.PROTECT, null=True, blank=True)
    servicio_aux = models.ForeignKey(
        ServiciosAux, on_delete=models.PROTECT, null=True, blank=True
    )
    establecimiento_ext = models.ForeignKey(
        Institucion_salud, on_delete=models.PROTECT, null=True, blank=True
    )

    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO,
    )

    def __str__(self):
        if self.area_atencion:
            return f"{self.area_atencion.nombre_area_atencion} ({self.area_atencion.servicio.nombre_servicio})"
        if self.sala:
            return f"{self.sala.nombre_sala}"
        if self.servicio_aux:
            return f"{self.servicio_aux.nombre_servicio_a}"
        if self.establecimiento_ext:
            return f"{self.establecimiento_ext.nivel_complejidad_institucional.siglas} | {self.establecimiento_ext.nombre_institucion_salud}"
        return "Punto clínico"

    def get_tipo_unidad(self):
        if self.area_atencion:
            return ("AREA", "Área de Atención")
        if self.sala:
            return ("SALA", "Sala")
        if self.servicio_aux:
            return ("SERVICIO_AUX", "Servicio Auxiliar")
        if self.establecimiento_ext:
            return ("EXTERNO", "Institución Externa")
        return ("NONE", "Sin tipo")

    def get_descripcion(self):
        if self.area_atencion:
            return self.area_atencion.nombre_area_atencion
        if self.sala:
            return self.sala.nombre_sala
        if self.servicio_aux:
            return self.servicio_aux.nombre_servicio_a
        if self.establecimiento_ext:
            return f"{self.establecimiento_ext.nivel_complejidad_institucional.siglas} | {self.establecimiento_ext.nombre_institucion_salud}"
        return "Sin descripción"

    def clean(self):
        campos = {
            "area_atencion": self.area_atencion,
            "sala": self.sala,
            "servicio_aux": self.servicio_aux,
            "establecimiento_ext": self.establecimiento_ext,
        }

        llenos = [nombre for nombre, valor in campos.items() if valor is not None]

        if len(llenos) == 0:
            raise ValidationError(
                "Debe seleccionar al menos un tipo de unidad clínica."
            )

        if len(llenos) > 1:
            raise ValidationError(
                f"Solo puede seleccionar un tipo de unidad clínica. Actualmente tiene: {', '.join(llenos)}"
            )

    @property
    def tipo_unidad(self):
        return self.get_tipo_unidad()

    @property
    def descripcion(self):
        return self.get_descripcion()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Unidad Clinica"
        verbose_name_plural = "Unidades Clinicas"

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from rrhh.models import Empleado
from servicio.models import Area_atencion, Unidad

# Helpers de normalizacion.
# Se ejecutan antes de guardar para evitar datos repetidos con espacios,
# inventarios demasiado largos o catalogos escritos con distintas mayusculas.

def normalizar_codigo_inventario(valor, nombre_campo):
    valor = (valor or "").strip()

    if not valor:
        return None

    cantidad_digitos = sum(caracter.isdigit() for caracter in valor)
    if cantidad_digitos > 15:
        raise ValidationError(
            f"El {nombre_campo} no puede contener más de 15 números."
        )

    return valor


def normalizar_inventario_bienes_nacionales(valor):
    return normalizar_codigo_inventario(valor, "inventario de bienes nacionales")


def normalizar_inventario_numero_ficha(valor):
    return normalizar_codigo_inventario(valor, "inventario número de ficha")


def normalizar_nombre_catalogo(valor):
    return (valor or "").strip().upper()


def obtener_catalogo_indefinido(modelo_catalogo):
    # Marca/modelo pueden venir vacios; se usa un registro comun de catalogo
    # para no guardar textos sueltos ni dejar la FK en blanco.
    objeto, _ = modelo_catalogo.objects.get_or_create(
        nombre="INDEFINIDO",
        defaults={"descripcion": "Valor usado cuando el dato no aplica."},
    )
    return objeto
# Choices: Django guarda numeros en base de datos y muestra etiquetas legibles
# en formularios/templates con get_campo_display().

class EstadoDispositivo(models.IntegerChoices):
    OPERATIVO = 1, "Operativo"
    EN_MANTENIMIENTO = 2, "En mantenimiento"
    FUERA_DE_SERVICIO = 3, "Fuera de servicio"
    DADO_DE_BAJA = 4, "Dado de baja"
    REPUESTO_PENDIENTE = 5, "Repuesto pendiente"


class CriticidadDispositivo(models.IntegerChoices):
    BAJA = 1, "Baja"
    MEDIA = 2, "Media"
    ALTA = 3, "Alta"


class TipoTecnologiaDispositivo(models.IntegerChoices):
    ELECTRONICO = 1, "Electrónico"
    NO_ELECTRONICO = 2, "No electrónico"


# Catalogos administrables desde Django admin.
# El campo activo oculta opciones nuevas sin borrar historico ya usado.
class TipoDispositivo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=250, blank=True)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "equipo_tipo_dispositivo"
        verbose_name = "Tipo de equipo"
        verbose_name_plural = "Tipos de equipo"
        ordering = ["nombre"]

    def clean(self):
        # clean() centraliza reglas del modelo. Django lo ejecuta desde full_clean().
        self.nombre = normalizar_nombre_catalogo(self.nombre)
        if not self.nombre:
            raise ValidationError({"nombre": "Debe ingresar el tipo de equipo."})

    def save(self, *args, **kwargs):
        # full_clean() hace que estas reglas apliquen tambien desde admin, shell
        # o vistas, no solo desde un formulario web.
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class MarcaDispositivo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=250, blank=True)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "equipo_marca_dispositivo"
        verbose_name = "Marca de equipo"
        verbose_name_plural = "Marcas de equipo"
        ordering = ["nombre"]

    def clean(self):
        # Los catalogos se guardan en mayuscula para evitar duplicados visuales.
        self.nombre = normalizar_nombre_catalogo(self.nombre)
        if not self.nombre:
            raise ValidationError({"nombre": "Debe ingresar la marca del equipo."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class ModeloDispositivo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=250, blank=True)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "equipo_modelo_dispositivo"
        verbose_name = "Modelo de equipo"
        verbose_name_plural = "Modelos de equipo"
        ordering = ["nombre"]

    def clean(self):
        # Misma regla que tipo/marca: nombres limpios y en mayuscula.
        self.nombre = normalizar_nombre_catalogo(self.nombre)
        if not self.nombre:
            raise ValidationError({"nombre": "Debe ingresar el modelo del equipo."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class AreaGestora(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=250, blank=True)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "equipo_area_gestora"
        verbose_name = "Area gestora"
        verbose_name_plural = "Areas gestoras"
        ordering = ["nombre"]

    def clean(self):
        # Area administrativa o tecnica que maneja el registro del equipo.
        self.nombre = normalizar_nombre_catalogo(self.nombre)
        if not self.nombre:
            raise ValidationError({"nombre": "Debe ingresar el area gestora."})
        if self.nombre == "INDEFINIDO":
            raise ValidationError({
                "nombre": "El area gestora debe ser un area real."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class ColorDispositivo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=250, blank=True)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "equipo_color_dispositivo"
        verbose_name = "Color de equipo"
        verbose_name_plural = "Colores de equipo"
        ordering = ["nombre"]

    def clean(self):
        self.nombre = normalizar_nombre_catalogo(self.nombre)
        if not self.nombre:
            raise ValidationError({"nombre": "Debe ingresar el color del equipo."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre

# Tabla principal del modulo.
# Guarda la ficha del equipo y apunta a catalogos por FK para mantener la base
# ligera: se guardan ids numericos, no textos repetidos.

class Dispositivo(models.Model):
    tipo = models.ForeignKey(
        TipoDispositivo,
        on_delete=models.PROTECT,
        related_name="dispositivos",
    )
    tipo_tecnologia = models.PositiveSmallIntegerField(
        choices=TipoTecnologiaDispositivo.choices,
        null=True,
        db_index=True,
    )
    marca = models.ForeignKey(
        MarcaDispositivo,
        on_delete=models.PROTECT,
        related_name="dispositivos",
        null=True,
        blank=True,
    )
    modelo = models.ForeignKey(
        ModeloDispositivo,
        on_delete=models.PROTECT,
        related_name="dispositivos",
        null=True,
        blank=True,
    )
    area_gestora = models.ForeignKey(
        AreaGestora,
        on_delete=models.PROTECT,
        related_name="dispositivos",
    )
    color = models.ForeignKey(
        ColorDispositivo,
        on_delete=models.PROTECT,
        related_name="dispositivos",
        null=True,
        blank=True,
    )
    numero_serie = models.CharField(max_length=100, unique=True, null=True, blank=True)
    inventario_bienes_nacionales = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
    )
    inventario_numero_ficha = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
    )
    estado = models.PositiveSmallIntegerField(
        choices=EstadoDispositivo.choices,
        default=EstadoDispositivo.OPERATIVO,
        db_index=True,
    )
    criticidad = models.PositiveSmallIntegerField(
        choices=CriticidadDispositivo.choices,
        db_index=True,
    )
    frecuencia_mantenimiento_meses = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Cantidad de meses entre mantenimientos preventivos.",
    )
    fecha_instalacion = models.DateField(null=True, blank=True)
    fin_garantia = models.DateField(null=True, blank=True)
    costo_adquisicion = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    observaciones = models.TextField(blank=True)
    fecha_creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="dispositivos_biomedicos_creados",
    )
    fecha_modificado = models.DateTimeField(auto_now=True)
    modificado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="dispositivos_biomedicos_modificados",
    )

    class Meta:
        # db_table fija el nombre real de la tabla. Si no se define, Django usaria
        # equipos_biomedicos_dispositivo.
        db_table = "equipo_dispositivo"
        verbose_name = "Equipo"
        verbose_name_plural = "Equipos"
        ordering = ["tipo_id", "marca_id", "modelo_id", "numero_serie"]
        indexes = [
            models.Index(
                fields=["estado", "criticidad"],
                name="bio_disp_estado_criticidad_idx",
            ),
        ]
        constraints = [
            # Restricciones de base de datos: protegen reglas criticas aunque
            # alguien intente guardar datos fuera del formulario.
            models.CheckConstraint(
                condition=Q(frecuencia_mantenimiento_meses__isnull=True)
                | Q(frecuencia_mantenimiento_meses__gt=0),
                name="bio_disp_frecuencia_positiva",
            ),
            models.CheckConstraint(
                condition=Q(costo_adquisicion__isnull=True)
                | Q(costo_adquisicion__gte=0),
                name="bio_disp_costo_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(fin_garantia__isnull=True)
                | Q(fecha_instalacion__isnull=True)
                | Q(fin_garantia__gte=F("fecha_instalacion")),
                name="bio_disp_garantia_fecha_valida",
            ),
        ]

    @property
    def codigo(self):
        # Codigo visible para usuarios. No se guarda en la tabla; se calcula con el id.
        if not self.pk:
            return "DISP-SIN-ID"
        return f"DISP-{self.pk:05d}"

    @property
    def nombre(self):
        # Mantiene compatibilidad con pantallas que esperan un "nombre" del equipo.
        if self.tipo_id:
            return self.tipo.nombre
        return "SIN TIPO"

    def clean(self):
        # Validaciones de negocio antes de guardar.
        # Aqui se normalizan opcionales y se revisan duplicados flexibles.
        errores = {}
        self.numero_serie = (self.numero_serie or "").strip() or None

        if self.marca_id is None:
            # Si no se conoce marca/modelo, no guardamos texto vacio:
            # usamos el catalogo INDEFINIDO.
            self.marca = obtener_catalogo_indefinido(MarcaDispositivo)

        if self.modelo_id is None:
            self.modelo = obtener_catalogo_indefinido(ModeloDispositivo)

        if self.color_id is None:
            self.color = obtener_catalogo_indefinido(ColorDispositivo)

        try:
            self.inventario_bienes_nacionales = (
                normalizar_inventario_bienes_nacionales(
                    self.inventario_bienes_nacionales
                )
            )
        except ValidationError as error:
            errores["inventario_bienes_nacionales"] = error

        try:
            self.inventario_numero_ficha = normalizar_inventario_numero_ficha(
                self.inventario_numero_ficha
            )
        except ValidationError as error:
            errores["inventario_numero_ficha"] = error

        if (
            self.fecha_instalacion
            and self.fin_garantia
            and self.fin_garantia < self.fecha_instalacion
        ):
            errores["fin_garantia"] = (
                "El fin de garantía no puede ser anterior a la fecha de instalación."
            )

        if self.inventario_bienes_nacionales:
            inventario_existente = Dispositivo.objects.filter(
                inventario_bienes_nacionales__iexact=(
                    self.inventario_bienes_nacionales
                )
            ).exclude(pk=self.pk)

            if inventario_existente.exists():
                errores["inventario_bienes_nacionales"] = (
                    "Ya existe un dispositivo registrado con este inventario "
                    "de bienes nacionales."
                )

        if self.inventario_numero_ficha:
            ficha_existente = Dispositivo.objects.filter(
                inventario_numero_ficha__iexact=self.inventario_numero_ficha
            ).exclude(pk=self.pk)

            if ficha_existente.exists():
                errores["inventario_numero_ficha"] = (
                    "Ya existe un dispositivo registrado con este inventario "
                    "número de ficha."
                )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class BajaDispositivo(models.Model):
    # Registro administrativo de baja. Es OneToOne porque un equipo solo debe
    # tener una baja final, parecida a un cierre de expediente.
    dispositivo = models.OneToOneField(
        Dispositivo,
        on_delete=models.PROTECT,
        related_name="baja",
    )
    fecha_baja = models.DateField(verbose_name="Fecha de baja")
    motivo = models.CharField(max_length=255, verbose_name="Motivo de baja")
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="bajas_dispositivos_biomedicos_registradas",
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro",
    )

    class Meta:
        db_table = "equipo_baja_dispositivo"
        verbose_name = "Baja de equipo"
        verbose_name_plural = "Bajas de equipos"
        ordering = ["-fecha_baja", "-fecha_registro"]

    def clean(self):
        # La baja exige motivo y no permite fechas futuras.
        errores = {}
        self.motivo = (self.motivo or "").strip()

        if not self.motivo:
            errores["motivo"] = "Debe ingresar el motivo de baja."

        if self.fecha_baja and self.fecha_baja > timezone.localdate():
            errores["fecha_baja"] = "La fecha de baja no puede ser futura."

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.dispositivo.codigo} - {self.fecha_baja}"


class AsignacionDispositivo(models.Model):
    # Historial de ubicacion/responsable.
    # Solo una asignacion debe quedar activa por equipo: fecha_fin = NULL.
    dispositivo = models.ForeignKey(
        Dispositivo,
        on_delete=models.PROTECT,
        related_name="asignaciones",
    )
    area_clinica = models.ForeignKey(
        Area_atencion,
        on_delete=models.PROTECT,
        related_name="asignaciones_dispositivos_biomedicos",
        null=True,
        blank=True,
    )
    unidad_no_clinica = models.ForeignKey(
        Unidad,
        on_delete=models.PROTECT,
        related_name="asignaciones_dispositivos_biomedicos",
        null=True,
        blank=True,
    )
    responsable = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        related_name="asignaciones_dispositivos_biomedicos",
    )
    fecha_inicio = models.DateTimeField(default=timezone.now, db_index=True)
    fecha_fin = models.DateTimeField(null=True, blank=True, db_index=True)
    observaciones = models.TextField(blank=True)
    fecha_creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="asignaciones_dispositivos_biomedicos_creadas",
    )
    fecha_modificado = models.DateTimeField(auto_now=True)
    modificado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="asignaciones_dispositivos_biomedicos_modificadas",
    )

    class Meta:
        db_table = "equipo_asignacion_dispositivo"
        verbose_name = "Asignación de equipo"
        verbose_name_plural = "Asignaciones de equipos"
        ordering = ["-fecha_inicio"]
        indexes = [
            models.Index(
                fields=["dispositivo", "fecha_fin"],
                name="bio_asig_disp_fecha_fin_idx",
            ),
            models.Index(
                fields=["area_clinica", "fecha_fin"],
                name="bio_asig_area_fecha_fin_idx",
            ),
            models.Index(
                fields=["unidad_no_clinica", "fecha_fin"],
                name="bio_asig_unidad_fecha_fin_idx",
            ),
        ]
        constraints = [
            # Un equipo se ubica en un area clinica o en una unidad no clinica,
            # nunca en ambas al mismo tiempo.
            models.CheckConstraint(
                condition=(
                    Q(area_clinica__isnull=False, unidad_no_clinica__isnull=True)
                    | Q(area_clinica__isnull=True, unidad_no_clinica__isnull=False)
                ),
                name="bio_asig_una_ubicacion",
            ),
            models.CheckConstraint(
                condition=Q(fecha_fin__isnull=True)
                | Q(fecha_fin__gte=F("fecha_inicio")),
                name="bio_asig_fechas_validas",
            ),
        ]

    @property
    def activa(self):
        # Una asignacion activa es la que todavia no tiene fecha_fin.
        return self.fecha_fin is None

    @property
    def ubicacion(self):
        # Permite mostrar una sola columna "ubicacion" sin importar el tipo de area.
        return self.area_clinica or self.unidad_no_clinica

    def clean(self):
        # Reglas de consistencia: exactamente una ubicacion, fechas coherentes
        # y una sola asignacion activa por equipo.
        errores = {}
        tiene_area_clinica = self.area_clinica_id is not None
        tiene_unidad_no_clinica = self.unidad_no_clinica_id is not None

        if tiene_area_clinica == tiene_unidad_no_clinica:
            errores["area_clinica"] = (
                "Debe seleccionar exactamente una ubicación clínica o no clínica."
            )

        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            errores["fecha_fin"] = (
                "La fecha de finalización no puede ser anterior a la fecha de inicio."
            )

        if self.dispositivo_id and self.fecha_fin is None:
            asignacion_activa = AsignacionDispositivo.objects.filter(
                dispositivo_id=self.dispositivo_id,
                fecha_fin__isnull=True,
            ).exclude(pk=self.pk)

            if asignacion_activa.exists():
                errores["dispositivo"] = (
                    "El dispositivo ya posee una asignación activa."
                )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.dispositivo.codigo} - {self.ubicacion}"

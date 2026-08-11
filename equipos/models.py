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


class TipoProcedencia(models.IntegerChoices):
    EMPRESA = 1, "Empresa"
    PERSONA = 2, "Persona"


class ModalidadProcedencia(models.IntegerChoices):
    COMPRA = 1, "Compra"
    DONACION = 2, "Donación"


class EstadoGarantiaDispositivo(models.TextChoices):
    """Situacion de la garantia. No se guarda: la calcula garantia_service."""

    SIN_GARANTIA = "sin_garantia", "Sin garantía"
    PAUSADA = "pausada", "Pausada"
    POR_VENCER = "por_vencer", "Por vencer"
    VIGENTE = "vigente", "Vigente"
    VENCIDA = "vencida", "Vencida"


# Dias de antelacion con los que una garantia se considera "por vencer".
# Tres meses dan margen para gestionar con el proveedor y levantar el papeleo
# antes de perder la cobertura. Subirlo o bajarlo solo requiere tocar aqui.
DIAS_AVISO_GARANTIA = 90


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
    # Un modelo pertenece siempre a una marca. El mismo nombre puede repetirse
    # entre marcas distintas (dos fabricantes pueden llamar igual a su equipo),
    # pero no dentro de una misma marca.
    marca = models.ForeignKey(
        MarcaDispositivo,
        on_delete=models.PROTECT,
        related_name="modelos",
        verbose_name="Marca",
    )
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=250, blank=True)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "equipo_modelo_dispositivo"
        verbose_name = "Modelo de equipo"
        verbose_name_plural = "Modelos de equipo"
        ordering = ["marca__nombre", "nombre"]
        constraints = [
            # La unicidad ya no es global: se limita a cada marca.
            models.UniqueConstraint(
                fields=["marca", "nombre"],
                name="equipo_modelo_unico_por_marca",
            ),
        ]

    @property
    def nombre_completo(self):
        # Util en admin y mensajes, donde el nombre suelto puede ser ambiguo.
        return f"{self.marca.nombre} - {self.nombre}"

    def clean(self):
        # Misma regla que tipo/marca: nombres limpios y en mayuscula.
        self.nombre = normalizar_nombre_catalogo(self.nombre)
        if not self.nombre:
            raise ValidationError({"nombre": "Debe ingresar el modelo del equipo."})

        if self.marca_id is None:
            raise ValidationError({"marca": "Debe indicar la marca del modelo."})

        # La restriccion de base cubre el duplicado; esto lo detecta antes para
        # devolver un mensaje entendible en vez de un IntegrityError.
        duplicado = ModeloDispositivo.objects.filter(
            marca_id=self.marca_id,
            nombre=self.nombre,
        ).exclude(pk=self.pk)

        if duplicado.exists():
            raise ValidationError({
                "nombre": "Esta marca ya tiene un modelo con ese nombre.",
            })

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


class Procedencia(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    tipo = models.PositiveSmallIntegerField(choices=TipoProcedencia.choices)
    rtn = models.CharField(max_length=20, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    contacto = models.CharField(max_length=150, blank=True)
    correo = models.EmailField(blank=True)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "equipo_procedencia"
        verbose_name = "Procedencia de equipo"
        verbose_name_plural = "Procedencias de equipos"
        ordering = ["nombre"]

    def clean(self):
        self.nombre = normalizar_nombre_catalogo(self.nombre)
        if not self.nombre:
            raise ValidationError({"nombre": "Debe ingresar la procedencia."})

        # MySQL permite varios NULL en una columna UNIQUE, pero no varias
        # cadenas vacias. Por eso un RTN omitido se persiste siempre como NULL.
        self.rtn = (self.rtn or "").strip() or None
        self.telefono = (self.telefono or "").strip()
        self.contacto = (self.contacto or "").strip()
        self.correo = (self.correo or "").strip()

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
    modalidad_procedencia = models.PositiveSmallIntegerField(
        choices=ModalidadProcedencia.choices,
    )
    procedencia = models.ForeignKey(
        Procedencia,
        on_delete=models.PROTECT,
        related_name="dispositivos",
    )
    numero_referencia = models.CharField(max_length=100, null=True, blank=True)
    color = models.ForeignKey(
        ColorDispositivo,
        on_delete=models.PROTECT,
        related_name="dispositivos",
        null=True,
        blank=True,
    )
    # Muchos equipos son de un solo color, asi que este queda en NULL y no se
    # rellena con INDEFINIDO: no tenerlo es un dato valido, no un hueco.
    color_secundario = models.ForeignKey(
        ColorDispositivo,
        on_delete=models.PROTECT,
        related_name="dispositivos_color_secundario",
        null=True,
        blank=True,
        verbose_name="Color secundario",
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
    # La garantia se guarda como la fecha que dice el contrato, no como una
    # duracion: las reales no vienen siempre en anios enteros. Este dato no se
    # toca nunca; el vencimiento efectivo lo calcula garantia_service sumandole
    # los dias que el equipo estuvo pausado, para poder mostrar por separado lo
    # que firmo el proveedor y el ajuste posterior.
    fecha_fin_garantia = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fin de garantía",
        help_text="Fecha en que vence la garantía según el contrato. "
                  "Dejar vacío si el equipo no tiene garantía.",
    )
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
        related_name="dispositivos_equipos_creados",
    )
    fecha_modificado = models.DateTimeField(auto_now=True)
    modificado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="dispositivos_equipos_modificados",
    )

    class Meta:
        # db_table fija el nombre real de la tabla. Si no se define, Django usaria
        # equipos_dispositivo.
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

    @property
    def costo_formateado(self):
        # Honduras escribe el dinero con coma para los miles y punto para los
        # decimales: L 1,234.56. Django, con LANGUAGE_CODE = "es", localiza al
        # formato español (1234,56) y dejaria la pantalla contradiciendo al
        # formulario, que espera el punto. Por eso se formatea aqui y la
        # plantilla imprime esta cadena tal cual.
        if self.costo_adquisicion is None:
            return ""
        return f"{self.costo_adquisicion:,.2f}"

    @property
    def modelo_nombre(self):
        # El modelo puede ser desconocido. En vez de crear una fila de catalogo
        # para representarlo, se deja en NULL y se muestra asi en pantalla.
        if self.modelo_id:
            return self.modelo.nombre
        return "INDEFINIDO"

    def clean(self):
        # Validaciones de negocio antes de guardar.
        # Aqui se normalizan opcionales y se revisan duplicados flexibles.
        errores = {}
        self.numero_serie = (self.numero_serie or "").strip() or None
        self.numero_referencia = (
            normalizar_nombre_catalogo(self.numero_referencia) or None
        )

        if self.marca_id is None:
            # Si no se conoce la marca no guardamos texto vacio: se usa el
            # catalogo INDEFINIDO.
            self.marca = obtener_catalogo_indefinido(MarcaDispositivo)

        if self.color_id is None:
            self.color = obtener_catalogo_indefinido(ColorDispositivo)

        # Se compara despues de resolver el principal: si el usuario deja el
        # principal vacio y elige INDEFINIDO como secundario, acaban siendo el
        # mismo y hay que avisarlo igual.
        if self.color_secundario_id and self.color_secundario_id == self.color_id:
            errores["color_secundario"] = (
                "El color secundario debe ser diferente del color principal"
            )

        # El modelo es opcional porque a veces se desconoce; en ese caso queda
        # en NULL y la interfaz lo presenta como INDEFINIDO. Pero si viene,
        # tiene que ser de la marca elegida: no basta con el filtro del
        # navegador, que un POST directo se salta.
        if self.modelo_id and self.marca_id:
            if self.modelo.marca_id != self.marca_id:
                errores["modelo"] = (
                    "El modelo seleccionado no pertenece a la marca indicada."
                )

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


class OrdenTrabajoBajaDispositivo(models.Model):
    # La orden se reserva al generar la ficha por primera vez. La relación
    # OneToOne garantiza que otros usuarios reutilicen el mismo consecutivo.
    dispositivo = models.OneToOneField(
        Dispositivo,
        on_delete=models.PROTECT,
        related_name="orden_trabajo_baja",
    )
    creado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="ordenes_trabajo_baja_dispositivos_creadas",
    )
    fecha_creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "equipo_orden_trabajo_baja"
        verbose_name = "Orden de trabajo para baja"
        verbose_name_plural = "Órdenes de trabajo para baja"
        ordering = ["-fecha_creado"]

    @property
    def numero_orden(self):
        # El año pertenece a la emisión original; una reimpresión futura no
        # cambia el identificador administrativo.
        if not self.pk or not self.fecha_creado:
            return "SIN ASIGNAR"
        return f"OT-{self.fecha_creado.year}-{self.pk:05d}"

    def __str__(self):
        return f"{self.numero_orden} - {self.dispositivo.codigo}"


class BajaDispositivo(models.Model):
    # Registro administrativo de baja. Es OneToOne porque un equipo solo debe
    # tener una baja final, parecida a un cierre de expediente.
    dispositivo = models.OneToOneField(
        Dispositivo,
        on_delete=models.PROTECT,
        related_name="baja",
    )
    # La fecha corresponde al cierre definitivo del tramite y no es editable.
    fecha_baja = models.DateField(
        default=timezone.localdate,
        editable=False,
        verbose_name="Fecha de baja",
    )
    motivo = models.CharField(max_length=255, verbose_name="Motivo de baja")
    habitacion_estancia = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Habitación o estancia",
    )
    # El archivo fisico vive en SIWIH Images. La base principal conserva solo
    # el UUID necesario para auditar y recuperar la constancia firmada.
    ficha_firmada_uuid = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        verbose_name="UUID de la ficha firmada",
    )
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="bajas_dispositivos_equipos_registradas",
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
        related_name="asignaciones_dispositivos_equipos",
        null=True,
        blank=True,
    )
    unidad_no_clinica = models.ForeignKey(
        Unidad,
        on_delete=models.PROTECT,
        related_name="asignaciones_dispositivos_equipos",
        null=True,
        blank=True,
    )
    responsable = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        related_name="asignaciones_dispositivos_equipos",
    )
    fecha_inicio = models.DateTimeField(default=timezone.now, db_index=True)
    fecha_fin = models.DateTimeField(null=True, blank=True, db_index=True)
    observaciones = models.TextField(blank=True)
    fecha_creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="asignaciones_dispositivos_equipos_creadas",
    )
    fecha_modificado = models.DateTimeField(auto_now=True)
    modificado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="asignaciones_dispositivos_equipos_modificadas",
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


class PausaGarantia(models.Model):
    """Periodo en que un equipo estuvo fuera y su garantia no debe correr.

    Nace del caso real: el equipo se manda a reparar y los dias que pasa en
    manos del proveedor no deberian consumir garantia. Se guarda como
    intervalo, no como un interruptor, para poder reconstruir despues por que
    una garantia vence cuando vence.

    Los dias se suman al cerrar la pausa, no dia a dia: hasta que el equipo no
    vuelve no se sabe cuanto estuvo fuera. Mientras la pausa sigue abierta el
    vencimiento mostrado es el del contrato, y la pantalla avisa de que se
    ajustara al retorno.
    """

    dispositivo = models.ForeignKey(
        Dispositivo,
        on_delete=models.CASCADE,
        related_name="pausas_garantia",
    )
    fecha_salida = models.DateField(
        verbose_name="Fecha de salida",
        help_text="Día en que el equipo salió del hospital.",
    )
    fecha_retorno = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de retorno",
        help_text="Día en que el equipo volvió. Vacío si sigue fuera.",
    )
    # Texto libre por ahora. Cuando exista el catalogo de proveedores este
    # campo convivira con una referencia a quien tiene el equipo.
    motivo = models.TextField(
        verbose_name="Motivo",
        help_text="A dónde fue y por qué. Número de orden del proveedor si lo hay.",
    )
    observaciones_retorno = models.TextField(
        blank=True,
        verbose_name="Observaciones del retorno",
        help_text="Trabajo realizado o novedades informadas al devolver el equipo.",
    )
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="pausas_garantia_registradas",
    )
    # Columna tecnica que impone "una sola pausa abierta por equipo" en el
    # motor. Vale el id del equipo mientras la pausa sigue abierta y NULL en
    # cuanto se cierra; como MySQL admite varios NULL en un indice unico, solo
    # puede haber una fila abierta por equipo.
    #
    # Se hace asi porque MySQL ignora los UniqueConstraint con condicion (aviso
    # W036 de Django): la restriccion se declara pero no llega a crearse, y la
    # regla quedaria solo en Python, donde un doble clic podria esquivarla.
    equipo_con_pausa_abierta = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )
    fecha_creado = models.DateTimeField(auto_now_add=True)
    fecha_modificado = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "equipo_pausa_garantia"
        verbose_name = "Pausa de garantía"
        verbose_name_plural = "Pausas de garantía"
        ordering = ["-fecha_salida"]
        indexes = [
            models.Index(
                fields=["dispositivo", "fecha_retorno"],
                name="equipo_pausa_disp_retorno_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(fecha_retorno__isnull=True)
                | Q(fecha_retorno__gte=models.F("fecha_salida")),
                name="equipo_pausa_retorno_no_anterior",
            ),
            models.CheckConstraint(
                condition=~Q(motivo=""),
                name="equipo_pausa_motivo_no_vacio",
            ),
            models.CheckConstraint(
                condition=Q(fecha_retorno__isnull=True)
                | ~Q(observaciones_retorno=""),
                name="equipo_pausa_retorno_con_observacion",
            ),
            # La unicidad de la pausa abierta la impone equipo_con_pausa_abierta,
            # no un UniqueConstraint con condicion: MySQL no los crea.
        ]

    @property
    def esta_abierta(self):
        return self.fecha_retorno is None

    @property
    def dias(self):
        """Dias que suma al vencimiento. Una pausa abierta todavia no suma."""
        if self.fecha_retorno is None:
            return 0
        return (self.fecha_retorno - self.fecha_salida).days

    @property
    def dias_transcurridos(self):
        """Dias que lleva fuera. Solo informativo, no entra en el calculo."""
        if self.fecha_retorno is not None:
            return self.dias
        return (timezone.localdate() - self.fecha_salida).days

    def clean(self):
        errores = {}

        # Se normalizan aqui tambien para proteger altas hechas desde Python,
        # el admin o futuras APIs, no solo las enviadas por los formularios.
        self.motivo = (self.motivo or "").strip()
        self.observaciones_retorno = (
            self.observaciones_retorno or ""
        ).strip()

        if not self.motivo:
            errores["motivo"] = "Debe indicar el motivo de la salida."

        if self.fecha_retorno is not None and not self.observaciones_retorno:
            errores["observaciones_retorno"] = (
                "Debe indicar las observaciones del retorno."
            )

        if self.fecha_retorno and self.fecha_salida:
            if self.fecha_retorno < self.fecha_salida:
                errores["fecha_retorno"] = (
                    "El retorno no puede ser anterior a la salida."
                )

        if self.dispositivo_id and self.fecha_salida:
            registro = self.dispositivo.fecha_creado
            if registro and self.fecha_salida < timezone.localtime(registro).date():
                errores["fecha_salida"] = (
                    "La salida no puede ser anterior al registro del equipo."
                )

        if self.dispositivo_id and self.fecha_retorno is None:
            abierta = PausaGarantia.objects.filter(
                dispositivo_id=self.dispositivo_id,
                fecha_retorno__isnull=True,
            ).exclude(pk=self.pk)

            if abierta.exists():
                errores["dispositivo"] = (
                    "El equipo ya tiene una pausa de garantía abierta."
                )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        # Mantiene la columna que hace cumplir la unicidad en el motor.
        self.equipo_con_pausa_abierta = (
            self.dispositivo_id if self.fecha_retorno is None else None
        )
        self.full_clean()

        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                "equipo_con_pausa_abierta"
            }

        return super().save(*args, **kwargs)

    def __str__(self):
        if self.fecha_retorno:
            return (
                f"{self.dispositivo.codigo}: {self.fecha_salida} a "
                f"{self.fecha_retorno} ({self.dias} días)"
            )
        return f"{self.dispositivo.codigo}: fuera desde {self.fecha_salida}"

import re
import unicodedata
from calendar import monthrange
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from expediente.models import ExpedienteUbicacion
from rrhh.models import Empleado

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
    valor = (valor or "").strip()

    if not valor:
        return None

    if valor.upper().startswith("F/"):
        valor = valor[2:].strip()

    if not valor.isdigit():
        raise ValidationError(
            "La ficha debe contener únicamente números después de F/."
        )

    if len(valor) > 15:
        raise ValidationError(
            "La ficha no puede contener más de 15 números."
        )

    return f"F/{valor}"


def normalizar_nombre_catalogo(valor):
    return (valor or "").strip().upper()


def normalizar_telefono(valor):
    """Deja los telefonos hondurenos como 3348-4816, mas faciles de leer.

    Solo se reformatea cuando hay exactamente ocho digitos, que es el largo de
    un numero en Honduras. Cualquier otra cosa se devuelve tal cual: un numero
    con prefijo de pais o con extension no debe mutilarse por encajarlo en un
    formato, y es preferible guardarlo como lo escribio el usuario.
    """
    valor = (valor or "").strip()

    if not valor:
        return ""

    digitos = "".join(caracter for caracter in valor if caracter.isdigit())

    if len(digitos) == 8:
        return f"{digitos[:4]}-{digitos[4:]}"

    return valor


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


# La tecnologia era un par fijo en el codigo -electronico o no- y por tanto no
# habia donde agregar una tercera. Pasa a ser catalogo como la categoria: en
# equipo hospitalario aparecen tambien electromecanicos, neumaticos e
# hidraulicos, y anadirlos no deberia requerir una migracion.


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
    # Cerrada a mano antes de que venciera: el proveedor incumplio, se
    # sustituyo el equipo o se renegocio el contrato. Se distingue de vencida
    # porque no fue el calendario quien la termino.
    TERMINADA = "terminada", "Terminada"


class MotivoCierreGarantia(models.TextChoices):
    """Por que dejo de estar vigente una garantia."""

    RENOVACION = "renovacion", "Renovada por otra"
    INCUMPLIMIENTO = "incumplimiento", "Incumplimiento del proveedor"
    SUSTITUCION = "sustitucion", "Equipo sustituido"
    ERROR = "error", "Corrección de un dato mal registrado"
    OTRO = "otro", "Otro motivo"


# Dias de antelacion con los que una garantia se considera "por vencer".
# Tres meses dan margen para gestionar con el proveedor y levantar el papeleo
# antes de perder la cobertura. Subirlo o bajarlo solo requiere tocar aqui.
DIAS_AVISO_GARANTIA = 90


def calcular_fin_garantia(inicio, meses):
    """Ultimo dia cubierto por una garantia de `meses` desde `inicio`.

    El plazo se cuenta en meses de calendario y no en dias: un contrato de dos
    anios vence el mismo dia del mes, no 730 dias despues. El ultimo dia
    cubierto es la vispera de cumplirse el plazo, asi que una garantia de 12
    meses iniciada el 1 de marzo vence el 28 de febrero: el 1 de marzo
    siguiente ya esta fuera.

    Vive suelta y no dentro del modelo porque la usan el modelo, el formulario
    y las pruebas, y porque asi se puede comprobar por separado.
    """
    if inicio is None or not meses:
        return None

    total_meses = inicio.month - 1 + meses
    anio = inicio.year + total_meses // 12
    mes = total_meses % 12 + 1

    # Un inicio el 31 de enero con 1 mes no puede caer en un 31 de febrero:
    # se toma el ultimo dia del mes que corresponda.
    ultimo_dia = monthrange(anio, mes)[1]
    dia = min(inicio.day, ultimo_dia)

    return date(anio, mes, dia) - timedelta(days=1)


# Catalogos administrables desde las pantallas del modulo o Django admin.
# El campo activo oculta opciones nuevas sin borrar historico ya usado.
class CategoriaEquipo(models.Model):
    """Gran familia del equipo: medico, informatica, electrico...

    La categoria cuelga del tipo, no del equipo. Un "MONITOR DE SIGNOS
    VITALES" es medico siempre, asi que se decide una vez en el catalogo y no
    en cada uno de los monitores que se registren: menos capturas y ningun
    equipo clasificado al reves que otro igual.

    Es un catalogo como los demas y se administra igual (agregar, renombrar,
    desactivar). Determina quien da mantenimiento y a que reporte entra el
    equipo, por eso cada tipo tiene una sola categoria principal.
    """

    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=250, blank=True)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "equipo_categoria"
        verbose_name = "Categoria de equipo"
        verbose_name_plural = "Categorias de equipo"
        ordering = ["nombre"]

    def clean(self):
        self.nombre = normalizar_nombre_catalogo(self.nombre)
        if not self.nombre:
            raise ValidationError({"nombre": "Debe ingresar la categoria."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class TecnologiaEquipo(models.Model):
    """De que naturaleza es el equipo: electronico, mecanico, neumatico...

    Como la categoria, pertenece al tipo y no a cada aparato: todas las
    camillas de traslado son mecanicas. Es un catalogo para que agregar una
    tecnologia nueva no obligue a tocar el codigo.
    """

    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=250, blank=True)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "equipo_tecnologia"
        verbose_name = "Tecnologia de equipo"
        verbose_name_plural = "Tecnologias de equipo"
        ordering = ["nombre"]

    def clean(self):
        self.nombre = normalizar_nombre_catalogo(self.nombre)
        if not self.nombre:
            raise ValidationError({"nombre": "Debe ingresar la tecnología."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class UbicacionFisica(models.Model):
    """Zona concreta donde esta el aparato: "SALA 3 - CAMA 12", "BODEGA B".

    La unidad de servicio dice de quien es el equipo; esto dice donde hay que
    ir a buscarlo. Se escribe la primera vez y queda en el catalogo con su
    identificador, de modo que la siguiente vez se elige en lugar de volver a
    teclearla: asi "Sala 3" y "SALA 3" no acaban siendo dos lugares distintos.
    """

    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.CharField(max_length=250, blank=True)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "equipo_ubicacion_fisica"
        verbose_name = "Ubicacion fisica"
        verbose_name_plural = "Ubicaciones fisicas"
        ordering = ["nombre"]

    def clean(self):
        self.nombre = normalizar_nombre_catalogo(self.nombre)
        if not self.nombre:
            raise ValidationError({"nombre": "Debe ingresar la ubicacion fisica."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class TipoDispositivo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    # Categoria principal: la que manda. Define el area responsable del
    # mantenimiento y no admite ambiguedad, por eso es una sola y obligatoria.
    categoria = models.ForeignKey(
        CategoriaEquipo,
        on_delete=models.PROTECT,
        related_name="tipos",
        verbose_name="Categoria principal",
    )
    # Los equipos hibridos existen: un ecografo con estacion de trabajo es
    # medico e informatico a la vez. Se registran aqui para que aparezcan en
    # las busquedas de ambas categorias sin discutir cual es "la" categoria.
    categorias_secundarias = models.ManyToManyField(
        CategoriaEquipo,
        blank=True,
        related_name="tipos_secundarios",
        verbose_name="Categorias secundarias",
    )
    # De que naturaleza es el equipo. Es una propiedad del tipo y no de cada
    # aparato: todas las camillas de traslado son mecanicas y todos los
    # monitores electronicos. Preguntarlo en cada registro solo permitia que
    # dos equipos iguales quedaran clasificados distinto.
    tecnologia = models.ForeignKey(
        "TecnologiaEquipo",
        on_delete=models.PROTECT,
        related_name="tipos",
        verbose_name="Tecnología",
    )
    # Marcas que fabrican este tipo de equipo. Es una relacion propia y no algo
    # deducido de los modelos porque una marca se registra en el tipo antes de
    # conocerle un solo modelo: primero se sabe que Epson hace impresoras y
    # despues se van agregando la L3250, la L3210 y las que vengan.
    marcas = models.ManyToManyField(
        "MarcaDispositivo",
        blank=True,
        related_name="tipos",
        db_table="equipo_tipo_marca",
        verbose_name="Marcas",
    )
    # Cada cuantos meses toca el preventivo a los equipos de este tipo. El
    # criterio es del tipo y no del aparato -todos los autoclaves se revisan
    # igual- asi que se declara una vez aqui y cada equipo solo lo cambia si
    # el suyo es una excepcion. Es opcional porque hay tipos que no llevan
    # preventivo programado.
    frecuencia_mantenimiento_meses = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name="Frecuencia de mantenimiento (meses)",
        help_text=(
            "Meses entre mantenimientos preventivos de este tipo. Cada "
            "equipo puede cambiarla si es una excepción."
        ),
    )
    descripcion = models.CharField(max_length=250, blank=True)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "equipo_tipo_dispositivo"
        verbose_name = "Tipo de equipo"
        verbose_name_plural = "Tipos de equipo"
        ordering = ["categoria__nombre", "nombre"]
        constraints = [
            models.CheckConstraint(
                condition=Q(frecuencia_mantenimiento_meses__isnull=True)
                | Q(frecuencia_mantenimiento_meses__gt=0),
                name="equipo_tipo_frecuencia_positiva",
            ),
        ]

    def clean(self):
        # clean() centraliza reglas del modelo. Django lo ejecuta desde full_clean().
        self.nombre = normalizar_nombre_catalogo(self.nombre)
        if not self.nombre:
            raise ValidationError({"nombre": "Debe ingresar el tipo de equipo."})

        if self.categoria_id is None:
            raise ValidationError({"categoria": "Debe indicar la categoria."})

        if self.tecnologia_id is None:
            raise ValidationError({"tecnologia": "Debe indicar la tecnología."})

    def save(self, *args, **kwargs):
        # full_clean() hace que estas reglas apliquen tambien desde admin, shell
        # o vistas, no solo desde un formulario web.
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def categorias(self):
        """Principal mas secundarias, para mostrar la clasificacion completa."""
        secundarias = list(self.categorias_secundarias.all())
        return [self.categoria, *secundarias] if self.categoria_id else secundarias

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
    # Un modelo es un producto concreto: la L3250 es la impresora de Epson, no
    # "un modelo de Epson" a secas. Por eso cuelga de la pareja tipo-marca y no
    # solo de la marca: asi el formulario puede ofrecer, para el tipo elegido,
    # unicamente los modelos que existen de esa marca para ese tipo.
    tipo = models.ForeignKey(
        TipoDispositivo,
        on_delete=models.PROTECT,
        related_name="modelos",
        verbose_name="Tipo de equipo",
    )
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
        ordering = ["tipo__nombre", "marca__nombre", "nombre"]
        constraints = [
            # El mismo nombre puede repetirse entre marcas, y una marca puede
            # llamar igual a productos de tipos distintos. Lo que no se repite
            # es el nombre dentro de la misma pareja tipo-marca.
            models.UniqueConstraint(
                fields=["tipo", "marca", "nombre"],
                name="equipo_modelo_unico_por_tipo_marca",
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

        if self.tipo_id is None:
            raise ValidationError({"tipo": "Debe indicar el tipo de equipo."})

        # La marca tiene que estar declarada en el tipo. Sin esta regla se
        # podria registrar "Mindray" como modelo de camilla sin que Mindray
        # figure entre las marcas de camillas, y la lista del formulario y el
        # catalogo dejarian de contar lo mismo.
        if not self.tipo.marcas.filter(pk=self.marca_id).exists():
            raise ValidationError({
                "marca": (
                    "Esta marca no está registrada en el tipo de equipo. "
                    "Agréguela primero al tipo."
                ),
            })

        # La restriccion de base cubre el duplicado; esto lo detecta antes para
        # devolver un mensaje entendible en vez de un IntegrityError.
        duplicado = ModeloDispositivo.objects.filter(
            tipo_id=self.tipo_id,
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
    telefono_alterno = models.CharField(max_length=30, blank=True)
    # Nombre de la persona por quien preguntar, no otro numero: un telefono de
    # empresa sin saber a quien buscar obliga a explicar el caso desde cero en
    # cada llamada.
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
        self.telefono = normalizar_telefono(self.telefono)
        self.telefono_alterno = normalizar_telefono(self.telefono_alterno)
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
    # Lista ordenada, no un principal y un secundario sueltos: los colores se
    # agregan de uno en uno y el orden es el dato. El primero es el principal
    # (el que se ve al mirar el aparato) y los siguientes son secundarios, sin
    # tope de dos. Sin colores tampoco es un hueco: hay equipos que nadie
    # describe por color.
    colores = models.ManyToManyField(
        ColorDispositivo,
        through="DispositivoColor",
        blank=True,
        related_name="dispositivos",
        verbose_name="Colores",
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
    # Arranca en MEDIA para no frenar la captura: quien registra en la sala no
    # siempre sabe cuan critico es el aparato, y dejarlo obligatorio hacia que
    # se eligiera cualquiera. Se corrige despues desde la edicion.
    criticidad = models.PositiveSmallIntegerField(
        choices=CriticidadDispositivo.choices,
        default=CriticidadDispositivo.MEDIA,
        db_index=True,
    )
    # Excepcion para este aparato. En blanco manda la del tipo, que es el
    # caso normal: ver la propiedad frecuencia_mantenimiento.
    frecuencia_mantenimiento_meses = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name="Frecuencia propia (meses)",
        help_text=(
            "Solo si este equipo es una excepción. En blanco se usa la "
            "frecuencia de su tipo."
        ),
    )
    fecha_instalacion = models.DateField(null=True, blank=True)
    # La garantia no vive aqui: un equipo puede tener varias a lo largo de su
    # vida -se renueva, se termina a mano, se contrata otra- y hace falta el
    # historial completo. Ver GarantiaDispositivo y la propiedad
    # garantia_vigente.
    costo_adquisicion = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    # Anios de vida util esperada. Activo fijo lo pide para la depreciacion y
    # junto con la fecha de instalacion permite anticipar reemplazos.
    vida_util_anios = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name="Vida útil (años)",
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
            models.CheckConstraint(
                condition=Q(vida_util_anios__isnull=True)
                | Q(vida_util_anios__gt=0),
                name="equipo_disp_vida_util_positiva",
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
    def garantia_vigente(self):
        """La garantia que esta en curso, o None si el equipo no tiene.

        Es la unica sin fecha de cierre. Las cerradas siguen en la tabla como
        historial: una garantia renovada o terminada a mano no se borra.
        """
        return self.garantias.filter(fecha_cierre__isnull=True).first()

    @property
    def frecuencia_mantenimiento(self):
        """Cada cuantos meses toca el preventivo de este equipo.

        Manda lo que diga el aparato y, si no dice nada -que es lo normal-, lo
        que diga su tipo. Devuelve None cuando ninguno de los dos la tiene: ese
        equipo no entra al calendario de preventivos hasta que se le ponga.
        """
        if self.frecuencia_mantenimiento_meses:
            return self.frecuencia_mantenimiento_meses

        return self.tipo.frecuencia_mantenimiento_meses if self.tipo_id else None

    @property
    def frecuencia_es_excepcion(self):
        """Si este equipo lleva una frecuencia distinta a la de su tipo."""
        return bool(self.frecuencia_mantenimiento_meses)

    @property
    def tecnologia(self):
        """La lleva el tipo de equipo, no cada aparato."""
        return self.tipo.tecnologia if self.tipo_id else None

    @property
    def color_principal(self):
        """El primero de la lista: el color con el que se reconoce el equipo."""
        primero = self.colores_asignados.first()
        return primero.color if primero else None

    @property
    def colores_ordenados(self):
        """Colores en el orden en que se agregaron, principal primero."""
        return [fila.color for fila in self.colores_asignados.all()]

    def definir_colores(self, colores):
        """Reescribe la lista completa respetando el orden recibido.

        Se borra y se vuelve a insertar en lugar de comparar fila por fila:
        son tres o cuatro colores, y cualquier cambio (agregar, quitar o
        mover) altera la numeracion de los demas de todos modos.
        """
        self.colores_asignados.all().delete()

        DispositivoColor.objects.bulk_create([
            DispositivoColor(dispositivo=self, color=color, orden=posicion)
            for posicion, color in enumerate(colores, start=1)
        ])

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

    def clean(self):
        # Validaciones de negocio antes de guardar.
        # Aqui se normalizan opcionales y se revisan duplicados flexibles.
        errores = {}
        self.numero_serie = (self.numero_serie or "").strip() or None
        self.numero_referencia = (
            normalizar_nombre_catalogo(self.numero_referencia) or None
        )

        # Una marca desconocida se queda en NULL y la interfaz la presenta
        # como INDEFINIDO. Antes se guardaba apuntando a un registro de
        # catalogo llamado asi, pero desde que las marcas pertenecen al tipo
        # eso dejo de tener sentido: INDEFINIDO no figura entre las marcas de
        # ningun tipo, asi que la propia validacion de abajo lo rechazaria.

        # Marca y modelo son opcionales porque a veces se desconocen. Pero si
        # vienen, tienen que encajar con el tipo: el navegador ya solo ofrece
        # las combinaciones validas, y un POST directo se salta ese filtro.
        if self.marca_id and self.tipo_id:
            if not self.tipo.marcas.filter(pk=self.marca_id).exists():
                errores["marca"] = (
                    "Esta marca no está registrada en el tipo de equipo elegido."
                )

        if self.modelo_id:
            if self.marca_id and self.modelo.marca_id != self.marca_id:
                errores["modelo"] = (
                    "El modelo seleccionado no pertenece a la marca indicada."
                )

            if self.tipo_id and self.modelo.tipo_id != self.tipo_id:
                errores["modelo"] = (
                    "El modelo seleccionado no pertenece al tipo de equipo "
                    "indicado."
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


class DispositivoColor(models.Model):
    """Un color del equipo y el lugar que ocupa en la lista.

    Existe como tabla propia y no como una relacion simple porque el orden es
    informacion: el primero es el color con el que se reconoce el aparato y
    los demas lo acompanan. Sin esta columna la base devolveria los colores en
    el orden que quisiera y "blanco con gris" podria mostrarse como "gris con
    blanco" de una pantalla a otra.
    """

    dispositivo = models.ForeignKey(
        Dispositivo,
        on_delete=models.CASCADE,
        related_name="colores_asignados",
    )
    color = models.ForeignKey(
        ColorDispositivo,
        on_delete=models.PROTECT,
        related_name="dispositivos_asignados",
    )
    # 1 es el principal. Se numera desde uno y no desde cero porque este valor
    # se muestra en pantalla.
    orden = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )

    class Meta:
        db_table = "equipo_dispositivo_color"
        verbose_name = "Color del equipo"
        verbose_name_plural = "Colores del equipo"
        ordering = ["orden"]
        constraints = [
            models.UniqueConstraint(
                fields=["dispositivo", "color"],
                name="equipo_disp_color_sin_repetir",
            ),
            models.UniqueConstraint(
                fields=["dispositivo", "orden"],
                name="equipo_disp_color_orden_unico",
            ),
            models.CheckConstraint(
                condition=Q(orden__gt=0),
                name="equipo_disp_color_orden_positivo",
            ),
        ]

    @property
    def es_principal(self):
        return self.orden == 1

    def __str__(self):
        return f"{self.dispositivo.codigo} - {self.color} ({self.orden})"


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

    # Prefijo de esta serie. Las ordenes de baja y las de mantenimiento son
    # tramites distintos con su propio correlativo, asi que llevan prefijo
    # propio: sin el, el numero 7 de una serie y el 7 de la otra se escriben
    # igual en el papel y no son la misma orden.
    PREFIJO = "OTB"

    @property
    def numero_orden(self):
        # El año pertenece a la emisión original; una reimpresión futura no
        # cambia el identificador administrativo.
        if not self.pk or not self.fecha_creado:
            return "SIN ASIGNAR"
        return f"{self.PREFIJO}-{self.fecha_creado.year}-{self.pk:05d}"

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
    """Historial de quien responde por el equipo y donde esta.

    Solo una asignacion queda activa por equipo: la que tiene fecha_fin NULL.

    La ubicacion apunta al catalogo compartido expediente_ubicacion, el mismo
    que usa el prestamo de expedientes. Antes habia dos columnas excluyentes
    (area clinica o unidad no clinica) y cada consulta tenia que preguntar por
    las dos; ese catalogo ya resuelve ambos casos en una sola fila con un solo
    identificador y su propio campo tipo, que dice si el punto es clinico o no
    sin mirar las llaves. Si falta una unidad en el catalogo se agrega con
    "python manage.py poblar_ubicaciones".
    """

    dispositivo = models.ForeignKey(
        Dispositivo,
        on_delete=models.PROTECT,
        related_name="asignaciones",
    )
    ubicacion = models.ForeignKey(
        "expediente.ExpedienteUbicacion",
        on_delete=models.PROTECT,
        related_name="asignaciones_dispositivos_equipos",
        verbose_name="Unidad o área",
        help_text="Punto clínico o no clínico donde queda cargado el equipo.",
    )
    # La unidad dice de quien es el equipo; esta dice donde hay que ir a
    # buscarlo. Es opcional porque no todo equipo tiene un sitio fijo, y sale
    # de un catalogo para que la misma sala no se escriba de tres maneras.
    ubicacion_fisica = models.ForeignKey(
        UbicacionFisica,
        on_delete=models.PROTECT,
        related_name="asignaciones_dispositivos_equipos",
        null=True,
        blank=True,
        verbose_name="Ubicación física",
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

    # Columna tecnica que impone "una sola asignacion abierta por equipo" en
    # el motor. Vale el id del equipo mientras la asignacion sigue abierta y
    # NULL en cuanto se cierra; como MySQL admite varios NULL en un indice
    # unico, solo puede haber una fila abierta por equipo.
    #
    # clean() ya comprobaba la regla, pero preguntar y despues insertar deja
    # una rendija: dos ediciones del mismo equipo a la vez pasan las dos la
    # comprobacion y las dos insertan, y el equipo queda con dos responsables
    # abiertos sin que nadie se entere. Mismo recurso que en GarantiaDispositivo
    # y PausaGarantia, y por el mismo motivo: MySQL ignora los UniqueConstraint
    # con condicion (aviso W036 de Django).
    equipo_con_asignacion_abierta = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        editable=False,
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
            # Sostiene la pregunta mas frecuente del inventario: que equipos
            # hay ahora mismo en tal unidad.
            models.Index(
                fields=["ubicacion", "fecha_fin"],
                name="equipo_asig_ubicacion_fin_idx",
            ),
        ]
        constraints = [
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
    def es_clinica(self):
        """Si el equipo esta cargado a un punto clinico o administrativo."""
        if not self.ubicacion_id:
            return None
        return self.ubicacion.tipo == ExpedienteUbicacion.TIPO_CLINICA

    def clean(self):
        # Reglas de consistencia: fechas coherentes y una sola asignacion
        # activa por equipo. La ubicacion ya es una sola FK obligatoria, asi
        # que no hay nada excluyente que comprobar aqui.
        errores = {}

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
        # Mantiene la columna que hace cumplir la unicidad en el motor.
        self.equipo_con_asignacion_abierta = (
            self.dispositivo_id if self.activa else None
        )
        self.full_clean()

        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                "equipo_con_asignacion_abierta"
            }

        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.dispositivo.codigo} - {self.ubicacion}"


class GarantiaDispositivo(models.Model):
    """Un periodo de cobertura del equipo. Un equipo puede tener varios.

    Antes la garantia eran tres columnas del propio equipo, asi que solo cabia
    una y cambiarla borraba la anterior. En la practica un equipo pasa por
    varias: se renueva al vencer, se termina a mano cuando el proveedor
    incumple o cuando el aparato se sustituye, y a veces se contrata una
    extension aparte. Guardarlas como filas permite responder "que cobertura
    tenia este equipo en marzo del ano pasado", que es justo lo que se
    pregunta cuando aparece un reclamo tardio.

    La que esta en curso es la unica sin fecha_cierre. Las demas son
    historial y no se tocan: ni se borran ni se editan, porque son el
    respaldo de lo que se reclamo en su momento.
    """

    dispositivo = models.ForeignKey(
        Dispositivo,
        on_delete=models.CASCADE,
        related_name="garantias",
    )
    fecha_inicio = models.DateField(
        verbose_name="Inicio de la cobertura",
        help_text="Día en que empezó a correr esta garantía.",
    )
    # Duracion pactada, cuando el contrato habla en anios o meses. Guardarla
    # permite explicar de donde sale el vencimiento, en vez de mostrar una
    # fecha suelta que despues nadie sabe justificar.
    meses = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name="Duración pactada (meses)",
        help_text="Vacío si el contrato solo da la fecha de vencimiento.",
    )
    # El vencimiento del contrato. Si hay inicio y duracion se calcula solo;
    # si el contrato trae una fecha suelta se escribe a mano. Puede quedar en
    # el pasado: se registran equipos viejos cuya garantia ya vencio y saberlo
    # sigue siendo util. garantia_service le suma despues los dias que el
    # equipo estuvo pausado por reparacion.
    fecha_fin = models.DateField(
        verbose_name="Vence el",
        help_text="Fecha en que vence según el contrato.",
    )
    # Referencia del papel que la sustenta: numero de contrato, de factura o
    # de acta. Una renovacion suele traer su propio documento.
    referencia = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Contrato o factura",
    )
    observaciones = models.TextField(blank=True)

    # --- Cierre administrativo ---
    # Dia en que esta garantia dejo de ser la vigente, sea porque se renovo o
    # porque se termino a mano. NULL significa que sigue en curso. No es lo
    # mismo que fecha_fin: una garantia puede cerrarse antes de vencer.
    fecha_cierre = models.DateField(
        null=True,
        blank=True,
        verbose_name="Cerrada el",
    )
    motivo_cierre = models.CharField(
        max_length=20,
        choices=MotivoCierreGarantia.choices,
        blank=True,
        verbose_name="Motivo del cierre",
    )
    detalle_cierre = models.TextField(
        blank=True,
        verbose_name="Detalle del cierre",
    )

    registrado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="garantias_equipos_registradas",
    )
    fecha_creado = models.DateTimeField(auto_now_add=True)

    # Columna tecnica que impone "una sola garantia vigente por equipo" en el
    # motor. Vale el id del equipo mientras la garantia sigue abierta y NULL
    # en cuanto se cierra; como MySQL admite varios NULL en un indice unico,
    # solo puede haber una fila abierta por equipo.
    #
    # Se hace asi porque MySQL ignora los UniqueConstraint con condicion
    # (aviso W036 de Django): la restriccion se declara pero no llega a
    # crearse, y la regla quedaria solo en Python, donde un doble clic podria
    # esquivarla. Mismo recurso que en PausaGarantia.
    equipo_con_garantia_vigente = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )

    # El formulario de renovacion lo pone en True: cierra la garantia anterior
    # y guarda la nueva en la misma transaccion, asi que durante la validacion
    # todavia hay una vigente y el control de abajo la rechazaria. No relaja
    # la regla: la columna unica equipo_con_garantia_vigente la sigue
    # imponiendo en el motor pase lo que pase.
    omitir_control_de_vigente = False

    class Meta:
        db_table = "equipo_garantia"
        verbose_name = "Garantía de equipo"
        verbose_name_plural = "Garantías de equipos"
        # La vigente primero y el historial detras, de lo mas reciente a lo
        # mas viejo, que es el orden en que se consulta.
        ordering = ["fecha_cierre", "-fecha_inicio", "-pk"]
        indexes = [
            models.Index(
                fields=["dispositivo", "fecha_cierre"],
                name="equipo_gar_disp_cierre_idx",
            ),
            models.Index(
                fields=["fecha_fin"],
                name="equipo_gar_fin_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(meses__isnull=True) | Q(meses__gt=0),
                name="equipo_gar_meses_positiva",
            ),
            models.CheckConstraint(
                condition=Q(fecha_fin__gte=F("fecha_inicio")),
                name="equipo_gar_fin_no_anterior_al_inicio",
            ),
            # Una garantia cerrada tiene que decir por que.
            models.CheckConstraint(
                condition=Q(fecha_cierre__isnull=True)
                | ~Q(motivo_cierre=""),
                name="equipo_gar_cierre_con_motivo",
            ),
        ]

    @property
    def esta_vigente(self):
        """Si es la garantia en curso. No dice nada de si ya vencio."""
        return self.fecha_cierre is None

    @property
    def dias_pausados(self):
        """Dias que aportan sus pausas ya cerradas.

        Las abiertas suman cero: hasta que el equipo no vuelve no se sabe
        cuanto estuvo fuera, y es preferible no prometer cobertura que no
        consta.
        """
        return sum(pausa.dias for pausa in self.pausas.all())

    @property
    def fin_real(self):
        """Vencimiento una vez sumadas las pausas cerradas."""
        return self.fecha_fin + timedelta(days=self.dias_pausados)

    @property
    def etiqueta_cierre(self):
        if not self.motivo_cierre:
            return ""
        return MotivoCierreGarantia(self.motivo_cierre).label

    def cerrar(self, motivo, detalle="", fecha=None, guardar=True):
        """Deja de ser la vigente, conservando la fila como historial."""
        self.fecha_cierre = fecha or timezone.localdate()
        self.motivo_cierre = motivo
        self.detalle_cierre = detalle or ""

        if guardar:
            self.save()

        return self

    def clean_fields(self, exclude=None):
        """Deriva el vencimiento antes de que Django valide los campos.

        Va aqui y no en clean() porque full_clean() comprueba primero que
        fecha_fin tenga valor: con inicio y duracion todavia no lo tiene, y
        el usuario recibiria un "este campo no puede ser nulo" por un dato
        que el sistema sabe calcular.
        """
        calculado = calcular_fin_garantia(self.fecha_inicio, self.meses)

        if calculado is not None:
            self.fecha_fin = calculado

        super().clean_fields(exclude=exclude)

    def clean(self):
        errores = {}

        if self.fecha_inicio is None:
            errores["fecha_inicio"] = "Debe indicar el inicio de la garantía."

        if self.fecha_fin is None:
            errores["fecha_fin"] = (
                "Elija una duración o escriba la fecha de vencimiento."
            )

        if (
            self.fecha_inicio
            and self.fecha_fin
            and self.fecha_fin < self.fecha_inicio
        ):
            errores["fecha_fin"] = (
                "El vencimiento no puede ser anterior al inicio de la garantía."
            )

        if self.fecha_cierre and not self.motivo_cierre:
            errores["motivo_cierre"] = "Debe indicar por qué se cierra."

        # No se exige que el cierre sea posterior al inicio: un contrato
        # firmado con cobertura a futuro puede caerse antes de arrancar, y
        # ese cierre hay que poder registrarlo.

        if (
            self.esta_vigente
            and self.dispositivo_id
            and not self.omitir_control_de_vigente
        ):
            otra = GarantiaDispositivo.objects.filter(
                dispositivo_id=self.dispositivo_id,
                fecha_cierre__isnull=True,
            ).exclude(pk=self.pk)

            if otra.exists():
                errores["dispositivo"] = (
                    "El equipo ya tiene una garantía vigente. Ciérrela o "
                    "renuévela antes de registrar otra."
                )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        # Mantiene la columna que hace cumplir la unicidad en el motor.
        self.equipo_con_garantia_vigente = (
            self.dispositivo_id if self.esta_vigente else None
        )
        self.full_clean()

        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                "equipo_con_garantia_vigente"
            }

        return super().save(*args, **kwargs)

    def __str__(self):
        cierre = f" (cerrada {self.fecha_cierre})" if self.fecha_cierre else ""
        return (
            f"{self.dispositivo.codigo}: {self.fecha_inicio} a "
            f"{self.fecha_fin}{cierre}"
        )


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

    # Cuelga de la garantia y no del equipo: lo que se detiene es esa
    # cobertura concreta. Con varias garantias por equipo hace falta saber a
    # cual se le sumaron los dias, o el historial deja de cuadrar.
    garantia = models.ForeignKey(
        GarantiaDispositivo,
        on_delete=models.CASCADE,
        related_name="pausas",
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
    # Columna tecnica que impone "una sola pausa abierta por garantia" en el
    # motor. Vale el id de la garantia mientras la pausa sigue abierta y NULL
    # en cuanto se cierra; como MySQL admite varios NULL en un indice unico,
    # solo puede haber una fila abierta por garantia.
    #
    # Se hace asi porque MySQL ignora los UniqueConstraint con condicion (aviso
    # W036 de Django): la restriccion se declara pero no llega a crearse, y la
    # regla quedaria solo en Python, donde un doble clic podria esquivarla.
    garantia_con_pausa_abierta = models.BigIntegerField(
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
                fields=["garantia", "fecha_retorno"],
                name="equipo_pausa_gar_retorno_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(motivo=""),
                name="equipo_pausa_motivo_no_vacio",
            ),
            models.CheckConstraint(
                condition=Q(fecha_retorno__isnull=True)
                | ~Q(observaciones_retorno=""),
                name="equipo_pausa_retorno_con_observacion",
            ),
            # La unicidad de la pausa abierta la impone
            # garantia_con_pausa_abierta, no un UniqueConstraint con
            # condicion: MySQL no los crea.
        ]

    @property
    def esta_abierta(self):
        return self.fecha_retorno is None

    @property
    def dias(self):
        """Dias que suma al vencimiento. Una pausa abierta todavia no suma."""
        if self.esta_abierta:
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

        # Una salida anterior al inicio de la cobertura no puede haber
        # pausado nada: o la fecha esta mal o la pausa es de otra garantia.
        if self.garantia_id and self.fecha_salida:
            if self.fecha_salida < self.garantia.fecha_inicio:
                errores["fecha_salida"] = (
                    "La salida no puede ser anterior al inicio de la garantía."
                )

        if self.garantia_id and self.esta_abierta:
            abierta = PausaGarantia.objects.filter(
                garantia_id=self.garantia_id,
                fecha_retorno__isnull=True,
            ).exclude(pk=self.pk)

            if abierta.exists():
                errores["garantia"] = (
                    "Esta garantía ya tiene una pausa abierta."
                )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        # Mantiene la columna que hace cumplir la unicidad en el motor.
        self.garantia_con_pausa_abierta = (
            self.garantia_id if self.esta_abierta else None
        )
        self.full_clean()

        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                "garantia_con_pausa_abierta"
            }

        return super().save(*args, **kwargs)

    @property
    def dispositivo(self):
        """El equipo al que pertenece, a traves de su garantia."""
        return self.garantia.dispositivo

    def __str__(self):
        codigo = self.garantia.dispositivo.codigo

        if self.fecha_retorno:
            return (
                f"{codigo}: {self.fecha_salida} a "
                f"{self.fecha_retorno} ({self.dias} días)"
            )
        return f"{codigo}: fuera desde {self.fecha_salida}"


# ===========================================================================
# MANTENIMIENTO
#
# El preventivo se programa solo: cada equipo tiene un plan con su frecuencia
# y un responsable, y de ahi salen las visitas que llenan el calendario. El
# correctivo no se programa, llega cuando se dana algo.
#
# Lo que se hizo en la visita se escribe linea por linea, no se marca de una
# lista precargada: cada aparato llega distinto y una plantilla con casillas
# sin marcar no dice si la tarea no se hizo o si nunca aplicaba. Cada linea
# escrita queda en el catalogo de actividades, de modo que la siguiente vez se
# sugiere en lugar de volver a teclearla.
# ===========================================================================

# Hasta donde se dibuja el calendario hacia adelante. Dos anios alcanzan para
# planificar compras y vacaciones sin llenar la tabla de visitas que nadie va
# a mirar; cada visita realizada empuja el horizonte.
HORIZONTE_PREVENTIVO_MESES = 24


class ClaseMantenimiento(models.IntegerChoices):
    PREVENTIVO = 1, "Preventivo"
    CORRECTIVO = 2, "Correctivo"


class EstadoVisitaPreventiva(models.IntegerChoices):
    PROGRAMADA = 1, "Programada"
    REALIZADA = 2, "Realizada"
    OMITIDA = 3, "Omitida"


class EstadoOrdenTrabajo(models.IntegerChoices):
    ABIERTA = 1, "Abierta"
    CERRADA = 2, "Cerrada"
    ANULADA = 3, "Anulada"


class OrigenOrdenTrabajo(models.IntegerChoices):
    """Como entro el trabajo al sistema.

    El hospital trabaja en hibrido a proposito: hay personal que no usa
    telefono y pide las cosas en papel. En ese caso quien recibe el papel es
    el mismo que levanta la orden, y conviene que quede dicho de donde salio
    para no confundir la fecha en que se pidio con la fecha en que se digito.
    """

    DIGITAL = 1, "Registrado en el sistema"
    PAPEL = 2, "Solicitud en papel"


def normalizar_actividad(valor):
    """Clave con la que dos actividades se consideran la misma.

    Sin esto el catalogo se llena de variantes de la misma linea: "Limpieza
    general", "limpieza general" y "Limpieza general." serian tres
    actividades distintas y la sugerencia dejaria de servir justo donde mas
    hace falta. Se quitan tildes, mayusculas, espacios de sobra y la
    puntuacion final, que es lo que cambia entre una escritura y otra; el
    texto que se guarda y se imprime sigue siendo el que escribio la persona.
    """
    texto = re.sub(r"\s+", " ", (valor or "")).strip()

    if not texto:
        return ""

    sin_tildes = "".join(
        letra
        for letra in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(letra) != "Mn"
    )

    return re.sub(r"[\s.,;:]+$", "", sin_tildes).strip()


class ActividadMantenimiento(models.Model):
    """Una linea de trabajo que alguien escribio alguna vez.

    El catalogo nace vacio y se llena con el uso. No se importa de ninguna
    parte a proposito: la hoja de calculo que se venia usando arrastraba tres
    tareas del amalgamador copiadas en casi todas las hojas, y cargarlas
    habria puesto a pedir "lubricacion de partes moviles del motor" en un
    glucometro durante anios. Lo que entra aqui es lo que de verdad se hizo.
    """

    nombre = models.CharField(
        max_length=250,
        verbose_name="Actividad",
    )
    # Columna derivada de nombre. Es la que lleva la unicidad para que dos
    # escrituras de la misma linea no creen dos filas; nombre se conserva tal
    # como se escribio porque es lo que sale impreso en la orden.
    clave = models.CharField(max_length=250, unique=True, editable=False)
    # Contador para ordenar las sugerencias: lo que mas se hace sale primero.
    # Se lleva en la fila y no se cuenta con un COUNT cada vez porque el
    # autocompletado responde a cada tecla.
    veces_usada = models.PositiveIntegerField(default=0, editable=False)
    fecha_primer_uso = models.DateTimeField(auto_now_add=True)
    fecha_ultimo_uso = models.DateTimeField(auto_now=True)
    # Permite retirar de las sugerencias una linea mal escrita sin borrarla:
    # las ordenes viejas que la usaron tienen que seguir diciendo lo mismo.
    activa = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "equipo_actividad_mantenimiento"
        verbose_name = "Actividad de mantenimiento"
        verbose_name_plural = "Actividades de mantenimiento"
        ordering = ["-veces_usada", "nombre"]

    def clean(self):
        self.nombre = re.sub(r"\s+", " ", (self.nombre or "")).strip()
        self.clave = normalizar_actividad(self.nombre)

        if not self.clave:
            raise ValidationError({"nombre": "Debe escribir la actividad."})

        if len(self.nombre) < 4:
            raise ValidationError(
                {"nombre": "La actividad es demasiado corta para entenderse."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()

        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"clave"}

        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class ActividadTipoDispositivo(models.Model):
    """Cuantas veces se uso una actividad en equipos de un tipo.

    Es lo que permite sugerir primero lo que se le hace a un autoclave cuando
    se esta llenando la orden de un autoclave. Se guarda aparte del catalogo
    general para poder decidir mas adelante si la sugerencia se limita al tipo
    o se abre a todo lo escrito, sin tocar la base: las dos consultas salen de
    aqui.
    """

    actividad = models.ForeignKey(
        ActividadMantenimiento,
        on_delete=models.CASCADE,
        related_name="usos_por_tipo",
    )
    tipo = models.ForeignKey(
        TipoDispositivo,
        on_delete=models.CASCADE,
        related_name="actividades_usadas",
    )
    veces_usada = models.PositiveIntegerField(default=0, editable=False)
    fecha_ultimo_uso = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "equipo_actividad_tipo"
        verbose_name = "Actividad usada por tipo"
        verbose_name_plural = "Actividades usadas por tipo"
        ordering = ["-veces_usada", "actividad__nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["actividad", "tipo"],
                name="equipo_actividad_tipo_unica",
            ),
        ]

    def __str__(self):
        return f"{self.tipo.nombre}: {self.actividad.nombre}"


def corresponde_dia_habil(fecha, incluye_fin_de_semana=False):
    """Mueve una fecha al siguiente lunes si cayo en sabado o domingo.

    El taller trabaja de lunes a viernes, asi que una fecha calculada que cae
    en fin de semana no sirve como esta. Se mueve hacia adelante y no hacia
    atras porque adelantar acortaria el intervalo entre preventivos, que es
    justo lo que la frecuencia quiere garantizar.

    Algunas personas si pueden ir sabado o domingo, y eso se pregunta una vez
    al asignarles el plan; cuando aceptaron, la fecha se respeta tal cual.
    """
    if fecha is None or incluye_fin_de_semana:
        return fecha

    # weekday(): lunes 0 ... sabado 5, domingo 6.
    dias_de_sobra = fecha.weekday() - 4

    if dias_de_sobra <= 0:
        return fecha

    return fecha + timedelta(days=3 - dias_de_sobra)


def sumar_meses(fecha, meses):
    """Misma fecha `meses` despues, sin salirse del calendario.

    Se cuenta en meses y no en dias por lo mismo que las garantias: "cada seis
    meses" quiere decir el mismo dia del mes, no 180 dias despues. Un 31 de
    enero mas un mes es el 28 o 29 de febrero, porque el 31 de febrero no
    existe.
    """
    if fecha is None or not meses:
        return None

    total_meses = fecha.month - 1 + meses
    anio = fecha.year + total_meses // 12
    mes = total_meses % 12 + 1
    dia = min(fecha.day, monthrange(anio, mes)[1])

    return date(anio, mes, dia)


class PlanMantenimiento(models.Model):
    """El preventivo de un equipo: cada cuanto toca y quien lo hace.

    Es uno por equipo y no una lista de fechas sueltas: la frecuencia y el
    responsable son lo estable, y las fechas se calculan. Asi un cambio de
    responsable o de frecuencia no obliga a reescribir el calendario a mano.

    El plan se puede desactivar sin borrarlo. Un equipo que se fue a
    reparacion larga deja de generar visitas, pero su historial de
    mantenimientos no desaparece.
    """

    dispositivo = models.OneToOneField(
        Dispositivo,
        on_delete=models.PROTECT,
        related_name="plan_mantenimiento",
        verbose_name="Equipo",
    )
    # El calendario es de la persona: cada tecnico abre el suyo y ve lo que le
    # toca. No hay tope de equipos por dia a proposito, porque revisar quince
    # monitores de la misma sala es una manana y revisar un autoclave es un
    # dia; el que conoce el trabajo es quien reparte.
    responsable = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="planes_mantenimiento_equipos",
        verbose_name="Responsable",
    )
    # Se copia del tipo (o de la excepcion del equipo) al crear el plan, pero
    # queda en el plan: cambiar la frecuencia del tipo no debe mover de golpe
    # el calendario de todos los equipos ya programados sin que nadie lo pida.
    frecuencia_meses = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Frecuencia (meses)",
    )
    fecha_inicio = models.DateField(
        verbose_name="Primera visita",
        help_text="De aquí salen las siguientes, sumando la frecuencia.",
    )
    # Se pregunta al asignar, no se supone. Decidirlo por el tecnico es como
    # acaban apareciendo visitas en domingo que nadie va a atender.
    trabaja_fines_de_semana = models.BooleanField(
        default=False,
        verbose_name="Puede trabajar sábado o domingo",
        help_text=(
            "En blanco, las fechas que caigan en fin de semana se pasan al "
            "lunes siguiente."
        ),
    )
    activo = models.BooleanField(default=True, db_index=True)
    observaciones = models.TextField(blank=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="planes_mantenimiento_equipos_creados",
    )
    fecha_creado = models.DateTimeField(auto_now_add=True)
    fecha_modificado = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "equipo_plan_mantenimiento"
        verbose_name = "Plan de mantenimiento"
        verbose_name_plural = "Planes de mantenimiento"
        ordering = ["dispositivo__tipo__nombre", "dispositivo_id"]
        indexes = [
            models.Index(
                fields=["responsable", "activo"],
                name="bio_plan_responsable_idx",
            ),
        ]

    def clean(self):
        errores = {}

        if not self.frecuencia_meses:
            errores["frecuencia_meses"] = (
                "Debe indicar cada cuántos meses toca el preventivo."
            )

        if not self.fecha_inicio:
            errores["fecha_inicio"] = "Debe indicar la fecha de la primera visita."

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def ultima_realizada(self):
        """La visita realizada mas reciente, que es el ancla del calculo."""
        return (
            self.visitas.filter(estado=EstadoVisitaPreventiva.REALIZADA)
            .order_by("-fecha_realizada", "-id")
            .first()
        )

    @property
    def proxima_visita(self):
        return (
            self.visitas.filter(estado=EstadoVisitaPreventiva.PROGRAMADA)
            .order_by("fecha_programada", "id")
            .first()
        )

    def __str__(self):
        return f"{self.dispositivo.codigo} cada {self.frecuencia_meses} meses"


class VisitaPreventiva(models.Model):
    """Un dia en el calendario: a este equipo le toca revision.

    Las visitas futuras existen como filas porque hay que poder verlas y
    moverlas; no se calculan al dibujar la pantalla. Mover una arrastra a las
    que vienen detras -si el preventivo de marzo se corre dos semanas, el de
    septiembre tambien- y las ya realizadas no se tocan nunca, porque son un
    hecho y no una intencion.
    """

    plan = models.ForeignKey(
        PlanMantenimiento,
        on_delete=models.CASCADE,
        related_name="visitas",
    )
    fecha_programada = models.DateField(db_index=True)
    estado = models.PositiveSmallIntegerField(
        choices=EstadoVisitaPreventiva.choices,
        default=EstadoVisitaPreventiva.PROGRAMADA,
        db_index=True,
    )
    fecha_realizada = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha en que se hizo",
    )
    # La orden que documenta el trabajo. Una orden cubre varios equipos, asi
    # que varias visitas de distintos equipos pueden apuntar a la misma.
    orden = models.ForeignKey(
        "OrdenTrabajoMantenimiento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visitas",
    )
    # Deja ver en el calendario que esa fecha no es la que salio del calculo.
    movida_a_mano = models.BooleanField(default=False, editable=False)
    observaciones = models.CharField(max_length=250, blank=True)

    class Meta:
        db_table = "equipo_visita_preventiva"
        verbose_name = "Visita preventiva"
        verbose_name_plural = "Visitas preventivas"
        ordering = ["fecha_programada", "id"]
        indexes = [
            models.Index(
                fields=["fecha_programada", "estado"],
                name="bio_visita_fecha_estado_idx",
            ),
        ]

    def clean(self):
        errores = {}

        if self.estado == EstadoVisitaPreventiva.REALIZADA:
            if not self.fecha_realizada:
                errores["fecha_realizada"] = (
                    "Una visita realizada necesita la fecha en que se hizo."
                )
            elif self.fecha_realizada > timezone.localdate():
                errores["fecha_realizada"] = (
                    "La fecha en que se hizo no puede ser futura."
                )
        elif self.fecha_realizada:
            errores["fecha_realizada"] = (
                "Solo una visita realizada lleva fecha de realización."
            )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def esta_pendiente(self):
        return self.estado == EstadoVisitaPreventiva.PROGRAMADA

    @property
    def esta_atrasada(self):
        return self.esta_pendiente and self.fecha_programada < timezone.localdate()

    def __str__(self):
        return f"{self.plan.dispositivo.codigo} - {self.fecha_programada}"


class OrdenTrabajoMantenimiento(models.Model):
    """La hoja de trabajo: un tipo de equipo, varios aparatos, una lista de lo hecho.

    Reproduce la hoja que el taller ya venia llenando en papel, donde una sola
    hoja cubre todos los equipos del mismo tipo que se atendieron en esa
    salida y lleva un unico numero de orden. Se respeta esa forma porque es
    como se firma y como se archiva: partirla en una orden por aparato
    multiplicaria por quince el papeleo de revisar quince monitores de la
    misma sala.

    De ahi que el tipo este en la orden y no en cada fila: la lista de
    actividades es comun a todos los equipos de la hoja, y una lista comun
    solo tiene sentido si todos son del mismo tipo.
    """

    # Prefijo de esta serie. Las ordenes de mantenimiento llevan su propio
    # correlativo, separado del de las bajas (OTB): sin prefijo el numero 7 de
    # una serie y el 7 de la otra se escriben igual en el papel sin ser la
    # misma orden.
    PREFIJO = "OTM"

    tipo = models.ForeignKey(
        TipoDispositivo,
        on_delete=models.PROTECT,
        related_name="ordenes_mantenimiento",
        verbose_name="Tipo de equipo",
    )
    clase = models.PositiveSmallIntegerField(
        choices=ClaseMantenimiento.choices,
        default=ClaseMantenimiento.PREVENTIVO,
        db_index=True,
        verbose_name="Clase de mantenimiento",
    )
    estado = models.PositiveSmallIntegerField(
        choices=EstadoOrdenTrabajo.choices,
        default=EstadoOrdenTrabajo.ABIERTA,
        db_index=True,
    )
    origen = models.PositiveSmallIntegerField(
        choices=OrigenOrdenTrabajo.choices,
        default=OrigenOrdenTrabajo.DIGITAL,
        verbose_name="Origen de la solicitud",
    )
    fecha = models.DateField(
        default=timezone.localdate,
        db_index=True,
        verbose_name="Fecha del trabajo",
    )
    # Quien hizo el trabajo. Es un usuario del sistema y no un texto porque es
    # el mismo a quien se le asignan las visitas en el calendario; si fueran
    # dos cosas distintas no habria forma de ver que le toca a cada uno.
    operario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="ordenes_mantenimiento_equipos",
        verbose_name="Operario",
    )
    # El jefe del departamento o servicio que recibe el trabajo y firma la
    # hoja. Es opcional porque la firma se recoge en papel y puede llegar
    # despues de cerrar la orden.
    jefe_servicio = models.ForeignKey(
        Empleado,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ordenes_mantenimiento_equipos_firmadas",
        verbose_name="Jefe de departamento o servicio",
    )
    # Cuando la solicitud llego en papel, quien la pidio y cuando. Queda como
    # texto porque el solicitante no suele tener usuario en el sistema, que es
    # justamente el motivo de que haya pedido en papel.
    solicitado_por = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Solicitado por",
    )
    fecha_solicitud = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de la solicitud",
        help_text="Cuándo se pidió, que no es cuándo se digitó.",
    )
    observaciones = models.TextField(blank=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="ordenes_mantenimiento_equipos_creadas",
    )
    fecha_creado = models.DateTimeField(auto_now_add=True)
    cerrada_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ordenes_mantenimiento_equipos_cerradas",
    )
    fecha_cierre = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "equipo_orden_trabajo_mantenimiento"
        verbose_name = "Orden de trabajo de mantenimiento"
        verbose_name_plural = "Órdenes de trabajo de mantenimiento"
        ordering = ["-fecha", "-id"]
        indexes = [
            models.Index(
                fields=["estado", "fecha"],
                name="bio_orden_estado_fecha_idx",
            ),
            models.Index(
                fields=["operario", "fecha"],
                name="bio_orden_operario_fecha_idx",
            ),
        ]

    @property
    def numero_orden(self):
        """El numero que va en el papel: OTM-2026-00031.

        El anio es el de la fecha del trabajo y no el de hoy: una orden de
        diciembre que se digita en enero sigue perteneciendo al anio en que se
        hizo el trabajo.
        """
        if not self.pk:
            return "SIN ASIGNAR"

        anio = (self.fecha or timezone.localdate()).year
        return f"{self.PREFIJO}-{anio}-{self.pk:05d}"

    @property
    def esta_abierta(self):
        return self.estado == EstadoOrdenTrabajo.ABIERTA

    def clean(self):
        errores = {}
        self.solicitado_por = (self.solicitado_por or "").strip()

        if self.fecha and self.fecha > timezone.localdate():
            errores["fecha"] = "La fecha del trabajo no puede ser futura."

        if self.origen == OrigenOrdenTrabajo.PAPEL and not self.solicitado_por:
            errores["solicitado_por"] = (
                "Una solicitud en papel necesita el nombre de quien la pidió."
            )

        if self.fecha_solicitud and self.fecha:
            if self.fecha_solicitud > self.fecha:
                errores["fecha_solicitud"] = (
                    "La solicitud no puede ser posterior al trabajo."
                )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.numero_orden} - {self.tipo.nombre}"


class EquipoEnOrdenTrabajo(models.Model):
    """Una fila de la hoja: un aparato concreto que se atendio en esa orden.

    Las horas van en la fila y no en la orden porque es lo que dice el papel:
    en la misma salida un monitor puede llevar veinte minutos y el siguiente
    una hora, y esos tiempos son lo que justifica la jornada.
    """

    orden = models.ForeignKey(
        OrdenTrabajoMantenimiento,
        on_delete=models.CASCADE,
        related_name="equipos",
    )
    dispositivo = models.ForeignKey(
        Dispositivo,
        on_delete=models.PROTECT,
        related_name="atenciones_mantenimiento",
        verbose_name="Equipo",
    )
    # El "Ambiente" de la hoja: donde estaba el aparato ese dia. Se copia de
    # la ubicacion del equipo al agregarlo, pero queda escrito aqui porque si
    # el equipo se traslada despues, la hoja firmada tiene que seguir diciendo
    # donde se atendio.
    ambiente = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Ambiente",
    )
    hora_inicio = models.TimeField(null=True, blank=True, verbose_name="Hora inicio")
    hora_final = models.TimeField(null=True, blank=True, verbose_name="Hora final")
    observaciones = models.CharField(max_length=250, blank=True)

    class Meta:
        db_table = "equipo_orden_trabajo_equipo"
        verbose_name = "Equipo atendido en la orden"
        verbose_name_plural = "Equipos atendidos en la orden"
        ordering = ["id"]
        constraints = [
            # El mismo aparato no se lista dos veces en la misma hoja: seria
            # imposible saber cual de las dos filas es la buena.
            models.UniqueConstraint(
                fields=["orden", "dispositivo"],
                name="equipo_orden_dispositivo_unico",
            ),
        ]

    def clean(self):
        errores = {}
        self.ambiente = (self.ambiente or "").strip()

        if self.hora_inicio and self.hora_final:
            if self.hora_final <= self.hora_inicio:
                errores["hora_final"] = (
                    "La hora final tiene que ser posterior a la de inicio."
                )

        if self.hora_final and not self.hora_inicio:
            errores["hora_inicio"] = "Falta la hora de inicio."

        # Todos los aparatos de la hoja son del tipo de la hoja, porque la
        # lista de actividades es comun. Mezclar tipos dejaria la orden
        # diciendo que a un glucometro se le hizo lo de un autoclave.
        if self.orden_id and self.dispositivo_id:
            if self.dispositivo.tipo_id != self.orden.tipo_id:
                errores["dispositivo"] = (
                    f"La orden es de {self.orden.tipo.nombre} y este equipo "
                    f"es {self.dispositivo.tipo.nombre}."
                )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def minutos(self):
        """Cuanto duro la atencion, para poder sumar la jornada."""
        if not self.hora_inicio or not self.hora_final:
            return None

        inicio = self.hora_inicio.hour * 60 + self.hora_inicio.minute
        final = self.hora_final.hour * 60 + self.hora_final.minute

        return final - inicio

    def __str__(self):
        return f"{self.orden.numero_orden} - {self.dispositivo.codigo}"


class ActividadEnOrdenTrabajo(models.Model):
    """Una linea de lo que se hizo, escrita en el momento.

    Se agregan de una en una, en el orden en que se trabajo, y no se marcan de
    una lista precargada: cada aparato llega distinto y una plantilla con
    casillas sin marcar no distingue entre "no se hizo" y "nunca aplicaba".
    La linea apunta al catalogo para poder sugerirla la proxima vez, y el
    detalle guarda lo particular de esta vez -que pieza, que lectura- que no
    tiene sentido meter en el catalogo.
    """

    orden = models.ForeignKey(
        OrdenTrabajoMantenimiento,
        on_delete=models.CASCADE,
        related_name="actividades",
    )
    actividad = models.ForeignKey(
        ActividadMantenimiento,
        on_delete=models.PROTECT,
        related_name="lineas",
    )
    # El orden importa: la hoja se lee como una secuencia de trabajo.
    posicion = models.PositiveSmallIntegerField(default=1)
    detalle = models.CharField(
        max_length=250,
        blank=True,
        verbose_name="Detalle",
        help_text="Lo particular de esta vez, si hace falta.",
    )
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="actividades_mantenimiento_equipos_registradas",
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "equipo_orden_trabajo_actividad"
        verbose_name = "Actividad realizada"
        verbose_name_plural = "Actividades realizadas"
        ordering = ["posicion", "id"]
        constraints = [
            # La misma actividad no se escribe dos veces en la misma hoja. Si
            # de verdad se repitio -se limpio al principio y al final- lo que
            # cambia es el detalle, y eso va en una sola linea.
            models.UniqueConstraint(
                fields=["orden", "actividad"],
                name="equipo_orden_actividad_unica",
            ),
        ]

    def clean(self):
        self.detalle = (self.detalle or "").strip()

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def texto(self):
        """Como se lee la linea en la hoja impresa."""
        if self.detalle:
            return f"{self.actividad.nombre} — {self.detalle}"
        return self.actividad.nombre

    def __str__(self):
        return f"{self.orden.numero_orden} - {self.actividad.nombre}"

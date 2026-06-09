
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.constants.choices_constants import EstadoMapeoCategoria
from mapeo_camas.constants.choices_constants import DetalleMapeoTipoAccion


# =============================================================================
# EstadoMapeo
# -----------------------------------------------------------------------------
# Catálogo centralizado de estados para camas, sesiones, etc.
# =============================================================================
class EstadoMapeo(models.Model):
    Categoria = EstadoMapeoCategoria

    codigo = models.CharField(max_length=255, unique=True, db_index=True, verbose_name="Código")
    categoria = models.CharField(
        max_length=20,
        choices=EstadoMapeoCategoria.choices,
        verbose_name="Categoría",
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        db_table = "mapeo_camas_estado_mapeo"
        verbose_name = "Estado de mapeo"
        verbose_name_plural = "Estados de mapeo"
        ordering = ["categoria", "codigo"]

    def __str__(self):
        return f"{self.categoria} | {self.codigo}"


@lru_cache(maxsize=512)
def get_observacion_mapeo(codigo):
    if hasattr(codigo, "codigo"):
        codigo = codigo.codigo
    codigo_normalizado = (codigo or "").strip() or "Sin observaciones"
    observacion, _ = EstadoMapeo.objects.get_or_create(
        codigo=codigo_normalizado,
        categoria=EstadoMapeoCategoria.OBSERVACION,
        defaults={"activo": True},
    )
    return observacion
    


# =============================================================================
# AsignacionCamaPaciente
# -----------------------------------------------------------------------------
# Tabla operativa central del módulo. Representa el estado actual de cada cama:
# quién la ocupa, desde cuándo y en qué condición.
# Cada cama tiene siempre exactamente un registro activo en esta tabla,
# lo que permite construir el mapa de camas en tiempo real.
# =============================================================================
class AsignacionCamaPaciente(models.Model):

    # El estado ahora es una FK a EstadoMapeo (categoria="ESTADO_CAMA")

    # Cama física a la que corresponde esta asignación.
    cama = models.ForeignKey(
        "servicio.Cama",
        on_delete=models.PROTECT,
        related_name="asignaciones_cama",
        verbose_name="Cama",
    )
    # [2026-05-26 REFACTOR FINAL] Ingreso es el pivote operativo único.
    # En próxima versión será null=False. Por ahora es nullable para rollback de backfill.
    ingreso = models.ForeignKey(
        "ingreso.Ingreso",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asignaciones_cama",
        verbose_name="Ingreso (pivote operativo)",
    )
    # Momento en que se creó esta asignación (automático).
    fecha_inicio = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de inicio")
    # (Eliminado: fecha_fin, ahora gestionado solo por historial)
    # Estado actual de la cama. Ahora FK a EstadoMapeo.
    estado = models.ForeignKey(
        "mapeo_camas.EstadoMapeo",
        on_delete=models.PROTECT,
        related_name="asignaciones_cama",
        verbose_name="Estado",
        db_index=True,
        limit_choices_to={"categoria": "ESTADO_CAMA"},
    )
    # Usuario que realizó la asignación (ingreso del paciente o cambio de estado).
    usuario_asignacion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asignaciones_cama_creadas",
        verbose_name="Usuario de asignacion",
    )
    # (Eliminado: usuario_cierre, ahora gestionado solo por historial)

    class Meta:
        db_table = "mapeo_camas_asignacion_cama_paciente"
        verbose_name = "Asignacion de cama"
        verbose_name_plural = "Asignaciones de cama"
        ordering = ["-fecha_inicio"]
        indexes = [
            # Optimiza la consulta del mapa por cama y estado.
            models.Index(fields=["cama", "estado"], name="idx_asig_cama_estado"),
            # [2026-05-26 AUDIT] Consulta operativa por ingreso activo y estado.
            models.Index(fields=["ingreso", "estado"], name="idx_asig_ingreso_estado"),
        ]

    def clean(self):
        """
        Validaciones de negocio ejecutadas antes de guardar.
        Se activan tanto desde formularios (formas Django) como desde save().
        """
        errors = {}

        # Se asume que los códigos de estado siguen el catálogo de EstadoMapeo
        if self.estado and self.estado.codigo == "OCUPADA":
            # [2026-05-26 REFACTOR FINAL] Ingreso_id es obligatorio para OCUPADA (sin fallback a paciente).
            if not self.ingreso_id:
                errors["ingreso"] = "Una asignacion ocupada debe tener un ingreso activo válido."

            # Impide que una misma cama tenga dos asignaciones OCUPADA al mismo tiempo.
            cama_ocupada = AsignacionCamaPaciente.objects.filter(
                cama=self.cama,
                estado__codigo="OCUPADA",
            ).exclude(pk=self.pk)
            if cama_ocupada.exists():
                errors["cama"] = "La cama ya tiene una asignacion ocupada."

            # Impide que un mismo ingreso esté en dos camas OCUPADA al mismo tiempo.
            if self.ingreso_id is not None:
                ingreso_con_cama = AsignacionCamaPaciente.objects.filter(
                    ingreso_id=self.ingreso_id,
                    estado__codigo="OCUPADA",
                ).exclude(pk=self.pk)
                if ingreso_con_cama.exists():
                    errors["ingreso"] = "El ingreso ya tiene una asignacion ocupada en otra cama."

        if self.estado and self.estado.codigo == "VACIA":
            # Regla de negocio: cama vacia implica asignacion sin ingreso.
            self.ingreso = None

        # (Eliminado: validación de fecha_fin)

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # [2026-05-26 REFACTOR FINAL] Ingreso_id es el pivote operativo único.
        if self.estado and self.estado.codigo == "VACIA":
            self.ingreso = None
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"Cama {self.cama_id} | Ingreso {self.ingreso_id} | "
            f"Estado {self.estado.codigo if self.estado else 'SIN_ESTADO'}"
        )


# =============================================================================
# HistorialEstadoCama
# -----------------------------------------------------------------------------
# Registro inmutable de cada cambio de estado de una cama.
# Permite auditar todos los movimientos: quién cambió el estado, cuándo
# y con qué motivo. No se modifica; solo se inserta.
# =============================================================================
class HistorialEstadoCama(models.Model):

    # Catálogo para auditoría histórica.
    # Incluye ALTA como valor legado para no perder trazabilidad.
    # El estado ahora es una FK a EstadoMapeo (categoria="ESTADO_CAMA")

    # Cama cuyo estado cambió.
    cama = models.ForeignKey(
        "servicio.Cama",
        on_delete=models.PROTECT,
        related_name="historial_estado",
        verbose_name="Cama",
    )
    # Estado en el que estaba la cama antes del cambio. Null para el primer registro.
    estado_anterior = models.ForeignKey(
        "mapeo_camas.EstadoMapeo",
        on_delete=models.PROTECT,
        related_name="historiales_como_anterior",
        null=True,
        blank=True,
        verbose_name="Estado anterior",
        limit_choices_to={"categoria": "ESTADO_CAMA"},
    )
    # Estado al que transitó la cama en este evento.
    estado_nuevo = models.ForeignKey(
        "mapeo_camas.EstadoMapeo",
        on_delete=models.PROTECT,
        related_name="historiales_como_nuevo",
        verbose_name="Estado nuevo",
        limit_choices_to={"categoria": "ESTADO_CAMA"},
    )
    # Paciente involucrado en el cambio, si aplica (p.ej. ingreso o alta).
    # [2026-05-26 AUDIT] Ingreso como referencia operativa principal del evento.
    ingreso = models.ForeignKey(
        "ingreso.Ingreso",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="historial_camas",
        verbose_name="Ingreso",
    )
    # Usuario que ejecutó el cambio de estado.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="historial_camas_usuario",
        verbose_name="Usuario",
    )
    # Timestamp automático del momento exacto del cambio.
    fecha_hora = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Fecha y hora",
    )
    # Descripción breve del motivo o contexto del cambio.
    observacion = models.ForeignKey(
        "mapeo_camas.EstadoMapeo",
        on_delete=models.PROTECT,
        related_name="historiales_como_observacion",
        null=True,
        blank=True,
        verbose_name="Observacion",
        limit_choices_to={"categoria": "OBSERVACION"},
    )

    class Meta:
        db_table = "mapeo_camas_historial_estado_cama"
        verbose_name = "Historial de estado de cama"
        verbose_name_plural = "Historial de estados de camas"
        ordering = ["-fecha_hora"]
        indexes = [
            # Optimiza la consulta del historial cronológico de una cama específica.
            models.Index(fields=["cama", "fecha_hora"], name="idx_hist_cama_fecha"),
        ]

    def __str__(self):
        hora_local = timezone.localtime(self.fecha_hora)
        return (
            f"Cama {self.cama_id} | {self.estado_anterior.codigo if self.estado_anterior else ''} → {self.estado_nuevo.codigo if self.estado_nuevo else ''}"
            f" | {hora_local:%d/%m/%Y %H:%M}"
        )


# =============================================================================
# MovimientoCama
# -----------------------------------------------------------------------------
# Auditoría operativa de traslados de pacientes entre camas.
# Se crea un registro cada vez que un paciente pasa de una cama a otra
# dentro del mismo servicio o entre servicios distintos.
# Complementa el historial de estados con información de origen y destino.
# =============================================================================
class MovimientoCama(models.Model):

    # Tipo de movimiento registrado. Por ahora: "TRASLADO".
    # Se deja como CharField para permitir nuevos tipos sin migraciones.
    tipo_movimiento = models.CharField(
        max_length=50,
        default="TRASLADO",
        verbose_name="Tipo de movimiento",
        db_index=True,
    )
    # Cama de la que proviene el paciente en este movimiento.
    cama_origen = models.ForeignKey(
        "servicio.Cama",
        on_delete=models.PROTECT,
        related_name="movimientos_como_origen",
        verbose_name="Cama origen",
    )
    # Cama a la que se traslada el paciente.
    cama_destino = models.ForeignKey(
        "servicio.Cama",
        on_delete=models.PROTECT,
        related_name="movimientos_como_destino",
        verbose_name="Cama destino",
    )
    # Paciente trasladado.
    # [2026-05-26 AUDIT] Ingreso como pivote clínico del traslado.
    ingreso = models.ForeignKey(
        "ingreso.Ingreso",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimientos_cama",
        verbose_name="Ingreso",
    )
    # Usuario que ejecutó el traslado en el sistema.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="movimientos_cama_usuario",
        verbose_name="Usuario",
    )
    # Timestamp automático del momento en que se registró el movimiento.
    fecha_hora = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Fecha y hora",
    )
    # Nota libre opcional sobre el motivo o contexto del traslado.
    observacion = models.ForeignKey(
        "mapeo_camas.EstadoMapeo",
        on_delete=models.PROTECT,
        related_name="movimientos_como_observacion",
        null=True,
        blank=True,
        verbose_name="Observacion",
        limit_choices_to={"categoria": "OBSERVACION"},
    )

    class Meta:
        db_table = "mapeo_camas_MovimientoCama"
        verbose_name = "Movimiento de cama"
        verbose_name_plural = "Movimientos de cama"
        ordering = ["-fecha_hora"]
        indexes = [
            # Consultas generales ordenadas por fecha.
            models.Index(fields=["fecha_hora"], name="idx_mov_cama_fecha"),
            # Análisis de flujo: qué camas intercambian pacientes con qué frecuencia.
            models.Index(fields=["cama_origen", "cama_destino"], name="idx_mov_origen_destino"),
            # [2026-05-26 AUDIT] Historial por ingreso para reingresos y trazabilidad.
            models.Index(fields=["ingreso", "fecha_hora"], name="idx_mov_ingreso_fecha"),
        ]

    def __str__(self):
        hora_local = timezone.localtime(self.fecha_hora)
        return (
            f"{self.tipo_movimiento}: {self.cama_origen_id} -> {self.cama_destino_id}"
            f" | Ingreso {self.ingreso_id} | {hora_local:%d/%m/%Y %H:%M}"
        )


# =============================================================================
# MapeoSesionCama
# -----------------------------------------------------------------------------
# Encapsula una ejecucion completa del proceso de mapeo de camas.
# Permite saber quien lo inicio, su ventana temporal y estado de cierre.
# =============================================================================
class MapeoSesionCama(models.Model):

    # El estado ahora es una FK a EstadoMapeo (categoria="ESTADO_SESION")

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sesiones_mapeo_cama",
        verbose_name="Usuario",
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Fecha de inicio")
    fecha_fin = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de fin")
    estado = models.ForeignKey(
        "mapeo_camas.EstadoMapeo",
        on_delete=models.PROTECT,
        related_name="sesiones_mapeo",
        verbose_name="Estado",
        db_index=True,
        limit_choices_to={"categoria": "ESTADO_SESION"},
    )
    observacion = models.ForeignKey(
        "mapeo_camas.EstadoMapeo",
        on_delete=models.PROTECT,
        related_name="sesiones_mapeo_como_observacion",
        null=True,
        blank=True,
        verbose_name="Observacion",
        limit_choices_to={"categoria": "OBSERVACION"},
    )
    observacion_texto = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        default=None,
        verbose_name="Observacion libre",
    )

    class Meta:
        db_table = "mapeo_camas_sesion_cama"
        verbose_name = "Sesion de mapeo de cama"
        verbose_name_plural = "Sesiones de mapeo de cama"
        ordering = ["-fecha_inicio"]

    def __str__(self):
        hora_local = timezone.localtime(self.fecha_inicio)
        observacion_visible = self.observacion_texto or (self.observacion.codigo if self.observacion else "")
        return (
            f"Sesion {self.id} | {self.estado.codigo if self.estado else ''} | "
            f"{observacion_visible} | {hora_local:%d/%m/%Y %H:%M}"
        )


# =============================================================================
# MapeoSesionServicio
# -----------------------------------------------------------------------------
# Servicios incluidos dentro de una sesion de mapeo de camas.
# Permite restringir el alcance de una sesion a uno o varios servicios.
# =============================================================================
class MapeoSesionServicio(models.Model):

    sesion_mapeo = models.ForeignKey(
        MapeoSesionCama,
        on_delete=models.PROTECT,
        related_name="servicios_incluidos",
        verbose_name="Sesion de mapeo",
    )
    servicio = models.ForeignKey(
        "servicio.Servicio",
        on_delete=models.PROTECT,
        related_name="sesiones_mapeo_incluidas",
        verbose_name="Servicio",
    )

    class Meta:
        db_table = "mapeo_camas_sesion_servicio"
        verbose_name = "Servicio incluido en sesion de mapeo"
        verbose_name_plural = "Servicios incluidos en sesiones de mapeo"
        unique_together = ("sesion_mapeo", "servicio")
        ordering = ["sesion_mapeo_id", "servicio_id"]

    def __str__(self):
        return f"Sesion {self.sesion_mapeo_id} | Servicio {self.servicio_id}"


# =============================================================================
# DetalleMapeoCama
# -----------------------------------------------------------------------------
# Registro unitario de una cama dentro de una sesion de mapeo.
# Guarda validacion, tipo de accion aplicada y observaciones del usuario.
# =============================================================================
class DetalleMapeoCama(models.Model):

    # 2026-06-09: alias de compatibilidad; origen central en mapeo_camas/constants/choices_constants.py.
    TipoAccion = DetalleMapeoTipoAccion

    sesion_mapeo = models.ForeignKey(
        MapeoSesionCama,
        on_delete=models.PROTECT,
        related_name="detalles",
        verbose_name="Sesion de mapeo",
    )
    cama = models.ForeignKey(
        "servicio.Cama",
        on_delete=models.PROTECT,
        related_name="detalles_mapeo",
        verbose_name="Cama",
    )
    fue_validada = models.BooleanField(default=False, verbose_name="Fue validada")
    hubo_cambio = models.BooleanField(default=False, verbose_name="Hubo cambio")
    estado_actual = models.ForeignKey(
        "mapeo_camas.EstadoMapeo",
        on_delete=models.PROTECT,
        related_name="detalles_mapeo_como_estado",
        null=True,
        blank=True,
        verbose_name="Estado actual",
        limit_choices_to={"categoria": "ESTADO_CAMA"},
    )
    # [2026-05-26 AUDIT] Referencia operativa para detalle de mapeo.
    ingreso_actual = models.ForeignKey(
        "ingreso.Ingreso",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="detalles_mapeo_actual",
        verbose_name="Ingreso actual",
    )
    tipo_accion = models.ForeignKey(
        "mapeo_camas.EstadoMapeo",
        on_delete=models.PROTECT,
        related_name="detalles_mapeo_como_accion",
        verbose_name="Tipo de accion",
        limit_choices_to={"categoria": "TIPO_ACCION"},
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="detalles_mapeo_cama",
        verbose_name="Usuario",
    )
    fecha_hora = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Fecha y hora")
    observacion = models.ForeignKey(
        "mapeo_camas.EstadoMapeo",
        on_delete=models.PROTECT,
        related_name="detalles_mapeo_como_observacion",
        null=True,
        blank=True,
        verbose_name="Observacion",
        limit_choices_to={"categoria": "OBSERVACION"},
    )

    class Meta:
        db_table = "mapeo_camas_detalle_mapeo_cama"
        verbose_name = "Detalle de mapeo de cama"
        verbose_name_plural = "Detalles de mapeo de cama"
        ordering = ["-fecha_hora"]
        indexes = [
            models.Index(fields=["sesion_mapeo", "fecha_hora"], name="idx_det_mapeo_sesion_fecha"),
            models.Index(fields=["cama", "fecha_hora"], name="idx_det_mapeo_cama_fecha"),
            models.Index(fields=["sesion_mapeo", "cama"], name="idx_det_mapeo_sesion_cama"),
        ]

    def __str__(self):
        hora_local = timezone.localtime(self.fecha_hora)
        return (
            f"Sesion {self.sesion_mapeo_id} | Cama {self.cama_id} | {self.tipo_accion}"
            f" | {hora_local:%d/%m/%Y %H:%M}"
        )

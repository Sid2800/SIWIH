
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# =============================================================================
# EstadoMapeo
# -----------------------------------------------------------------------------
# Catálogo centralizado de estados para camas, sesiones, etc.
# =============================================================================
class EstadoMapeo(models.Model):

    class Categoria(models.TextChoices):
        ESTADO_CAMA = "ESTADO_CAMA", "Estado de cama"
        ESTADO_SESION = "ESTADO_SESION", "Estado de sesion"
        TIPO_ACCION = "TIPO_ACCION", "Tipo de accion"

    codigo = models.CharField(max_length=40, unique=True, db_index=True, verbose_name="Código")
    categoria = models.CharField(
        max_length=20,
        choices=Categoria.choices,
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
    # Paciente asignado. Puede ser nulo cuando la cama está en estado VACIA.
    paciente = models.ForeignKey(
        "paciente.Paciente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asignaciones_cama",
        verbose_name="Paciente",
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
        verbose_name = "Asignacion de cama por paciente"
        verbose_name_plural = "Asignaciones de cama por paciente"
        ordering = ["-fecha_inicio"]
        indexes = [
            # Optimiza la consulta del mapa por cama y estado.
            models.Index(fields=["cama", "estado"], name="idx_asig_cama_estado"),
            # Optimiza la búsqueda de la cama activa de un paciente.
            models.Index(fields=["paciente", "estado"], name="idx_asig_paciente_estado"),
        ]

    def clean(self):
        """
        Validaciones de negocio ejecutadas antes de guardar.
        Se activan tanto desde formularios (formas Django) como desde save().
        """
        errors = {}

        # Se asume que los códigos de estado siguen el catálogo de EstadoMapeo
        if self.estado and self.estado.codigo == "OCUPADA":
            # Una cama OCUPADA debe tener paciente.
            if self.paciente is None:
                errors["paciente"] = "Una asignacion ocupada debe tener paciente."

            # Impide que una misma cama tenga dos asignaciones OCUPADA al mismo tiempo.
            cama_ocupada = AsignacionCamaPaciente.objects.filter(
                cama=self.cama,
                estado__codigo="OCUPADA",
            ).exclude(pk=self.pk)
            if cama_ocupada.exists():
                errors["cama"] = "La cama ya tiene una asignacion ocupada."

            # Impide que un mismo paciente esté en dos camas OCUPADA al mismo tiempo.
            if self.paciente_id is not None:
                paciente_con_cama = AsignacionCamaPaciente.objects.filter(
                    paciente=self.paciente,
                    estado__codigo="OCUPADA",
                ).exclude(pk=self.pk)
                if paciente_con_cama.exists():
                    errors["paciente"] = "El paciente ya tiene una asignacion ocupada."

        if self.estado and self.estado.codigo == "VACIA":
            # Regla de negocio: cama vacia implica asignacion sin paciente.
            self.paciente = None

        # (Eliminado: validación de fecha_fin)

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Garantiza integridad antes de persistir, independientemente del origen.
        if self.estado and self.estado.codigo == "VACIA":
            self.paciente = None
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Cama {self.cama_id} - Paciente {self.paciente_id} ({self.estado.codigo if self.estado else ''})"


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
    paciente = models.ForeignKey(
        "paciente.Paciente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="historial_camas",
        verbose_name="Paciente",
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
    observacion = models.CharField(
        max_length=255,
        default="Ingreso (sync)",
        blank=True,
        verbose_name="Observacion",
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
    paciente = models.ForeignKey(
        "paciente.Paciente",
        on_delete=models.PROTECT,
        related_name="movimientos_cama",
        verbose_name="Paciente",
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
    observacion = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Observacion",
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
            # Historial de movimientos de un paciente en particular.
            models.Index(fields=["paciente", "fecha_hora"], name="idx_mov_paciente_fecha"),
        ]

    def __str__(self):
        hora_local = timezone.localtime(self.fecha_hora)
        return (
            f"{self.tipo_movimiento}: {self.cama_origen_id} -> {self.cama_destino_id}"
            f" | Paciente {self.paciente_id} | {hora_local:%d/%m/%Y %H:%M}"
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
    observacion = models.CharField(
        max_length=500,
        blank=True,
        default="Sin Observaciones",
        verbose_name="Observacion",
    )

    class Meta:
        db_table = "mapeo_camas_sesion_cama"
        verbose_name = "Sesion de mapeo de cama"
        verbose_name_plural = "Sesiones de mapeo de cama"
        ordering = ["-fecha_inicio"]

    def __str__(self):
        hora_local = timezone.localtime(self.fecha_inicio)
        return f"Sesion {self.id} | {self.estado.codigo if self.estado else ''} | {hora_local:%d/%m/%Y %H:%M}"


# =============================================================================
# DetalleMapeoCama
# -----------------------------------------------------------------------------
# Registro unitario de una cama dentro de una sesion de mapeo.
# Guarda validacion, tipo de accion aplicada y observaciones del usuario.
# =============================================================================
class DetalleMapeoCama(models.Model):

    # Constantes de codigo para los tipos de accion (categoria TIPO_ACCION en EstadoMapeo)
    class TipoAccion:
        CONFIRMACION = "CONFIRMACION"
        ALTA = "ALTA"
        CAMBIO = "CAMBIO"
        TRASLADO = "TRASLADO"
        CORRECCION = "CORRECCION"

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
    paciente_actual = models.ForeignKey(
        "paciente.Paciente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="detalles_mapeo_actual",
        verbose_name="Paciente actual",
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
    observacion = models.CharField(max_length=255, blank=True, default="", verbose_name="Observacion")

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

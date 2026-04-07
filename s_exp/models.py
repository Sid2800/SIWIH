from django.db import models
from django.contrib.auth.models import User
from expediente.models import Expediente


# ============================================
# CATÁLOGO: MOTIVOS DE SOLICITUD
# ============================================
class MotivoSolicitud(models.Model):
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Motivo'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )

    class Meta:
        db_table = 's_exp_motivosolicitud'
        verbose_name = 'Motivo de Solicitud'
        verbose_name_plural = 'Motivos de Solicitud'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


# ============================================
# EXPEDIENTE PARA PRÉSTAMO
# ============================================
class ExpedientePrestamo(models.Model):
    ESTADO_CHOICES = [
        ('Disponible', 'Disponible'),
        ('Prestado', 'Prestado'),
        ('Baja', 'Baja'),
    ]

    expediente = models.OneToOneField(
        Expediente,
        on_delete=models.PROTECT,
        related_name='prestamo_info',
        verbose_name='Expediente'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='Disponible',
        verbose_name='Estado'
    )
    ubicacion_fisica = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Ubicación Física'
    )

    class Meta:
        db_table = 's_exp_expedienteprestamo'
        verbose_name = 'Expediente Préstamo'
        verbose_name_plural = 'Expedientes Préstamo'
        ordering = ['expediente__numero']

    def __str__(self):
        return f"Exp #{self.expediente.numero} - {self.estado}"


# ============================================
# SOLICITUD DE PRÉSTAMO
# ============================================
class SolicitudPrestamo(models.Model):
    ESTADO_FLUJO_CHOICES = [
        ('Pendiente', 'Pendiente'),
        ('Aprobado', 'Aprobado'),
        ('Rechazado', 'Rechazado'),
        ('Listo', 'Listo para Retirar'),
        ('EnPrestamo', 'En Préstamo'),
        ('Devuelto', 'Devuelto'),
        ('DevolucionParcial', 'Devolución Parcial'),
        ('Anulado', 'Anulado'),
    ]

    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='solicitudes_prestamo',
        verbose_name='Solicitante'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    estado_flujo = models.CharField(
        max_length=30,
        choices=ESTADO_FLUJO_CHOICES,
        default='Pendiente',
        verbose_name='Estado del Flujo'
    )
    motivo = models.ForeignKey(
        MotivoSolicitud,
        on_delete=models.PROTECT,
        related_name='solicitudes',
        verbose_name='Motivo de la Solicitud'
    )
    observaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observaciones'
    )
    area_destino = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Área de Destino'
    )
    expedientes = models.ManyToManyField(
        ExpedientePrestamo,
        through='SolicitudExpedienteDetalle',
        related_name='solicitudes',
        verbose_name='Expedientes Solicitados'
    )

    class Meta:
        db_table = 's_exp_solicitudprestamo'
        verbose_name = 'Solicitud de Préstamo'
        verbose_name_plural = 'Solicitudes de Préstamo'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Solicitud #{self.id} - {self.usuario.username} - {self.estado_flujo}"

    @property
    def cantidad_expedientes(self):
        return self.detalles.count()


# ============================================
# DETALLE DE SOLICITUD (Tabla intermedia)
# ============================================
class SolicitudExpedienteDetalle(models.Model):
    solicitud = models.ForeignKey(
        SolicitudPrestamo,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='Solicitud'
    )
    expediente_prestamo = models.ForeignKey(
        ExpedientePrestamo,
        on_delete=models.PROTECT,
        related_name='detalle_solicitudes',
        verbose_name='Expediente'
    )
    # Campos historiales: se guardan al crear la solicitud
    paciente_identidad = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='Identidad del Paciente'
    )
    paciente_nombre = models.CharField(
        max_length=300, blank=True, null=True,
        verbose_name='Nombre del Paciente'
    )
    numero_expediente = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='N° Expediente (snapshot)'
    )
    devuelto = models.BooleanField(
        default=False,
        verbose_name='Devuelto'
    )

    class Meta:
        db_table = 's_exp_solicituddetalle'
        verbose_name = 'Detalle de Solicitud'
        verbose_name_plural = 'Detalles de Solicitud'
        unique_together = ('solicitud', 'expediente_prestamo')

    def __str__(self):
        return f"Solicitud #{self.solicitud.id} → Exp #{self.expediente_prestamo.expediente.numero}"


# ============================================
# PRÉSTAMO
# ============================================
class Prestamo(models.Model):
    ESTADO_CHOICES = [
        ('Activo', 'Activo'),
        ('Entregado', 'Entregado'),
        ('Vencido', 'Vencido'),
        ('DevolucionParcial', 'Devolución Parcial'),
        ('Cerrado', 'Cerrado'),
    ]

    solicitud = models.OneToOneField(
        SolicitudPrestamo,
        on_delete=models.PROTECT,
        related_name='prestamo',
        verbose_name='Solicitud'
    )
    fecha_aprobacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Aprobación'
    )
    fecha_entrega = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Entrega al Solicitante'
    )
    fecha_limite = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha Límite de Devolución'
    )
    fecha_devolucion_real = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Devolución Real'
    )
    admin_aprobador = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='prestamos_aprobados',
        verbose_name='Admin que Aprobó'
    )
    motivo_rechazo = models.TextField(
        blank=True,
        null=True,
        verbose_name='Motivo de Rechazo'
    )
    comentarios = models.TextField(
        blank=True,
        null=True,
        verbose_name='Comentarios del Admin'
    )
    estado = models.CharField(
        max_length=30,
        choices=ESTADO_CHOICES,
        default='Activo',
        verbose_name='Estado del Préstamo'
    )
    tiempo_limite_horas = models.PositiveIntegerField(
        default=24,
        verbose_name='Tiempo Límite (horas)',
        help_text='Mínimo 24 horas. Configurable por préstamo.'
    )

    class Meta:
        db_table = 's_exp_prestamo'
        verbose_name = 'Préstamo'
        verbose_name_plural = 'Préstamos'
        ordering = ['-fecha_aprobacion']

    def __str__(self):
        return f"Préstamo #{self.id} - Solicitud #{self.solicitud.id} - {self.estado}"

    @property
    def esta_vencido(self):
        from django.utils import timezone
        if self.fecha_limite and self.estado == 'Entregado':
            return timezone.now() > self.fecha_limite
        return False

    @property
    def tiempo_restante_segundos(self):
        from django.utils import timezone
        if self.fecha_limite and self.estado == 'Entregado':
            delta = self.fecha_limite - timezone.now()
            return max(0, int(delta.total_seconds()))
        return None

    @property
    def porcentaje_tiempo_usado(self):
        from django.utils import timezone
        if self.fecha_entrega and self.fecha_limite and self.estado == 'Entregado':
            total = (self.fecha_limite - self.fecha_entrega).total_seconds()
            usado = (timezone.now() - self.fecha_entrega).total_seconds()
            if total > 0:
                return min(100, round((usado / total) * 100, 1))
        return 0


# ============================================
# DEVOLUCIÓN
# ============================================
class Devolucion(models.Model):
    ESTADO_CHOICES = [
        ('Completa', 'Completa'),
        ('Incompleta', 'Incompleta'),
        ('Parcial', 'Parcial'),
    ]

    prestamo = models.ForeignKey(
        Prestamo,
        on_delete=models.PROTECT,
        related_name='devoluciones',
        verbose_name='Préstamo'
    )
    fecha_devolucion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Devolución'
    )
    cantidad_esperada = models.PositiveIntegerField(
        verbose_name='Cantidad Esperada'
    )
    cantidad_recibida = models.PositiveIntegerField(
        verbose_name='Cantidad Recibida'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='Completa',
        verbose_name='Estado de Devolución'
    )
    notas_admin = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas del Administrador'
    )

    class Meta:
        db_table = 's_exp_devolucion'
        verbose_name = 'Devolución'
        verbose_name_plural = 'Devoluciones'
        ordering = ['-fecha_devolucion']

    def __str__(self):
        return f"Devolución #{self.id} - Préstamo #{self.prestamo.id} - {self.estado}"


# ============================================
# LOG HISTÓRICO
# ============================================
class LogHistorico(models.Model):
    accion = models.CharField(
        max_length=100,
        verbose_name='Acción'
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha/Hora'
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='logs_s_exp',
        verbose_name='Usuario'
    )
    detalle = models.TextField(
        blank=True,
        null=True,
        verbose_name='Detalle'
    )
    objeto_tipo = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Tipo de Objeto'
    )
    objeto_id = models.BigIntegerField(
        blank=True,
        null=True,
        verbose_name='ID del Objeto'
    )

    class Meta:
        db_table = 's_exp_loghistorico'
        verbose_name = 'Log Histórico'
        verbose_name_plural = 'Logs Históricos'
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.accion} - {self.usuario.username}"

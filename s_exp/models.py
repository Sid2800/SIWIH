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
# CATÁLOGO: ESTADOS DE SOLICITUD
# ============================================
class EstadoSolicitud(models.Model):
    codigo = models.CharField(
        max_length=50,
        primary_key=True,
        verbose_name='Código (Ejem: SOL_PENDIENTE)'
    )
    nombre = models.CharField(
        max_length=100,
        verbose_name='Nombre del Estado'
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descripción'
    )

    class Meta:
        db_table = 's_exp_estadosolicitud'
        verbose_name = 'Estado de Solicitud'
        verbose_name_plural = 'Estados de Solicitud'

    def __str__(self):
        return self.nombre


# ============================================
# CATÁLOGO: ESTADOS DEL EXPEDIENTE FISICO
# ============================================
class EstadoExpedienteFisico(models.Model):
    """
    Define el estado físico actual de un expediente en el archivo
    (ej. Disponible, Prestado, En Proceso de Ubicación).
    """
    codigo = models.CharField(
        max_length=50,
        primary_key=True,
        verbose_name='Código (Ejem: EXP_DISPONIBLE)'
    )
    nombre = models.CharField(
        max_length=100,
        verbose_name='Nombre del Estado'
    )

    class Meta:
        db_table = 's_exp_estadoexpedientefisico'
        verbose_name = 'Estado de Expediente Físico'
        verbose_name_plural = 'Estados de Expediente Físico'

    def __str__(self):
        return self.nombre


# ============================================
# EXPEDIENTE PARA PRÉSTAMO (Estado Actual)
# ============================================
class ExpedientePrestamo(models.Model):
    expediente = models.OneToOneField(
        Expediente,
        on_delete=models.PROTECT,
        related_name='prestamo_info',
        verbose_name='Expediente'
    )
    estado = models.ForeignKey(
        EstadoExpedienteFisico,
        on_delete=models.PROTECT,
        related_name='expedientes',
        verbose_name='Estado Físico Actual',
        default='EXP_DISPONIBLE'
    )

    # Ubicación física ACTUAL del expediente, referenciada por relación
    # al catálogo unificado (expediente_ubicacion). Captura solo el ID.
    #   - Al entregar un préstamo → apunta a la unidad del solicitante.
    #   - Al devolver            → apunta a ADMISION.
    # NULL = ubicación no determinada por este módulo (usar fallback legacy).
    ubicacion = models.ForeignKey(
        'expediente.ExpedienteUbicacion',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='expedientes_prestamo',
        verbose_name='Ubicación actual (catálogo)',
        help_text='FK a expediente_ubicacion. Se actualiza al entregar/devolver.'
    )

    # ----- DEPRECATED: texto libre, reemplazado por la FK 'ubicacion'.
    # Se mantiene temporalmente para no romper código legacy durante transición.
    ubicacion_fisica = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='[DEPRECATED] Ubicación Física (texto)'
    )

    class Meta:
        db_table = 's_exp_expedienteprestamo'
        verbose_name = 'Expediente Préstamo'
        verbose_name_plural = 'Expedientes Préstamo'
        ordering = ['expediente__numero']

    def __str__(self):
        return f"Exp #{self.expediente.numero} - {self.estado.nombre}"


# ============================================
# SOLICITUD DE PRÉSTAMO
# ============================================
class SolicitudPrestamo(models.Model):
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
    estado_flujo = models.ForeignKey(
        EstadoSolicitud,
        on_delete=models.PROTECT,
        related_name='solicitudes',
        verbose_name='Estado de la Solicitud',
        default='SOL_PENDIENTE'
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
    # ============================================================
    # Ubicación del solicitante (FK a la unidad de servicio donde trabaja)
    # ============================================================
    # Esta es la "ubicación física" del usuario que pidió el préstamo.
    # Se obtiene en cascada via RRHH:
    #   1. PersonalNoClinico.servicio_unidad
    #   2. PersonalSalud.servicio_unidad (si no está en no-clínico)
    # Para mostrar el nombre se usa servicio_unidad.nombre_unidad
    # via los servicios (s_exp/services/datos_solicitud.py).
    servicio_unidad = models.ForeignKey(
        'servicio.Unidad',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='solicitudes_prestamo',
        verbose_name='Unidad de Servicio del Solicitante',
        help_text='FK a servicio.Unidad. Capturada del registro RRHH al crear la solicitud.'
    )

    # El campo area_destino (texto) fue eliminado en migración 0015.
    # El acceso a la unidad del solicitante ahora se hace vía
    # s_exp/services/datos_solicitud.py → DatosSolicitud.unidad_nombre.
    expedientes = models.ManyToManyField(
        ExpedientePrestamo,
        through='SolicitudExpedienteDetalle',
        related_name='solicitudes',
        verbose_name='Expedientes Solicitados'
    )
    notificado_listo = models.BooleanField(
        default=False,
        verbose_name='Notificado al usuario (Listo para recoger)'
    )
    tiempo_sugerido_horas = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Tiempo sugerido por el solicitante (horas)',
        help_text='Sugerencia opcional del usuario al crear la solicitud. Mismo día: máx hasta 4:00 PM. Días posteriores: máx 72 horas.'
    )

    class Meta:
        db_table = 's_exp_solicitudprestamo'
        verbose_name = 'Solicitud de Préstamo'
        verbose_name_plural = 'Solicitudes de Préstamo'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Solicitud #{self.id} - {self.usuario.username} - {self.estado_flujo.nombre}"

    @property
    def cantidad_expedientes(self):
        return self.detalles.count()

    @property
    def get_servicio_unidad(self):
        """
        Retorna la unidad de servicio de la solicitud.

        Intenta devolver el servicio_unidad almacenado directamente.
        Si no existe, intenta obtenerlo desde la cadena RRHH del usuario.
        """
        if self.servicio_unidad:
            return self.servicio_unidad

        # Fallback: intentar obtener desde RRHH
        try:
            empleado = self.usuario.empleado
            if empleado:
                # Intentar PersonalNoClinico primero
                personal = empleado.personal_no_clinico
                if personal and personal.servicio_unidad:
                    return personal.servicio_unidad

                # Luego intentar PersonalSalud
                personal_salud = empleado.personal_salud_empleado
                if personal_salud and personal_salud.servicio_unidad:
                    return personal_salud.servicio_unidad
        except (AttributeError, Exception):
            pass

        return None


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

    # ============================================================
    # Paciente vinculado al expediente AL MOMENTO de crear la solicitud.
    # ============================================================
    # Antes guardábamos texto duplicado (paciente_identidad + paciente_nombre).
    # Ahora solo guardamos el ID y consultamos en vivo via los servicios
    # (ver s_exp/services/datos_solicitud.py).
    #
    # ¿Por qué guardar el paciente y no inferirlo de la asignación actual?
    # Porque PacienteAsignacion puede cambiar (un expediente se puede reasignar
    # a otro paciente). Necesitamos conservar la referencia al paciente que
    # tenía el expediente AL MOMENTO del préstamo, para auditoría histórica.
    paciente = models.ForeignKey(
        'paciente.Paciente',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='solicitudes_expediente_detalle',
        verbose_name='Paciente vinculado al momento de la solicitud',
        help_text='FK al paciente. Para mostrar nombre/identidad se consulta en vivo.'
    )

    # Los campos snapshot fueron eliminados en migración 0015.
    # El acceso a paciente_dni, paciente_nombre y numero_expediente ahora
    # se hace vía s_exp/services/datos_solicitud.py → DatosDetalleSolicitud.
    aprobado = models.BooleanField(
        default=True,
        verbose_name='Expediente Aprobado para préstamo'
    )
    motivo_rechazo_individual = models.TextField(
        blank=True,
        null=True,
        verbose_name='Motivo de rechazo del expediente'
    )
    devuelto = models.BooleanField(
        default=False,
        verbose_name='Devuelto'
    )
    fuera_de_tiempo = models.BooleanField(
        default=False,
        verbose_name='Entregado fuera de tiempo'
    )
    comentario_devolucion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Comentario de devolución del expediente'
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
    alerta_vencimiento_leida_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Última alerta de vencimiento aceptada'
    )
    estado = models.CharField(
        max_length=30,
        choices=ESTADO_CHOICES,
        default='Activo',
        verbose_name='Estado del Préstamo'
    )
    tiempo_limite_horas = models.PositiveIntegerField(
        default=24,
        verbose_name='Tiempo Límite',
        help_text='Configurable por préstamo. Representa horas por defecto o minutos si es_minutos es True.'
    )
    es_minutos = models.BooleanField(
        default=False,
        verbose_name='¿Es en minutos?',
        help_text='Solo para pruebas. Si es True, el tiempo límite se cuenta en minutos.'
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
# LOG HISTÓRICO GENERAL
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


# ============================================
# TRANSACCIONAL: HISTORIAL DE ESTADOS EXPEDIENTE
# ============================================
class ExpedienteEstadoLog(models.Model):
    expediente = models.ForeignKey(
        Expediente,
        on_delete=models.CASCADE,
        related_name='historial_estados_fisicos',
        verbose_name='Expediente'
    )
    estado_anterior = models.ForeignKey(
        EstadoExpedienteFisico,
        on_delete=models.PROTECT,
        related_name='logs_como_anterior',
        null=True,
        blank=True,
        verbose_name='Estado Anterior'
    )
    estado_nuevo = models.ForeignKey(
        EstadoExpedienteFisico,
        on_delete=models.PROTECT,
        related_name='logs_como_nuevo',
        verbose_name='Estado Nuevo'
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cambios_estado_fisico',
        verbose_name='Usuario que cambió'
    )
    solicitud = models.ForeignKey(
        SolicitudPrestamo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_expediente',
        verbose_name='Solicitud Relacionada'
    )
    fecha = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha/Hora'
    )
    observacion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observación'
    )

    class Meta:
        db_table = 's_exp_expedienteestadolog'
        verbose_name = 'Transacción de Estado'
        verbose_name_plural = 'Transacciones de Estados'
        ordering = ['-fecha']

    def __str__(self):
        return f"Exp #{self.expediente.numero}: {self.estado_nuevo.nombre} ({self.fecha})"


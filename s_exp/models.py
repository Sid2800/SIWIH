from django.db import models
from django.contrib.auth.models import User
from expediente.models import Expediente


# ============================================
# MIXIN: CATÁLOGO CON CÓDIGO SEMÁNTICO
# ============================================
class CatalogoCodigoMixin(models.Model):
    """
    Base para los catálogos de estados/acciones del módulo.

    DISEÑO RELACIONAL:
      - La LLAVE PRIMARIA es un 'id' entero autoincremental (lo agrega Django
        automáticamente). Las FK de las tablas transaccionales guardan ese id
        (entero pequeño), NO el texto — esto reduce el tamaño de la BD y es la
        forma correcta de normalizar (igual que s_exp_motivosolicitud).
      - 'codigo' es un texto ESTABLE y ÚNICO ('Entregado', 'SOL_PENDIENTE'...).
        Sirve para que la LÓGICA del código siga siendo legible y para mostrar
        en el frontend. NO es la PK: es solo una columna indexada única.

    ACCESO DESDE EL CÓDIGO:
      - Para FILTRAR por código:   Modelo.objects.filter(campo__codigo='X')
      - Para ASIGNAR/COMPARAR id:  Modelo.id_de('X')   → devuelve el id entero
      - Para LEER el código de un id (sin query): Modelo.codigo_de(id)
      - Para obtener la instancia: Modelo.obtener('X')

    RENDIMIENTO:
      id_de()/codigo_de()/obtener() cachean el mapeo a nivel de clase. Los
      catálogos son pequeños y casi inmutables, así que tras la primera
      consulta se sirven de memoria (0 queries). codigo_de() evita el N+1 al
      serializar muchas filas (no toca la relación). Si se repuebla el
      catálogo, reinicie el proceso (o llame a limpiar_cache()).
    """
    codigo = models.CharField(max_length=50, unique=True)

    class Meta:
        abstract = True

    # Cachés por clase. Cada subclase obtiene los suyos al asignarse por primera
    # vez (cls.<attr> = ...), sin compartir con las demás subclases.
    _cache_id = None        # { codigo: id }
    _cache_codigo = None    # { id: codigo }

    @classmethod
    def id_de(cls, codigo):
        """Devuelve el id ENTERO correspondiente a un código (cacheado)."""
        if cls._cache_id is None:
            cls._cache_id = {}
        if codigo not in cls._cache_id:
            cls._cache_id[codigo] = cls.objects.get(codigo=codigo).pk
        return cls._cache_id[codigo]

    @classmethod
    def codigo_de(cls, id_):
        """Devuelve el CÓDIGO (texto) a partir de un id, sin query (cacheado)."""
        if not id_:
            return ''
        if cls._cache_codigo is None:
            cls._cache_codigo = {
                row['id']: row['codigo'] for row in cls.objects.values('id', 'codigo')
            }
        return cls._cache_codigo.get(id_, '')

    @classmethod
    def obtener(cls, codigo):
        """Devuelve la INSTANCIA correspondiente a un código."""
        return cls.objects.get(codigo=codigo)

    @classmethod
    def limpiar_cache(cls):
        """Invalida las cachés (usar tras repoblar el catálogo)."""
        cls._cache_id = None
        cls._cache_codigo = None


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
class EstadoSolicitud(CatalogoCodigoMixin):
    # 'codigo' (texto único) y la PK entera 'id' vienen de CatalogoCodigoMixin.
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
class EstadoExpedienteFisico(CatalogoCodigoMixin):
    """
    Define el estado físico actual de un expediente en el archivo
    (ej. Disponible, Prestado, En Proceso de Ubicación).
    'codigo' (texto único) y la PK entera 'id' vienen de CatalogoCodigoMixin.
    """
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
# CATÁLOGO: ESTADOS DEL PRÉSTAMO
# ============================================
class EstadoPrestamo(CatalogoCodigoMixin):
    """
    Catálogo de estados del ciclo de vida de un préstamo.

    Reemplaza el antiguo CharField con choices en Prestamo.estado.
    El 'codigo' es la clave primaria (string) — mismo patrón que
    EstadoSolicitud y EstadoExpedienteFisico — para que las consultas
    existentes (filter(estado='Entregado')) sigan funcionando: Django las
    interpreta como filter(estado_id='Entregado').

    Estados:
      Activo            → préstamo aprobado, aún no entregado
      Entregado         → entregado al solicitante, cronómetro corriendo
      Vencido           → superó la fecha límite sin devolverse
      DevolucionParcial → devolución incompleta (faltan expedientes)
      Cerrado           → devolución completa, préstamo finalizado
      DevueltoVencido   → devuelto pero fuera de tiempo

    'codigo' (texto único) y la PK entera 'id' vienen de CatalogoCodigoMixin.
    """
    nombre = models.CharField(
        max_length=60,
        verbose_name='Nombre legible del Estado'
    )

    class Meta:
        db_table = 's_exp_estadoprestamo'
        verbose_name = 'Estado de Préstamo'
        verbose_name_plural = 'Estados de Préstamo'

    def __str__(self):
        return self.nombre


# ============================================
# CATÁLOGO: ESTADOS DE LA DEVOLUCIÓN
# ============================================
class EstadoDevolucion(CatalogoCodigoMixin):
    """
    Catálogo de estados de una devolución (auditoría).

    Reemplaza el CharField con choices en Devolucion.estado.
    'codigo' como PK (string) por consistencia con los demás catálogos.

    Estados:
      Completa   → se recibieron todos los expedientes esperados
      Incompleta → faltaron expedientes por recibir
      Parcial    → devolución parcial registrada

    'codigo' (texto único) y la PK entera 'id' vienen de CatalogoCodigoMixin.
    """
    nombre = models.CharField(
        max_length=40,
        verbose_name='Nombre legible del Estado'
    )

    class Meta:
        db_table = 's_exp_estadodevolucion'
        verbose_name = 'Estado de Devolución'
        verbose_name_plural = 'Estados de Devolución'

    def __str__(self):
        return self.nombre


# ============================================
# CATÁLOGO: TIPOS DE ACCIÓN DEL LOG
# ============================================
class TipoAccionLog(CatalogoCodigoMixin):
    """
    Catálogo de tipos de acción registrados en la bitácora (LogHistorico).

    Reemplaza el CharField libre en LogHistorico.accion. Tener un catálogo
    relacional evita typos, permite traducir/describir cada acción en un
    solo lugar y facilita reportes/filtros por tipo.

    'codigo' como PK (string) para que _registrar_log siga recibiendo el
    código tal cual ('SOLICITUD_CREADA') y se asigne como accion_id.

    Tipos:
      SOLICITUD_CREADA              → usuario crea una solicitud
      SOLICITUD_APROBADA            → admin aprueba
      SOLICITUD_RECHAZADA           → admin rechaza
      SOLICITUD_LISTA               → admin marca lista para recoger
      SOLICITUD_DEVOLUCION_INICIADA → usuario pide devolver
      PRESTAMO_ENTREGADO            → admin entrega el préstamo
      REVISION_ENTREGA              → admin revisa entrega
      DEVOLUCION_PROCESADA          → admin audita la devolución

    'codigo' (texto único) y la PK entera 'id' vienen de CatalogoCodigoMixin.
    """
    nombre = models.CharField(
        max_length=100,
        verbose_name='Nombre legible de la Acción'
    )

    class Meta:
        db_table = 's_exp_tipoaccionlog'
        verbose_name = 'Tipo de Acción (Log)'
        verbose_name_plural = 'Tipos de Acción (Log)'

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
    # FK al catálogo (guarda el id entero). El estado inicial 'EXP_DISPONIBLE'
    # se asigna explícitamente en el código (get_or_create) vía
    # EstadoExpedienteFisico.id_de('EXP_DISPONIBLE').
    estado = models.ForeignKey(
        EstadoExpedienteFisico,
        on_delete=models.PROTECT,
        related_name='expedientes',
        verbose_name='Estado Físico Actual'
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
    # FK al catálogo (guarda el id entero). El estado inicial 'SOL_PENDIENTE'
    # se asigna explícitamente al crear la solicitud vía
    # EstadoSolicitud.id_de('SOL_PENDIENTE').
    estado_flujo = models.ForeignKey(
        EstadoSolicitud,
        on_delete=models.PROTECT,
        related_name='solicitudes',
        verbose_name='Estado de la Solicitud'
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
    # -------------------------------------------------------------------------
    # Decisión del USUARIO al iniciar la devolución (flujo devolución completa /
    # parcial). Es distinta de 'devuelto'/'comentario_devolucion', que los llena
    # el ADMIN durante la auditoría de recepción física.
    #   - None  : el usuario aún no inició devolución para este expediente.
    #   - True  : el usuario quiere devolver este expediente (completa, o los
    #             marcados "Devolver" en la parcial).
    #   - False : el usuario lo deja "todavía en uso" (parcial no devueltos).
    # El admin usa este valor para PRE-CARGAR su auditoría (Recibido / No Recibido).
    # -------------------------------------------------------------------------
    usuario_solicita_devolver = models.BooleanField(
        null=True,
        blank=True,
        default=None,
        verbose_name='El usuario solicitó devolver este expediente'
    )
    comentario_usuario_devolucion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Comentario del usuario al iniciar la devolución'
    )
    # ---- Préstamo pendiente (marcado en la Revisión de Entrega) ----
    # El expediente fue encontrado pero NO se entrega aún: queda RESERVADO
    # (expediente_prestamo.estado = EXP_PENDIENTE_PRESTAMO, no disponible para
    # otros) hasta que el admin lo entregue ("Entregar pendientes") o lo cancele
    # ("Cancelar pendientes"). Persiste aunque el resto de la solicitud ya se
    # haya entregado; se muestra en morado en los listados.
    prestamo_pendiente = models.BooleanField(
        default=False,
        verbose_name='Marcado como préstamo pendiente'
    )
    comentario_pendiente = models.TextField(
        blank=True,
        null=True,
        verbose_name='Comentario del préstamo pendiente'
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
    # Estado del préstamo: FK RELACIONAL al catálogo EstadoPrestamo, cuya PK
    # es un id ENTERO (no el texto). Para trabajar con el código:
    #   - Asignar:  prestamo.estado_id = EstadoPrestamo.id_de('Entregado')
    #   - Filtrar:  Prestamo.objects.filter(estado__codigo='Entregado')
    #   - Comparar: prestamo.estado_id == EstadoPrestamo.id_de('Entregado')
    #   - Leer cód: prestamo.estado.codigo  (o vía DatosPrestamo en servicios)
    estado = models.ForeignKey(
        EstadoPrestamo,
        on_delete=models.PROTECT,
        related_name='prestamos',
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

    # Estados en los que el préstamo sigue vigente (hay expedientes fuera del
    # archivo) y por lo tanto el CRONÓMETRO debe seguir corriendo:
    #   - Entregado         → préstamo normal en curso.
    #   - Vencido           → se pasó del límite, pero sigue sin devolverse.
    #   - DevolucionParcial → solo regresaron ALGUNOS expedientes; la solicitud
    #                         NO ha terminado y los que siguen prestados
    #                         continúan consumiendo tiempo.
    # Se excluyen Cerrado y DevueltoVencido (ahí el préstamo ya finalizó).
    ESTADOS_CRONOMETRO_ACTIVO = ('Entregado', 'Vencido', 'DevolucionParcial')

    @property
    def cronometro_activo(self):
        """
        True si el tiempo del préstamo debe seguir contando.

        Antes las propiedades de tiempo exigían estado == 'Entregado', por lo que
        al registrar una devolución PARCIAL (estado 'DevolucionParcial') el
        cronómetro desaparecía aunque la solicitud siguiera abierta.
        """
        return self.estado_id in {
            EstadoPrestamo.id_de(codigo) for codigo in self.ESTADOS_CRONOMETRO_ACTIVO
        }

    @property
    def esta_vencido(self):
        from django.utils import timezone
        if self.fecha_limite and self.cronometro_activo:
            return timezone.now() > self.fecha_limite
        return False

    @property
    def tiempo_restante_segundos(self):
        from django.utils import timezone
        if self.fecha_limite and self.cronometro_activo:
            delta = self.fecha_limite - timezone.now()
            return max(0, int(delta.total_seconds()))
        return None

    @property
    def porcentaje_tiempo_usado(self):
        from django.utils import timezone
        if self.fecha_entrega and self.fecha_limite and self.cronometro_activo:
            total = (self.fecha_limite - self.fecha_entrega).total_seconds()
            usado = (timezone.now() - self.fecha_entrega).total_seconds()
            if total > 0:
                return min(100, round((usado / total) * 100, 1))
        return 0


# ============================================
# DEVOLUCIÓN
# ============================================
class Devolucion(models.Model):
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
    # Estado de la devolución ahora es RELACIONAL (FK al catálogo
    # EstadoDevolucion). PK = código string ('Completa', 'Incompleta',
    # 'Parcial'). Asignar con estado_id; las queries por string siguen igual.
    estado = models.ForeignKey(
        EstadoDevolucion,
        on_delete=models.PROTECT,
        related_name='devoluciones',
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
# CATÁLOGO: TIPOS DE OBJETO DEL LOG
# ============================================
class TipoObjetoLog(CatalogoCodigoMixin):
    """
    Catálogo del 'tipo de objeto' al que apunta una entrada de LogHistorico
    (junto con objeto_id forman una referencia genérica).

    Antes objeto_tipo era texto libre ('SolicitudPrestamo', 'Prestamo'...).
    Ahora es relacional: la FK guarda el id entero y aquí vive el código/nombre.
    'codigo' y la PK entera 'id' vienen de CatalogoCodigoMixin.

    Códigos esperados (nombre del modelo referenciado):
      SolicitudPrestamo, Prestamo, Devolucion, ...
    Se crean al vuelo (get_or_create) si aparece un código nuevo.
    """
    nombre = models.CharField(
        max_length=100,
        verbose_name='Nombre legible del Tipo de Objeto'
    )

    class Meta:
        db_table = 's_exp_tipoobjetolog'
        verbose_name = 'Tipo de Objeto (Log)'
        verbose_name_plural = 'Tipos de Objeto (Log)'

    def __str__(self):
        return self.nombre


# ============================================
# LOG HISTÓRICO GENERAL
# ============================================
class LogHistorico(models.Model):
    # Acción ahora es RELACIONAL (FK al catálogo TipoAccionLog).
    # PK = código string ('SOLICITUD_CREADA'...). _registrar_log sigue
    # recibiendo el código y lo asigna como accion_id. Las queries
    # filter(accion__in=[...]) siguen funcionando (mapean a accion_id__in).
    accion = models.ForeignKey(
        TipoAccionLog,
        on_delete=models.PROTECT,
        related_name='logs',
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
    # Tipo de objeto ahora es RELACIONAL (FK al catálogo TipoObjetoLog).
    # La FK guarda el id entero; registrar_log sigue recibiendo el código
    # ('SolicitudPrestamo'...) y lo resuelve a la instancia.
    objeto_tipo = models.ForeignKey(
        TipoObjetoLog,
        on_delete=models.PROTECT,
        related_name='logs',
        null=True,
        blank=True,
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


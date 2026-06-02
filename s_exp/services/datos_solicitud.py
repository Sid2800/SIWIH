"""
Servicios de acceso a datos de Solicitudes de Expedientes.
=============================================================================

Este módulo encapsula el acceso a los datos relacionados con una solicitud
de préstamo y sus detalles. La idea es que el código que necesita mostrar
información (APIs, PDF, etc.) NO acceda directamente a campos snapshot de
texto, sino que use estas clases para consultar en vivo via los FK.

¿Por qué existe esta capa?
--------------------------
Antes, los modelos guardaban texto duplicado (paciente_identidad, paciente_nombre,
numero_expediente, area_destino). Eso causa varios problemas:

  - Crecimiento innecesario de la BD (un mismo nombre se guarda N veces).
  - Inconsistencias: si cambia el nombre del paciente, los snapshots quedan obsoletos.
  - Tiempo de filtrado más lento por índices más grandes.

Con esta capa:

  - Los modelos solo guardan IDs (FK).
  - El nombre, identidad, etc. se consultan en vivo cuando se necesitan.
  - Si el dato cambia en su tabla origen, se refleja en todos los lugares.

Convenciones:
-------------
- Métodos estáticos: no requieren instanciar nada (clases-namespace).
- Cada método dice CLARAMENTE de dónde viene el dato (tabla.campo).
- Si el FK es NULL, se intenta caer al snapshot deprecado y se devuelve ''.
- Si todo falla, se devuelve cadena vacía (NUNCA None — evita errores en templates).
"""

from typing import Optional
from django.utils import timezone


def _fmt_local_dt(dt, formato='%d/%m/%Y %H:%M'):
    """
    Formatea un datetime convirtiéndolo a la zona horaria local (UTC-6) en
    formato de 24 horas. Django guarda en UTC; la conversión a local se hace
    solo al mostrar.
    """
    if not dt:
        return ''
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.strftime(formato).strip()


# =============================================================================
# DatosDetalleSolicitud
# =============================================================================
class DatosDetalleSolicitud:
    """
    Acceso unificado a los datos de un SolicitudExpedienteDetalle.

    Encapsula la lectura de:
      - Número del expediente (desde Expediente.numero via FK).
      - Identidad del paciente (desde Paciente.dni via FK).
      - Nombre completo del paciente (desde Paciente via FK).
      - ID del paciente (para enviar al frontend).

    Si en algún momento el FK `paciente` es NULL (registros viejos sin backfill),
    los métodos caen al snapshot deprecado como respaldo. Cuando se eliminen
    los campos deprecados (Fase 5), esta caída desaparecerá automáticamente.
    """

    # -------------------------------------------------------------------------
    # Datos del expediente
    # -------------------------------------------------------------------------
    @staticmethod
    def numero_expediente(detalle) -> int:
        """
        Devuelve el número de expediente.
        Origen: expediente_prestamo.expediente.numero (vía FK).
        """
        try:
            return detalle.expediente_prestamo.expediente.numero
        except AttributeError:
            return 0

    @staticmethod
    def expediente_id(detalle) -> Optional[int]:
        """
        Devuelve el ID del expediente (no el número).
        Útil para construir URLs / FKs en respuestas.
        """
        try:
            return detalle.expediente_prestamo.expediente_id
        except AttributeError:
            return None

    # -------------------------------------------------------------------------
    # Datos del paciente
    # -------------------------------------------------------------------------
    @staticmethod
    def paciente_id(detalle) -> Optional[int]:
        """
        Devuelve el ID del paciente vinculado al expediente AL MOMENTO de la solicitud.
        """
        return detalle.paciente_id

    @staticmethod
    def paciente_dni(detalle) -> str:
        """
        Devuelve la identidad/DNI del paciente.
        Origen: paciente.dni (vía FK).
        """
        if detalle.paciente_id and detalle.paciente:
            return detalle.paciente.dni or ''
        return ''

    @staticmethod
    def paciente_nombre_completo(detalle) -> str:
        """
        Devuelve el nombre completo del paciente (primer_nombre segundo_nombre
        primer_apellido segundo_apellido, con espacios reducidos).
        Origen: paciente.primer_nombre + ... (vía FK).
        """
        if detalle.paciente_id and detalle.paciente:
            p = detalle.paciente
            partes = [p.primer_nombre, p.segundo_nombre, p.primer_apellido, p.segundo_apellido]
            return ' '.join([t for t in partes if t]).strip()
        return ''

    # -------------------------------------------------------------------------
    # Enriquecimiento completo (para APIs JSON)
    # -------------------------------------------------------------------------
    @staticmethod
    def enriquecer(detalle) -> dict:
        """
        Devuelve un dict con TODOS los datos derivados del detalle.
        Útil para construir respuestas JSON de APIs.

        Estructura:
          {
              "detalle_id":          int,
              "numero":              int,    # número de expediente
              "expediente_id":       int,
              "paciente_id":         int,
              "paciente_identidad":  str,    # DNI
              "paciente_nombre":     str,    # nombre completo
              "aprobado":            bool,
              "devuelto":            bool,
              "fuera_de_tiempo":     bool,
              "motivo_rechazo":      str,
              "comentario_devolucion": str,
          }
        """
        return {
            'detalle_id': detalle.id,
            'numero': DatosDetalleSolicitud.numero_expediente(detalle),
            'expediente_id': DatosDetalleSolicitud.expediente_id(detalle),
            'paciente_id': DatosDetalleSolicitud.paciente_id(detalle),
            'paciente_identidad': DatosDetalleSolicitud.paciente_dni(detalle),
            'paciente_nombre': DatosDetalleSolicitud.paciente_nombre_completo(detalle),
            'aprobado': bool(detalle.aprobado),
            'devuelto': bool(detalle.devuelto),
            'fuera_de_tiempo': bool(detalle.fuera_de_tiempo),
            'motivo_rechazo_individual': detalle.motivo_rechazo_individual or '',
            'comentario_devolucion': detalle.comentario_devolucion or '',
        }


# =============================================================================
# DatosSolicitud
# =============================================================================
class DatosSolicitud:
    """
    Acceso unificado a los datos de una SolicitudPrestamo (cabecera).

    Encapsula la lectura de:
      - Datos del usuario solicitante (username, nombre, etc.).
      - Unidad/Área destino (via servicio_unidad FK).
      - Motivo (via FK al catálogo).
      - Estado del flujo (via FK al catálogo).
    """

    # -------------------------------------------------------------------------
    # Usuario solicitante
    # -------------------------------------------------------------------------
    @staticmethod
    def usuario_username(solicitud) -> str:
        """Username del solicitante (auth_user.username)."""
        return solicitud.usuario.username if solicitud.usuario_id else ''

    @staticmethod
    def usuario_nombre_completo(solicitud) -> str:
        """
        Nombre completo del solicitante (first_name + last_name).
        Cae a username si no hay nombre.
        """
        if not solicitud.usuario_id:
            return ''
        u = solicitud.usuario
        nombre = f"{u.first_name or ''} {u.last_name or ''}".strip()
        return nombre or u.username

    # -------------------------------------------------------------------------
    # Ubicación / Unidad del solicitante
    # -------------------------------------------------------------------------
    @staticmethod
    def unidad_id(solicitud) -> Optional[int]:
        """ID de la unidad de servicio asociada (servicio_unidad.id)."""
        return solicitud.servicio_unidad_id

    @staticmethod
    def unidad_nombre(solicitud) -> str:
        """
        Nombre de la unidad de servicio (servicio_unidad.nombre_unidad).
        Si la FK es NULL, devuelve cadena vacía.
        """
        if solicitud.servicio_unidad_id and solicitud.servicio_unidad:
            return solicitud.servicio_unidad.nombre_unidad or ''
        return ''

    # -------------------------------------------------------------------------
    # Motivo y estado
    # -------------------------------------------------------------------------
    @staticmethod
    def motivo_nombre(solicitud) -> str:
        """Nombre del motivo (catalogo MotivoSolicitud)."""
        return solicitud.motivo.nombre if solicitud.motivo_id else ''

    @staticmethod
    def estado_codigo(solicitud) -> str:
        """Código del estado de la solicitud (ej: SOL_PENDIENTE)."""
        return solicitud.estado_flujo_id or ''

    @staticmethod
    def estado_nombre(solicitud) -> str:
        """Nombre legible del estado (catalogo EstadoSolicitud)."""
        return solicitud.estado_flujo.nombre if solicitud.estado_flujo_id else ''

    # -------------------------------------------------------------------------
    # Enriquecimiento completo
    # -------------------------------------------------------------------------
    @staticmethod
    def enriquecer(solicitud, incluir_detalles: bool = True) -> dict:
        """
        Devuelve un dict con los datos derivados de la solicitud.
        Si incluir_detalles=True, agrega la lista de expedientes enriquecidos.
        """
        data = {
            'id': solicitud.id,
            'usuario': DatosSolicitud.usuario_username(solicitud),
            'usuario_nombre': DatosSolicitud.usuario_nombre_completo(solicitud),
            # Convertir a hora local (UTC-6) antes de formatear
            'fecha_creacion': _fmt_local_dt(solicitud.fecha_creacion),
            'estado_flujo': DatosSolicitud.estado_codigo(solicitud),
            'estado_flujo_nombre': DatosSolicitud.estado_nombre(solicitud),
            'motivo': DatosSolicitud.motivo_nombre(solicitud),
            'observaciones': solicitud.observaciones or '',
            'unidad_id': DatosSolicitud.unidad_id(solicitud),
            'unidad': DatosSolicitud.unidad_nombre(solicitud),
            'tiempo_sugerido_horas': solicitud.tiempo_sugerido_horas,
        }
        if incluir_detalles:
            data['detalles'] = [
                DatosDetalleSolicitud.enriquecer(d)
                for d in solicitud.detalles.select_related(
                    'expediente_prestamo__expediente', 'paciente'
                )
            ]
            data['cant_expedientes'] = len(data['detalles'])
        return data


# =============================================================================
# UbicacionUsuario
# =============================================================================
class UbicacionUsuario:
    """
    Resuelve la unidad de servicio (ubicación física) de un usuario.

    Cascada de resolución (en orden):
      1. RRHH: empleado → PersonalNoClinico → servicio_unidad
      2. RRHH: empleado → PersonalSalud → servicio_unidad

    Pensado para llamarse al CREAR una solicitud, así se captura la unidad
    al momento. Si después el usuario cambia de área, las solicitudes viejas
    conservan la unidad original via servicio_unidad FK.
    """

    @staticmethod
    def resolver(user) -> Optional[object]:
        """
        Devuelve la instancia de servicio.Unidad o None.

        El método NO lanza excepciones por ausencia de registros RRHH —
        simplemente devuelve None.
        """
        if not user or not user.is_authenticated:
            return None

        try:
            from rrhh.models import Empleado, PersonalNoClinico, PersonalSalud
        except ImportError:
            return None

        empleado = Empleado.objects.filter(usuario_id=user.id).first()
        if not empleado:
            return None

        # Personal NO clínico (administrativos, estadística, archivo, etc.)
        pnc = PersonalNoClinico.objects.filter(
            empleado_id=empleado.id, servicio_unidad__isnull=False
        ).select_related('servicio_unidad').first()
        if pnc and pnc.servicio_unidad:
            return pnc.servicio_unidad

        # Personal clínico (médicos, enfermeros)
        ps = PersonalSalud.objects.filter(
            empleado_id=empleado.id, servicio_unidad__isnull=False
        ).select_related('servicio_unidad').first()
        if ps and ps.servicio_unidad:
            return ps.servicio_unidad

        return None

    @staticmethod
    def esta_registrado(user) -> bool:
        """
        Verifica que el usuario tenga la cadena RRHH completa:
          auth_user → rrhh_empleado → PersonalNoClinico/PersonalSalud → servicio_unidad
        """
        return UbicacionUsuario.resolver(user) is not None


# =============================================================================
# DatosPaciente
# =============================================================================
class DatosPaciente:
    """
    Acceso a datos de paciente por ID. Para usar cuando ya tenemos el paciente_id
    y queremos mostrar info (sin pasar por SolicitudExpedienteDetalle).
    """

    @staticmethod
    def obtener_por_id(paciente_id):
        """Devuelve la instancia Paciente o None."""
        if not paciente_id:
            return None
        try:
            from paciente.models import Paciente
            return Paciente.objects.filter(id=paciente_id).first()
        except ImportError:
            return None

    @staticmethod
    def dni(paciente) -> str:
        """DNI / identidad del paciente."""
        return paciente.dni if paciente else ''

    @staticmethod
    def nombre_completo(paciente) -> str:
        """Nombre completo (primer_nombre + segundo_nombre + apellidos)."""
        if not paciente:
            return ''
        partes = [
            paciente.primer_nombre, paciente.segundo_nombre,
            paciente.primer_apellido, paciente.segundo_apellido,
        ]
        return ' '.join([t for t in partes if t]).strip()

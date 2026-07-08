"""
comunes.py - Helpers compartidos y mixins de acceso del modulo s_exp.

Parte del paquete s_exp.views (antes views.py monolitico).
"""



from django.utils import timezone

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect

from s_exp.models import LogHistorico
from usuario.models import PerfilUnidad


from core.utils.utilidades_logging import log_info, log_warning, log_error
from core.constants.domain_constants import LogApp


# ============================================
# UTILIDAD: Formateo de fecha/hora en zona local
# ============================================
def _fmt_local(dt, formato="%d/%m/%Y %H:%M"):
    """
    Formatea un datetime CONVIRTIÉNDOLO a la zona horaria local del sistema
    (TIME_ZONE = America/Tegucigalpa, UTC-6), en formato de 24 horas.

    Compatibilidad:
      - La BD guarda en UTC (USE_TZ=True), igual que TODOS los módulos.
        NO se cambia el almacenamiento para no romper compatibilidad.
      - La conversión a hora local se hace SOLO al mostrar, con
        timezone.localtime(), idéntico a core/utils/utilidades_fechas.py.

    Formato 24h: "%H:%M" → ej. "09:09" / "20:30".

    Args:
        dt: datetime aware (o None).
        formato: patrón strftime (por defecto 24h).

    Returns:
        str: fecha/hora local formateada, o '' si dt es None.
    """
    if not dt:
        return ''
    # Si es aware, convertir a la zona local; si es naive, asumir que ya es local
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.strftime(formato).strip()


# ============================================
# UTILIDAD: Registrar Log en BD
# ============================================
def _registrar_log(usuario, accion, descripcion, objeto_tipo=None, objeto_id=None):
    """
    Registra un evento en la bitácora de auditoría del sistema (LogHistorico).

    Args:
        usuario: Instancia de User que realiza la acción.
        accion: CÓDIGO de la acción (ej. 'SOLICITUD_CREADA'). Es el 'codigo'
                (texto único) del catálogo TipoAccionLog; la FK guarda su id.
        descripcion: Texto explicativo del evento.
        objeto_tipo: Nombre del modelo afectado (opcional).
        objeto_id: ID del registro afectado (opcional).

    Nota: si el código de acción no existe en el catálogo TipoAccionLog,
    se crea al vuelo (get_or_create) para que el log nunca falle por un
    código nuevo no registrado previamente.
    """
    from s_exp.models import TipoAccionLog, TipoObjetoLog
    # Asegurar que el tipo de acción exista en el catálogo (evita FK error).
    # La PK es un id ENTERO; usamos la instancia obtenida para la FK.
    tipo, _ = TipoAccionLog.objects.get_or_create(codigo=accion, defaults={'nombre': accion})

    # objeto_tipo ahora es relacional (FK a TipoObjetoLog): recibimos el código
    # (nombre del modelo) y lo resolvemos a su instancia.
    obj_tipo = None
    if objeto_tipo:
        obj_tipo, _ = TipoObjetoLog.objects.get_or_create(
            codigo=objeto_tipo, defaults={'nombre': objeto_tipo})

    LogHistorico.objects.create(
        accion=tipo,            # FK a TipoAccionLog (PK = id entero)
        usuario=usuario,
        detalle=descripcion,
        objeto_tipo=obj_tipo,   # FK a TipoObjetoLog (PK = id entero) o None
        objeto_id=objeto_id,
    )


# ============================================
# UTILIDAD: Verificar permisos basados en PerfilUnidad
# ============================================
def _es_exp_admin(user):
    """
    Verifica si un usuario tiene permisos administrativos sobre el módulo de expedientes.
    Requisitos:
    - Debe estar registrado en RRHH (rrhh_empleado)
    - Debe tener uno de estos roles: Administrador, Digitador, Directivo
    """
    # Validación global: usuario debe estar en RRHH
    if not _es_usuario_valido_rrhh(user):
        return False

    if user.is_superuser or user.is_staff:
        return True
    if user.groups.filter(name='administradores').exists():
        return True
    # Permitir acceso a usuarios con roles: admin, digitador, directivo
    return PerfilUnidad.objects.filter(
        usuario=user,
        rol__in=['admin', 'digitador', 'directivo']
    ).exists()


def _es_usuario_valido_rrhh(user):
    """
    Verifica si el usuario está completamente registrado en la cadena RRHH.
    Requisito previo para cualquier acceso al módulo s_exp.

    Valida la cadena completa:
    1. Existe en rrhh_empleado (usuario_id = user.id)
    2. Existe en rrhh_personalnoclinico O rrhh_personalsalud (empleado_id)
    3. Tiene servicio_unidad_id asignado en uno de los dos

    Retorna: True si está completamente registrado, False en caso contrario
    """
    from rrhh.models import Empleado, PersonalNoClinico, PersonalSalud

    try:
        # Paso 1: Verificar que existe rrhh_empleado
        empleado = Empleado.objects.filter(usuario_id=user.id).first()
        if not empleado:
            log_warning(f"Usuario {user.username} (id={user.id}) no existe en rrhh_empleado", app=LogApp.S_EXP)
            return False

        # Paso 2 & 3: Verificar que está en PersonalNoClinico O PersonalSalud CON servicio_unidad
        personal_no_clinico = PersonalNoClinico.objects.filter(
            empleado_id=empleado.id,
            servicio_unidad_id__isnull=False  # Verificar que servicio_unidad_id está asignado
        ).exists()

        if personal_no_clinico:
            log_info(f"Usuario {user.username}: Validado - PersonalNoClinico con servicio_unidad", app=LogApp.S_EXP)
            return True

        personal_salud = PersonalSalud.objects.filter(
            empleado_id=empleado.id,
            servicio_unidad_id__isnull=False  # Verificar que servicio_unidad_id está asignado
        ).exists()

        if personal_salud:
            log_info(f"Usuario {user.username}: Validado - PersonalSalud con servicio_unidad", app=LogApp.S_EXP)
            return True

        # No está en PersonalNoClinico ni PersonalSalud, o no tiene servicio_unidad
        log_warning(f"Usuario {user.username}: Empleado registrado pero sin PersonalNoClinico/PersonalSalud o sin servicio_unidad asignado", app=LogApp.S_EXP)
        return False

    except Exception as e:
        log_error(f"Error al validar RRHH para usuario {user.username}: {e}", app=LogApp.S_EXP)
        return False


def _es_exp_solicitante(user):
    """True si el usuario puede acceder al módulo (solicitar expedientes).
    Condiciones:
    - Debe estar registrado en RRHH (rrhh_empleado)
    - Debe tener rol 'exp_solicitante' o 'admin' en PerfilUnidad, o ser admin del módulo
    """
    # Validación global: usuario debe estar en RRHH
    if not _es_usuario_valido_rrhh(user):
        return False

    if _es_exp_admin(user):
        return True
    return PerfilUnidad.objects.filter(usuario=user, rol='exp_solicitante').exists()


def _get_unidad_usuario(user):
    """
    Obtiene el NOMBRE de la unidad del usuario con cascada de resolución:
      1. PerfilUnidad (sistema de roles del módulo s_exp)
      2. Cadena RRHH: Empleado → PersonalNoClinico/PersonalSalud → servicio_unidad

    Esto cubre tanto solicitantes (que suelen tener PerfilUnidad) como
    admins/digitadores (que suelen estar solo en RRHH). Devuelve '' si no
    se encuentra en ninguno.
    """
    # 1) PerfilUnidad
    perfil = PerfilUnidad.objects.filter(usuario=user).select_related('servicio_unidad').first()
    if perfil and perfil.servicio_unidad:
        return perfil.servicio_unidad.nombre_unidad

    # 2) Cadena RRHH (reutilizamos el servicio de datos de solicitud)
    try:
        from s_exp.services.datos_solicitud import UbicacionUsuario
        unidad = UbicacionUsuario.resolver(user)
        if unidad:
            return unidad.nombre_unidad
    except Exception:
        pass

    return ''


def _get_servicio_unidad_from_rrhh(user):
    """
    Obtiene la Unidad de Servicio del usuario mediante la cadena de relaciones RRHH.

    Verifica explícitamente la cadena de relaciones:
    1. auth_user.id
    2. rrhh_empleado donde usuario_id = auth_user.id
    3. rrhh_personalnoclinico donde empleado_id = rrhh_empleado.id
    4. servicio_unidad_id en rrhh_personalnoclinico

    Retorna:
        - Tuple: (servicio_unidad_obj, es_valido)
        - servicio_unidad_obj: La instancia de ServicioUnidad o None si no existe
        - es_valido: True si el usuario está correctamente registrado en RRHH, False en caso contrario
    """
    from rrhh.models import Empleado, PersonalNoClinico, PersonalSalud

    try:
        # Paso 1: Verificar que existe rrhh_empleado donde usuario_id = user.id
        empleado = Empleado.objects.filter(usuario_id=user.id).first()
        if not empleado:
            log_warning(f"Usuario {user.username} (id={user.id}) no tiene registro en rrhh_empleado", app=LogApp.S_EXP)
            return None, False

        # Paso 2: Intentar obtener PersonalNoClinico donde empleado_id = empleado.id
        personal_no_clinico = PersonalNoClinico.objects.filter(
            empleado_id=empleado.id
        ).select_related('servicio_unidad').first()

        if personal_no_clinico:
            # Paso 3: Verificar que servicio_unidad_id está asignado
            if personal_no_clinico.servicio_unidad_id:
                log_info(f"Usuario {user.username}: ServicioUnidad {personal_no_clinico.servicio_unidad_id} desde PersonalNoClinico", app=LogApp.S_EXP)
                return personal_no_clinico.servicio_unidad, True
            else:
                log_warning(f"Usuario {user.username}: PersonalNoClinico sin servicio_unidad asignado", app=LogApp.S_EXP)
                return None, True  # Registrado en RRHH pero sin unidad

        # Paso 2 (alternativo): Intentar obtener PersonalSalud si no tiene PersonalNoClinico
        personal_salud = PersonalSalud.objects.filter(
            empleado_id=empleado.id
        ).select_related('servicio_unidad').first()

        if personal_salud:
            # Paso 3: Verificar que servicio_unidad_id está asignado
            if personal_salud.servicio_unidad_id:
                log_info(f"Usuario {user.username}: ServicioUnidad {personal_salud.servicio_unidad_id} desde PersonalSalud", app=LogApp.S_EXP)
                return personal_salud.servicio_unidad, True
            else:
                log_warning(f"Usuario {user.username}: PersonalSalud sin servicio_unidad asignado", app=LogApp.S_EXP)
                return None, True  # Registrado en RRHH pero sin unidad

        # Si llegamos aquí: empleado existe pero sin PersonalNoClinico ni PersonalSalud
        log_warning(f"Usuario {user.username}: Empleado registrado pero sin PersonalNoClinico ni PersonalSalud", app=LogApp.S_EXP)
        return None, True

    except Exception as e:
        log_error(f"Error al verificar RRHH para usuario {user.username}: {e}", app=LogApp.S_EXP)
        return None, False


def _resolver_ubicacion_expediente(expediente, info_exp=None):
    """
    Resuelve la ubicación ACTUAL del expediente (texto legible).

    Prioridad (obtención híbrida durante la transición a expediente_ubicacion):
    1. NUEVO: expediente.ubicacion (FK a ExpedienteUbicacion en la tabla
       principal Expediente) → fuente canónica del catálogo unificado.
    2. NUEVO: ExpedientePrestamo.ubicacion (FK) → específico del préstamo s_exp.
    3. LEGACY: expediente.localizacion.descripcion_localizacion
       → lo que usa el módulo expediente (atenciones/ingresos).
    4. "ADMISION" como último fallback (ARCHIVO quedó deprecado en s_exp).

    Args:
        expediente: instancia de Expediente
        info_exp: instancia opcional de ExpedientePrestamo

    Returns:
        str: descripción de la ubicación actual
    """
    # 1) Nuevo catálogo en la tabla principal Expediente (FK relacional)
    try:
        if getattr(expediente, 'ubicacion_id', None):
            desc = expediente.ubicacion.descripcion
            if desc:
                return desc
    except Exception:
        pass

    # 2) Nuevo catálogo en ExpedientePrestamo (préstamo s_exp)
    try:
        if info_exp and getattr(info_exp, 'ubicacion_id', None):
            desc = info_exp.ubicacion.descripcion
            if desc:
                return desc
    except Exception:
        pass

    # 3) Legacy: localizacion del expediente (atenciones/ingresos)
    try:
        if expediente.localizacion and expediente.localizacion.descripcion_localizacion:
            return expediente.localizacion.descripcion_localizacion
    except Exception:
        pass

    return "ADMISION"


def _set_localizacion_por_solicitud(expediente, solicitud, usuario_admin, ubicacion_obj=None):
    """
    Actualiza la ubicación del expediente al ENTREGAR un préstamo.

    NUEVO (catálogo unificado): si se pasa ubicacion_obj (ExpedienteUbicacion),
    se guarda en expediente.ubicacion (FK por id) — esta es la fuente futura.

    LEGACY: además sincroniza expediente.localizacion (texto) mientras dura la
    transición, con la unidad del SOLICITANTE obtenida desde
    SolicitudPrestamo.servicio_unidad o, si no existe, vía la cadena RRHH.

    Args:
        expediente: instancia de Expediente
        solicitud: instancia de SolicitudPrestamo
        usuario_admin: usuario que aprueba/entrega el préstamo
        ubicacion_obj: instancia de ExpedienteUbicacion (catálogo unificado) o None

    Returns:
        str: descripción de la nueva ubicación asignada
    """
    from expediente.models import Localizacion

    nombre_ubicacion = None

    # 1. Intentar tomar de SolicitudPrestamo.servicio_unidad
    try:
        if solicitud.servicio_unidad and solicitud.servicio_unidad.nombre_unidad:
            nombre_ubicacion = solicitud.servicio_unidad.nombre_unidad
    except Exception:
        pass

    # 2. Fallback: resolver via cadena RRHH del usuario solicitante
    if not nombre_ubicacion:
        try:
            servicio_unidad, _ok = _get_servicio_unidad_from_rrhh(solicitud.usuario)
            if servicio_unidad and servicio_unidad.nombre_unidad:
                nombre_ubicacion = servicio_unidad.nombre_unidad
        except Exception:
            pass

    # 3. Fallback final: el nombre de la unidad si está, o el texto genérico "PRESTADO".
    if not nombre_ubicacion:
        if solicitud.servicio_unidad_id and solicitud.servicio_unidad:
            nombre_ubicacion = (solicitud.servicio_unidad.nombre_unidad or '').strip()
        if not nombre_ubicacion:
            nombre_ubicacion = 'PRESTADO'

    nombre_ubicacion = nombre_ubicacion.upper()

    try:
        loc_obj, _ = Localizacion.objects.get_or_create(
            descripcion_localizacion=nombre_ubicacion,
            defaults={'estado': True}
        )
        expediente.localizacion = loc_obj
        expediente.modificado_por = usuario_admin
        campos = ['localizacion', 'modificado_por', 'fecha_modificado']
        # NUEVO: persistir también la FK al catálogo unificado en la tabla principal.
        if ubicacion_obj is not None:
            expediente.ubicacion = ubicacion_obj
            campos.append('ubicacion')
        expediente.save(update_fields=campos)
        return nombre_ubicacion
    except Exception as e:
        log_warning(f"No se pudo actualizar localizacion del expediente #{expediente.numero}: {e}", app=LogApp.S_EXP)
        return nombre_ubicacion


def _set_ubicacion_admision(expediente, usuario_admin, ubicacion_obj=None):
    """
    Devuelve la ubicación del expediente a 'ADMISION' tras una DEVOLUCIÓN.

    NUEVO (catálogo unificado): si se pasa ubicacion_obj (la fila ADMISION de
    ExpedienteUbicacion), se guarda en expediente.ubicacion (FK por id).

    LEGACY: además sincroniza expediente.localizacion (texto) a 'ADMISION'
    mientras dura la transición. El módulo s_exp ya NO usa 'ARCHIVO'.

    Args:
        expediente: instancia de Expediente
        usuario_admin: usuario que recibe la devolución
        ubicacion_obj: fila ADMISION de ExpedienteUbicacion o None

    Returns:
        str: "ADMISION"
    """
    from expediente.models import Localizacion

    try:
        loc_obj = Localizacion.objects.filter(
            descripcion_localizacion__iexact='ADMISION'
        ).first()
        if not loc_obj:
            loc_obj, _ = Localizacion.objects.get_or_create(
                descripcion_localizacion='ADMISION',
                defaults={'estado': True}
            )
        expediente.localizacion = loc_obj
        expediente.modificado_por = usuario_admin
        campos = ['localizacion', 'modificado_por', 'fecha_modificado']
        # NUEVO: persistir también la FK al catálogo unificado en la tabla principal.
        if ubicacion_obj is not None:
            expediente.ubicacion = ubicacion_obj
            campos.append('ubicacion')
        expediente.save(update_fields=campos)
    except Exception as e:
        log_warning(f"No se pudo regresar a ADMISION el expediente #{expediente.numero}: {e}", app=LogApp.S_EXP)

    return 'ADMISION'


# ============================================
# MIXIN: Acceso basado en Groups
# ============================================
class SExpAdminMixin(LoginRequiredMixin):
    """Acceso solo para administradores del módulo."""
    def dispatch(self, request, *args, **kwargs):
        if not _es_exp_admin(request.user):
            return redirect('acceso_denegado')
        return super().dispatch(request, *args, **kwargs)


class SExpUsuarioMixin(LoginRequiredMixin):
    """Acceso para cualquier usuario con acceso al módulo (Solicitantes + Admin)."""
    def dispatch(self, request, *args, **kwargs):
        if not _es_exp_solicitante(request.user):
            return redirect('acceso_denegado')
        return super().dispatch(request, *args, **kwargs)

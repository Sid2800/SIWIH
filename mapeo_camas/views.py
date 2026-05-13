from datetime import datetime, timedelta
import json 
from collections import defaultdict
from functools import lru_cache

from django.contrib.auth.decorators import login_required
from usuario.permisos import verificar_permisos_usuario
from core.constants.permisos import (
    MAPEO_CAMAS_EDITOR_ROLES,
    MAPEO_CAMAS_EDITOR_UNIDADES,
    MAPEO_CAMAS_HISTORIALES_ROLES,
    MAPEO_CAMAS_HISTORIALES_UNIDADES,
    MAPEO_CAMAS_VISUALIZACION_ROLES,
    MAPEO_CAMAS_VISUALIZACION_UNIDADES,
)
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q, Subquery
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView
from ingreso.models import Ingreso
from core.services.mapeo_camas_service import MapeoCamasService
from core.mixins import UnidadRolRequiredMixin
from usuario.models import PerfilUnidad, AlcanceUsuario


from mapeo_camas.models import (
    AsignacionCamaPaciente,
    DetalleMapeoCama,
    EstadoMapeo,
    HistorialEstadoCama,
    MapeoSesionCama,
    MapeoSesionServicio,
    MovimientoCama,
)
from paciente.models import Paciente
from servicio.models import Cama, Cubiculo, Sala, Servicio


# =============================================================================
# Constantes de configuración operativa
# -----------------------------------------------------------------------------
# MAX_CAMBIOS_CAMA: número máximo de movimientos permitidos por sala dentro
# de la ventana temporal, para usuarios que no son superadmin.
# VENTANA_LIMITE_CAMBIOS_SALA_HORAS: tamaño de la ventana de tiempo (horas)
# que se usa para contabilizar los cambios manuales y resetear el conteo.
# Las constantes OBSERVACION_* son los textos fijos grabados en el historial,
# usados también como criterio de filtrado al contar cambios por sala.
# =============================================================================
MAX_CAMBIOS_CAMA = 5
# Parametro de ventana para reinicio del limite por sala (horas)
VENTANA_LIMITE_CAMBIOS_SALA_HORAS = 24
# Ventana para considerar altas recientes en el buscador de pacientes del mapa.
VENTANA_ALTAS_RECIENTES_HORAS = 24
OBSERVACION_CAMBIO_MANUAL_MAPA = "Cambio manual desde mapa"
OBSERVACION_CAMBIO_MANUAL_MAPA_DETALLE = "Cambio manual desde mapa (detalle)"
OBSERVACION_MOVIMIENTO_PACIENTE_MAPA = "Movimiento de paciente entre camas (mapa)"
OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_DETALLE = "Movimiento de paciente entre camas (mapa detalle)"
# Observacion para traslados de superadmin: queda registrado pero NO cuenta
# en _contar_cambios_manual_por_sala, por lo que no descuenta del límite.
OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_SUPERADMIN = "Movimiento de paciente entre camas (superadmin)"


# --- Helpers de serialización robustos para el mapa de camas ---
# [2026-05-07] Helper para serializar datos de paciente
def _paciente_payload_v2(paciente):
    if not paciente:
        return None
    return {
        "id": paciente.id,
        "nombre": str(paciente),
        "dni": getattr(paciente, "dni", "") or ""
    }

# [2026-05-07] Helper para serializar datos de cama con asignación actual
def _cama_payload(cama, asig, cambios_realizados, max_cambios, meta_actualizacion):
    return {
        "numero_cama": cama.numero_cama,
        "estado_visual": asig.estado.codigo if (asig and asig.estado) else "SIN_ASIGNACION",
        "asignacion_estado": asig.estado.codigo if (asig and asig.estado) else "SIN_ASIGNACION",
        "paciente": _paciente_payload_v2(asig.paciente) if asig else None,
        "cambios_realizados": cambios_realizados,
        "max_cambios": max_cambios,
        "ultima_actualizacion": meta_actualizacion.get("ultima_actualizacion", ""),
        "usuario_ultima_actualizacion": meta_actualizacion.get("usuario_ultima_actualizacion", ""),
    }

# [2026-05-07] Helper para serializar datos de cubículo
def _cubiculo_payload(cubiculo, camas_data):
    return {
        "id": cubiculo.id,
        "numero": cubiculo.numero,
        "nombre": cubiculo.nombre_cubiculo,
        "camas": camas_data,
    }

# [2026-05-07] Helper para serializar datos de sala
def _sala_payload(sala, cubiculos_data, camas_directas_data):
    return {
        "id": sala.id,
        "nombre": sala.nombre_sala,
        "nombre_corto": sala.nombre_corto_sala,
        "cubiculos": cubiculos_data,
        "camas_directas": camas_directas_data,
    }

# [2026-05-07] Helper para serializar datos de servicio
def _servicio_payload(servicio, salas_data):
    return {
        "id": servicio.id,
        "nombre": servicio.nombre_servicio,
        "nombre_corto": getattr(servicio, "nombre_corto", ""),
        "salas": salas_data,
    }

# Helper global para obtener instancias de EstadoMapeo
@lru_cache(maxsize=64)
# [2026-05-07] Helper para obtener instancia de EstadoMapeo por código y categoría
def get_estado_mapeo(codigo, categoria):
    return EstadoMapeo.objects.get(codigo=codigo, categoria=categoria)
# =============================================================================
# [2026-05-07] API: Sincronizar camas con ingresos activos (solo admin ADMI)
# =============================================================================
@login_required
def sincronizar_camas_superadmin(request):
    """
    Sincroniza AsignacionCamaPaciente para todos los ingresos activos con cama asignada.
    Solo accesible para administradores de ADMI.
    """
    # [2026-05-08] Solo editores (admin/digitador de ADMI) pueden sincronizar
    if not verificar_permisos_usuario(request.user, MAPEO_CAMAS_EDITOR_ROLES, MAPEO_CAMAS_EDITOR_UNIDADES):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Solo se permite POST."}, status=405)

    # Obtener el ÚLTIMO ingreso activo POR CAMA (más reciente para cada cama)
    from django.db.models import Max
    
    camas_ultimos_ingresos = (
        Ingreso.objects.filter(
            estado=1,
            fecha_egreso__isnull=True,
            cama_id__isnull=False,
            paciente_id__isnull=False,
        )
        .values("cama_id")
        .annotate(ingreso_id=Max("id"))
        .values_list("ingreso_id", flat=True)
    )
    
    ingresos = Ingreso.objects.filter(pk__in=camas_ultimos_ingresos).values(
        "id", "cama_id", "paciente_id"
    )
    
    if not ingresos.exists():
        return JsonResponse({"ok": True, "mensaje": "No hay ingresos activos con cama asignada."})

    from mapeo_camas.models import AsignacionCamaPaciente
    estado_ocupada = get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
    ocupadas = set(
        AsignacionCamaPaciente.objects.filter(
            estado=estado_ocupada
        ).values_list("cama_id", flat=True)
    )

    sincronizados = 0
    omitidos = 0
    errores = 0
    errores_detalle = []

    for ingreso in ingresos:
        cama_id = ingreso["cama_id"]
        paciente_id = ingreso["paciente_id"]
        ingreso_id = ingreso["id"]
        if cama_id in ocupadas:
            omitidos += 1
            continue
        try:
            MapeoCamasService.sincronizar_cama_con_ingreso(
                cama_id=cama_id,
                paciente_id=paciente_id,
                usuario=request.user,
            )
            ocupadas.add(cama_id)
            sincronizados += 1
        except Exception as exc:
            errores += 1
            errores_detalle.append(f"Ingreso #{ingreso_id} — cama #{cama_id}: {exc}")

    return JsonResponse({
        "ok": True,
        "sincronizados": sincronizados,
        "omitidos": omitidos,
        "errores": errores,
        "errores_detalle": errores_detalle,
        "mensaje": f"Sincronización finalizada. {sincronizados} sincronizados, {omitidos} omitidos, {errores} errores."
    })

# =============================================================================
# MapeoCamasMapaView
# -----------------------------------------------------------------------------
# Vista de tipo TemplateView que únicamente renderiza el HTML base del mapa.
# No lleva datos de camas en el contexto: la estructura completa se obtiene
# después vía la API mapa_camas_data (llamada desde JavaScript al cargar la página).
# =============================================================================
# [2026-05-07] Vista: Página principal del mapa de camas con sesión de mapeo
# [2026-05-11] Permisos manejados localmente en mapeo_camas para no afectar mixins globales
class MapeoCamasMapaView(UnidadRolRequiredMixin, TemplateView):
    template_name = "mapeo_camas/mapa.html"
    required_roles = MAPEO_CAMAS_VISUALIZACION_ROLES
    required_unidades = MAPEO_CAMAS_VISUALIZACION_UNIDADES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Mapa de Camas"
        context["subtitulo"] = "Asignacion por paciente y estado de cama"
        # [2026-05-04 FEATURE] Sesion activa de OTRO usuario (para mostrar advertencia a los demas).
        # Banner rojo con nombre del usuario aparece si otro usuario tiene mapeo activo.
        context["sesion_ajena"] = (
            MapeoSesionCama.objects.select_related("usuario")
            .filter(
                estado=get_estado_mapeo("EN_PROGRESO", "ESTADO_SESION"),
                fecha_fin__isnull=True,
            )
            .exclude(usuario=self.request.user)
            .order_by("-fecha_inicio")
            .first()
        )
        # [2026-05-08] Indica si el usuario tiene permisos de edición sobre el mapa.
        # Se usa en el template para inyectar window.MAPA_SOLO_LECTURA al JS.
        context["es_editor"] = verificar_permisos_usuario(
            self.request.user, MAPEO_CAMAS_EDITOR_ROLES, MAPEO_CAMAS_EDITOR_UNIDADES
        )
        return context


# [2026-05-07] Vista: Página de historiales con permiso restringido por rol/unidad
# [2026-05-11] Permisos manejados localmente en mapeo_camas para no afectar mixins globales
class MapeoCamasHistorialView(UnidadRolRequiredMixin, TemplateView):
    template_name = "mapeo_camas/historiales.html"
    required_roles = MAPEO_CAMAS_HISTORIALES_ROLES
    required_unidades = MAPEO_CAMAS_HISTORIALES_UNIDADES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Historiales de Camas"
        context["subtitulo"] = "Consulta de historial, movimientos y mapeos"
        return context


# [2026-05-07] Vista: Página de detalle de historiales con permiso restringido
# [2026-05-11] Permisos manejados localmente en mapeo_camas para no afectar mixins globales
class MapeoCamasHistorialDetalleView(UnidadRolRequiredMixin, TemplateView):
    template_name = "mapeo_camas/historiales_detalle.html"
    required_roles = MAPEO_CAMAS_HISTORIALES_ROLES
    required_unidades = MAPEO_CAMAS_HISTORIALES_UNIDADES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Detalle de Historial"
        context["subtitulo"] = "Cards de detalle por registro"
        return context


@login_required
@require_GET
def debug_permisos_mapa(request):
    """Diagnostico en vivo de permisos para la vista principal del mapa."""
    usuario = request.user
    perfiles = list(
        PerfilUnidad.objects.filter(usuario=usuario)
        .select_related("servicio_unidad")
        .values(
            "rol",
            "alcance",
            "servicio_unidad__nombre_corto_unidad",
            "servicio_unidad__nombre_unidad",
        )
    )

    match_global = PerfilUnidad.objects.filter(
        usuario=usuario,
        rol__in=MAPEO_CAMAS_VISUALIZACION_ROLES,
        alcance=AlcanceUsuario.GLOBAL,
    ).exists()

    match_unidad = PerfilUnidad.objects.filter(
        usuario=usuario,
        rol__in=MAPEO_CAMAS_VISUALIZACION_ROLES,
        alcance=AlcanceUsuario.UNIDAD,
        servicio_unidad__nombre_corto_unidad__in=MAPEO_CAMAS_VISUALIZACION_UNIDADES,
    ).exists()

    return JsonResponse(
        {
            "ok": True,
            "usuario": {
                "id": usuario.id,
                "username": usuario.username,
                "is_authenticated": usuario.is_authenticated,
                "is_active": usuario.is_active,
                "is_superuser": usuario.is_superuser,
            },
            "requerido_mapa": {
                "roles": MAPEO_CAMAS_VISUALIZACION_ROLES,
                "unidades": MAPEO_CAMAS_VISUALIZACION_UNIDADES,
            },
            "perfiles": perfiles,
            "evaluacion": {
                "verificar_permisos_usuario": verificar_permisos_usuario(
                    usuario,
                    MAPEO_CAMAS_VISUALIZACION_ROLES,
                    MAPEO_CAMAS_VISUALIZACION_UNIDADES,
                ),
                "mixin_global": match_global,
                "mixin_unidad": match_unidad,
                "mixin_resultado": bool(usuario.is_superuser or match_global or match_unidad),
            },
        }
    )


# --- Helpers privados --------------------------------------------------------

# [2026-05-07] Helper para obtener nombre completo de paciente
def _nombre_paciente(paciente):
    """Construye el nombre completo del paciente concatenando los cuatro campos.
    Retorna 'Sin nombre' si todos están vacíos."""
    partes = [
        getattr(paciente, "primer_nombre", ""),
        getattr(paciente, "segundo_nombre", ""),
        getattr(paciente, "primer_apellido", ""),
        getattr(paciente, "segundo_apellido", ""),
    ]
    nombre = " ".join([p for p in partes if p]).strip()
    return nombre or "Sin nombre"


# [2026-05-07] Helper para obtener nombre completo de usuario
def _nombre_usuario(usuario):
    """Retorna nombre visible del usuario; usa username como fallback."""
    if not usuario:
        return ""
    nombre = ""
    if hasattr(usuario, "get_full_name"):
        nombre = (usuario.get_full_name() or "").strip()
    return nombre or getattr(usuario, "username", "") or ""


# [2026-05-07] Helper para convertir datetime a ISO local
def _hora_local_iso(dt):
    """Convierte datetime a ISO local para consumo del frontend."""
    if not dt:
        return ""
    return timezone.localtime(dt).isoformat()


# [2026-05-07] Helper para extraer código de estado visual de asignación
def _estado_visual(asignacion):
    """Devuelve el estado de la asignación para mostrarlo en el mapa.
    Si la cama no tiene asignación registrada, retorna 'SIN_ASIGNACION'."""
    if not asignacion or not asignacion.estado:
        return "SIN_ASIGNACION"
    return asignacion.estado.codigo


# [2026-05-07] Helper para serializar datos de paciente en historiales
def _paciente_payload(paciente):
    """Serializa los datos mínimos del paciente para el JSON del mapa.
    Retorna None si no hay paciente (cama vacía)."""
    if not paciente:
        return None
    return {
        "id": paciente.id,
        "nombre": _nombre_paciente(paciente),
        "dni": getattr(paciente, "dni", None) or "",
    }


# [2026-05-07] Helper para verificar si usuario es superadmin
def _es_superadmin(usuario):
    """Indica si el usuario es superadmin, lo que exime del límite de cambios."""
    return bool(usuario and usuario.is_superuser)


# [2026-05-07] Helper para calcular inicio de ventana de límite de movimientos
def _inicio_ventana_limite_sala():
    """Calcula el datetime de inicio de la ventana temporal para el conteo de cambios."""
    return timezone.now() - timedelta(hours=VENTANA_LIMITE_CAMBIOS_SALA_HORAS)


# [2026-05-07] Helper para contar movimientos manuales recientes por sala
def _contar_cambios_manual_por_sala(sala_id):
    """Cuenta cuántos movimientos de paciente se han registrado en la sala
    dentro de la ventana temporal activa. Se usa para aplicar el límite
    MAX_CAMBIOS_CAMA a usuarios no superadmin."""
    if not sala_id:
        return 0

    return HistorialEstadoCama.objects.filter(
        cama__sala_id=sala_id,
        observacion=OBSERVACION_MOVIMIENTO_PACIENTE_MAPA,
        fecha_hora__gte=_inicio_ventana_limite_sala(),
    ).count()


# [2026-05-07] Helper para obtener sesión de mapeo activa del usuario
def _obtener_sesion_mapeo_activa(usuario):
    """Retorna la sesion EN_PROGRESO activa mas reciente del usuario."""
    return (
        MapeoSesionCama.objects.filter(
            usuario=usuario,
            estado=get_estado_mapeo("EN_PROGRESO", "ESTADO_SESION"),
            fecha_fin__isnull=True,
        )
        .order_by("-fecha_inicio")
        .first()
    )


# [2026-05-07] Helper para obtener IDs de servicios en sesión de mapeo
def _obtener_servicios_ids_sesion(sesion):
    """Retorna los ids de servicio incluidos en la sesion de mapeo."""
    if not sesion:
        return []
    return list(
        sesion.servicios_incluidos.order_by("servicio_id").values_list("servicio_id", flat=True)
    )


# [2026-05-07] Helper para obtener ubicación descriptiva de cama
def _ubicacion_cama(cama):
    """Construye una etiqueta compacta de ubicacion: servicio/sala/modulo."""
    servicio = getattr(getattr(cama, "sala", None), "servicio", None)
    sala_nombre = getattr(getattr(cama, "sala", None), "nombre_sala", "") or "SIN_SALA"
    servicio_nombre = getattr(servicio, "nombre_servicio", "") or "SIN_SERVICIO"
    modulo_nombre = getattr(getattr(cama, "cubiculo", None), "nombre_cubiculo", "") or "SIN_MODULO"
    return f"{servicio_nombre}/{sala_nombre}/{modulo_nombre}"


# [2026-05-07] Helper para registrar detalle de mapeo (auditoría)
def _registrar_detalle_mapeo(
    *,
    usuario,
    cama,
    asignacion,
    tipo_accion,
    hubo_cambio,
    observacion="",
    fue_validada=True,
    sesion_mapeo=None,
):
    """Guarda el detalle por cama en tiempo real dentro de la sesion activa."""
    sesion = sesion_mapeo or _obtener_sesion_mapeo_activa(usuario)
    if not sesion:
        return None

    # [2026-05-04 AUDIT] Bug Fix: Convertir string de tipo_accion a objeto FK EstadoMapeo.
    # tipo_accion puede ser un string (codigo) o un objeto EstadoMapeo.
    # codigo es unique en la tabla, por lo que no se necesita filtrar por categoria.
    if isinstance(tipo_accion, str):
        tipo_accion = EstadoMapeo.objects.get(codigo=tipo_accion)

    return DetalleMapeoCama.objects.create(
        sesion_mapeo=sesion,
        cama=cama,
        fue_validada=fue_validada,
        hubo_cambio=hubo_cambio,
        estado_actual=asignacion.estado if asignacion else None,
        paciente_actual=asignacion.paciente if asignacion else None,
        tipo_accion=tipo_accion,
        usuario=usuario,
        observacion=observacion or "",
    )


# [2026-05-07] Helper para obtener IDs de camas mapeadas en sesión
def _camas_mapeadas_sesion(sesion):
    """Retorna ids de camas ya mapeadas en la sesion."""
    if not sesion:
        return []
    return list(
        DetalleMapeoCama.objects.filter(sesion_mapeo=sesion)
        .values_list("cama__numero_cama", flat=True)
        .distinct()
    )


def _meta_ultima_actualizacion(historial):
    """Serializa metadatos de la ultima actualizacion de una cama."""
    if not historial:
        return {
            "ultima_actualizacion": "",
            "usuario_ultima_actualizacion": "",
        }
    return {
        "ultima_actualizacion": _hora_local_iso(historial.fecha_hora),
        "usuario_ultima_actualizacion": _nombre_usuario(historial.usuario),
    }


def _parse_fecha_filtro(fecha_texto, fin_del_dia=False):
    """Convierte fecha YYYY-MM-DD a datetime aware en zona local."""
    if not fecha_texto:
        return None
    try:
        fecha = datetime.strptime(fecha_texto, "%Y-%m-%d")
    except ValueError:
        return None
    if fin_del_dia:
        fecha = fecha.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        fecha = fecha.replace(hour=0, minute=0, second=0, microsecond=0)
    return timezone.make_aware(fecha, timezone.get_current_timezone())


def _nombre_cama(cama):
    if not cama:
        return ""
    return str(getattr(cama, "numero_cama", "") or "")


def _ubicacion_desde_cama(cama):
    if not cama:
        return ""
    sala = getattr(cama, "sala", None)
    servicio = getattr(sala, "servicio", None)
    cubiculo = getattr(cama, "cubiculo", None)
    servicio_nombre = getattr(servicio, "nombre_servicio", "") or ""
    sala_nombre = getattr(sala, "nombre_sala", "") or ""
    cubiculo_nombre = getattr(cubiculo, "nombre_cubiculo", "") or "SIN_CUBICULO"
    return f"{servicio_nombre} / {sala_nombre} / {cubiculo_nombre}"


def _estado_css_mapa(estado):
    """Mapea estado de cama a clase visual usada en el mapa."""
    valor = (getattr(estado, "codigo", estado) or "").strip().upper()
    if valor == "VACIA":
        return "mapa-cama--vacia"
    if valor == "OCUPADA":
        return "mapa-cama--ocupada"
    if valor == "ALTA":
        return "mapa-cama--alta"
    if valor == "FUERA_SERVICIO":
        return "mapa-cama--fuera-servicio"
    if valor == "CONSULTA_EXTERNA":
        return "mapa-cama--consulta-externa"
    return "mapa-cama--sin-asignacion"


# [2026-05-07] API: Obtener catálogo de camas para filtros de historiales
@login_required
@require_GET
def historiales_camas_filtro(request):
    if not verificar_permisos_usuario(request.user, MAPEO_CAMAS_HISTORIALES_ROLES, MAPEO_CAMAS_HISTORIALES_UNIDADES):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)
    """Retorna catálogo de camas para el select de filtros."""
    camas = (
        Cama.objects.filter(estado=1)
        .select_related("sala__servicio", "cubiculo")
        .order_by("numero_cama")
    )
    data = []
    for cama in camas:
        data.append(
            {
                "id": str(cama.numero_cama),
                "numero_cama": str(cama.numero_cama),
                "ubicacion": _ubicacion_desde_cama(cama),
            }
        )
    return JsonResponse({"ok": True, "results": data})


# [2026-05-07] API: Obtener datos de registros en historiales filtrados
@login_required
@require_GET
def historiales_data(request):
    """Lista registros según tipo: mapeo, historial o movimiento."""
    if not verificar_permisos_usuario(request.user, MAPEO_CAMAS_HISTORIALES_ROLES, MAPEO_CAMAS_HISTORIALES_UNIDADES):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)
    tipo = (request.GET.get("tipo") or "mapeo").strip().lower()
    cama_id = (request.GET.get("cama_id") or "").strip()
    fecha_inicio = _parse_fecha_filtro(request.GET.get("fecha_inicio"), fin_del_dia=False)
    fecha_fin = _parse_fecha_filtro(request.GET.get("fecha_fin"), fin_del_dia=True)

    if tipo not in {"mapeo", "historial", "movimiento"}:
        return JsonResponse({"ok": False, "error": "Tipo de historial no valido."}, status=400)

    if tipo == "mapeo":
        sesiones = MapeoSesionCama.objects.select_related("usuario").prefetch_related(
            Prefetch(
                "servicios_incluidos",
                queryset=MapeoSesionServicio.objects.select_related("servicio").order_by("servicio__nombre_servicio"),
                to_attr="servicios_prefetch",
            )
        ).order_by("-fecha_inicio")
        if fecha_inicio:
            sesiones = sesiones.filter(fecha_inicio__gte=fecha_inicio)
        if fecha_fin:
            sesiones = sesiones.filter(fecha_inicio__lte=fecha_fin)

        sesiones = sesiones.annotate(
            total_detalles=Count("detalles", distinct=True),
            total_camas=Count("detalles__cama", distinct=True),
            total_cambios=Count("detalles", filter=Q(detalles__hubo_cambio=True), distinct=True),
        )[:200]

        results = []
        for sesion in sesiones:
            nombres_servicios = [
                ss.servicio.nombre_servicio
                for ss in getattr(sesion, "servicios_prefetch", [])
                if ss.servicio_id
            ]
            results.append(
                {
                    "id": sesion.id,
                    "referencia": f"Sesion {sesion.id}",
                    "tipo": "MAPEO",
                    "estado": sesion.estado.codigo if hasattr(sesion.estado, 'codigo') else str(sesion.estado),
                    "fecha_principal": _hora_local_iso(sesion.fecha_inicio),
                    "fecha_inicio": _hora_local_iso(sesion.fecha_inicio),
                    "fecha_fin": _hora_local_iso(sesion.fecha_fin),
                    "usuario": _nombre_usuario(sesion.usuario),
                    "detalle_1": f"Camas procesadas: {sesion.total_camas}",
                    "detalle_2": f"Cambios detectados: {sesion.total_cambios}",
                    "detalle_3": f"Registros detalle: {sesion.total_detalles}",
                    "servicios": nombres_servicios,
                }
            )
        return JsonResponse({"ok": True, "results": results})

    if tipo == "historial":
        historial_qs = HistorialEstadoCama.objects.select_related(
            "cama__sala__servicio", "cama__cubiculo", "paciente", "usuario"
        )
        if fecha_inicio:
            historial_qs = historial_qs.filter(fecha_hora__gte=fecha_inicio)
        if fecha_fin:
            historial_qs = historial_qs.filter(fecha_hora__lte=fecha_fin)
        if cama_id:
            historial_qs = historial_qs.filter(cama_id=cama_id)

        # Optimización: obtener solo el último evento por cama en DB,
        # evitando recorrer y ordenar en Python todo el historial filtrado.
        latest_id_por_cama = (
            historial_qs.filter(cama_id=OuterRef("cama_id"))
            .order_by("-fecha_hora", "-id")
            .values("id")[:1]
        )

        eventos_por_cama = {
            str(item["cama_id"]): item["total"]
            for item in historial_qs.values("cama_id").annotate(total=Count("id"))
        }

        ultimos_eventos = (
            historial_qs.filter(id=Subquery(latest_id_por_cama))
            .order_by("-fecha_hora", "-id")[:300]
        )

        results = []
        for item in ultimos_eventos:
            total_eventos = eventos_por_cama.get(str(item.cama_id), 0)
            paciente = _paciente_payload(item.paciente)
            results.append(
                {
                    "id": item.cama_id,
                    "referencia": f"Cama {_nombre_cama(item.cama)}",
                    "tipo": "HISTORIAL",
                    "estado": item.estado_nuevo.codigo if hasattr(item.estado_nuevo, 'codigo') else str(item.estado_nuevo),
                    "fecha_principal": _hora_local_iso(item.fecha_hora),
                    "fecha_inicio": _hora_local_iso(item.fecha_hora),
                    "fecha_fin": "",
                    "usuario": _nombre_usuario(item.usuario),
                    "detalle_1": f"Cama: {_nombre_cama(item.cama)}",
                    "detalle_2": f"Ultimo cambio: {(getattr(item.estado_anterior, 'codigo', item.estado_anterior) or 'SIN_ESTADO')} -> {getattr(item.estado_nuevo, 'codigo', item.estado_nuevo)}",
                    "detalle_3": f"Eventos: {total_eventos} | " + (
                        f"Paciente: {paciente['nombre']}" if paciente else "Paciente: Sin paciente"
                    ),
                }
            )
        return JsonResponse({"ok": True, "results": results})

    # [2026-05-05 FEATURE] Agrupa movimientos por cama para mostrar una fila por cama.
    # id = cama.pk → al abrir detalle se muestran todos los movimientos de esa cama.
    movimientos = (
        MovimientoCama.objects.select_related(
            "cama_origen__sala__servicio",
            "cama_origen__cubiculo",
            "cama_destino__sala__servicio",
            "cama_destino__cubiculo",
            "paciente",
            "usuario",
        )
        .order_by("-fecha_hora")
    )
    if fecha_inicio:
        movimientos = movimientos.filter(fecha_hora__gte=fecha_inicio)
    if fecha_fin:
        movimientos = movimientos.filter(fecha_hora__lte=fecha_fin)
    if cama_id:
        movimientos = movimientos.filter(Q(cama_origen_id=cama_id) | Q(cama_destino_id=cama_id))

    camas_map = {}
    for mov in movimientos[:500]:
        for cama in [mov.cama_origen, mov.cama_destino]:
            key = str(cama.pk)
            if key not in camas_map:
                camas_map[key] = {"cama": cama, "ultimo": mov, "total": 0}
            camas_map[key]["total"] += 1

    camas_ordenadas = sorted(
        camas_map.values(),
        key=lambda x: x["ultimo"].fecha_hora,
        reverse=True,
    )[:300]

    results = []
    for registro in camas_ordenadas:
        cama = registro["cama"]
        ultimo = registro["ultimo"]
        total = registro["total"]
        paciente = _paciente_payload(ultimo.paciente)
        results.append(
            {
                "id": cama.pk,
                "referencia": f"Cama {_nombre_cama(cama)}",
                "tipo": "MOVIMIENTO",
                "estado": f"{total} movimiento(s)",
                "fecha_principal": _hora_local_iso(ultimo.fecha_hora),
                "fecha_inicio": _hora_local_iso(ultimo.fecha_hora),
                "fecha_fin": "",
                "usuario": _nombre_usuario(ultimo.usuario),
                "detalle_1": f"Cama: {_nombre_cama(cama)}",
                "detalle_2": f"Total movimientos: {total}",
                "detalle_3": f"Ultimo paciente: {paciente['nombre']}" if paciente else "Sin paciente",
            }
        )
    return JsonResponse({"ok": True, "results": results})


# [2026-05-07] API: Obtener cards de detalle seg\u00fan tipo y registro
@login_required
@require_GET
def historiales_cards_data(request):
    """Devuelve cards de detalle según tipo seleccionado y registro."""
    if not verificar_permisos_usuario(request.user, MAPEO_CAMAS_HISTORIALES_ROLES, MAPEO_CAMAS_HISTORIALES_UNIDADES):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)
    tipo = (request.GET.get("tipo") or "").strip().lower()
    registro_id = (request.GET.get("id") or "").strip()

    if not registro_id:
        return JsonResponse({"ok": False, "error": "Debe indicar id."}, status=400)

    if tipo == "mapeo":
        sesion = MapeoSesionCama.objects.filter(pk=registro_id).first()
        if not sesion:
            return JsonResponse({"ok": False, "error": "Sesion no encontrada."}, status=404)

        # [2026-05-04 AUDIT] Bug Fix: Añadir select_related() para estado_actual y tipo_accion
        # para evitar serialización de objetos FK. Asegurar acceso a .codigo para serializar.
        detalles = (
            DetalleMapeoCama.objects.filter(sesion_mapeo=sesion)
            .select_related("cama__sala__servicio", "cama__cubiculo__sala__servicio", "paciente_actual", "usuario", "estado_actual", "tipo_accion")
            .order_by("cama__sala__nombre_sala", "cama__cubiculo__numero", "cama__numero_cama", "-fecha_hora")
        )
        cards = []
        servicios_map = {}
        # [2026-05-07] Deduplicar por cama dentro de cada cubículo/sala:
        # la consulta ordena por "-fecha_hora" por cama, así que el primer registro
        # por numero_cama es el más reciente. Se omiten los duplicados posteriores.
        camas_vistas_estructura = set()
        for item in detalles:
            paciente = _paciente_payload(item.paciente_actual)
            cama_numero = _nombre_cama(item.cama)
            cubiculo_obj = getattr(item.cama, "cubiculo", None)
            # [2026-05-07] Usar la sala del cubículo cuando existe, porque la FK sala
            # de la cama puede apuntar a una sala diferente (dato inconsistente en BD).
            sala_real = (cubiculo_obj.sala if cubiculo_obj else None) or getattr(item.cama, "sala", None)
            servicio_nombre = getattr(getattr(sala_real, "servicio", None), "nombre_servicio", "") or "SIN_SERVICIO"
            sala_nombre = getattr(sala_real, "nombre_sala", "") or "SIN_SALA"
            cubiculo_nombre = (f"#{cubiculo_obj.numero} {cubiculo_obj.nombre_cubiculo}") if cubiculo_obj else "SIN_CUBICULO"

            if servicio_nombre not in servicios_map:
                servicios_map[servicio_nombre] = {"nombre": servicio_nombre, "salas": {}}
            if sala_nombre not in servicios_map[servicio_nombre]["salas"]:
                servicios_map[servicio_nombre]["salas"][sala_nombre] = {
                    "nombre": sala_nombre,
                    "cubiculos": {},
                    "camas_directas": [],
                }

            # [2026-05-04 AUDIT] Access .codigo for serializable values (EstadoMapeo objects).
            cama_item = {
                "numero_cama": cama_numero,
                "estado": item.estado_actual.codigo if item.estado_actual else "",
                "paciente": paciente["nombre"] if paciente else "Sin paciente",
                "dni": paciente["dni"] if paciente else "",
                "usuario": _nombre_usuario(item.usuario),
                "fecha": _hora_local_iso(item.fecha_hora),
                "tipo_accion": item.tipo_accion.codigo if item.tipo_accion else "",
                "hubo_cambio": bool(item.hubo_cambio),
                "fue_validada": bool(item.fue_validada),
                "observacion": item.observacion or "",
            }

            # [2026-05-07] Solo agregar a la estructura si la cama no fue vista antes.
            clave_cama = (servicio_nombre, sala_nombre, cubiculo_nombre, cama_numero)
            if clave_cama not in camas_vistas_estructura:
                camas_vistas_estructura.add(clave_cama)
                if cubiculo_nombre == "SIN_CUBICULO":
                    servicios_map[servicio_nombre]["salas"][sala_nombre]["camas_directas"].append(cama_item)
                else:
                    cubiculos_map = servicios_map[servicio_nombre]["salas"][sala_nombre]["cubiculos"]
                    if cubiculo_nombre not in cubiculos_map:
                        cubiculos_map[cubiculo_nombre] = {
                            "nombre": cubiculo_nombre,
                            "camas": [],
                        }
                    cubiculos_map[cubiculo_nombre]["camas"].append(cama_item)

            cards.append(
                {
                    "titulo": f"Cama {item.cama_id}",
                    "subtitulo": item.tipo_accion.codigo if item.tipo_accion else "",
                    "estado": item.estado_actual.codigo if item.estado_actual else "",
                    "paciente": paciente["nombre"] if paciente else "Sin paciente",
                    "usuario": _nombre_usuario(item.usuario),
                    "fecha": _hora_local_iso(item.fecha_hora),
                    "detalle_1": f"Ubicacion: {_ubicacion_desde_cama(item.cama)}",
                    "detalle_2": f"Validada: {'SI' if item.fue_validada else 'NO'}",
                    "detalle_3": f"Hubo cambio: {'SI' if item.hubo_cambio else 'NO'}",
                    "observacion": item.observacion or "",
                }
            )

        estructura = []
        for servicio_data in servicios_map.values():
            salas_data = []
            for sala_data in servicio_data["salas"].values():
                cubiculos_data = list(sala_data["cubiculos"].values())
                salas_data.append(
                    {
                        "nombre": sala_data["nombre"],
                        "cubiculos": cubiculos_data,
                        "camas_directas": sala_data["camas_directas"],
                    }
                )
            estructura.append({"nombre": servicio_data["nombre"], "salas": salas_data})

        # [2026-05-08] Servicios incluidos en la sesión (para nota en detalle)
        servicios_sesion = [
            ss.servicio.nombre_servicio
            for ss in MapeoSesionServicio.objects.select_related("servicio")
            .filter(sesion_mapeo=sesion)
            .order_by("servicio__nombre_servicio")
        ]

        return JsonResponse({"ok": True, "cards": cards, "estructura": estructura, "servicios_sesion": servicios_sesion})

    if tipo == "historial":
        # [2026-05-05 FEATURE] Construye estructura servicio>sala>cubiculo igual que mapeo.
        # Cada evento del historial se convierte en un cama_item de la estructura.
        timeline_qs = (
            HistorialEstadoCama.objects.select_related(
                "cama__sala__servicio", "cama__cubiculo__sala__servicio",
                "estado_anterior", "estado_nuevo", "paciente", "usuario",
            )
            .filter(cama_id=registro_id)
            .order_by("cama__sala__nombre_sala", "cama__cubiculo__numero", "cama__numero_cama", "-fecha_hora")
        )
        if not timeline_qs.exists():
            return JsonResponse({"ok": False, "error": "Historial no encontrado para esta cama."}, status=404)

        servicios_map = {}
        for item in timeline_qs:
            paciente = _paciente_payload(item.paciente)
            estado_nuevo_codigo = item.estado_nuevo.codigo if hasattr(item.estado_nuevo, "codigo") else str(item.estado_nuevo)
            estado_anterior_codigo = (
                item.estado_anterior.codigo if hasattr(item.estado_anterior, "codigo") else str(item.estado_anterior)
            ) if item.estado_anterior else "SIN_ESTADO"

            cubiculo_obj = getattr(item.cama, "cubiculo", None)
            # [2026-05-07] Usar sala del cubículo cuando existe para evitar grupos duplicados.
            sala_real = (cubiculo_obj.sala if cubiculo_obj else None) or getattr(item.cama, "sala", None)
            servicio_nombre = getattr(getattr(sala_real, "servicio", None), "nombre_servicio", "") or "SIN_SERVICIO"
            sala_nombre = getattr(sala_real, "nombre_sala", "") or "SIN_SALA"
            cubiculo_nombre = (f"#{cubiculo_obj.numero} {cubiculo_obj.nombre_cubiculo}") if cubiculo_obj else "SIN_CUBICULO"

            if servicio_nombre not in servicios_map:
                servicios_map[servicio_nombre] = {"nombre": servicio_nombre, "salas": {}}
            if sala_nombre not in servicios_map[servicio_nombre]["salas"]:
                servicios_map[servicio_nombre]["salas"][sala_nombre] = {
                    "nombre": sala_nombre, "cubiculos": {}, "camas_directas": [],
                }

            cama_item = {
                "numero_cama": _nombre_cama(item.cama),
                "estado": estado_nuevo_codigo,
                "paciente": paciente["nombre"] if paciente else "Sin paciente",
                "dni": paciente["dni"] if paciente else "",
                "usuario": _nombre_usuario(item.usuario),
                "fecha": _hora_local_iso(item.fecha_hora),
                "tipo_accion": f"{estado_anterior_codigo} \u2192 {estado_nuevo_codigo}",
                "observacion": item.observacion or "",
            }

            if cubiculo_nombre == "SIN_CUBICULO":
                servicios_map[servicio_nombre]["salas"][sala_nombre]["camas_directas"].append(cama_item)
            else:
                cubiculos_map = servicios_map[servicio_nombre]["salas"][sala_nombre]["cubiculos"]
                if cubiculo_nombre not in cubiculos_map:
                    cubiculos_map[cubiculo_nombre] = {"nombre": cubiculo_nombre, "camas": []}
                cubiculos_map[cubiculo_nombre]["camas"].append(cama_item)

        estructura = []
        for servicio_data in servicios_map.values():
            salas_data = []
            for sala_data in servicio_data["salas"].values():
                salas_data.append({
                    "nombre": sala_data["nombre"],
                    "cubiculos": list(sala_data["cubiculos"].values()),
                    "camas_directas": sala_data["camas_directas"],
                })
            estructura.append({"nombre": servicio_data["nombre"], "salas": salas_data})

        return JsonResponse({"ok": True, "cards": [], "estructura": estructura})

    if tipo == "movimiento":
        # [2026-05-05 FEATURE] Recibe cama_id, muestra todos sus movimientos en estructura mapeo.
        # Cada movimiento = un cama_item con rol SALIDA/ENTRADA y la cama contraparte.
        movimientos_qs = (
            MovimientoCama.objects.select_related(
                "cama_origen__sala__servicio", "cama_origen__cubiculo__sala__servicio",
                "cama_destino__sala__servicio", "cama_destino__cubiculo__sala__servicio",
                "paciente", "usuario",
            )
            .filter(Q(cama_origen_id=registro_id) | Q(cama_destino_id=registro_id))
            .order_by("-fecha_hora")
        )
        if not movimientos_qs.exists():
            return JsonResponse({"ok": False, "error": "No se encontraron movimientos para esta cama."}, status=404)

        # Determinar la cama de referencia usando el primer movimiento
        primer_mov = movimientos_qs.first()
        cama_ref = (
            primer_mov.cama_origen
            if str(primer_mov.cama_origen_id) == str(registro_id)
            else primer_mov.cama_destino
        )

        cubiculo_obj_ref = getattr(cama_ref, "cubiculo", None)
        # [2026-05-07] Usar sala del cubículo cuando existe para evitar grupos duplicados.
        sala_real_ref = (cubiculo_obj_ref.sala if cubiculo_obj_ref else None) or getattr(cama_ref, "sala", None)
        servicio_nombre = getattr(getattr(sala_real_ref, "servicio", None), "nombre_servicio", "") or "SIN_SERVICIO"
        sala_nombre = getattr(sala_real_ref, "nombre_sala", "") or "SIN_SALA"
        cubiculo_nombre = (f"#{cubiculo_obj_ref.numero} {cubiculo_obj_ref.nombre_cubiculo}") if cubiculo_obj_ref else "SIN_CUBICULO"

        servicios_map = {
            servicio_nombre: {
                "nombre": servicio_nombre,
                "salas": {
                    sala_nombre: {
                        "nombre": sala_nombre, "cubiculos": {}, "camas_directas": [],
                    }
                },
            }
        }

        for mov in movimientos_qs:
            paciente = _paciente_payload(mov.paciente)
            tipo_mov = mov.tipo_movimiento.codigo if hasattr(mov.tipo_movimiento, "codigo") else str(mov.tipo_movimiento)
            es_origen = str(mov.cama_origen_id) == str(registro_id)
            otra_cama = mov.cama_destino if es_origen else mov.cama_origen
            rol = f"SALIDA \u2192 Cama {_nombre_cama(otra_cama)}" if es_origen else f"ENTRADA \u2190 Cama {_nombre_cama(otra_cama)}"

            cama_item = {
                "numero_cama": _nombre_cama(cama_ref),
                "estado": tipo_mov,
                "paciente": paciente["nombre"] if paciente else "Sin paciente",
                "dni": paciente["dni"] if paciente else "",
                "usuario": _nombre_usuario(mov.usuario),
                "fecha": _hora_local_iso(mov.fecha_hora),
                "tipo_accion": rol,
                "observacion": mov.observacion or "",
            }

            if cubiculo_nombre == "SIN_CUBICULO":
                servicios_map[servicio_nombre]["salas"][sala_nombre]["camas_directas"].append(cama_item)
            else:
                cubiculos_map = servicios_map[servicio_nombre]["salas"][sala_nombre]["cubiculos"]
                if cubiculo_nombre not in cubiculos_map:
                    cubiculos_map[cubiculo_nombre] = {"nombre": cubiculo_nombre, "camas": []}
                cubiculos_map[cubiculo_nombre]["camas"].append(cama_item)

        salas_data = []
        for sala_data in servicios_map[servicio_nombre]["salas"].values():
            salas_data.append({
                "nombre": sala_data["nombre"],
                "cubiculos": list(sala_data["cubiculos"].values()),
                "camas_directas": sala_data["camas_directas"],
            })
        estructura = [{"nombre": servicio_nombre, "salas": salas_data}]

        return JsonResponse({"ok": True, "cards": [], "estructura": estructura})

    return JsonResponse({"ok": False, "error": "Tipo no soportado."}, status=400)


# [2026-05-07] API: Iniciar nueva sesi\u00f3n de mapeo de camas
@login_required
@require_POST
def iniciar_mapeo(request):
    """Inicia una sesion de mapeo para el usuario actual."""
    if not verificar_permisos_usuario(request.user, MAPEO_CAMAS_EDITOR_ROLES, MAPEO_CAMAS_EDITOR_UNIDADES):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)
    sesion_activa = _obtener_sesion_mapeo_activa(request.user)
    if sesion_activa:
        servicios_ids = _obtener_servicios_ids_sesion(sesion_activa)
        return JsonResponse(
            {
                "ok": True,
                "sesion_id": sesion_activa.id,
                "estado": sesion_activa.estado.codigo if sesion_activa.estado else None,
                "hora_inicio": timezone.localtime(sesion_activa.fecha_inicio).isoformat(),
                "camas_mapeadas": _camas_mapeadas_sesion(sesion_activa),
                "servicio_ids": servicios_ids,
                "mensaje": "Ya existe una sesion de mapeo en progreso.",
            }
        )

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}

    servicio_ids = payload.get("servicio_ids") or []
    if not isinstance(servicio_ids, list):
        return JsonResponse({"ok": False, "error": "Debe indicar una lista valida de servicios."}, status=400)

    # [2026-05-07] El mapeo deja de ser global: la sesion ahora se inicia con servicios explicitamente seleccionados.
    servicios_ids_normalizados = []
    for servicio_id in servicio_ids:
        try:
            servicios_ids_normalizados.append(int(servicio_id))
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "La lista de servicios contiene valores invalidos."}, status=400)

    servicios_ids_normalizados = sorted(set(servicios_ids_normalizados))
    if not servicios_ids_normalizados:
        return JsonResponse({"ok": False, "error": "Debe seleccionar al menos un servicio para iniciar el mapeo."}, status=400)

    servicios_validos_ids = list(
        Servicio.objects.filter(estado=1, id__in=servicios_ids_normalizados)
        .order_by("id")
        .values_list("id", flat=True)
    )
    if len(servicios_validos_ids) != len(servicios_ids_normalizados):
        return JsonResponse({"ok": False, "error": "Uno o más servicios seleccionados no están disponibles."}, status=400)

    with transaction.atomic():
        sesion = MapeoSesionCama.objects.create(
            usuario=request.user,
            estado=get_estado_mapeo("EN_PROGRESO", "ESTADO_SESION"),
        )
        MapeoSesionServicio.objects.bulk_create([
            MapeoSesionServicio(sesion_mapeo=sesion, servicio_id=servicio_id)
            for servicio_id in servicios_validos_ids
        ])

    return JsonResponse(
        {
            "ok": True,
            "sesion_id": sesion.id,
            "estado": sesion.estado.codigo if sesion.estado else None,
            "hora_inicio": timezone.localtime(sesion.fecha_inicio).isoformat(),
            "camas_mapeadas": [],
            "servicio_ids": servicios_validos_ids,
            "mensaje": "Mapeo iniciado correctamente.",
        },
        status=201,
    )


# [2026-05-07] API: Obtener estado actual de sesión de mapeo activa
@login_required
@require_GET
def estado_mapeo(request):
    """Devuelve la sesion de mapeo activa y camas ya procesadas para restaurar UI."""
    sesion = _obtener_sesion_mapeo_activa(request.user)
    if not sesion:
        return JsonResponse({"ok": True, "sesion_activa": None, "camas_mapeadas": [], "servicio_ids": []})

    return JsonResponse(
        {
            "ok": True,
            "sesion_activa": {
                "id": sesion.id,
                "estado": sesion.estado.codigo if sesion.estado else None,
                "hora_inicio": timezone.localtime(sesion.fecha_inicio).isoformat(),
            },
            "camas_mapeadas": _camas_mapeadas_sesion(sesion),
            "servicio_ids": _obtener_servicios_ids_sesion(sesion),
        }
    )


# [2026-05-07] API: Terminar sesión de mapeo activa
# [2026-05-08] Requiere rol de editor (admin/digitador de ADMI)
@login_required
@require_POST
def terminar_mapeo(request):
    """Finaliza la sesion activa de mapeo del usuario."""
    if not verificar_permisos_usuario(request.user, MAPEO_CAMAS_EDITOR_ROLES, MAPEO_CAMAS_EDITOR_UNIDADES):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)
    sesion = _obtener_sesion_mapeo_activa(request.user)
    if not sesion:
        return JsonResponse({"ok": False, "error": "No hay una sesion de mapeo activa."}, status=400)

    # [2026-05-07] El alcance de cierre se calcula solo sobre los servicios ligados a la sesion activa.
    servicios_ids_sesion = _obtener_servicios_ids_sesion(sesion)
    total_camas_qs = Cama.objects.filter(
        sala__estado=1,
        sala__servicio__estado=1,
    ).filter(
        Q(cubiculo__isnull=True) | Q(cubiculo__estado=1)
    )
    if servicios_ids_sesion:
        total_camas_qs = total_camas_qs.filter(sala__servicio_id__in=servicios_ids_sesion)
    total_camas_objetivo = total_camas_qs.count()
    total_camas_mapeadas = (
        DetalleMapeoCama.objects.filter(sesion_mapeo=sesion)
        .values("cama_id")
        .distinct()
        .count()
    )

    if total_camas_mapeadas < total_camas_objetivo:
        faltantes = total_camas_objetivo - total_camas_mapeadas
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    f"No se puede finalizar el mapeo. Faltan {faltantes} cama(s) por procesar."
                ),
                "faltantes": faltantes,
                "total_camas": total_camas_objetivo,
                "camas_mapeadas": total_camas_mapeadas,
            },
            status=400,
        )

    sesion.estado = get_estado_mapeo("FINALIZADO", "ESTADO_SESION")
    sesion.fecha_fin = timezone.now()
    sesion.save(update_fields=["estado", "fecha_fin"])

    total_detalles = DetalleMapeoCama.objects.filter(sesion_mapeo=sesion).count()
    return JsonResponse(
        {
            "ok": True,
            "sesion_id": sesion.id,
            "estado": sesion.estado.codigo if hasattr(sesion.estado, 'codigo') else str(sesion.estado),
            "hora_fin": timezone.localtime(sesion.fecha_fin).isoformat(),
            "total_detalles": total_detalles,
            "mensaje": "Mapeo finalizado correctamente.",
        }
    )


# [2026-05-07] API: Cancelar sesión de mapeo activa
# [2026-05-08] Requiere rol de editor (admin/digitador de ADMI)
@login_required
@require_POST
def cancelar_mapeo(request):
    """Cancela la sesion activa de mapeo del usuario."""
    if not verificar_permisos_usuario(request.user, MAPEO_CAMAS_EDITOR_ROLES, MAPEO_CAMAS_EDITOR_UNIDADES):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)
    sesion = _obtener_sesion_mapeo_activa(request.user)
    if not sesion:
        return JsonResponse({"ok": False, "error": "No hay una sesion de mapeo activa."}, status=400)

    sesion.estado = get_estado_mapeo("CANCELADO", "ESTADO_SESION")
    sesion.fecha_fin = timezone.now()
    sesion.save(update_fields=["estado", "fecha_fin"])

    total_detalles = DetalleMapeoCama.objects.filter(sesion_mapeo=sesion).count()
    return JsonResponse(
        {
            "ok": True,
            "sesion_id": sesion.id,
            "estado": sesion.estado.codigo if hasattr(sesion.estado, 'codigo') else str(sesion.estado),
            "hora_fin": timezone.localtime(sesion.fecha_fin).isoformat(),
            "total_detalles": total_detalles,
            "mensaje": "Mapeo cancelado correctamente.",
        }
    )


# =============================================================================
# mapa_camas_data
# -----------------------------------------------------------------------------
# API GET que construye y retorna en JSON la estructura completa del mapa:
#   Servicio → Sala → Cubículo → Cama  (con estado visual y datos del paciente)
#                   → Camas directas  (camas sin cubículo asignado)
#
# La función no renderiza HTML: prepara exclusivamente un payload JSON para que
# el frontend pinte dinámicamente la estructura del mapa.
#
# Idea general del algoritmo:
# 1. Obtener la última asignación registrada por cama.
# 2. Calcular cuántos movimientos recientes tiene cada sala.
# 3. Cargar la jerarquía Servicio -> Sala -> Cubículo -> Cama usando prefetch.
# 4. Transformar esa jerarquía en listas/diccionarios serializables a JSON.
#
# La última asignación de cada cama determina su estado visual actual.
# También incluye el conteo de cambios recientes por sala para aplicar
# el límite de movimientos en el frontend.
# =============================================================================
# [2026-05-07] API: Obtener estructura completa de camas agrupadas por servicio/sala/cub\u00edculo
@login_required
def mapa_camas_data(request):
    sesion_activa = _obtener_sesion_mapeo_activa(request.user)
    servicios_ids_sesion = _obtener_servicios_ids_sesion(sesion_activa)

    # 1. Cargar todas las asignaciones históricas y quedarse solo con la más
    #    reciente por cama.
    #
    #    Se ordena por:
    #    - cama_id: para agrupar naturalmente las filas de una misma cama.
    #    - -fecha_inicio: para que la asignación más nueva quede primero.
    #    - -id: desempate final si hubiera dos registros con igual fecha.
    #
    #    Luego se recorre secuencialmente y se guarda solo la primera vez que
    #    aparece cada cama, construyendo un diccionario:
    #        { numero_cama: ultima_asignacion }
    #
    #    Este diccionario permite resolver en O(1) el estado actual de una cama
    #    al momento de armar el árbol del mapa.
    asignaciones = (
        AsignacionCamaPaciente.objects
        .select_related("paciente", "estado")
        .order_by("cama_id", "-fecha_inicio", "-id")
    )
    asignacion_por_cama = {}
    for asig in asignaciones.iterator(chunk_size=1000):
        if asig.cama_id not in asignacion_por_cama:
            asignacion_por_cama[asig.cama_id] = asig

    # 1.b. Obtener ultima actualizacion registrada por cama para mostrar
    #      hora y usuario responsable en cada card.
    historial_por_cama = {}
    historial_qs = (
        HistorialEstadoCama.objects
        .select_related("usuario")
        .order_by("cama_id", "-fecha_hora", "-id")
    )
    for historial in historial_qs.iterator(chunk_size=1000):
        if historial.cama_id not in historial_por_cama:
            historial_por_cama[historial.cama_id] = historial

    # 2. Calcular el número de movimientos manuales recientes por sala.
    #
    #    Este conteo se toma del historial y queda agrupado por cama__sala_id.
    #    El resultado final se transforma en otro diccionario:
    #        { sala_id: total_cambios }
    #
    #    Se usa después para dos cosas:
    #    - mostrar en cada cama cuántos cambios lleva la sala
    #    - permitir que el frontend informe el límite operativo disponible
    cambios_por_sala = {
        item["cama__sala_id"]: item["total"]
        for item in HistorialEstadoCama.objects.filter(
            observacion=OBSERVACION_MOVIMIENTO_PACIENTE_MAPA,
            fecha_hora__gte=_inicio_ventana_limite_sala(),
        )
        .values("cama__sala_id")
        .annotate(total=Count("id"))
    }

    # 3. Construcción eficiente de la jerarquía física del hospital.
    #
    #    Se separan dos tipos de camas:
    #    - camas_directas_qs: camas colgadas directamente de una sala.
    #    - camas_cubiculo_qs: camas que pertenecen a un cubículo.
    #
    #    Luego se encadenan prefetch_related para traer toda la estructura en
    #    memoria con el menor número posible de consultas:
    #    Servicio -> Salas -> Cubículos -> Camas
    #                      -> Camas directas
    #
    #    Esto evita el problema N+1 cuando más abajo se recorre cada servicio,
    #    cada sala y cada cubículo para construir el JSON final.
    camas_directas_qs = Cama.objects.filter(cubiculo__isnull=True).order_by("numero_cama")
    camas_cubiculo_qs = Cama.objects.order_by("numero_cama")

    cubiculos_qs = Cubiculo.objects.filter(estado=1).prefetch_related(
        Prefetch("camas", queryset=camas_cubiculo_qs)
    )

    salas_qs = (
        Sala.objects.filter(estado=1)
        .prefetch_related(
            Prefetch("cubiculos", queryset=cubiculos_qs),
            Prefetch("camas_sala", queryset=camas_directas_qs),
        )
        .order_by("nombre_sala")
    )

    servicios = Servicio.objects.filter(estado=1)
    if servicios_ids_sesion:
        # [2026-05-07] Durante un mapeo activo, el mapa se restringe a los servicios elegidos al iniciar la sesion.
        servicios = servicios.filter(id__in=servicios_ids_sesion)
    servicios = servicios.prefetch_related(
        Prefetch("salas_servicio", queryset=salas_qs)
    ).order_by("nombre_servicio")

    # 4. Transformar la jerarquía ORM en una estructura serializable a JSON.
    #
    #    Formato de salida esperado:
    #    {
    #        "servicios": [
    #            {
    #                "id": ...,
    #                "nombre": ...,
    #                "salas": [
    #                    {
    #                        "id": ...,
    #                        "cubiculos": [...],
    #                        "camas_directas": [...]
    #                    }
    #                ]
    #            }
    #        ]
    #    }
    #
    #    Cada cama expone:
    #    - numero_cama
    #    - estado_visual
    #    - asignacion_estado
    #    - paciente
    #    - cambios_realizados
    #    - max_cambios
    #
    #    Esto le evita al frontend tener que inferir relaciones o recalcular
    #    estados: el backend entrega el árbol listo para pintar.
    data = []
    for servicio in servicios:
        salas_data = []
        for sala in servicio.salas_servicio.all():
            cubiculos_data = []
            for cubiculo in sala.cubiculos.all():
                camas_data = []
                for cama in cubiculo.camas.all():
                    asig = asignacion_por_cama.get(cama.numero_cama)
                    meta_actualizacion = _meta_ultima_actualizacion(historial_por_cama.get(cama.numero_cama))
                    camas_data.append(_cama_payload(
                        cama,
                        asig,
                        cambios_por_sala.get(sala.id, 0),
                        MAX_CAMBIOS_CAMA,
                        meta_actualizacion
                    ))
                if camas_data:
                    cubiculos_data.append(_cubiculo_payload(cubiculo, camas_data))
            camas_directas_data = []
            for cama in sala.camas_sala.all():
                asig = asignacion_por_cama.get(cama.numero_cama)
                meta_actualizacion = _meta_ultima_actualizacion(historial_por_cama.get(cama.numero_cama))
                camas_directas_data.append(_cama_payload(
                    cama,
                    asig,
                    cambios_por_sala.get(sala.id, 0),
                    MAX_CAMBIOS_CAMA,
                    meta_actualizacion
                ))
            if cubiculos_data or camas_directas_data:
                salas_data.append(_sala_payload(sala, cubiculos_data, camas_directas_data))
        if salas_data:
            data.append(_servicio_payload(servicio, salas_data))
    return JsonResponse({"servicios": data})


# =============================================================================
# buscar_pacientes_mapa
# -----------------------------------------------------------------------------
# API GET de autocompletado. Busca pacientes activos que NO tienen una cama
# OCUPADA actualmente, para poder asignarlos desde el mapa.
#
# Regla de negocio:
# - Solo mostrar pacientes con ingreso activo sin cama asignada, o
# - pacientes con alta reciente.
# En ambos casos, se excluyen pacientes que mantengan ocupacion activa.
# Acepta el parámetro ?q= para filtrar por nombre o DNI.
# Retorna un máximo de 20 resultados.
# =============================================================================
# [2026-05-07] API: Buscar pacientes disponibles para asignar camas
@login_required
@require_GET
def buscar_pacientes_mapa(request):
    termino = (request.GET.get("q") or "").strip()
    tipo_busqueda = (request.GET.get("tipo") or "dni").strip().lower()

    # --- 1. Base: pacientes activos o pendientes; aplica filtro de texto primero
    #        (rápido: usa índices de la tabla paciente).
    pacientes_qs = Paciente.objects.filter(estado__in=["A", "P"])

    if termino:
        if tipo_busqueda == "dni":
            pacientes_qs = pacientes_qs.filter(dni__icontains=termino)
        elif tipo_busqueda == "nombre":
            pacientes_qs = pacientes_qs.filter(
                Q(primer_nombre__icontains=termino)
                | Q(segundo_nombre__icontains=termino)
                | Q(primer_apellido__icontains=termino)
                | Q(segundo_apellido__icontains=termino)
            )
        else:
            pacientes_qs = pacientes_qs.filter(
                Q(dni__icontains=termino)
                | Q(primer_nombre__icontains=termino)
                | Q(segundo_nombre__icontains=termino)
                | Q(primer_apellido__icontains=termino)
                | Q(segundo_apellido__icontains=termino)
            )

    # --- 2. Regla de negocio: excluir pacientes que ya tienen una cama OCUPADA.
    #        Evita duplicados en el mapa. Usa EXISTS para mayor rendimiento.
    ya_ocupando_cama = Exists(
        AsignacionCamaPaciente.objects.filter(
            paciente_id=OuterRef("pk"),
            estado__codigo="OCUPADA",
            estado__categoria="ESTADO_CAMA",
        )
    )
    pacientes_qs = pacientes_qs.exclude(ya_ocupando_cama)

    pacientes = pacientes_qs.order_by("primer_nombre", "primer_apellido")[:20]
    resultados = [_paciente_payload(p) for p in pacientes]
    return JsonResponse({"results": resultados})


# =============================================================================
# camas_disponibles_mapa
# -----------------------------------------------------------------------------
# API GET que retorna todas las camas en estado VACIA disponibles para
# recibir un traslado de paciente.
# Acepta el parámetro ?excluir= para omitir la cama origen del traslado
# y no ofrecerla como opción de destino.
# =============================================================================
# [2026-05-07] API: Obtener camas disponibles para traslado de pacientes
@login_required
@require_GET
def camas_disponibles_mapa(request):
    excluir_cama = request.GET.get("excluir") or None

    # Obtener el estado actual de cada cama tomando solo la asignación más reciente.
    asignaciones = AsignacionCamaPaciente.objects.order_by("cama_id", "-fecha_inicio", "-id")
    asignacion_por_cama = {}
    for asig in asignaciones:
        if asig.cama_id not in asignacion_por_cama:
            asignacion_por_cama[asig.cama_id] = asig

    todas_camas = (
        Cama.objects.filter(estado=1)
        .select_related("sala__servicio", "cubiculo")
        .order_by("sala__servicio__nombre_servicio", "sala__nombre_sala", "numero_cama")
    )

    resultados = []
    estado_vacia = get_estado_mapeo("VACIA", "ESTADO_CAMA")
    for cama in todas_camas:
        # Omitir la cama de origen para que no aparezca como destino disponible.
        if excluir_cama and str(cama.numero_cama) == str(excluir_cama):
            continue
        # [2026-05-04 AUDIT] Bug Fix: Usar cama.pk (PK real) como clave, no numero_cama.
        # Esto arregla el problema donde camas disponibles no se mostraban correctamente.
        asig = asignacion_por_cama.get(cama.pk)
        estado = asig.estado if asig else estado_vacia
        if getattr(estado, "codigo", estado) == "VACIA":
            resultados.append({
                "numero_cama": cama.numero_cama,
                "sala": cama.sala.nombre_sala,
                "servicio": cama.sala.servicio.nombre_servicio,
                "cubiculo": cama.cubiculo.nombre_cubiculo if cama.cubiculo else None,
            })

    return JsonResponse({"results": resultados})


# =============================================================================
# mover_paciente_cama
# -----------------------------------------------------------------------------
# API POST que ejecuta un traslado atómico de paciente entre camas.
# Flujo dentro de transaction.atomic():
#   1. Libera la cama origen (OCUPADA → VACIA, paciente = None).
#   2. Ocupa la cama destino (VACIA → OCUPADA, asigna el mismo paciente).
#   3. Registra un HistorialEstadoCama por cada cama afectada.
#   4. Crea un MovimientoCama con origen, destino y paciente.
# Para usuarios no superadmin verifica el límite de cambios por sala
# en la ventana temporal activa antes de ejecutar el movimiento.
# =============================================================================
# [2026-05-07] API: Realizar traslado de paciente entre camas
# [2026-05-08] Requiere rol de editor (admin/digitador de ADMI)
@login_required
@require_POST
def mover_paciente_cama(request):
    if not verificar_permisos_usuario(request.user, MAPEO_CAMAS_EDITOR_ROLES, MAPEO_CAMAS_EDITOR_UNIDADES):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)
    cama_origen_id = request.POST.get("cama_origen_id")
    cama_destino_id = request.POST.get("cama_destino_id")

    if not cama_origen_id or not cama_destino_id:
        return JsonResponse({"ok": False, "error": "Debe indicar la cama origen y la cama destino."}, status=400)

    if str(cama_origen_id) == str(cama_destino_id):
        return JsonResponse({"ok": False, "error": "La cama destino debe ser diferente a la cama origen."}, status=400)

    try:
        cama_origen = Cama.objects.select_related("sala__servicio", "cubiculo").get(pk=cama_origen_id)
        cama_destino = Cama.objects.select_related("sala__servicio", "cubiculo").get(pk=cama_destino_id)
    except Cama.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Una de las camas indicadas no existe."}, status=404)

    sala_origen_id = cama_origen.sala_id
    sala_destino_id = cama_destino.sala_id

    asig_origen = (
        AsignacionCamaPaciente.objects
        .filter(cama_id=cama_origen_id)
        .order_by("-fecha_inicio", "-id")
        .first()
    )
    asig_destino = (
        AsignacionCamaPaciente.objects
        .filter(cama_id=cama_destino_id)
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    estado_ocupada = get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
    estado_vacia = get_estado_mapeo("VACIA", "ESTADO_CAMA")

    if not asig_origen or asig_origen.estado is None or asig_origen.estado.codigo not in {"OCUPADA", "PRE_ALTA"}:
        return JsonResponse({"ok": False, "error": "La cama origen no tiene paciente asignado (debe estar OCUPADA o PRE_ALTA)."}, status=400)

    paciente = asig_origen.paciente
    if not paciente:
        return JsonResponse({"ok": False, "error": "La cama origen no tiene paciente asignado."}, status=400)

    if asig_destino and (asig_destino.estado is not None and asig_destino.estado.codigo != "VACIA"):
        return JsonResponse({"ok": False, "error": "La cama destino no esta disponible (no esta vacia)."}, status=400)

    if not _es_superadmin(request.user):
        cambios_sala_origen = _contar_cambios_manual_por_sala(sala_origen_id)
        if cambios_sala_origen >= MAX_CAMBIOS_CAMA:
            return JsonResponse(
                {
                    "ok": False,
                    "error": (
                        f"La sala de la cama origen ya alcanzo el maximo de {MAX_CAMBIOS_CAMA} cambios "
                        f"en las ultimas {VENTANA_LIMITE_CAMBIOS_SALA_HORAS} hora(s)."
                    ),
                },
                status=400,
            )

        if sala_destino_id != sala_origen_id:
            cambios_sala_destino = _contar_cambios_manual_por_sala(sala_destino_id)
            if cambios_sala_destino >= MAX_CAMBIOS_CAMA:
                return JsonResponse(
                    {
                        "ok": False,
                        "error": (
                            f"La sala de la cama destino ya alcanzo el maximo de {MAX_CAMBIOS_CAMA} cambios "
                            f"en las ultimas {VENTANA_LIMITE_CAMBIOS_SALA_HORAS} hora(s)."
                        ),
                    },
                    status=400,
                )

    estado_anterior_origen = asig_origen.estado
    estado_anterior_destino = asig_destino.estado if asig_destino else estado_vacia

    # Superadmin: el registro queda, pero con una observación distinta
    # para que _contar_cambios_manual_por_sala no lo cuente.
    es_superadmin = _es_superadmin(request.user)
    obs_origen = (
        OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_SUPERADMIN
        if es_superadmin
        else OBSERVACION_MOVIMIENTO_PACIENTE_MAPA
    )
    obs_destino = (
        OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_SUPERADMIN
        if es_superadmin
        else (
            OBSERVACION_MOVIMIENTO_PACIENTE_MAPA
            if sala_destino_id != sala_origen_id
            else OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_DETALLE
        )
    )

    with transaction.atomic():
        # 1. Liberar cama origen (OCUPADA -> VACIA)
        asig_origen.estado = estado_vacia
        asig_origen.paciente = None
        asig_origen.save()

        # 2. Ocupar cama destino (VACIA -> OCUPADA con el mismo paciente)
        if not asig_destino:
            asig_destino = AsignacionCamaPaciente(
                cama=cama_destino,
                estado=estado_ocupada,
                paciente=paciente,
                usuario_asignacion=request.user,
            )
        else:
            asig_destino.estado = estado_ocupada
            asig_destino.paciente = paciente
            asig_destino.usuario_asignacion = request.user
            asig_destino.fecha_fin = None
            asig_destino.usuario_cierre = None
        asig_destino.save()

        # 3. Registrar historial para ambas camas
        historial_origen = HistorialEstadoCama.objects.create(
            cama_id=cama_origen_id,
            estado_anterior=estado_anterior_origen,
            estado_nuevo=estado_vacia,
            paciente=None,
            usuario=request.user,
            observacion=obs_origen,
        )
        historial_destino = HistorialEstadoCama.objects.create(
            cama_id=cama_destino_id,
            estado_anterior=estado_anterior_destino,
            estado_nuevo=estado_ocupada,
            paciente=paciente,
            usuario=request.user,
            observacion=obs_destino,
        )

        MovimientoCama.objects.create(
            tipo_movimiento="TRASLADO",
            cama_origen_id=cama_origen_id,
            cama_destino_id=cama_destino_id,
            paciente=paciente,
            usuario=request.user,
            observacion="Movimiento desde mapa de camas",
        )

        # Registro en tiempo real por cama dentro de sesion de mapeo activa.
        _registrar_detalle_mapeo(
            usuario=request.user,
            cama=cama_origen,
            asignacion=asig_origen,
            tipo_accion=DetalleMapeoCama.TipoAccion.TRASLADO,
            hubo_cambio=True,
            observacion="Traslado de paciente desde mapa (cama origen).",
        )
        _registrar_detalle_mapeo(
            usuario=request.user,
            cama=cama_destino,
            asignacion=asig_destino,
            tipo_accion=DetalleMapeoCama.TipoAccion.TRASLADO,
            hubo_cambio=True,
            observacion="Traslado de paciente desde mapa (cama destino).",
        )

    cambios_origen_post = _contar_cambios_manual_por_sala(sala_origen_id)
    cambios_destino_post = _contar_cambios_manual_por_sala(sala_destino_id)

    return JsonResponse({
        "ok": True,
        "mensaje": f"Paciente movido a la cama {cama_destino_id} correctamente.",
        "cama_origen": {
            "numero_cama": int(cama_origen_id),
            "estado_visual": estado_vacia.codigo,
            "paciente": None,
            "cambios_realizados": cambios_origen_post,
            "max_cambios": MAX_CAMBIOS_CAMA,
            "ultima_actualizacion": _hora_local_iso(historial_origen.fecha_hora),
            "usuario_ultima_actualizacion": _nombre_usuario(historial_origen.usuario),
        },
        "cama_destino": {
            "numero_cama": int(cama_destino_id),
            "estado_visual": estado_ocupada.codigo,
            "paciente": _paciente_payload(paciente),
            "cambios_realizados": cambios_destino_post,
            "max_cambios": MAX_CAMBIOS_CAMA,
            "ultima_actualizacion": _hora_local_iso(historial_destino.fecha_hora),
            "usuario_ultima_actualizacion": _nombre_usuario(historial_destino.usuario),
        },
    })


# ===========================================================================
# actualizar_cama_mapa
# ---------------------------------------------------------------------------
# API POST para cambio manual de estado de una cama individual desde el mapa.
# Permite al usuario seleccionar cualquier estado válido y, si el estado
# es OCUPADA, también debe indicar el paciente a asignar.
# Si no existe asignación previa para la cama, la crea en estado VACIA
# antes de aplicar el cambio solicitado.
# Registra el cambio en HistorialEstadoCama con observación de cambio manual.
# ===========================================================================
# [2026-05-08] Requiere rol de editor (admin/digitador de ADMI)
@login_required
@require_POST
def actualizar_cama_mapa(request):
    if not verificar_permisos_usuario(request.user, MAPEO_CAMAS_EDITOR_ROLES, MAPEO_CAMAS_EDITOR_UNIDADES):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)
    cama_id = request.POST.get("cama_id")
    estado_codigo = (request.POST.get("estado") or "").strip()
    paciente_id = request.POST.get("paciente_id") or None

    if not cama_id:
        return JsonResponse({"ok": False, "error": "Debe indicar la cama."}, status=400)

    # Validar que el estado existe y pertenece a la categoría ESTADO_CAMA
    try:
        estado_nuevo_obj = EstadoMapeo.objects.get(codigo=estado_codigo, categoria="ESTADO_CAMA")
    except EstadoMapeo.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Estado de cama no válido."}, status=400)

    try:
        cama = Cama.objects.select_related("sala__servicio", "cubiculo").get(pk=cama_id)
    except Cama.DoesNotExist:
        return JsonResponse({"ok": False, "error": "La cama no existe."}, status=404)

    # Obtener la asignación actual (la más reciente)
    asignacion = (
        AsignacionCamaPaciente.objects.select_related("paciente", "estado")
        .filter(cama_id=cama_id)
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    # Si no existe asignación previa, crear una en estado VACIA
    if not asignacion:
        estado_vacia = EstadoMapeo.objects.get(codigo="VACIA", categoria="ESTADO_CAMA")
        asignacion = AsignacionCamaPaciente.objects.create(
            cama=cama,
            usuario_asignacion=request.user,
            estado=estado_vacia,
            paciente=None,
        )

    paciente_nuevo = None
    if paciente_id:
        try:
            paciente_nuevo = Paciente.objects.get(pk=paciente_id)
        except Paciente.DoesNotExist:
            return JsonResponse({"ok": False, "error": "El paciente seleccionado no existe."}, status=404)

    # Si el paciente ya tiene otra cama (OCUPADA o PRE_ALTA), detectar para liberar
    asig_previa_paciente = None
    if paciente_nuevo and estado_codigo == "OCUPADA":
        asig_previa_paciente = (
            AsignacionCamaPaciente.objects
            .select_related("estado", "cama")
            .filter(
                paciente=paciente_nuevo,
                estado__codigo__in=["OCUPADA", "PRE_ALTA"],
                estado__categoria="ESTADO_CAMA",
            )
            .exclude(cama_id=cama_id)
            .order_by("-fecha_inicio", "-id")
            .first()
        )

    # Validar que OCUPADA requiere paciente
    if estado_codigo == "OCUPADA" and not paciente_nuevo:
        return JsonResponse(
            {
                "ok": False,
                "error": "Para estado OCUPADA debe seleccionar un paciente.",
            },
            status=400,
        )

    estado_anterior = asignacion.estado
    paciente_anterior_id = asignacion.paciente_id
    paciente_anterior = asignacion.paciente
    estado_vacia = get_estado_mapeo("VACIA", "ESTADO_CAMA")
    estado_alta = get_estado_mapeo("ALTA", "ESTADO_CAMA")

    # Si la cama estaba en PRE_ALTA y se reasigna a OCUPADA con otro paciente,
    # se registra primero el cierre histórico de alta y la liberación lógica.
    requiere_cierre_prealta = (
        estado_anterior
        and estado_anterior.codigo == "PRE_ALTA"
        and estado_codigo == "OCUPADA"
        and paciente_anterior
        and (not paciente_nuevo or paciente_anterior.id != paciente_nuevo.id)
    )

    # Si la cama pasa a VACIA desde un estado con paciente, se registra alta.
    requiere_registro_alta_a_vacia = (
        estado_codigo == "VACIA"
        and paciente_anterior is not None
        and estado_anterior is not None
        and estado_anterior.codigo in {"OCUPADA", "PRE_ALTA", "ALTA"}
    )

    # Lógica de estados especiales
    if estado_codigo == "VACIA":
        paciente_nuevo = None
    elif estado_codigo in {"PRE_ALTA", "ALTA"} and paciente_nuevo is None:
        # PRE_ALTA y ALTA deben conservar el paciente actual
        # hasta que la cama pase a VACIA.
        paciente_nuevo = paciente_anterior

    # Verificar si hay cambio real
    hubo_cambio = (
        estado_anterior.id != estado_nuevo_obj.id
        or paciente_anterior_id != (paciente_nuevo.id if paciente_nuevo else None)
    )

    cambios_realizados = _contar_cambios_manual_por_sala(cama.sala_id)

    if not hubo_cambio:
        _registrar_detalle_mapeo(
            usuario=request.user,
            cama=cama,
            asignacion=asignacion,
            tipo_accion=DetalleMapeoCama.TipoAccion.CONFIRMACION,
            hubo_cambio=False,
            observacion="Confirmacion sin cambios desde mapa.",
        )
        return JsonResponse(
            {
                "ok": True,
                "mensaje": "No se detectaron cambios para guardar.",
                "cama": {
                    "numero_cama": int(cama_id),
                    "estado_visual": asignacion.estado.codigo,
                    "paciente": _paciente_payload(asignacion.paciente),
                    "cambios_realizados": cambios_realizados,
                    "max_cambios": MAX_CAMBIOS_CAMA,
                },
            }
        )

    try:
        with transaction.atomic():
            estado_historial_anterior = estado_anterior

            if requiere_cierre_prealta:
                HistorialEstadoCama.objects.create(
                    cama_id=cama_id,
                    estado_anterior=estado_anterior,
                    estado_nuevo=estado_alta,
                    paciente=paciente_anterior,
                    usuario=request.user,
                    observacion="Alta historica por reasignacion desde PRE_ALTA",
                )
                estado_historial_anterior = estado_vacia

            if requiere_registro_alta_a_vacia:
                HistorialEstadoCama.objects.create(
                    cama_id=cama_id,
                    estado_anterior=estado_anterior,
                    estado_nuevo=estado_alta,
                    paciente=paciente_anterior,
                    usuario=request.user,
                    observacion="Alta historica por cambio manual a VACIA",
                )
                estado_historial_anterior = estado_alta

            # Si el paciente ya tenía otra cama asignada, liberarla (cambio de cama)
            if asig_previa_paciente:
                estado_anterior_previa = asig_previa_paciente.estado
                asig_previa_paciente.estado = estado_vacia
                asig_previa_paciente.paciente = None
                asig_previa_paciente.save()

                HistorialEstadoCama.objects.create(
                    cama=asig_previa_paciente.cama,
                    estado_anterior=estado_anterior_previa,
                    estado_nuevo=estado_vacia,
                    paciente=None,
                    usuario=request.user,
                    observacion="Cambio de cama: paciente trasladado a otra cama",
                )

                MovimientoCama.objects.create(
                    tipo_movimiento="TRASLADO",
                    cama_origen=asig_previa_paciente.cama,
                    cama_destino=cama,
                    paciente=paciente_nuevo,
                    usuario=request.user,
                    observacion="Cambio de cama desde mapa",
                )

            # Aplicar cambios finales de la asignacion.
            asignacion.estado = estado_nuevo_obj
            asignacion.paciente = paciente_nuevo
            asignacion.usuario_asignacion = request.user
            asignacion.save()

            # Registrar historial final del cambio visible en cama.
            historial = HistorialEstadoCama.objects.create(
                cama_id=cama_id,
                estado_anterior=estado_historial_anterior,
                estado_nuevo=estado_nuevo_obj,
                paciente=asignacion.paciente,
                usuario=request.user,
                observacion=OBSERVACION_CAMBIO_MANUAL_MAPA,
            )
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    # Registrar detalle del mapeo
    _registrar_detalle_mapeo(
        usuario=request.user,
        cama=cama,
        asignacion=asignacion,
        tipo_accion=(
            DetalleMapeoCama.TipoAccion.ALTA
            if estado_codigo == "ALTA" or requiere_registro_alta_a_vacia
            else DetalleMapeoCama.TipoAccion.CAMBIO
        ),
        hubo_cambio=True,
        observacion="Actualización de cama desde mapa.",
    )

    cambios_realizados = _contar_cambios_manual_por_sala(cama.sala_id)
    return JsonResponse(
        {
            "ok": True,
            "mensaje": "Cambio de cama actualizado correctamente.",
            "cama": {
                "numero_cama": int(cama_id),
                "estado_visual": asignacion.estado.codigo,
                "paciente": _paciente_payload(asignacion.paciente),
                "cambios_realizados": cambios_realizados,
                "max_cambios": MAX_CAMBIOS_CAMA,
                "ultima_actualizacion": _hora_local_iso(historial.fecha_hora),
                "usuario_ultima_actualizacion": _nombre_usuario(historial.usuario),
            },
        }
    )


# [2026-05-07] API: Procesar acción de mapeo en cama (confirmar, alta, traslado, etc.)
# [2026-05-08] Requiere rol de editor (admin/digitador de ADMI)
@login_required
@require_POST
def procesar_cama_mapeo(request):
    """
    Ciclo principal de mapeo por cama:
    evaluar -> decidir -> ejecutar -> registrar.
    """
    if not verificar_permisos_usuario(request.user, MAPEO_CAMAS_EDITOR_ROLES, MAPEO_CAMAS_EDITOR_UNIDADES):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)
    cama_id = request.POST.get("cama_id")
    accion = (request.POST.get("accion") or "").strip().upper()
    observacion = (request.POST.get("observacion") or "").strip()
    paciente_observado_id = request.POST.get("paciente_observado_id") or None
    sesion_mapeo_id = request.POST.get("sesion_mapeo_id") or None

    if not cama_id:
        return JsonResponse({"ok": False, "error": "Debe indicar cama_id."}, status=400)

    acciones_validas = {
        "CONFIRMAR",
        "CONFIRMAR_ALTA",
        "CANCELAR_PREALTA",
        "CAMBIO_TRASLADO",
        "ASIGNACION",
        "ALTA_FORZADA",
    }
    if accion not in acciones_validas:
        return JsonResponse({"ok": False, "error": "Accion de mapeo no valida."}, status=400)

    try:
        cama = Cama.objects.select_related("sala__servicio", "cubiculo__sala__servicio").get(pk=cama_id)
    except Cama.DoesNotExist:
        return JsonResponse({"ok": False, "error": "La cama no existe."}, status=404)

    sesion = None
    if sesion_mapeo_id:
        sesion = MapeoSesionCama.objects.filter(
            pk=sesion_mapeo_id,
            usuario=request.user,
            estado=get_estado_mapeo("EN_PROGRESO", "ESTADO_SESION"),
            fecha_fin__isnull=True,
        ).first()
    if not sesion:
        sesion = _obtener_sesion_mapeo_activa(request.user)

    if not sesion:
        return JsonResponse(
            {"ok": False, "error": "No hay una sesion de mapeo activa. Debe iniciar mapeo primero."},
            status=400,
        )

    servicios_ids_sesion = _obtener_servicios_ids_sesion(sesion)
    # [2026-05-07] Usar sala del cubículo cuando existe para evitar error con FKs inconsistentes.
    sala_real = (cama.cubiculo.sala if cama.cubiculo else None) or cama.sala
    if servicios_ids_sesion and sala_real.servicio_id not in servicios_ids_sesion:
        # [2026-05-07] La cama debe pertenecer a uno de los servicios seleccionados en la sesion.
        return JsonResponse(
            {"ok": False, "error": "La cama seleccionada no pertenece a los servicios de esta sesion de mapeo."},
            status=403,
        )

    asig_actual = (
        AsignacionCamaPaciente.objects.select_related("paciente")
        .filter(cama_id=cama_id)
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    paciente_observado = None
    if paciente_observado_id:
        try:
            paciente_observado = Paciente.objects.get(pk=paciente_observado_id)
        except Paciente.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Paciente observado no existe."}, status=404)

    # Obtener instancias de estados
    estado_vacia = get_estado_mapeo("VACIA", "ESTADO_CAMA")
    estado_ocupada = get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
    estado_alta = get_estado_mapeo("ALTA", "ESTADO_CAMA")
    
    # [2026-05-04 AUDIT] Bug Fix: estado_sistema es EstadoMapeo object.
    # Se serializa como .codigo en JsonResponse. No retornar el objeto directamente.
    estado_sistema = asig_actual.estado if asig_actual else estado_vacia

    with transaction.atomic():
        # Caso 1: todo correcto (sin cambios en sistema)
        if accion == "CONFIRMAR":
            # Auditoria de mapeo: aunque no haya cambios, se registra la validacion.
            HistorialEstadoCama.objects.create(
                cama=cama,
                estado_anterior=estado_sistema,
                estado_nuevo=estado_sistema,
                paciente=asig_actual.paciente if asig_actual else None,
                usuario=request.user,
                observacion="Confirmacion de mapeo sin cambios",
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asig_actual,
                tipo_accion=DetalleMapeoCama.TipoAccion.CONFIRMACION,
                hubo_cambio=False,
                observacion=observacion or "Confirmacion de estado sin cambios.",
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Cama confirmada sin cambios.", "estado_sistema": estado_sistema.codigo})

        # Caso 2A: sistema en ALTA (prealta) y paciente ya egreso.
        if accion == "CONFIRMAR_ALTA":
            if not asig_actual:
                return JsonResponse({"ok": False, "error": "No hay asignacion activa para confirmar alta."}, status=400)

            paciente_mov = asig_actual.paciente
            estado_anterior = asig_actual.estado
            asig_actual.estado = estado_vacia
            asig_actual.paciente = None
            asig_actual.save()

            HistorialEstadoCama.objects.create(
                cama=cama,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_vacia,
                paciente=None,
                usuario=request.user,
                observacion="Confirmacion de alta desde mapeo",
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asig_actual,
                tipo_accion=DetalleMapeoCama.TipoAccion.ALTA,
                hubo_cambio=True,
                observacion=observacion or "Confirmar alta (egreso).",
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Alta confirmada. Cama liberada."})

        # Caso 2B: cancelar prealta (ALTA -> OCUPADA con mismo paciente)
        if accion == "CANCELAR_PREALTA":
            if not asig_actual or not asig_actual.paciente:
                return JsonResponse({"ok": False, "error": "No existe paciente actual para cancelar prealta."}, status=400)

            estado_anterior = asig_actual.estado
            asig_actual.estado = estado_ocupada
            asig_actual.save()

            HistorialEstadoCama.objects.create(
                cama=cama,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_ocupada,
                paciente=asig_actual.paciente,
                usuario=request.user,
                observacion="Cancelar prealta desde mapeo",
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asig_actual,
                tipo_accion=DetalleMapeoCama.TipoAccion.CORRECCION,
                hubo_cambio=True,
                observacion=observacion or "Cancelar prealta, paciente permanece.",
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Prealta cancelada. Cama en OCUPADA."})

        # Caso 3: paciente diferente (cambio/traslado)
        if accion == "CAMBIO_TRASLADO":
            if not paciente_observado:
                return JsonResponse(
                    {"ok": False, "error": "Debe indicar paciente_observado_id para cambio/traslado."},
                    status=400,
                )

            if asig_actual and asig_actual.paciente_id == paciente_observado.id:
                # Auditoria de mapeo: se registra validacion aunque paciente y estado coincidan.
                HistorialEstadoCama.objects.create(
                    cama=cama,
                    estado_anterior=estado_sistema,
                    estado_nuevo=estado_sistema,
                    paciente=asig_actual.paciente,
                    usuario=request.user,
                    observacion="Confirmacion de mapeo sin cambios (paciente coincide)",
                )

                _registrar_detalle_mapeo(
                    usuario=request.user,
                    cama=cama,
                    asignacion=asig_actual,
                    tipo_accion=DetalleMapeoCama.TipoAccion.CONFIRMACION,
                    hubo_cambio=False,
                    observacion=observacion or "Paciente coincide con sistema.",
                    sesion_mapeo=sesion,
                )
                return JsonResponse({"ok": True, "mensaje": "Sin cambios: paciente ya coincide con sistema."})

            estado_anterior = asig_actual.estado if asig_actual else estado_vacia
            if asig_actual and asig_actual.paciente:
                asig_actual.estado = estado_vacia
                asig_actual.paciente = None
                asig_actual.save()

            nueva_asig = AsignacionCamaPaciente.objects.create(
                cama=cama,
                paciente=paciente_observado,
                estado=estado_ocupada,
                usuario_asignacion=request.user,
            )

            HistorialEstadoCama.objects.create(
                cama=cama,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_ocupada,
                paciente=paciente_observado,
                usuario=request.user,
                observacion="Cambio/traslado desde mapeo",
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=nueva_asig,
                tipo_accion=DetalleMapeoCama.TipoAccion.CAMBIO,
                hubo_cambio=True,
                observacion=observacion or "Cambio/traslado de paciente.",
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Cambio/traslado aplicado correctamente."})

        # Caso 4: sistema libre, pero hay paciente real.
        if accion == "ASIGNACION":
            if not paciente_observado:
                return JsonResponse(
                    {"ok": False, "error": "Debe indicar paciente_observado_id para asignacion."},
                    status=400,
                )

            if asig_actual and asig_actual.estado == estado_ocupada:
                return JsonResponse(
                    {"ok": False, "error": "La cama ya figura ocupada en sistema. Use CAMBIO_TRASLADO."},
                    status=400,
                )

            if asig_actual:
                asig_actual.estado = estado_ocupada
                asig_actual.paciente = paciente_observado
                asig_actual.usuario_asignacion = request.user
                asig_actual.save()
                asignacion_obj = asig_actual
            else:
                asignacion_obj = AsignacionCamaPaciente.objects.create(
                    cama=cama,
                    paciente=paciente_observado,
                    estado=estado_ocupada,
                    usuario_asignacion=request.user,
                )

            HistorialEstadoCama.objects.create(
                cama=cama,
                estado_anterior=estado_vacia,
                estado_nuevo=estado_ocupada,
                paciente=paciente_observado,
                usuario=request.user,
                observacion="Asignacion detectada durante mapeo",
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asignacion_obj,
                tipo_accion=DetalleMapeoCama.TipoAccion.CAMBIO,
                hubo_cambio=True,
                observacion=observacion or "Sistema libre, paciente presente (asignacion).",
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Asignacion aplicada correctamente."})

        # Caso 5: sistema ocupado, pero cama vacia en la realidad.
        if accion == "ALTA_FORZADA":
            if not asig_actual or asig_actual.estado != estado_ocupada:
                return JsonResponse(
                    {"ok": False, "error": "No existe ocupacion activa para forzar alta."},
                    status=400,
                )

            paciente_prev = asig_actual.paciente
            asig_actual.estado = estado_vacia
            asig_actual.paciente = None
            asig_actual.save()

            HistorialEstadoCama.objects.create(
                cama=cama,
                estado_anterior=estado_ocupada,
                estado_nuevo=estado_vacia,
                paciente=None,
                usuario=request.user,
                observacion="Alta forzada desde mapeo",
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asig_actual,
                tipo_accion=DetalleMapeoCama.TipoAccion.ALTA,
                hubo_cambio=True,
                observacion=observacion or "Sistema ocupado, cama vacia (alta forzada).",
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Alta forzada aplicada. Cama liberada."})

    return JsonResponse({"ok": False, "error": "No se pudo procesar la accion solicitada."}, status=400)

# 2026-05-29: extraído de mapeo_camas/views.py en refactor E (split)
"""Vistas administrativas: sincronización masiva y diagnóstico de permisos."""

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Exists, Max, OuterRef, Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from core.constants.permisos import (
    MAPEO_CAMAS_CAMBIOS_ROLES,
    MAPEO_CAMAS_CAMBIOS_UNIDADES,
    MAPEO_CAMAS_HISTORIALES_ROLES,
    MAPEO_CAMAS_HISTORIALES_UNIDADES,
    MAPEO_CAMAS_MAPEAR_ROLES,
    MAPEO_CAMAS_MAPEAR_UNIDADES,
    MAPEO_CAMAS_VISUALIZACION_ROLES,
    MAPEO_CAMAS_VISUALIZACION_UNIDADES,
)
from core.services.usuario_service import UsuarioService
from ingreso.models import Ingreso
from usuario.models import AlcanceUsuario, PerfilUnidad

from mapeo_camas.models import (
    AsignacionCamaPaciente,
    EstadoMapeo,
    HistorialEstadoCama,
    get_observacion_mapeo,
)
from servicio.models import Cama

from ._helpers import get_estado_mapeo
from ._permisos import (
    _es_rol_intentos_restringido,
    _puede_gestionar_sesion_mapeo,
    _tiene_permiso_cambios_mapa,
    _tiene_permiso_historiales,
    _tiene_permiso_mapear,
    _tiene_permiso_visualizacion_mapa,
)


__all__ = ["sincronizar_camas_superadmin", "debug_permisos_mapa"]


# =============================================================================
# [2026-05-07] API: Sincronizar camas con ingresos activos
# [2026-05-25] Restringida nuevamente solo a superusuario.
# [2026-05-28] MC-PERM-006: se fija el método HTTP con @require_POST; el chequeo
# is_superuser se mantiene por ser operación de mantenimiento.
# =============================================================================
@login_required
@require_POST
def sincronizar_camas_superadmin(request):
    """
    Sincroniza AsignacionCamaPaciente para todos los ingresos activos con cama asignada.
    Solo accesible para superusuario.
    """
    if not getattr(request.user, "is_superuser", False):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

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
        "id", "cama_id"
    )

    camas_con_ingreso_activo = set(ingresos.values_list("cama_id", flat=True))

    estado_vacia = get_estado_mapeo("VACIA", "ESTADO_CAMA")
    estado_valido_subquery = EstadoMapeo.objects.filter(
        pk=OuterRef("estado_id"),
        categoria="ESTADO_CAMA",
    )
    # 2026-06-01: asegura atomic en saneamiento masivo de asignaciones inválidas.
    with transaction.atomic():
        asignaciones_reparadas = (
            AsignacionCamaPaciente.objects
            .annotate(estado_valido=Exists(estado_valido_subquery))
            .filter(Q(estado_id__isnull=True) | Q(estado_valido=False))
            .update(estado_id=estado_vacia.pk, ingreso_id=None)
        )

    estado_ocupada = get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
    # 2026-06-04: optimiza lectura masiva con values() para evitar instanciar modelos completos.
    asignaciones_actuales_qs = (
        AsignacionCamaPaciente.objects
        .order_by("cama_id", "-fecha_inicio", "-id")
        .values("cama_id", "estado__codigo", "ingreso_id")
    )
    ultima_asignacion_por_cama = {}
    for asig in asignaciones_actuales_qs:
        if asig["cama_id"] not in ultima_asignacion_por_cama:
            ultima_asignacion_por_cama[asig["cama_id"]] = asig

    sincronizados = 0
    omitidos = 0
    errores = 0
    errores_detalle = []

    for ingreso in ingresos:
        cama_id = ingreso["cama_id"]
        ingreso_id = ingreso["id"]
        asig_actual = ultima_asignacion_por_cama.get(cama_id)

        if (
            asig_actual
            and asig_actual.get("estado__codigo") == "OCUPADA"
            and asig_actual.get("ingreso_id") == ingreso_id
        ):
            omitidos += 1
            continue

        try:
            with transaction.atomic():
                asig_bloqueada = (
                    AsignacionCamaPaciente.objects
                    .select_for_update()
                    .filter(cama_id=cama_id)
                    .order_by("-fecha_inicio", "-id")
                    .first()
                )
                if (
                    asig_bloqueada
                    and asig_bloqueada.estado
                    and asig_bloqueada.estado.codigo == "OCUPADA"
                    and asig_bloqueada.ingreso_id == ingreso_id
                ):
                    omitidos += 1
                    ultima_asignacion_por_cama[cama_id] = {
                        "cama_id": cama_id,
                        "estado__codigo": asig_bloqueada.estado.codigo,
                        "ingreso_id": asig_bloqueada.ingreso_id,
                    }
                    continue

                estado_anterior = asig_bloqueada.estado if asig_bloqueada else estado_vacia

                if asig_bloqueada:
                    asig_bloqueada.estado = estado_ocupada
                    asig_bloqueada.ingreso_id = ingreso_id
                    asig_bloqueada.usuario_asignacion = request.user
                    asig_bloqueada.save(update_fields=["estado", "ingreso", "usuario_asignacion"])
                    asig_sync = asig_bloqueada
                else:
                    asig_sync = AsignacionCamaPaciente.objects.create(
                        cama_id=cama_id,
                        estado=estado_ocupada,
                        ingreso_id=ingreso_id,
                        usuario_asignacion=request.user,
                    )

                HistorialEstadoCama.objects.create(
                    cama_id=cama_id,
                    estado_anterior=estado_anterior,
                    estado_nuevo=estado_ocupada,
                    ingreso_id=ingreso_id,
                    usuario=request.user,
                    observacion=get_observacion_mapeo("Ingreso (sync masivo)"),
                )

                ultima_asignacion_por_cama[cama_id] = {
                    "cama_id": cama_id,
                    "estado__codigo": "OCUPADA",
                    "ingreso_id": ingreso_id,
                }

            sincronizados += 1
        except Exception as exc:
            errores += 1
            errores_detalle.append(f"Ingreso #{ingreso_id} — cama #{cama_id}: {exc}")

    # [2026-05-25] Registrar también camas desocupadas en VACIA.
    camas_activas_ids = set(Cama.objects.filter(estado=1).values_list("pk", flat=True))
    camas_desocupadas_ids = camas_activas_ids - camas_con_ingreso_activo
    vacias_creadas = 0
    vacias_actualizadas = 0
    if camas_desocupadas_ids:
        # 2026-06-09: optimiza preclasificación con values() y evita instanciar todas las asignaciones.
        asignaciones_desocupadas = (
            AsignacionCamaPaciente.objects
            .filter(cama_id__in=camas_desocupadas_ids)
            .values("id", "cama_id", "estado__codigo", "ingreso_id")
            .order_by("cama_id", "-fecha_inicio", "-id")
        )
        ultima_asignacion_por_cama = {}
        for asig in asignaciones_desocupadas:
            if asig["cama_id"] not in ultima_asignacion_por_cama:
                ultima_asignacion_por_cama[asig["cama_id"]] = asig

        camas_para_crear = []
        asignaciones_para_actualizar_ids = []
        for cama_id in camas_desocupadas_ids:
            asig = ultima_asignacion_por_cama.get(cama_id)
            if not asig:
                camas_para_crear.append(cama_id)
                continue
            estado_codigo = asig.get("estado__codigo")
            ingreso_id = asig.get("ingreso_id")
            if estado_codigo == "VACIA" and ingreso_id is None:
                continue
            if estado_codigo == "OCUPADA" or ingreso_id is not None or estado_codigo is None:
                asignaciones_para_actualizar_ids.append(asig["id"])

        # 2026-06-01: asegura atomic en creación/actualización masiva de camas VACIA.
        with transaction.atomic():
            if camas_para_crear:
                AsignacionCamaPaciente.objects.bulk_create([
                    AsignacionCamaPaciente(
                        cama_id=cama_id,
                        estado=estado_vacia,
                        ingreso=None,
                        usuario_asignacion=request.user,
                    )
                    for cama_id in camas_para_crear
                ])
                vacias_creadas = len(camas_para_crear)

            for asig in AsignacionCamaPaciente.objects.filter(id__in=asignaciones_para_actualizar_ids):
                asig.estado = estado_vacia
                asig.ingreso = None
                asig.usuario_asignacion = request.user
                asig.save(update_fields=["estado", "ingreso", "usuario_asignacion"])
            vacias_actualizadas = len(asignaciones_para_actualizar_ids)

    return JsonResponse({
        "ok": True,
        "asignaciones_reparadas": asignaciones_reparadas,
        "vacias_creadas": vacias_creadas,
        "vacias_actualizadas": vacias_actualizadas,
        "sincronizados": sincronizados,
        "omitidos": omitidos,
        "errores": errores,
        "errores_detalle": errores_detalle,
        "mensaje": (
            f"Sincronizacion finalizada. {asignaciones_reparadas} reparadas a VACIA, "
            f"{vacias_creadas} vacias creadas, {vacias_actualizadas} vacias actualizadas, "
            f"{sincronizados} sincronizados, {omitidos} omitidos, {errores} errores."
        )
    })


@login_required
@require_GET
def debug_permisos_mapa(request):
    """Diagnostico en vivo de permisos para la vista principal del mapa."""
    # [2026-05-28] MC-PERM-008: endpoint diagnóstico restringido a MAPEAR_*.
    if not _tiene_permiso_mapear(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)
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

    match_alcance_global_vista = PerfilUnidad.objects.filter(
        usuario=usuario,
        rol__in=MAPEO_CAMAS_VISUALIZACION_ROLES,
        alcance=AlcanceUsuario.GLOBAL,
    ).exists()

    match_unidad_vista = PerfilUnidad.objects.filter(
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
            "requerido_vista_mapa": {
                "roles": MAPEO_CAMAS_VISUALIZACION_ROLES,
                "unidades": MAPEO_CAMAS_VISUALIZACION_UNIDADES,
            },
            "requerido_historiales_dashboard": {
                "regla": "superusuario o alcance global sin permiso extra",
                "es_global": UsuarioService.es_global(usuario),
            },
            "requerido_flujo_mapeo": {
                "roles": MAPEO_CAMAS_MAPEAR_ROLES,
                "unidades": MAPEO_CAMAS_MAPEAR_UNIDADES,
            },
            "requerido_cambios_mapa": {
                "roles": MAPEO_CAMAS_CAMBIOS_ROLES,
                "unidades": MAPEO_CAMAS_CAMBIOS_UNIDADES,
            },
            "perfiles": perfiles,
            "evaluacion": {
                "puede_ver_mapa": _tiene_permiso_visualizacion_mapa(usuario),
                "puede_mapear": _tiene_permiso_mapear(usuario),
                "puede_gestionar_sesion_mapeo": _puede_gestionar_sesion_mapeo(usuario),
                "puede_hacer_cambios_mapa": _tiene_permiso_cambios_mapa(usuario),
                "es_rol_intentos_restringido": _es_rol_intentos_restringido(usuario),
                "mixin_alcance_global": match_alcance_global_vista,
                "mixin_vista_unidad": match_unidad_vista,
                "mixin_vista_resultado": bool(usuario.is_superuser or match_alcance_global_vista or match_unidad_vista),
            },
        }
    )

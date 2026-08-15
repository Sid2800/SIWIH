"""
Vistas del módulo de Egresos.

Fase 2: pantalla de CAPTURA. Estadística ve los ingresos aún abiertos (solo
tienen fecha de ingreso) y toma los expedientes disponibles para llenar sus
egresos. Aquí va, por ahora, la API que ALIMENTA ese listado (solo lectura; no
modifica el módulo Ingreso).
"""
import json
from datetime import date, datetime

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect

from ingreso.models import Ingreso
from expediente.models import PacienteAsignacion, Expediente
from clinico.models import CIE10
from s_exp.models import (
    ExpedientePrestamo, SolicitudExpedienteDetalle,
    EstadoSolicitud, EstadoExpedienteFisico,
)
from s_exp.services.datos_solicitud import DatosPaciente

from egresos.models import (
    LoteEgreso, LoteEgresoDetalle,
    AreaEgreso, Procedimiento, Egreso, EgresoDiagnostico,
)
from egresos.services.movimiento import mover_a_estadistica

from core.mixins import UnidadRolRequiredMixin
from usuario.permisos import verificar_permisos_usuario
from core.constants.permisos import (
    EGRESOS_VISUALIZACION_ROLES, EGRESOS_VISUALIZACION_UNIDADES,
)
from core.utils.utilidades_logging import log_error, log_info
from core.constants.domain_constants import LogApp


# =============================================================================
# Acceso: mismo mecanismo que el resto de módulos (no se inventa nada nuevo).
#   - Vistas: UnidadRolRequiredMixin (superuser / GLOBAL / rol+unidad).
#   - APIs:   verificar_permisos_usuario(user, roles, unidades).
# =============================================================================
def _tiene_permiso_egresos(user):
    return verificar_permisos_usuario(
        user, EGRESOS_VISUALIZACION_ROLES, EGRESOS_VISUALIZACION_UNIDADES
    )


class CapturaEgresosView(UnidadRolRequiredMixin, TemplateView):
    """Pantalla donde Estadística captura expedientes desde los ingresos."""
    template_name = 'egresos/captura.html'
    required_roles = EGRESOS_VISUALIZACION_ROLES
    required_unidades = EGRESOS_VISUALIZACION_UNIDADES


# =============================================================================
# Helpers de disponibilidad (reutilizan el criterio de s_exp)
# =============================================================================
def _expedientes_no_disponibles():
    """
    IDs de expedientes que NO se pueden tomar, con el mismo criterio de s_exp:
      - los que están en cualquier estado físico distinto de DISPONIBLE, y
      - los que participan en una solicitud de préstamo activa (aprobados y sin
        devolver).
    Se calcula en 2 consultas (sin N+1) para clasificar el listado completo.
    """
    no_disp = set(
        ExpedientePrestamo.objects
        .exclude(estado_id=EstadoExpedienteFisico.id_de('EXP_DISPONIBLE'))
        .values_list('expediente_id', flat=True)
    )
    en_proceso = set(
        SolicitudExpedienteDetalle.objects.filter(
            solicitud__estado_flujo_id__in=EstadoSolicitud.ids_de([
                'SOL_PENDIENTE', 'SOL_APROBADA_ORGANIZANDO', 'SOL_LISTO_RECOGER',
                'SOL_EN_PRESTAMO', 'SOL_EN_DEVOLUCION', 'SOL_INCOMPLETA',
            ]),
            devuelto=False, aprobado=True,
        ).values_list('expediente_prestamo__expediente_id', flat=True)
    )
    return no_disp | en_proceso


@require_GET
def ingresos_para_egreso_api(request):
    """
    Lista los ingresos ABIERTOS (solo fecha de ingreso, sin egreso) para que
    Estadística tome sus expedientes.

    Devuelve por ingreso: paciente (identidad y nombre), fecha de ingreso, área
    (sala/servicio del ingreso), número de expediente y si está DISPONIBLE para
    capturar. No modifica nada del módulo Ingreso (solo lectura).
    """
    if not _tiene_permiso_egresos(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        from s_exp.services.datos_solicitud import DatosPaciente

        ingresos = (
            Ingreso.objects
            .filter(fecha_egreso__isnull=True, paciente__isnull=False)
            .select_related('paciente', 'sala', 'sala__servicio')
            .order_by('-fecha_ingreso')
        )

        # Expediente de cada paciente (uno solo, el vigente), en bloque para no
        # disparar una consulta por fila.
        paciente_ids = list(ingresos.values_list('paciente_id', flat=True))
        exp_por_paciente = {}
        for asig in (PacienteAsignacion.objects
                     .filter(paciente_id__in=paciente_ids)
                     .select_related('expediente')
                     .order_by('-estado')):
            # order_by('-estado') deja la asignación vigente primero; nos quedamos
            # con la primera vista por paciente.
            exp_por_paciente.setdefault(asig.paciente_id, asig.expediente)

        no_disponibles = _expedientes_no_disponibles()

        data = []
        for ing in ingresos:
            pac = ing.paciente
            exp = exp_por_paciente.get(pac.id)
            disponible = bool(exp) and exp.id not in no_disponibles
            data.append({
                "ingreso_id": ing.id,
                "paciente_id": pac.id,
                "identidad": DatosPaciente.dni(pac),
                "nombre": DatosPaciente.nombre_completo(pac),
                "fecha_ingreso": ing.fecha_ingreso.date().isoformat() if ing.fecha_ingreso else '',
                "area_ingreso": str(ing.sala) if ing.sala_id else '',
                "expediente_id": exp.id if exp else None,
                "numero_expediente": exp.numero if exp else None,
                "disponible": disponible,
            })

        return JsonResponse({"data": data, "total": len(data)})

    except Exception as e:
        log_error(f"Error en ingresos_para_egreso_api: {e}", app=LogApp.EGRESOS)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def crear_lote_captura_api(request):
    """
    Estadística captura los expedientes seleccionados: crea un LOTE con sus
    detalles y marca cada expediente como "prestado a Estadística" (se ubica en
    Estadística y deja de estar disponible para otros).

    Solo se aceptan expedientes DISPONIBLES; la disponibilidad se revalida aquí
    (no se confía en lo que mandó el navegador). Todo va en una transacción: o se
    capturan todos o ninguno.
    """
    if not _tiene_permiso_egresos(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    # El front manda parejas expediente/paciente de las filas elegidas.
    seleccion = body.get('seleccion') or []
    observaciones = (body.get('observaciones') or '').strip()

    expediente_ids = [s.get('expediente_id') for s in seleccion if s.get('expediente_id')]
    if not expediente_ids:
        return JsonResponse({"error": "Seleccione al menos un expediente"}, status=400)

    # Revalidación de disponibilidad en el servidor.
    no_disponibles = _expedientes_no_disponibles()
    validos = [eid for eid in expediente_ids if eid not in no_disponibles]
    if not validos:
        return JsonResponse(
            {"error": "Los expedientes seleccionados ya no están disponibles"}, status=400
        )

    # paciente por expediente (según lo que mandó el front, para no re-resolver).
    paciente_por_exp = {
        s['expediente_id']: s.get('paciente_id')
        for s in seleccion if s.get('expediente_id')
    }

    try:
        expedientes = {e.id: e for e in Expediente.objects.filter(id__in=validos)}

        with transaction.atomic():
            lote = LoteEgreso.objects.create(
                usuario_estadistica=request.user,
                observaciones=observaciones or None,
            )
            for eid in validos:
                exp = expedientes.get(eid)
                if not exp:
                    continue
                LoteEgresoDetalle.objects.create(
                    lote=lote,
                    expediente=exp,
                    paciente_id=paciente_por_exp.get(eid),
                    estado=LoteEgresoDetalle.PRESTADO,
                )
                # Marca el expediente como prestado a Estadística.
                mover_a_estadistica(exp, request.user)

        log_info(
            f"Lote de egresos #{lote.id}: {len(validos)} expediente(s) capturados por "
            f"{request.user.username}", app=LogApp.EGRESOS
        )
        return JsonResponse({"success": True, "lote_id": lote.id, "capturados": len(validos)})

    except Exception as e:
        log_error(f"Error en crear_lote_captura_api: {e}", app=LogApp.EGRESOS)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# =============================================================================
# LLENADO: lista de expedientes tomados y su formulario de egreso
# =============================================================================
class LlenadoView(UnidadRolRequiredMixin, TemplateView):
    """Lista los expedientes que Estadística tomó, para llenar sus egresos."""
    template_name = 'egresos/llenado.html'
    required_roles = EGRESOS_VISUALIZACION_ROLES
    required_unidades = EGRESOS_VISUALIZACION_UNIDADES


class EgresoFormView(UnidadRolRequiredMixin, TemplateView):
    """Formulario de egreso para un expediente tomado (un detalle de lote)."""
    template_name = 'egresos/egreso_form.html'
    required_roles = EGRESOS_VISUALIZACION_ROLES
    required_unidades = EGRESOS_VISUALIZACION_UNIDADES

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['detalle_id'] = kwargs.get('detalle_id')
        return ctx


# ---- Helpers de llenado --------------------------------------------------
def _edad(fecha_nac, referencia):
    """Edad en años cumplidos a la fecha de referencia (None si falta el dato)."""
    if not fecha_nac or not referencia:
        return None
    return referencia.year - fecha_nac.year - (
        (referencia.month, referencia.day) < (fecha_nac.month, fecha_nac.day)
    )


def _ingreso_de_paciente(paciente_id):
    """El ingreso más reciente del paciente (para prefill de fecha/área)."""
    if not paciente_id:
        return None
    return (
        Ingreso.objects
        .filter(paciente_id=paciente_id)
        .select_related('sala', 'sala__servicio')
        .order_by('-fecha_ingreso')
        .first()
    )


def _parse_fecha(valor):
    """'YYYY-MM-DD' -> date, o None."""
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _tribool(valor):
    """Sí/No/(vacío) -> True/False/None."""
    if valor in (True, 'true', 'si', 'sí', 'SI', '1', 1):
        return True
    if valor in (False, 'false', 'no', 'NO', '0', 0):
        return False
    return None


def _entero(valor):
    try:
        return int(valor)
    except (ValueError, TypeError):
        return None


@require_GET
def pendientes_llenado_api(request):
    """
    Lista los expedientes tomados por Estadística (detalles de lotes abiertos)
    con su estado de llenado: 'completado' si ya tiene egreso, 'pendiente' si no.
    Agrupado por lote para que se vea la lista tal como se capturó.
    """
    if not _tiene_permiso_egresos(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        lotes = (
            LoteEgreso.objects
            .filter(estado=LoteEgreso.ABIERTO)
            .prefetch_related(
                'detalles__expediente', 'detalles__paciente', 'detalles__egreso',
            )
            .order_by('-fecha_captura_estadistica')
        )

        data = []
        for lote in lotes:
            detalles = []
            for d in lote.detalles.all():
                completado = hasattr(d, 'egreso') and d.egreso is not None
                pac = d.paciente
                detalles.append({
                    "detalle_id": d.id,
                    "expediente_id": d.expediente_id,
                    "numero_expediente": d.expediente.numero if d.expediente_id else None,
                    "identidad": DatosPaciente.dni(pac) if pac else '',
                    "nombre": DatosPaciente.nombre_completo(pac) if pac else '',
                    "estado_fisico": d.estado,
                    "completado": completado,
                    "egreso_id": d.egreso.id if completado else None,
                })
            total = len(detalles)
            hechos = sum(1 for d in detalles if d["completado"])
            data.append({
                "lote_id": lote.id,
                "fecha": lote.fecha_captura_estadistica.date().isoformat(),
                "responsable": (lote.usuario_estadistica.get_full_name()
                                or lote.usuario_estadistica.username),
                "observaciones": lote.observaciones or '',
                "total": total,
                "completados": hechos,
                "detalles": detalles,
            })

        return JsonResponse({"data": data, "total": len(data)})

    except Exception as e:
        log_error(f"Error en pendientes_llenado_api: {e}", app=LogApp.EGRESOS)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@require_GET
def datos_llenado_api(request, detalle_id):
    """
    Datos para el formulario de un expediente tomado: paciente (prefill), ingreso
    de referencia (fecha/área) y, si ya se había llenado, el egreso existente para
    editarlo.
    """
    if not _tiene_permiso_egresos(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        detalle = get_object_or_404(
            LoteEgresoDetalle.objects.select_related(
                'expediente', 'paciente', 'lote'
            ),
            id=detalle_id,
        )
        pac = detalle.paciente
        ing = _ingreso_de_paciente(pac.id if pac else None)

        fecha_ing = ing.fecha_ingreso.date() if (ing and ing.fecha_ingreso) else None
        hoy = date.today()

        # Sexo del paciente (H/M); 'N' u otro se deja en blanco para que elija.
        sexo_pac = getattr(pac, 'sexo', None)
        sexo = sexo_pac if sexo_pac in (Egreso.SEXO_HOMBRE, Egreso.SEXO_MUJER) else ''

        paciente = {
            "id": pac.id if pac else None,
            "identidad": DatosPaciente.dni(pac) if pac else '',
            "nombre": DatosPaciente.nombre_completo(pac) if pac else '',
            "sexo": sexo,
            "edad": _edad(getattr(pac, 'fecha_nacimiento', None),
                          fecha_ing or hoy) if pac else None,
        }
        ingreso = {
            "id": ing.id if ing else None,
            "fecha_ingreso": fecha_ing.isoformat() if fecha_ing else '',
            "area_ingreso": str(ing.sala) if (ing and ing.sala_id) else '',
        }

        # Egreso existente (edición).
        egreso = None
        eg = getattr(detalle, 'egreso', None)
        if eg:
            egreso = {
                "id": eg.id,
                "area_id": eg.area_id,
                "numero": eg.numero,
                "pagina": eg.pagina or '',
                "fecha_egreso": eg.fecha_egreso.isoformat() if eg.fecha_egreso else '',
                "fecha_ingreso": eg.fecha_ingreso.isoformat() if eg.fecha_ingreso else '',
                "edad": eg.edad,
                "procedencia": eg.procedencia or '',
                "sexo": eg.sexo or '',
                "condicion": eg.condicion or '',
                "peso_gramos": eg.peso_gramos,
                "operacion_codigo": eg.operacion.codigo if eg.operacion_id else '',
                "operacion_descripcion": eg.operacion.descripcion if eg.operacion_id else '',
                "tipo_referencia": eg.tipo_referencia or '',
                "referencia_texto": eg.referencia_texto or '',
                "epicrisis": eg.epicrisis,
                "deberia_ir_sala": eg.deberia_ir_sala,
                "en_censo": eg.en_censo,
                "comentario": eg.comentario or '',
                "diagnosticos": [
                    {
                        "tipo": dg.tipo,
                        "orden": dg.orden,
                        "codigo": dg.cie10.codigo if dg.cie10_id else '',
                        "descripcion": dg.descripcion or (
                            dg.cie10.descripcion if dg.cie10_id else ''),
                    }
                    for dg in eg.diagnosticos.all().order_by('tipo', 'orden')
                ],
            }

        return JsonResponse({
            "detalle": {
                "id": detalle.id,
                "lote_id": detalle.lote_id,
                "expediente_id": detalle.expediente_id,
                "numero_expediente": detalle.expediente.numero if detalle.expediente_id else None,
                "estado_fisico": detalle.estado,
            },
            "paciente": paciente,
            "ingreso": ingreso,
            "egreso": egreso,
        })

    except Exception as e:
        log_error(f"Error en datos_llenado_api ({detalle_id}): {e}", app=LogApp.EGRESOS)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def guardar_egreso_api(request, detalle_id):
    """
    Crea o actualiza el egreso de un expediente tomado (detalle de lote) y sus
    diagnósticos (ilimitados). No mueve el expediente: sigue prestado a
    Estadística hasta que Admisión reciba el lote de vuelta.
    """
    if not _tiene_permiso_egresos(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    detalle = get_object_or_404(
        LoteEgresoDetalle.objects.select_related('expediente', 'paciente'),
        id=detalle_id,
    )

    # --- Validaciones mínimas ---
    area_id = _entero(body.get('area_id'))
    if not area_id:
        return JsonResponse({"error": "Seleccione el área del censo"}, status=400)
    area = AreaEgreso.objects.filter(id=area_id, activo=True).first()
    if not area:
        return JsonResponse({"error": "El área seleccionada no es válida"}, status=400)

    fecha_egreso = _parse_fecha(body.get('fecha_egreso'))
    if not fecha_egreso:
        return JsonResponse({"error": "La fecha de egreso es obligatoria"}, status=400)

    fecha_ingreso = _parse_fecha(body.get('fecha_ingreso'))
    if fecha_ingreso and fecha_ingreso > fecha_egreso:
        return JsonResponse(
            {"error": "La fecha de ingreso no puede ser posterior al egreso"}, status=400
        )

    # Operación: el usuario escribe SOLO el código; se clasifica por catálogo.
    operacion = None
    op_codigo = (body.get('operacion_codigo') or '').strip()
    if op_codigo:
        operacion, _ = Procedimiento.objects.get_or_create(
            codigo=op_codigo,
            defaults={'descripcion': (body.get('operacion_descripcion') or '').strip()
                      or op_codigo},
        )

    try:
        with transaction.atomic():
            eg = getattr(detalle, 'egreso', None)
            if eg is None:
                eg = Egreso(creado_por=request.user)
                eg.lote_detalle = detalle

            eg.area = area
            eg.paciente = detalle.paciente
            eg.expediente = detalle.expediente
            eg.ingreso = _ingreso_de_paciente(
                detalle.paciente_id if detalle.paciente_id else None
            )
            eg.numero = _entero(body.get('numero'))
            eg.pagina = (body.get('pagina') or '').strip() or None
            eg.fecha_egreso = fecha_egreso
            eg.fecha_ingreso = fecha_ingreso
            eg.edad = _entero(body.get('edad'))
            eg.procedencia = (body.get('procedencia') or '').strip() or None
            eg.sexo = (body.get('sexo') or '').strip() or None
            eg.condicion = (body.get('condicion') or '').strip() or None
            eg.peso_gramos = _entero(body.get('peso_gramos'))
            eg.operacion = operacion
            eg.tipo_referencia = (body.get('tipo_referencia') or '').strip() or None
            eg.referencia_texto = (body.get('referencia_texto') or '').strip() or None
            eg.epicrisis = _tribool(body.get('epicrisis'))
            eg.deberia_ir_sala = _tribool(body.get('deberia_ir_sala'))
            eg.en_censo = bool(_tribool(body.get('en_censo')))
            eg.comentario = (body.get('comentario') or '').strip() or None
            eg.modificado_por = request.user
            eg.save()

            # Diagnósticos: se reemplazan por completo (simple y consistente).
            eg.diagnosticos.all().delete()
            for dg in (body.get('diagnosticos') or []):
                codigo = (dg.get('codigo') or '').strip()
                descripcion = (dg.get('descripcion') or '').strip()
                if not codigo and not descripcion:
                    continue
                cie10 = CIE10.objects.filter(codigo=codigo).first() if codigo else None
                EgresoDiagnostico.objects.create(
                    egreso=eg,
                    tipo=(dg.get('tipo') or EgresoDiagnostico.TIPO_EGRESO),
                    orden=_entero(dg.get('orden')) or 1,
                    cie10=cie10,
                    descripcion=descripcion or (cie10.descripcion if cie10 else None),
                )

        log_info(
            f"Egreso #{eg.id} guardado (detalle {detalle.id}) por {request.user.username}",
            app=LogApp.EGRESOS,
        )
        return JsonResponse({
            "success": True,
            "egreso_id": eg.id,
            "dias_estancia": eg.dias_estancia,
        })

    except Exception as e:
        log_error(f"Error en guardar_egreso_api ({detalle_id}): {e}", app=LogApp.EGRESOS)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# ---- Catálogos / búsquedas ----------------------------------------------
@require_GET
def areas_api(request):
    """Áreas de censo activas para el combobox del formulario."""
    if not _tiene_permiso_egresos(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)
    areas = (
        AreaEgreso.objects.filter(activo=True)
        .values('id', 'codigo', 'nombre', 'tipo')
        .order_by('orden', 'nombre')
    )
    return JsonResponse({"data": list(areas)})


@require_GET
def buscar_cie10_api(request):
    """Búsqueda de CIE10 por código o descripción (para diagnósticos)."""
    if not _tiene_permiso_egresos(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)
    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({"data": []})
    from django.db.models import Q
    resultados = (
        CIE10.objects
        .filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
        .values('id', 'codigo', 'descripcion')[:20]
    )
    return JsonResponse({"data": list(resultados)})


@require_GET
def buscar_procedimiento_api(request):
    """Clasifica una operación por su código (si existe en el catálogo)."""
    if not _tiene_permiso_egresos(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)
    codigo = (request.GET.get('codigo') or '').strip()
    if not codigo:
        return JsonResponse({"data": None})
    proc = Procedimiento.objects.filter(codigo=codigo).values(
        'id', 'codigo', 'descripcion'
    ).first()
    return JsonResponse({"data": proc})

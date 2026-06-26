"""
buscador.py - APIs del buscador de expedientes e historial por paciente/expediente.

Parte del paquete s_exp.views (antes views.py monolitico).
"""



from django.http import JsonResponse
from django.views.decorators.http import require_GET

from django.db.models import Q

from s_exp.models import ExpedientePrestamo, SolicitudExpedienteDetalle
from expediente.models import Expediente, PacienteAsignacion
from paciente.models import Paciente


from .comunes import (
    _es_exp_solicitante,
    _fmt_local,
    _resolver_ubicacion_expediente,
)


from core.utils.utilidades_logging import log_info, log_warning, log_error
from core.constants.domain_constants import LogApp


@require_GET
def buscar_expedientes_api(request):
    """
    Buscador principal de expedientes con filtrado de disponibilidad en tiempo real.
    
    Query Params:
        q (str): Término de búsqueda (número, identidad o nombre).
        tipo (str): 'expediente', 'identidad' o 'nombre'.
        
    Returns:
        JSON con los resultados y flags de 'disponible' (True/False).
    """
    """
    Busca pacientes en la base SIWI por identidad, N° expediente o nombre.
    Todos los expedientes están disponibles excepto aquellos con préstamo activo.
    """
    if not _es_exp_solicitante(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        query = request.GET.get('q', '').strip()
        tipo = request.GET.get('tipo', 'expediente')  # expediente, identidad, nombre

        if not query:
            return JsonResponse({"data": []})

        # IDs de expedientes no disponibles (Cualquier estado que no sea disponible)
        expedientes_no_disponibles = set(
            ExpedientePrestamo.objects.exclude(estado__codigo='EXP_DISPONIBLE')
            .values_list('expediente_id', flat=True)
        )
        # También las solicitudes activas que podrían no haber actualizado el estado físico aún.
        # IMPORTANTE: solo cuentan los detalles APROBADOS — los rechazados ya no apartan al expediente.
        en_proceso = set(
            SolicitudExpedienteDetalle.objects.filter(
                solicitud__estado_flujo__codigo__in=['SOL_PENDIENTE', 'SOL_APROBADA_ORGANIZANDO', 'SOL_LISTO_RECOGER', 'SOL_EN_PRESTAMO', 'SOL_EN_DEVOLUCION', 'SOL_INCOMPLETA'],
                devuelto=False,
                aprobado=True,
            ).values_list('expediente_prestamo__expediente_id', flat=True)
        )
        expedientes_prestados_ids = expedientes_no_disponibles | en_proceso

        # Usamos el servicio DatosPaciente para formatear nombres de manera consistente.
        # IMPORTANTE: aquí SÍ devolvemos paciente_id porque el frontend lo guarda
        # en el carrito y lo envía al backend al crear la solicitud (ya no captura
        # texto, solo IDs).
        from s_exp.services.datos_solicitud import DatosPaciente

        # Ubicaciones que cuentan como "en el archivo / disponible para prestar".
        # Regla: un expediente solo puede prestarse si está físicamente en ADMISION.
        # Durante la transición híbrida también aceptamos ARCHIVO (legacy).
        # A futuro, dejar únicamente 'ADMISION'.
        UBICACIONES_DISPONIBLES = {'ADMISION', 'ARCHIVO'}

        def _construir_resultado(exp, paciente):
            """Helper interno: dado un Expediente y un Paciente, arma el dict de respuesta."""
            # Precargamos la ubicación (catálogo nuevo) y sus relaciones para
            # que _resolver_ubicacion_expediente no dispare queries extra.
            info_exp = ExpedientePrestamo.objects.select_related(
                'ubicacion__unidad_clinica__area_atencion__servicio',
                'ubicacion__unidad_clinica__sala',
                'ubicacion__unidad_clinica__servicio_aux',
                'ubicacion__unidad_no_clinica',
            ).filter(expediente=exp).first()

            ubicacion_texto = _resolver_ubicacion_expediente(exp, info_exp)

            # DISPONIBLE requiere DOS condiciones:
            #   1. No estar prestado ni en un proceso de solicitud activo.
            #   2. Estar físicamente en ADMISION (o ARCHIVO durante el híbrido).
            #      Si está en un área clínica (atención/ingreso), NO se presta.
            ubic_upper = (ubicacion_texto or '').strip().upper()
            en_ubicacion_disponible = ubic_upper in UBICACIONES_DISPONIBLES
            disponible = (exp.id not in expedientes_prestados_ids) and en_ubicacion_disponible

            return {
                "expediente_id": exp.id,
                "numero_expediente": exp.numero,
                "paciente_id": paciente.id if paciente else None,
                "paciente_nombre": DatosPaciente.nombre_completo(paciente),
                "paciente_dni": DatosPaciente.dni(paciente),
                "disponible": disponible,
                "ubicacion_fisica": ubicacion_texto,
            }

        resultados = []

        if tipo == 'expediente':
            # Buscar por número de expediente — Top 5 resultados
            expedientes_encontrados = set()
            try:
                numero_int = int(query.lstrip("0") or "0")
                for exp in Expediente.objects.filter(numero=numero_int)[:5]:
                    expedientes_encontrados.add(exp.id)
            except ValueError:
                pass

            # También permite buscar via Paciente.expediente_numero (vínculo viejo)
            pacientes_por_exp = Paciente.objects.filter(expediente_numero__icontains=query)[:5]
            for pac in pacientes_por_exp:
                asig = PacienteAsignacion.objects.filter(paciente=pac).select_related('expediente').first()
                if asig:
                    expedientes_encontrados.add(asig.expediente.id)

            for exp in Expediente.objects.filter(id__in=expedientes_encontrados)[:5]:
                asignacion = PacienteAsignacion.objects.filter(
                    expediente=exp
                ).select_related('paciente').order_by('-estado').first()
                paciente = asignacion.paciente if asignacion else None
                resultados.append(_construir_resultado(exp, paciente))

        elif tipo == 'identidad':
            query_limpio = query.replace("-", "").replace(" ", "")
            pacientes = Paciente.objects.filter(dni__icontains=query_limpio, estado='A')[:5]
            for pac in pacientes:
                asignaciones = PacienteAsignacion.objects.filter(
                    paciente=pac, estado='1'
                ).select_related('expediente')
                for asig in asignaciones:
                    resultados.append(_construir_resultado(asig.expediente, pac))
                    if len(resultados) >= 5:
                        break
                if len(resultados) >= 5:
                    break

        elif tipo == 'nombre':
            palabras = query.split()
            filtro = Q(estado='A')
            for palabra in palabras:
                filtro &= (
                    Q(primer_nombre__icontains=palabra) |
                    Q(segundo_nombre__icontains=palabra) |
                    Q(primer_apellido__icontains=palabra) |
                    Q(segundo_apellido__icontains=palabra)
                )
            pacientes = Paciente.objects.filter(filtro)[:5]
            for pac in pacientes:
                asignaciones = PacienteAsignacion.objects.filter(
                    paciente=pac, estado='1'
                ).select_related('expediente')
                for asig in asignaciones:
                    resultados.append(_construir_resultado(asig.expediente, pac))
                    if len(resultados) >= 5:
                        break
                if len(resultados) >= 5:
                    break

        return JsonResponse({"data": resultados})

    except Exception as e:
        log_error(f"Error en buscar_expedientes_api: {e}", app=LogApp.S_EXP)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# ============================================
# API: Historial de préstamos por paciente
# ============================================

@require_GET
def historial_prestamos_paciente_api(request, paciente_id):
    """Retorna el historial de préstamos asociados a un paciente."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)

    try:
        from expediente.models import PacienteAsignacion

        # Obtener expedientes del paciente
        asignaciones = PacienteAsignacion.objects.filter(
            paciente_id=paciente_id
        ).select_related('expediente')

        expediente_ids = [a.expediente_id for a in asignaciones]

        if not expediente_ids:
            return JsonResponse({"data": [], "en_prestamo": False})

        # Buscar detalles de solicitud que involucren esos expedientes
        detalles = SolicitudExpedienteDetalle.objects.filter(
            expediente_prestamo__expediente_id__in=expediente_ids
        ).select_related(
            'solicitud', 'solicitud__usuario', 'solicitud__motivo',
            'solicitud__estado_flujo', 'solicitud__servicio_unidad',
            'expediente_prestamo', 'expediente_prestamo__expediente', 'paciente'
        ).order_by('-solicitud__fecha_creacion')

        # Servicios para acceso unificado (sin snapshots)
        from s_exp.services.datos_solicitud import DatosDetalleSolicitud, DatosSolicitud

        data = []
        en_prestamo_actual = False

        for d in detalles:
            s = d.solicitud
            estado = DatosSolicitud.estado_codigo(s)  # id -> código de texto
            if estado in ('SOL_EN_PRESTAMO', 'SOL_APROBADA_ORGANIZANDO') and not d.devuelto:
                en_prestamo_actual = True

            data.append({
                "numero_expediente": DatosDetalleSolicitud.numero_expediente(d),
                "fecha_solicitud": _fmt_local(s.fecha_creacion),
                "motivo": DatosSolicitud.motivo_nombre(s),
                "solicitante": DatosSolicitud.usuario_nombre_completo(s),
                "estado": DatosSolicitud.estado_nombre(s),
                "devuelto": d.devuelto,
                # alias de retrocompat (frontend espera 'area_destino')
                "area_destino": DatosSolicitud.unidad_nombre(s),
            })

        return JsonResponse({"data": data, "en_prestamo": en_prestamo_actual})

    except Exception as e:
        log_error(f"Error en historial_prestamos_paciente_api: {e}", app=LogApp.S_EXP)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@require_GET
def historial_prestamos_expediente_api(request, expediente_id):
    """Retorna el historial de préstamos asociados a un expediente."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)

    try:
        # Buscar detalles de solicitud que involucren ese expediente
        detalles = SolicitudExpedienteDetalle.objects.filter(
            expediente_prestamo__expediente_id=expediente_id
        ).select_related(
            'solicitud', 'solicitud__usuario', 'solicitud__motivo',
            'solicitud__estado_flujo', 'solicitud__servicio_unidad',
            'expediente_prestamo', 'expediente_prestamo__expediente', 'paciente'
        ).order_by('-solicitud__fecha_creacion')

        from s_exp.services.datos_solicitud import DatosDetalleSolicitud, DatosSolicitud

        # Ubicación ACTUAL del expediente (dónde está físicamente AHORA). Es un
        # dato único del expediente (no por préstamo), así que se resuelve UNA
        # vez. Fuente: catálogo unificado expediente_ubicacion (FK por id),
        # con fallback legacy — ver _resolver_ubicacion_expediente.
        ubicacion_actual = ''
        try:
            exp_obj = Expediente.objects.select_related('ubicacion', 'localizacion').filter(id=expediente_id).first()
            info_exp = ExpedientePrestamo.objects.select_related('ubicacion').filter(expediente_id=expediente_id).first()
            if exp_obj:
                ubicacion_actual = _resolver_ubicacion_expediente(exp_obj, info_exp)
        except Exception as _e:
            log_warning(f"No se pudo resolver ubicacion actual del expediente {expediente_id}: {_e}", app=LogApp.S_EXP)

        data = []
        en_prestamo_actual = False

        for d in detalles:
            s = d.solicitud
            estado = DatosSolicitud.estado_codigo(s)  # id -> código de texto
            if estado in ('SOL_EN_PRESTAMO', 'SOL_APROBADA_ORGANIZANDO') and not d.devuelto:
                en_prestamo_actual = True

            data.append({
                "numero_expediente": DatosDetalleSolicitud.numero_expediente(d),
                "fecha_solicitud": _fmt_local(s.fecha_creacion),
                "motivo": DatosSolicitud.motivo_nombre(s),
                "solicitante": DatosSolicitud.usuario_nombre_completo(s),
                "estado": DatosSolicitud.estado_nombre(s),
                "devuelto": d.devuelto,
                # Área a la que se prestó EN ESE MOMENTO (snapshot por la FK
                # servicio_unidad capturada al crear la solicitud; NO cambia
                # aunque el solicitante luego cambie de puesto).
                "area_destino": DatosSolicitud.unidad_nombre(s),
            })

        return JsonResponse({
            "data": data,
            "en_prestamo": en_prestamo_actual,
            # Ubicación física actual del expediente (igual para todo el historial).
            "ubicacion_actual": ubicacion_actual,
        })

    except Exception as e:
        log_error(f"Error en historial_prestamos_expediente_api: {e}", app=LogApp.S_EXP)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)

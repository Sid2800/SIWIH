import json
import logging
from datetime import timedelta
from io import BytesIO

from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.generic import TemplateView
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect, csrf_exempt

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, F
from django.shortcuts import redirect

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
except ImportError:
    Workbook = None

from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Table, TableStyle, Spacer
)

from .models import (
    MotivoSolicitud,
    ExpedientePrestamo,
    SolicitudPrestamo,
    SolicitudExpedienteDetalle,
    Prestamo,
    Devolucion,
    LogHistorico,
)
from usuario.models import PerfilUnidad

logger = logging.getLogger("s_exp")


# ============================================
# UTILIDAD: Registrar Log en BD
# ============================================
def _registrar_log(usuario, accion, descripcion, objeto_tipo=None, objeto_id=None):
    """
    Registra un evento en la bitácora de auditoría del sistema (ExpedienteLog).
    
    Args:
        usuario: Instancia de User que realiza la acción.
        accion: Código de la acción (ej. 'SOLICITUD_CREADA').
        descripcion: Texto explicativo del evento.
        objeto_tipo: Nombre del modelo afectado (opcional).
        objeto_id: ID del registro afectado (opcional).
    """
    LogHistorico.objects.create(
        accion=accion,
        usuario=usuario,
        detalle=descripcion,
        objeto_tipo=objeto_tipo,
        objeto_id=objeto_id,
    )


# ============================================
# UTILIDAD: Verificar permisos basados en PerfilUnidad
# ============================================
def _es_exp_admin(user):
    """
    Verifica si un usuario tiene permisos administrativos sobre el módulo de expedientes.
    Roles permitidos: Administrador, Digitador, Directivo.
    """
    if user.is_superuser or user.is_staff:
        return True
    if user.groups.filter(name='administradores').exists():
        return True
    # Permitir acceso a usuarios con roles: admin, digitador, directivo
    return PerfilUnidad.objects.filter(
        usuario=user,
        rol__in=['admin', 'digitador', 'directivo']
    ).exists()


def _es_exp_solicitante(user):
    """True si el usuario puede acceder al módulo (solicitar expedientes).
    Condiciones: rol 'exp_solicitante' o 'admin' en PerfilUnidad, o admin del módulo.
    """
    if _es_exp_admin(user):
        return True
    return PerfilUnidad.objects.filter(usuario=user, rol='exp_solicitante').exists()


def _get_unidad_usuario(user):
    """Obtiene el nombre de la unidad del usuario desde PerfilUnidad."""
    perfil = PerfilUnidad.objects.filter(usuario=user).select_related('servicio_unidad').first()
    return perfil.servicio_unidad.nombre_unidad if perfil and perfil.servicio_unidad else ''


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


# ============================================
# VISTAS ADMIN (Templates)
# ============================================

class DashboardAdminView(SExpAdminMixin, TemplateView):
    """Redirige a Gestión de Solicitudes como landing del admin."""
    def get(self, request, *args, **kwargs):
        return redirect('s_exp_solicitudes')


class GestionSolicitudesView(SExpAdminMixin, TemplateView):
    template_name = 's_exp/gestion_solicitudes.html'


class MonitoreoPrestamosView(SExpAdminMixin, TemplateView):
    template_name = 's_exp/monitoreo_prestamos.html'


class ControlDevolucionesView(SExpAdminMixin, TemplateView):
    template_name = 's_exp/control_devoluciones.html'


class ReportesView(SExpAdminMixin, TemplateView):
    template_name = 's_exp/reportes.html'


# ============================================
# VISTAS USUARIO (Templates)
# ============================================

class BuscadorExpedientesView(SExpUsuarioMixin, TemplateView):
    template_name = 's_exp/buscador_expedientes.html'


class SeguimientoView(SExpUsuarioMixin, TemplateView):
    template_name = 's_exp/seguimiento_usuario.html'


# ============================================
# APIs ADMIN - Dashboard Stats
# ============================================

@require_GET
def dashboard_stats_api(request):
    """Retorna estadísticas para el dashboard del admin."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        from expediente.models import Expediente
        total = Expediente.objects.count()

        # Expedientes con préstamo activo
        prestados = ExpedientePrestamo.objects.filter(estado_id='EXP_PRESTADO').count()
        disponibles = total - prestados

        solicitudes_pendientes = SolicitudPrestamo.objects.filter(estado_flujo_id='SOL_PENDIENTE').count()

        ahora = timezone.now()
        prestamos_activos = Prestamo.objects.filter(estado='Entregado').count()
        prestamos_vencidos = Prestamo.objects.filter(
            estado='Entregado',
            fecha_limite__lt=ahora
        ).count()

        # Próximos a vencer (más del 90% de tiempo usado)
        proximos_vencer = 0
        for p in Prestamo.objects.filter(estado='Entregado', fecha_limite__gte=ahora):
            if p.porcentaje_tiempo_usado >= 90:
                proximos_vencer += 1

        devoluciones_parciales = Prestamo.objects.filter(estado='DevolucionParcial').count()

        return JsonResponse({
            "total_expedientes": total,
            "disponibles": disponibles,
            "prestados": prestados,
            "solicitudes_pendientes": solicitudes_pendientes,
            "prestamos_activos": prestamos_activos,
            "prestamos_vencidos": prestamos_vencidos,
            "proximos_vencer": proximos_vencer,
            "devoluciones_parciales": devoluciones_parciales,
        })
    except Exception as e:
        logger.error(f"Error en dashboard_stats_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# ============================================
# APIs ADMIN - Gestión de Solicitudes
# ============================================

@require_GET
def listar_solicitudes_api(request):
    """
    API para alimentar el DataTable de gestión de solicitudes (Admin).
    Soporta filtrado por estado y búsqueda server-side.
    """
    """Lista solicitudes para el admin (DataTables server-side)."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        draw = int(request.GET.get('draw', 0))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 20))
        search_value = request.GET.get('search[value]', '').strip()
        estado_filtro = request.GET.get('estado', '')

        qs = SolicitudPrestamo.objects.select_related('usuario').annotate(
            cant_expedientes=Count('detalles')
        )

        if estado_filtro:
            qs = qs.filter(estado_flujo_id=estado_filtro)

        if search_value:
            qs = qs.filter(
                Q(usuario__username__icontains=search_value) |
                Q(motivo__nombre__icontains=search_value) |
                Q(id__icontains=search_value)
            )

        total_records = SolicitudPrestamo.objects.count()
        filtered_records = qs.count()

        solicitudes = qs.order_by('-fecha_creacion')[start:start + length]

        data = []
        for s in solicitudes:
            # Obtener expedientes y su estado de entrega
            detalles_info = []
            for d in s.detalles.select_related('expediente_prestamo__expediente'):
                detalles_info.append({
                    "detalle_id": d.id,
                    "numero": d.expediente_prestamo.expediente.numero,
                    "devuelto": d.devuelto,
                    "fuera_de_tiempo": d.fuera_de_tiempo,
                    "aprobado": d.aprobado,
                    "motivo_rechazo_individual": d.motivo_rechazo_individual or "",
                })

            data.append({
                "id": s.id,
                "usuario": s.usuario.username,
                "usuario_nombre": f"{s.usuario.first_name} {s.usuario.last_name}".strip() or s.usuario.username,
                "fecha_creacion": s.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
                "estado_flujo": s.estado_flujo_id,
                "estado_flujo_nombre": s.estado_flujo.nombre,
                "motivo": s.motivo.nombre if s.motivo else "",
                "observaciones": s.observaciones or "",
                "area_destino": s.area_destino or "",
                "cant_expedientes": s.cant_expedientes,
                "expedientes": detalles_info,
            })

        return JsonResponse({
            "draw": draw,
            "recordsTotal": total_records,
            "recordsFiltered": filtered_records,
            "data": data,
        })
    except Exception as e:
        logger.error(f"Error en listar_solicitudes_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def aprobar_solicitud_api(request):
    """
    Aprueba una solicitud y crea el préstamo.
    Soporta decisiones individuales por expediente (aprobado/rechazado).
    Si todos los expedientes son rechazados, la solicitud pasa a SOL_RECHAZADA.
    """
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    solicitud_id = body.get('solicitud_id')
    comentarios = body.get('comentarios', '')
    tiempo_limite = body.get('tiempo_limite_horas', 24)
    es_minutos = body.get('es_minutos', False)
    expedientes_decisiones = body.get('expedientes_decisiones', [])

    if int(tiempo_limite) < 1:
        return JsonResponse({"error": "El tiempo debe ser mayor a 0"}, status=400)

    # Validar tope de 72 horas cuando no es modo minutos (el frontend ya convierte días a horas)
    if not es_minutos and int(tiempo_limite) > 72:
        return JsonResponse({"error": "El tiempo máximo de préstamo es 72 horas (3 días)"}, status=400)

    # Mapa de decisiones: {detalle_id: {aprobado, observaciones}}
    mapa_decisiones = {}
    hay_rechazos = False
    for d in expedientes_decisiones:
        det_id = d.get('detalle_id')
        if det_id is None:
            continue
        aprobado = d.get('aprobado', True)
        if not aprobado:
            hay_rechazos = True
        mapa_decisiones[det_id] = {
            'aprobado': aprobado,
            'observaciones': (d.get('observaciones') or '').strip(),
        }

    # Si hay rechazos, comentarios generales es obligatorio
    if hay_rechazos and not comentarios.strip():
        return JsonResponse({
            "error": "Comentarios generales obligatorios cuando hay expedientes rechazados"
        }, status=400)

    try:
        solicitud = SolicitudPrestamo.objects.get(id=solicitud_id, estado_flujo_id='SOL_PENDIENTE')
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada o ya procesada"}, status=404)

    try:
        from .models import ExpedienteEstadoLog
        detalles = list(solicitud.detalles.select_related('expediente_prestamo__expediente'))

        # Verificar que los expedientes aprobados estén disponibles
        for d in detalles:
            info = mapa_decisiones.get(d.id, {'aprobado': True, 'observaciones': ''})
            if info['aprobado'] and d.expediente_prestamo.estado_id == 'EXP_PRESTADO':
                return JsonResponse({
                    "error": f"El expediente #{d.expediente_prestamo.expediente.numero} ya no está disponible"
                }, status=400)

        # Aplicar decisiones por expediente
        aprobados = []
        rechazados = []
        for d in detalles:
            info = mapa_decisiones.get(d.id, {'aprobado': True, 'observaciones': ''})
            d.aprobado = info['aprobado']
            # Guardar SIEMPRE las observaciones (tanto aprobados como rechazados pueden tenerlas)
            d.motivo_rechazo_individual = info['observaciones'] or None
            if info['aprobado']:
                aprobados.append(d)
            else:
                rechazados.append(d)
            d.save()

        # Texto motivo general: usamos las primeras observaciones de rechazados (para Prestamo.motivo_rechazo si aplica)
        motivo_rechazo_general = " | ".join(
            f"#{d.expediente_prestamo.expediente.numero}: {d.motivo_rechazo_individual}"
            for d in rechazados if d.motivo_rechazo_individual
        )

        todos_rechazados = len(aprobados) == 0

        if todos_rechazados:
            # Rechazar toda la solicitud
            solicitud.estado_flujo_id = 'SOL_RECHAZADA'
            solicitud.save()

            for d in rechazados:
                ep = d.expediente_prestamo
                estado_ant = ep.estado
                ep.estado_id = 'EXP_DISPONIBLE'
                ep.save()
                ExpedienteEstadoLog.objects.create(
                    expediente=ep.expediente,
                    estado_anterior=estado_ant,
                    estado_nuevo_id='EXP_DISPONIBLE',
                    usuario=request.user,
                    solicitud=solicitud,
                    observacion=f"Liberado: todos los expedientes rechazados. Motivo: {motivo_rechazo_general}"
                )

            Prestamo.objects.create(
                solicitud=solicitud,
                admin_aprobador=request.user,
                motivo_rechazo=motivo_rechazo_general,
                estado='Cerrado'
            )

            _registrar_log(
                request.user, 'SOLICITUD_RECHAZADA',
                f'Solicitud #{solicitud.id} rechazada (todos los expedientes rechazados individualmente). Motivo: {motivo_rechazo_general}',
                'SolicitudPrestamo', solicitud.id
            )
            return JsonResponse({"success": True, "todos_rechazados": True})

        # Al menos un expediente aprobado: continuar con la solicitud
        solicitud.estado_flujo_id = 'SOL_APROBADA_ORGANIZANDO'
        solicitud.save()

        # Aprobados → EXP_APARTADO
        for d in aprobados:
            if d.expediente_prestamo.estado_id != 'EXP_APARTADO':
                estado_ant = d.expediente_prestamo.estado
                d.expediente_prestamo.estado_id = 'EXP_APARTADO'
                d.expediente_prestamo.save()
                ExpedienteEstadoLog.objects.create(
                    expediente=d.expediente_prestamo.expediente,
                    estado_anterior=estado_ant,
                    estado_nuevo_id='EXP_APARTADO',
                    usuario=request.user,
                    solicitud=solicitud,
                    observacion="Apartado al aprobar solicitud"
                )

        # Rechazados → EXP_DISPONIBLE
        for d in rechazados:
            ep = d.expediente_prestamo
            estado_ant = ep.estado
            ep.estado_id = 'EXP_DISPONIBLE'
            ep.save()
            ExpedienteEstadoLog.objects.create(
                expediente=ep.expediente,
                estado_anterior=estado_ant,
                estado_nuevo_id='EXP_DISPONIBLE',
                usuario=request.user,
                solicitud=solicitud,
                observacion=f"No se prestará en esta solicitud. Motivo: {motivo_rechazo_general}"
            )

        prestamo = Prestamo.objects.create(
            solicitud=solicitud,
            admin_aprobador=request.user,
            comentarios=comentarios,
            tiempo_limite_horas=int(tiempo_limite),
            es_minutos=es_minutos,
            estado='Activo'
        )

        detalle_rechazo = f" ({len(rechazados)} expediente(s) rechazado(s))" if rechazados else ""
        _registrar_log(
            request.user, 'SOLICITUD_APROBADA',
            f'Solicitud #{solicitud.id} aprobada{detalle_rechazo}. En proceso de organización.',
            'Prestamo', prestamo.id
        )

        logger.info(f"Solicitud #{solicitud.id} aprobada por {request.user.username}")
        return JsonResponse({"success": True, "todos_rechazados": False, "prestamo_id": prestamo.id})

    except Exception as e:
        logger.error(f"Error en aprobar_solicitud_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@require_GET
def expedientes_solicitud_api(request, solicitud_id):
    """Retorna los expedientes de una solicitud pendiente para el modal de aprobación."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        solicitud = SolicitudPrestamo.objects.get(id=solicitud_id, estado_flujo_id='SOL_PENDIENTE')
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada o ya procesada"}, status=404)

    try:
        expedientes = []
        for d in solicitud.detalles.select_related('expediente_prestamo__expediente'):
            expedientes.append({
                "detalle_id": d.id,
                "numero": d.expediente_prestamo.expediente.numero,
                "paciente_nombre": d.paciente_nombre or "",
                "paciente_identidad": d.paciente_identidad or "",
                "estado_fisico": d.expediente_prestamo.estado_id,
            })
        return JsonResponse({"expedientes": expedientes})
    except Exception as e:
        logger.error(f"Error en expedientes_solicitud_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@require_GET
def imprimir_solicitud_pdf(request, solicitud_id):
    """Genera y descarga el PDF de una solicitud (aprobada/organizando/listo/prestamo/devolucion/finalizada)."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    estados_permitidos = {
        'SOL_APROBADA_ORGANIZANDO', 'SOL_LISTO_RECOGER',
        'SOL_EN_PRESTAMO', 'SOL_EN_DEVOLUCION',
        'SOL_FINALIZADA', 'SOL_INCOMPLETA',
    }
    try:
        solicitud = SolicitudPrestamo.objects.select_related(
            'usuario', 'motivo', 'prestamo', 'prestamo__admin_aprobador'
        ).get(id=solicitud_id)
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada"}, status=404)

    if solicitud.estado_flujo_id not in estados_permitidos:
        return JsonResponse({"error": "La solicitud no está en un estado imprimible"}, status=400)

    try:
        from s_exp.services.pdf_solicitud_service import generar_pdf_solicitud
        pdf_bytes = generar_pdf_solicitud(solicitud)
    except Exception as e:
        logger.error(f"Error generando PDF solicitud {solicitud_id}: {e}", exc_info=True)
        return JsonResponse({"error": "Error al generar el PDF"}, status=500)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="solicitud_{solicitud.id}.pdf"'
    return response


@csrf_protect
@require_POST
def marcar_listo_recojer_api(request):
    """Admin marca que los expedientes ya están organizados físicamente y listos en ventanilla."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
        solicitud_id = body.get('solicitud_id')
        
        solicitud = SolicitudPrestamo.objects.get(id=solicitud_id, estado_flujo_id='SOL_APROBADA_ORGANIZANDO')
        solicitud.estado_flujo_id = 'SOL_LISTO_RECOGER'
        solicitud.save()

        _registrar_log(
            request.user, 'SOLICITUD_LISTA',
            f'Solicitud #{solicitud.id} marcada como lista para recoger.',
            'SolicitudPrestamo', solicitud.id
        )

        return JsonResponse({"success": True})
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada o no está en proceso de organización"}, status=404)
    except Exception as e:
        logger.error(f"Error en marcar_listo_recojer_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def rechazar_solicitud_api(request):
    """
    Rechaza una solicitud de préstamo pendiente.
    Libera automáticamente los expedientes que estaban apartados (EXP_APARTADO -> EXP_DISPONIBLE).
    
    Body JSON:
        solicitud_id (int): ID de la solicitud a rechazar.
        motivo (str): Razón del rechazo.
    """
    """Rechaza una solicitud con motivo obligatorio."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    solicitud_id = body.get('solicitud_id')
    motivo_rechazo = body.get('motivo_rechazo', '').strip()

    if not motivo_rechazo:
        return JsonResponse({"error": "El motivo de rechazo es obligatorio"}, status=400)

    try:
        solicitud = SolicitudPrestamo.objects.get(id=solicitud_id, estado_flujo_id='SOL_PENDIENTE')
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada o ya procesada"}, status=404)

    try:
        solicitud.estado_flujo_id = 'SOL_RECHAZADA'
        solicitud.save()

        # Liberar expedientes: volver a ponerlos disponibles
        from .models import ExpedienteEstadoLog
        for detalle in solicitud.detalles.select_related('expediente_prestamo'):
            ep = detalle.expediente_prestamo
            estado_anterior = ep.estado
            ep.estado_id = 'EXP_DISPONIBLE'
            ep.save()

            ExpedienteEstadoLog.objects.create(
                expediente=ep.expediente,
                estado_anterior=estado_anterior,
                estado_nuevo_id='EXP_DISPONIBLE',
                usuario=request.user,
                solicitud=solicitud,
                observacion=f"Expediente liberado por rechazo de solicitud. Motivo: {motivo_rechazo}"
            )

        Prestamo.objects.create(
            solicitud=solicitud,
            admin_aprobador=request.user,
            motivo_rechazo=motivo_rechazo,
            estado='Cerrado'
        )

        _registrar_log(
            request.user, 'SOLICITUD_RECHAZADA',
            f'Solicitud #{solicitud.id} rechazada. Motivo: {motivo_rechazo}',
            'SolicitudPrestamo', solicitud.id
        )

        logger.info(f"Solicitud #{solicitud.id} rechazada por {request.user.username}")
        return JsonResponse({"success": True})

    except Exception as e:
        logger.error(f"Error en rechazar_solicitud_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# ============================================
# APIs ADMIN - Monitoreo de Préstamos
# ============================================

@require_GET
def prestamos_activos_api(request):
    """Lista préstamos activos/entregados para monitoreo con DataTables server-side."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        draw = int(request.GET.get('draw', 0))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 10))
        search_value = request.GET.get('search[value]', '').strip()
        estado_filtro = request.GET.get('estado', '')

        qs = Prestamo.objects.select_related(
            'solicitud__usuario', 'solicitud__motivo'
        ).filter(
            estado__in=['Activo', 'Entregado', 'Vencido', 'DevolucionParcial', 'DevueltoVencido']
        )

        if estado_filtro:
            qs = qs.filter(estado=estado_filtro)

        if search_value:
            qs = qs.filter(
                Q(solicitud__usuario__username__icontains=search_value) |
                Q(id__icontains=search_value) |
                Q(solicitud__usuario__first_name__icontains=search_value) |
                Q(solicitud__usuario__last_name__icontains=search_value)
            )

        total_records = Prestamo.objects.filter(
            estado__in=['Activo', 'Entregado', 'Vencido', 'DevolucionParcial', 'DevueltoVencido']
        ).count()
        filtered_records = qs.count()

        prestamos = qs.order_by('-fecha_aprobacion')[start:start + length]

        data = []
        for p in prestamos:
            numeros = list(
                p.solicitud.detalles.select_related('expediente_prestamo__expediente')
                .filter(aprobado=True)
                .values_list('expediente_prestamo__expediente__numero', flat=True)
            )

            data.append({
                "id": p.id,
                "solicitud_id": p.solicitud.id,
                "usuario": p.solicitud.usuario.username,
                "usuario_nombre": f"{p.solicitud.usuario.first_name} {p.solicitud.usuario.last_name}".strip() or p.solicitud.usuario.username,
                "area_destino": p.solicitud.area_destino or "",
                "motivo": str(p.solicitud.motivo.nombre) if p.solicitud.motivo else "",
                "estado": p.estado,
                "fecha_aprobacion": p.fecha_aprobacion.strftime("%d/%m/%Y %H:%M"),
                "fecha_entrega": p.fecha_entrega.strftime("%d/%m/%Y %H:%M") if p.fecha_entrega else None,
                "fecha_limite": p.fecha_limite.isoformat() if p.fecha_limite else None,
                "tiempo_limite_horas": p.tiempo_limite_horas,
                "tiempo_restante_segundos": p.tiempo_restante_segundos,
                "porcentaje_tiempo_usado": p.porcentaje_tiempo_usado,
                "esta_vencido": p.esta_vencido,
                "expedientes": numeros,
                "cant_expedientes": len(numeros),
                "solicitud_estado_flujo": p.solicitud.estado_flujo_id,
            })

        return JsonResponse({
            "draw": draw,
            "recordsTotal": total_records,
            "recordsFiltered": filtered_records,
            "data": data
        })

    except Exception as e:
        logger.error(f"Error en prestamos_activos_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def marcar_entregado_api(request):
    """Marca un préstamo como entregado e inicia el cronómetro."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    prestamo_id = body.get('prestamo_id')

    try:
        prestamo = Prestamo.objects.get(id=prestamo_id, estado='Activo')
        if prestamo.solicitud.estado_flujo_id != 'SOL_LISTO_RECOGER':
             return JsonResponse({"error": "La solicitud debe estar marcada como 'Listo para recoger' antes de entregar."}, status=400)
    except Prestamo.DoesNotExist:
        return JsonResponse({"error": "Préstamo no encontrado o no está en estado Activo"}, status=404)

    try:
        ahora = timezone.now()
        prestamo.fecha_entrega = ahora
        
        # Lógica de vencimiento flexible (Pruebas vs Producción)
        if prestamo.es_minutos:
            # Si el préstamo se configuró en minutos (para pruebas)
            prestamo.fecha_limite = ahora + timedelta(minutes=prestamo.tiempo_limite_horas)
        else:
            # Configuración estándar en horas
            prestamo.fecha_limite = ahora + timedelta(hours=prestamo.tiempo_limite_horas)
            
        prestamo.estado = 'Entregado'
        prestamo.save()

        prestamo.solicitud.estado_flujo_id = 'SOL_EN_PRESTAMO'
        prestamo.solicitud.save()

        # Solo marcar como prestados los expedientes aprobados
        from .models import ExpedienteEstadoLog
        for d in prestamo.solicitud.detalles.select_related('expediente_prestamo').filter(aprobado=True):
            estado_anterior = d.expediente_prestamo.estado
            d.expediente_prestamo.estado_id = 'EXP_PRESTADO'
            d.expediente_prestamo.save()

            ExpedienteEstadoLog.objects.create(
                expediente=d.expediente_prestamo.expediente,
                estado_anterior=estado_anterior,
                estado_nuevo_id='EXP_PRESTADO',
                usuario=request.user,
                solicitud=prestamo.solicitud
            )

        _registrar_log(
            request.user, 'PRESTAMO_ENTREGADO',
            f'Préstamo #{prestamo.id} entregado. Cronómetro iniciado: {prestamo.tiempo_limite_horas}h.',
            'Prestamo', prestamo.id
        )

        logger.info(f"Préstamo #{prestamo.id} entregado por {request.user.username}")
        return JsonResponse({
            "success": True,
            "fecha_entrega": ahora.strftime("%d/%m/%Y %H:%M"),
            "fecha_limite": prestamo.fecha_limite.isoformat(),
        })

    except Exception as e:
        logger.error(f"Error en marcar_entregado_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# ============================================
# APIs ADMIN - Control de Devoluciones
# ============================================

@require_GET
def prestamos_para_devolucion_api(request):
    """Lista préstamos que están pendientes de devolución."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        # Mostrar solicitudes marcadas para devolución O con devoluciones incompletas pendientes
        qs = Prestamo.objects.select_related('solicitud__usuario').filter(
            solicitud__estado_flujo_id='SOL_EN_DEVOLUCION',
            estado__in=['Entregado', 'Vencido', 'DevolucionParcial']
        ).order_by('fecha_limite')

        data = []
        for p in qs:
            detalles = []
            for d in p.solicitud.detalles.select_related('expediente_prestamo__expediente').filter(aprobado=True, devuelto=False):
                detalles.append({
                    "id": d.id,
                    "numero": d.expediente_prestamo.expediente.numero,
                    "estado_fisico": d.expediente_prestamo.estado.nombre
                })

            data.append({
                "id": p.id,
                "solicitud_id": p.solicitud.id,
                "usuario": p.solicitud.usuario.username,
                "usuario_nombre": f"{p.solicitud.usuario.first_name} {p.solicitud.usuario.last_name}".strip() or p.solicitud.usuario.username,
                "estado": p.estado,
                "detalles_expedientes": detalles,
                "cant_expedientes": p.solicitud.detalles.filter(aprobado=True).count(),
                "cant_devueltos": p.solicitud.detalles.filter(aprobado=True, devuelto=True).count(),
                "fecha_limite": p.fecha_limite.isoformat() if p.fecha_limite else None,
                "esta_vencido": p.esta_vencido,
            })

        return JsonResponse({"data": data})

    except Exception as e:
        logger.error(f"Error en prestamos_para_devolucion_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def solicitar_devolucion_api(request):
    """El personal (usuario) marca que ya no usará los expedientes y los devuelve al archivo."""
    if not request.user.is_authenticated:
         return JsonResponse({"error": "No autenticado"}, status=401)
    
    try:
        body = json.loads(request.body)
        solicitud_id = body.get('solicitud_id')
        
        # El usuario puede devolver si está en préstamo o si fue incompleta (quedan pendientes)
        solicitud = SolicitudPrestamo.objects.get(
            id=solicitud_id, 
            usuario=request.user, 
            estado_flujo_id__in=['SOL_EN_PRESTAMO', 'SOL_INCOMPLETA']
        )
        
        solicitud.estado_flujo_id = 'SOL_EN_DEVOLUCION'
        solicitud.save()

        _registrar_log(
            request.user, 'SOLICITUD_DEVOLUCION_INICIADA',
            f'Usuario marcó solicitud #{solicitud.id} para devolución.',
            'SolicitudPrestamo', solicitud.id
        )

        return JsonResponse({"success": True})
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada o no está en préstamo"}, status=404)
    except Exception as e:
        logger.error(f"Error en solicitar_devolucion_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def procesar_devolucion_api(request):
    """Admin audita los expedientes recibidos. Marca cuáles llegaron y cuáles se perdieron."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
        prestamo_id = body.get('prestamo_id')
        detalles_recibidos = body.get('detalles_recibidos', []) 
        detalles_perdidos = body.get('detalles_perdidos', [])   
        detalles_no_recibidos = body.get('detalles_no_recibidos', []) 
        notas = body.get('notas', '')

        prestamo = Prestamo.objects.get(id=prestamo_id)
        solicitud = prestamo.solicitud
        
        from .models import ExpedienteEstadoLog
        
        # 1. Procesar los que llegaron (Disponibles)
        esta_vencido = prestamo.esta_vencido
        unidad_usuario = _get_unidad_usuario(request.user)

        for det_id in detalles_recibidos:
            detalle = SolicitudExpedienteDetalle.objects.get(id=det_id, solicitud=solicitud)
            if not detalle.devuelto:
                detalle.devuelto = True
                if esta_vencido:
                    detalle.fuera_de_tiempo = True
                detalle.save()
                
                ep = detalle.expediente_prestamo
                estado_ant = ep.estado
                ep.estado_id = 'EXP_DISPONIBLE'
                ep.ubicacion_fisica = unidad_usuario
                ep.save()
                
                ExpedienteEstadoLog.objects.create(
                    expediente=ep.expediente,
                    estado_anterior=estado_ant,
                    estado_nuevo_id='EXP_DISPONIBLE',
                    usuario=request.user,
                    solicitud=solicitud,
                    observacion="Devuelto correctamente" + (" (Fuera de tiempo)" if esta_vencido else "")
                )

        # 2. Procesar los perdidos (Cuentan como procesados/cerrados para la solicitud)
        for det_id in detalles_perdidos:
            detalle = SolicitudExpedienteDetalle.objects.get(id=det_id, solicitud=solicitud)
            if not detalle.devuelto:
                detalle.devuelto = True # Se marca como procesado
                detalle.save()
                
                ep = detalle.expediente_prestamo
                estado_ant = ep.estado
                ep.estado_id = 'EXP_PERDIDO'
                ep.save()
                
                ExpedienteEstadoLog.objects.create(
                    expediente=ep.expediente,
                    estado_anterior=estado_ant,
                    estado_nuevo_id='EXP_PERDIDO',
                    usuario=request.user,
                    solicitud=solicitud,
                    observacion="Marcado como perdido durante auditoría"
                )

        # 3. Procesar los NO recibidos (Siguen pendientes)
        for det_id in detalles_no_recibidos:
            detalle = SolicitudExpedienteDetalle.objects.get(id=det_id, solicitud=solicitud)
            ep = detalle.expediente_prestamo
            ExpedienteEstadoLog.objects.create(
                expediente=ep.expediente,
                estado_anterior=ep.estado,
                estado_nuevo_id='EXP_PRESTADO',
                usuario=request.user,
                solicitud=solicitud,
                observacion="Auditado como NO RECIBIDO (Sigue en préstamo)"
            )

        # 4. Determinar estado final de la solicitud (solo expedientes aprobados cuentan)
        total_exp = solicitud.detalles.filter(aprobado=True).count()
        devueltos_ahora = solicitud.detalles.filter(aprobado=True, devuelto=True).count()
        hay_no_recibidos = len(detalles_no_recibidos) > 0
        
        if devueltos_ahora >= total_exp and not hay_no_recibidos:
            # Todo procesado: ver si fue vencido
            if prestamo.esta_vencido:
                solicitud.estado_flujo_id = 'SOL_FINALIZADA'
                prestamo.estado = 'DevueltoVencido'
            else:
                solicitud.estado_flujo_id = 'SOL_FINALIZADA'
                prestamo.estado = 'Cerrado'
            prestamo.fecha_devolucion_real = timezone.now()
        else:
            # Faltan expedientes (no_recibidos pendientes)
            solicitud.estado_flujo_id = 'SOL_INCOMPLETA'
            prestamo.estado = 'DevolucionParcial'
            
        solicitud.save()
        prestamo.save()

        # Registrar devolución parcial
        Devolucion.objects.create(
            prestamo=prestamo,
            cantidad_esperada=total_exp,
            cantidad_recibida=devueltos_ahora,
            estado='Completa' if devueltos_ahora >= total_exp and not hay_no_recibidos else 'Incompleta',
            notas_admin=notas
        )

        return JsonResponse({"success": True, "estado": solicitud.estado_flujo_id})

    except Exception as e:
        logger.error(f"Error en procesar_devolucion_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)

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

        from expediente.models import Expediente, PacienteAsignacion
        from paciente.models import Paciente

        # IDs de expedientes no disponibles (Cualquier estado que no sea disponible)
        from .models import SolicitudExpedienteDetalle
        expedientes_no_disponibles = set(
            ExpedientePrestamo.objects.exclude(estado_id='EXP_DISPONIBLE')
            .values_list('expediente_id', flat=True)
        )
        # También las solicitudes activas que podrían no haber actualizado el estado físico aún
        en_proceso = set(
            SolicitudExpedienteDetalle.objects.filter(
                solicitud__estado_flujo_id__in=['SOL_PENDIENTE', 'SOL_APROBADA_ORGANIZANDO', 'SOL_LISTO_RECOGER', 'SOL_EN_PRESTAMO', 'SOL_EN_DEVOLUCION', 'SOL_INCOMPLETA'],
                devuelto=False
            ).values_list('expediente_prestamo__expediente_id', flat=True)
        )
        expedientes_prestados_ids = expedientes_no_disponibles | en_proceso

        resultados = []

        if tipo == 'expediente':
            # Buscar por número de expediente  — Top 5 resultados
            expedientes_encontrados = set()
            try:
                numero_int = int(query.lstrip("0") or "0")
                for exp in Expediente.objects.filter(numero=numero_int)[:5]:
                    expedientes_encontrados.add(exp.id)
            except ValueError:
                pass

            pacientes_por_exp = Paciente.objects.filter(expediente_numero__icontains=query)[:5]
            for pac in pacientes_por_exp:
                asig = PacienteAsignacion.objects.filter(paciente=pac).select_related('expediente').first()
                if asig:
                    expedientes_encontrados.add(asig.expediente.id)

            for exp in Expediente.objects.filter(id__in=expedientes_encontrados)[:5]:
                asignacion = PacienteAsignacion.objects.filter(expediente=exp).select_related('paciente').order_by('-estado').first()
                paciente_nombre = ""
                paciente_dni = ""
                if asignacion:
                    p = asignacion.paciente
                    paciente_nombre = f"{p.primer_nombre} {p.segundo_nombre or ''} {p.primer_apellido} {p.segundo_apellido or ''}".strip()
                    paciente_dni = p.dni or ""

                disponible = exp.id not in expedientes_prestados_ids
                info_exp = ExpedientePrestamo.objects.filter(expediente=exp).first()
                ubicacion = info_exp.ubicacion_fisica if info_exp and info_exp.ubicacion_fisica else "Archivo Central"

                resultados.append({
                    "expediente_id": exp.id,
                    "numero_expediente": exp.numero,
                    "paciente_nombre": paciente_nombre,
                    "paciente_dni": paciente_dni,
                    "disponible": disponible,
                    "ubicacion_fisica": ubicacion,
                })

        elif tipo == 'identidad':
            query_limpio = query.replace("-", "").replace(" ", "")
            pacientes = Paciente.objects.filter(dni__icontains=query_limpio, estado='A')[:5]
            for pac in pacientes:
                asignaciones = PacienteAsignacion.objects.filter(paciente=pac, estado='1').select_related('expediente')
                for asig in asignaciones:
                    exp = asig.expediente
                    disponible = exp.id not in expedientes_prestados_ids
                    paciente_nombre = f"{pac.primer_nombre} {pac.segundo_nombre or ''} {pac.primer_apellido} {pac.segundo_apellido or ''}".strip()
                    
                    info_exp = ExpedientePrestamo.objects.filter(expediente=exp).first()
                    ubicacion = info_exp.ubicacion_fisica if info_exp and info_exp.ubicacion_fisica else "Archivo Central"

                    resultados.append({
                        "expediente_id": exp.id,
                        "numero_expediente": exp.numero,
                        "paciente_nombre": paciente_nombre,
                        "paciente_dni": pac.dni or "",
                        "disponible": disponible,
                        "ubicacion_fisica": ubicacion,
                    })
                    if len(resultados) >= 5:
                        break
                if len(resultados) >= 5:
                    break

        elif tipo == 'nombre':
            palabras = query.split()
            filtro = Q(estado='A')
            for palabra in palabras:
                filtro &= (Q(primer_nombre__icontains=palabra) | Q(segundo_nombre__icontains=palabra) | Q(primer_apellido__icontains=palabra) | Q(segundo_apellido__icontains=palabra))
            pacientes = Paciente.objects.filter(filtro)[:5]
            for pac in pacientes:
                asignaciones = PacienteAsignacion.objects.filter(paciente=pac, estado='1').select_related('expediente')
                for asig in asignaciones:
                    exp = asig.expediente
                    disponible = exp.id not in expedientes_prestados_ids
                    paciente_nombre = f"{pac.primer_nombre} {pac.segundo_nombre or ''} {pac.primer_apellido} {pac.segundo_apellido or ''}".strip()
                    
                    info_exp = ExpedientePrestamo.objects.filter(expediente=exp).first()
                    ubicacion = info_exp.ubicacion_fisica if info_exp and info_exp.ubicacion_fisica else "Archivo Central"

                    resultados.append({
                        "expediente_id": exp.id,
                        "numero_expediente": exp.numero,
                        "paciente_nombre": paciente_nombre,
                        "paciente_dni": pac.dni or "",
                        "disponible": disponible,
                        "ubicacion_fisica": ubicacion,
                    })
                    if len(resultados) >= 5:
                        break
                if len(resultados) >= 5:
                    break

        return JsonResponse({"data": resultados})

    except Exception as e:
        logger.error(f"Error en buscar_expedientes_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def crear_solicitud_api(request):
    """
    Crea una nueva solicitud de préstamo iniciada por un usuario del sistema.
    Verifica la disponibilidad física de los expedientes antes de permitir la creación.
    """
    """Crea una solicitud de préstamo con múltiples expedientes (carrito)."""
    if not _es_exp_solicitante(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    expediente_ids = body.get('expedientes', [])  # lista de expediente IDs (de tabla Expediente)
    motivo_id = body.get('motivo_id')
    observaciones = body.get('observaciones', '').strip()

    if not expediente_ids:
        return JsonResponse({"error": "Debe seleccionar al menos un expediente"}, status=400)
    if not motivo_id:
        return JsonResponse({"error": "El motivo es obligatorio"}, status=400)

    # Validar motivo
    try:
        motivo = MotivoSolicitud.objects.get(id=motivo_id, activo=True)
    except MotivoSolicitud.DoesNotExist:
        return JsonResponse({"error": "Motivo no válido"}, status=400)

    # Auto-asignar unidad del usuario
    area_destino = _get_unidad_usuario(request.user)

    try:
        from expediente.models import Expediente, PacienteAsignacion

        # Verificar que existan y no estén prestados o en proceso
        from .models import SolicitudExpedienteDetalle
        prestados = set(
            ExpedientePrestamo.objects.filter(estado_id='EXP_PRESTADO')
            .values_list('expediente_id', flat=True)
        )
        en_proceso = set(
            SolicitudExpedienteDetalle.objects.filter(
                solicitud__estado_flujo_id__in=['SOL_PENDIENTE', 'SOL_APROBADA_ORGANIZANDO']
            ).values_list('expediente_prestamo__expediente_id', flat=True)
        )
        expedientes_prestados_ids = prestados | en_proceso

        expedientes = Expediente.objects.filter(id__in=expediente_ids)
        if expedientes.count() != len(expediente_ids):
            return JsonResponse({"error": "Algunos expedientes no fueron encontrados"}, status=400)

        for exp in expedientes:
            if exp.id in expedientes_prestados_ids:
                return JsonResponse({
                    "error": f"El expediente #{exp.numero} ya no está disponible"
                }, status=400)

        # Crear solicitud
        solicitud = SolicitudPrestamo.objects.create(
            usuario=request.user,
            motivo=motivo,
            observaciones=observaciones or None,
            area_destino=area_destino or None,
        )

        # Crear detalles con datos históricos
        for exp in expedientes:
            # Obtener o crear ExpedientePrestamo
            ep, created_ep = ExpedientePrestamo.objects.get_or_create(
                expediente=exp,
                defaults={'estado_id': 'EXP_APARTADO'}
            )
            if not created_ep:
                estado_anterior = ep.estado
                ep.estado_id = 'EXP_APARTADO'
                ep.save()
                
                # Log transaccional para el apartado
                from .models import ExpedienteEstadoLog
                ExpedienteEstadoLog.objects.create(
                    expediente=exp,
                    estado_anterior=estado_anterior,
                    estado_nuevo_id='EXP_APARTADO',
                    usuario=request.user,
                    solicitud=solicitud,
                    observacion="Expediente apartado por solicitud"
                )
            else:
                # Log para creación inicial
                from .models import ExpedienteEstadoLog
                ExpedienteEstadoLog.objects.create(
                    expediente=exp,
                    estado_anterior=None,
                    estado_nuevo_id='EXP_APARTADO',
                    usuario=request.user,
                    solicitud=solicitud
                )

            # Obtener datos del paciente para el snapshot
            asig = PacienteAsignacion.objects.filter(
                expediente=exp, estado='1'
            ).select_related('paciente').first()

            pac_nombre = ""
            pac_dni = ""
            if asig:
                p = asig.paciente
                pac_nombre = f"{p.primer_nombre} {p.segundo_nombre or ''} {p.primer_apellido} {p.segundo_apellido or ''}".strip()
                pac_dni = p.dni or ""

            SolicitudExpedienteDetalle.objects.create(
                solicitud=solicitud,
                expediente_prestamo=ep,
                paciente_identidad=pac_dni,
                paciente_nombre=pac_nombre,
                numero_expediente=exp.numero,
            )

        _registrar_log(
            request.user, 'SOLICITUD_CREADA',
            f'Solicitud #{solicitud.id} creada con {expedientes.count()} expedientes.',
            'SolicitudPrestamo', solicitud.id
        )

        logger.info(f"Solicitud #{solicitud.id} creada por {request.user.username}")
        return JsonResponse({
            "success": True,
            "solicitud_id": solicitud.id,
            "mensaje": f"Solicitud #{solicitud.id} creada exitosamente con {expedientes.count()} expediente(s)."
        })

    except Exception as e:
        logger.error(f"Error en crear_solicitud_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# ============================================
# APIs USUARIO - Seguimiento
# ============================================

@require_GET
def mis_solicitudes_api(request):
    """
    Lista las solicitudes del usuario actual con filtros opcionales de fecha.
    
    Query Params:
        filtro (str): 'hoy', 'semana', 'mes', 'rango' o '' para todas.
        fecha_inicio (str): Fecha inicio en formato YYYY-MM-DD (aplica con filtro='rango').
        fecha_fin (str): Fecha fin en formato YYYY-MM-DD (aplica con filtro='rango').
    """
    if not _es_exp_solicitante(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        qs = SolicitudPrestamo.objects.filter(
            usuario=request.user
        ).order_by('-fecha_creacion')

        # --- Aplicar filtros de fecha (mismo patrón que reportes del módulo) ---
        filtro = request.GET.get('filtro', '').strip()
        from datetime import date as date_type
        hoy = date_type.today()

        if filtro == 'hoy':
            qs = qs.filter(
                fecha_creacion__gte=str(hoy),
                fecha_creacion__lte=str(hoy) + ' 23:59:59'
            )
        elif filtro == 'semana':
            inicio_semana = hoy - timedelta(days=hoy.weekday())  # Lunes
            fin_semana = inicio_semana + timedelta(days=6)        # Domingo
            qs = qs.filter(
                fecha_creacion__gte=str(inicio_semana),
                fecha_creacion__lte=str(fin_semana) + ' 23:59:59'
            )
        elif filtro == 'mes':
            import calendar
            ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
            inicio_mes = str(hoy.replace(day=1))
            fin_mes = str(hoy.replace(day=ultimo_dia))
            qs = qs.filter(
                fecha_creacion__gte=inicio_mes,
                fecha_creacion__lte=fin_mes + ' 23:59:59'
            )
        elif filtro == 'rango':
            fecha_inicio_str = request.GET.get('fecha_inicio', '').strip()
            fecha_fin_str = request.GET.get('fecha_fin', '').strip()
            if fecha_inicio_str:
                qs = qs.filter(fecha_creacion__gte=fecha_inicio_str)
            if fecha_fin_str:
                qs = qs.filter(fecha_creacion__lte=fecha_fin_str + ' 23:59:59')
        # Si filtro está vacío retorna todas las solicitudes
        data = []
        for s in qs:
            # Obtener expedientes y su estado de entrega
            detalles_info = []
            for d in s.detalles.select_related('expediente_prestamo__expediente'):
                detalles_info.append({
                    "numero": d.expediente_prestamo.expediente.numero,
                    "devuelto": d.devuelto,
                    "fuera_de_tiempo": d.fuera_de_tiempo,
                    "aprobado": d.aprobado,
                    "motivo_rechazo_individual": d.motivo_rechazo_individual or "",
                })

            prestamo_info = None
            try:
                p = s.prestamo
                prestamo_info = {
                    "id": p.id,
                    "estado": p.estado,
                    "fecha_entrega": p.fecha_entrega.strftime("%d/%m/%Y %H:%M") if p.fecha_entrega else None,
                    "fecha_limite": p.fecha_limite.isoformat() if p.fecha_limite else None,
                    "tiempo_restante_segundos": p.tiempo_restante_segundos,
                    "porcentaje_tiempo_usado": p.porcentaje_tiempo_usado,
                    "esta_vencido": p.esta_vencido,
                    "motivo_rechazo": p.motivo_rechazo or "",
                    "comentarios": p.comentarios or "",
                }
            except Prestamo.DoesNotExist:
                pass

            data.append({
                "id": s.id,
                "fecha_creacion": s.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
                "estado_flujo": s.estado_flujo_id,
                "estado_flujo_nombre": s.estado_flujo.nombre,
                "motivo": s.motivo.nombre if s.motivo else "",
                "observaciones": s.observaciones or "",
                "area_destino": s.area_destino or "",
                "expedientes": detalles_info,
                "cant_expedientes": len(detalles_info),
                "prestamo": prestamo_info,
            })

        return JsonResponse({"data": data})

    except Exception as e:
        logger.error(f"Error en mis_solicitudes_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# ============================================
# APIs - Alertas
# ============================================

@require_GET
def alertas_usuario_api(request):
    """Retorna alertas para el usuario actual."""
    if not request.user.is_authenticated:
        return JsonResponse({"alertas": []})

    try:
        alertas = []

        # Alertas para solicitantes: préstamos a punto de vencer
        prestamos_usuario = Prestamo.objects.filter(
            solicitud__usuario=request.user,
            estado='Entregado'
        )

        for p in prestamos_usuario:
            if p.esta_vencido:
                alertas.append({
                    "tipo": "danger",
                    "titulo": "Préstamo Vencido",
                    "mensaje": f"El préstamo #{p.id} ha superado el límite de tiempo. Devuelva los expedientes de inmediato.",
                    "prestamo_id": p.id,
                })
            elif p.porcentaje_tiempo_usado >= 90:
                alertas.append({
                    "tipo": "warning",
                    "titulo": "Préstamo por Vencer",
                    "mensaje": f"El préstamo #{p.id} está próximo a vencer. Considere devolver los expedientes.",
                    "prestamo_id": p.id,
                })

        # Alertas de Vencimiento Recurrentes (Sticky cada 5 min)
        prestamos_vencidos = Prestamo.objects.filter(
            solicitud__usuario=request.user,
            estado='Vencido'
        )
        ahora = timezone.now()
        for p in prestamos_vencidos:
            reaparecer = False
            if not p.alerta_vencimiento_leida_at:
                reaparecer = True
            else:
                diferencia = ahora - p.alerta_vencimiento_leida_at
                if diferencia.total_seconds() > 300:  # 5 min
                    reaparecer = True
            
            if reaparecer:
                alertas.append({
                    "tipo": "danger",
                    "titulo": "¡PRÉSTAMO VENCIDO!",
                    "mensaje": f"El préstamo #{p.id} está vencido. Por favor devuelva los expedientes.",
                    "prestamo_id": p.id,
                    "sticky": True,
                    "tipo_alerta": "vencimiento"
                })

        # Solicitudes aprobadas listas para retirar (Persistentes hasta que el usuario las acepte)
        solicitudes_aprobadas = SolicitudPrestamo.objects.filter(
            usuario=request.user,
            estado_flujo_id='SOL_LISTO_RECOGER',
            notificado_listo=False
        )
        for s in solicitudes_aprobadas:
            alertas.append({
                "tipo": "success",
                "titulo": "¡Listo para recoger!",
                "mensaje": "Sus expedientes ya estan listos para recoger.",
                "solicitud_id": s.id,
                "sticky": True
            })

        # Solicitudes rechazadas recientes
        solicitudes_rechazadas = SolicitudPrestamo.objects.filter(

            usuario=request.user,
            estado_flujo_id='SOL_RECHAZADA'
        ).order_by('-fecha_creacion')[:5]
        for s in solicitudes_rechazadas:
            try:
                motivo = s.prestamo.motivo_rechazo or "Sin motivo especificado"
            except Prestamo.DoesNotExist:
                motivo = "Sin motivo especificado"
            alertas.append({
                "tipo": "danger",
                "titulo": "Solicitud Rechazada",
                "mensaje": f"Su solicitud #{s.id} fue rechazada. Motivo: {motivo}",
                "solicitud_id": s.id,
            })

        return JsonResponse({"alertas": alertas})

    except Exception as e:
        logger.error(f"Error en alertas_usuario_api: {e}", exc_info=True)
        return JsonResponse({"alertas": []})


@csrf_exempt
@require_POST
def marcar_notificacion_leida_api(request):
    """Marca una notificación de 'Listo para recoger' como leída por el usuario."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)

    try:
        import json
        body = json.loads(request.body)
        solicitud_id = body.get('solicitud_id')

        if not solicitud_id:
            return JsonResponse({"error": "Falta ID de solicitud"}, status=400)

        solicitud = SolicitudPrestamo.objects.get(id=solicitud_id, usuario=request.user)
        solicitud.notificado_listo = True
        solicitud.save()

        return JsonResponse({"success": True})

    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada"}, status=404)
    except Exception as e:
        logger.error(f"Error en marcar_notificacion_leida_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno"}, status=500)


@csrf_exempt
@require_POST
def marcar_vencimiento_leido_api(request):
    """Marca una alerta de vencimiento como aceptada temporalmente (5 min)."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)

    try:
        import json
        body = json.loads(request.body)
        prestamo_id = body.get('prestamo_id')

        if not prestamo_id:
            return JsonResponse({"error": "Falta ID de préstamo"}, status=400)

        prestamo = Prestamo.objects.get(id=prestamo_id, solicitud__usuario=request.user)
        prestamo.alerta_vencimiento_leida_at = timezone.now()
        prestamo.save()

        return JsonResponse({"success": True})

    except Prestamo.DoesNotExist:
        return JsonResponse({"error": "Préstamo no encontrado"}, status=404)
    except Exception as e:
        logger.error(f"Error en marcar_vencimiento_leido_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno"}, status=500)


# ============================================
# APIs - Reportes

@require_GET
def reportes_data_api(request):
    """Retorna datos completos para los reportes con filtros de fecha.
    Cuenta solicitudes reales (SolicitudPrestamo) en el período seleccionado.
    """
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        fecha_inicio = request.GET.get('fecha_inicio', '')
        fecha_fin = request.GET.get('fecha_fin', '')

        # Filtros base sobre SolicitudPrestamo.fecha_creacion
        sol_filtros = {}
        if fecha_inicio:
            sol_filtros['fecha_creacion__gte'] = fecha_inicio
        if fecha_fin:
            sol_filtros['fecha_creacion__lte'] = fecha_fin + ' 23:59:59'

        qs_solicitudes = SolicitudPrestamo.objects.filter(**sol_filtros)

        # --- RESUMEN GENERAL ---
        total_solicitudes = qs_solicitudes.count()
        total_expedientes_solicitados = SolicitudExpedienteDetalle.objects.filter(
            solicitud__in=qs_solicitudes
        ).count()
        total_aprobadas = qs_solicitudes.filter(
            estado_flujo_id__in=['SOL_APROBADA_ORGANIZANDO', 'SOL_LISTO_RECOGER',
                                 'SOL_EN_PRESTAMO', 'SOL_EN_DEVOLUCION',
                                 'SOL_FINALIZADA', 'SOL_INCOMPLETA']
        ).count()
        total_rechazadas = qs_solicitudes.filter(
            estado_flujo_id='SOL_RECHAZADA'
        ).count()
        total_pendientes = qs_solicitudes.filter(
            estado_flujo_id='SOL_PENDIENTE'
        ).count()

        # --- DEMANDA POR ÁREA ---
        demanda_area = list(
            qs_solicitudes.values('area_destino').annotate(
                total=Count('id')
            ).order_by('-total')
        )

        # --- MOTIVOS DE USO ---
        motivos = list(
            qs_solicitudes.values(nombre=F('motivo__nombre')).annotate(
                total=Count('id')
            ).order_by('-total')[:10]
        )

        # --- EXPEDIENTE MÁS SOLICITADO ---
        expedientes_top = list(
            SolicitudExpedienteDetalle.objects.filter(
                solicitud__in=qs_solicitudes
            ).values(
                numero=F('expediente_prestamo__expediente__numero')
            ).annotate(
                total=Count('id')
            ).order_by('-total')[:10]
        )

        # --- USUARIOS CON MÁS SOLICITUDES ---
        usuarios_top = list(
            qs_solicitudes.values(
                username=F('usuario__username'),
                nombre_completo=F('usuario__first_name'),
            ).annotate(
                total=Count('id')
            ).order_by('-total')[:10]
        )
        # Construir nombre completo
        for u in usuarios_top:
            u['nombre'] = u.pop('nombre_completo', '') or u['username']

        # --- RECHAZOS CON DETALLE ---
        rechazos_qs = qs_solicitudes.filter(
            estado_flujo_id='SOL_RECHAZADA'
        ).select_related('usuario')
        rechazos = []
        for s in rechazos_qs:
            try:
                motivo_r = s.prestamo.motivo_rechazo or ""
            except Prestamo.DoesNotExist:
                motivo_r = ""
            rechazos.append({
                "solicitud_id": s.id,
                "usuario": s.usuario.username,
                "fecha": s.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
                "motivo_rechazo": motivo_r,
            })

        # --- MOROSIDAD (préstamos vencidos activos) ---
        ahora = timezone.now()
        filtros_prestamo = {}
        if fecha_inicio:
            filtros_prestamo['fecha_aprobacion__gte'] = fecha_inicio
        if fecha_fin:
            filtros_prestamo['fecha_aprobacion__lte'] = fecha_fin + ' 23:59:59'

        morosos = Prestamo.objects.filter(
            estado__in=['Entregado', 'Vencido'],
            fecha_limite__lt=ahora,
            **filtros_prestamo
        ).select_related('solicitud__usuario')

        morosidad = []
        for p in morosos:
            morosidad.append({
                "prestamo_id": p.id,
                "usuario": p.solicitud.usuario.username,
                "area": p.solicitud.area_destino or "",
                "fecha_limite": p.fecha_limite.strftime("%d/%m/%Y %H:%M") if p.fecha_limite else "",
                "dias_vencido": (ahora - p.fecha_limite).days if p.fecha_limite else 0,
            })

        # --- INCONSISTENCIAS (devoluciones parciales) ---
        parciales = Prestamo.objects.filter(
            estado='DevolucionParcial',
            **filtros_prestamo
        ).select_related('solicitud__usuario')

        inconsistencias = []
        for p in parciales:
            total_exp = p.solicitud.detalles.count()
            devueltos = sum(d.cantidad_recibida for d in p.devoluciones.all())
            inconsistencias.append({
                "prestamo_id": p.id,
                "usuario": p.solicitud.usuario.username,
                "total_expedientes": total_exp,
                "devueltos": devueltos,
                "faltantes": total_exp - devueltos,
            })

        return JsonResponse({
            "resumen": {
                "total_solicitudes": total_solicitudes,
                "total_expedientes": total_expedientes_solicitados,
                "aprobadas": total_aprobadas,
                "rechazadas": total_rechazadas,
                "pendientes": total_pendientes,
            },
            "demanda_area": demanda_area,
            "motivos": motivos,
            "expedientes_top": expedientes_top,
            "usuarios_top": usuarios_top,
            "rechazos": rechazos,
            "morosidad": morosidad,
            "inconsistencias": inconsistencias,
        })

    except Exception as e:
        logger.error(f"Error en reportes_data_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)



# ============================================
# API: Catálogo de Motivos
# ============================================

@require_GET
def motivos_api(request):
    """Retorna la lista de motivos activos para el dropdown."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)

    motivos = MotivoSolicitud.objects.filter(activo=True).order_by('nombre')
    data = [{"id": m.id, "nombre": m.nombre} for m in motivos]
    return JsonResponse({"data": data})


# ============================================
# API: Info del usuario (unidad)
# ============================================

@require_GET
def info_usuario_api(request):
    """Retorna información del usuario para el formulario de solicitud."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)

    unidad = _get_unidad_usuario(request.user)
    return JsonResponse({
        "unidad": unidad,
        "es_admin": _es_exp_admin(request.user),
    })


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
            'expediente_prestamo', 'expediente_prestamo__expediente'
        ).order_by('-solicitud__fecha_creacion')

        data = []
        en_prestamo_actual = False

        for d in detalles:
            s = d.solicitud
            estado = s.estado_flujo_id
            if estado in ('SOL_EN_PRESTAMO', 'SOL_APROBADA_ORGANIZANDO') and not d.devuelto:
                en_prestamo_actual = True

            data.append({
                "numero_expediente": d.numero_expediente or d.expediente_prestamo.expediente.numero,
                "fecha_solicitud": s.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
                "motivo": s.motivo.nombre if s.motivo else "",
                "solicitante": f"{s.usuario.first_name} {s.usuario.last_name}".strip() or s.usuario.username,
                "estado": s.estado_flujo.nombre,
                "devuelto": d.devuelto,
                "area_destino": s.area_destino or "",
            })

        return JsonResponse({"data": data, "en_prestamo": en_prestamo_actual})

    except Exception as e:
        logger.error(f"Error en historial_prestamos_paciente_api: {e}", exc_info=True)
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
            'expediente_prestamo', 'expediente_prestamo__expediente'
        ).order_by('-solicitud__fecha_creacion')

        data = []
        en_prestamo_actual = False

        for d in detalles:
            s = d.solicitud
            estado = s.estado_flujo_id
            if estado in ('SOL_EN_PRESTAMO', 'SOL_APROBADA_ORGANIZANDO') and not d.devuelto:
                en_prestamo_actual = True

            data.append({
                "numero_expediente": d.numero_expediente or d.expediente_prestamo.expediente.numero,
                "fecha_solicitud": s.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
                "motivo": s.motivo.nombre if s.motivo else "",
                "solicitante": f"{s.usuario.first_name} {s.usuario.last_name}".strip() or s.usuario.username,
                "estado": s.estado_flujo.nombre,
                "devuelto": d.devuelto,
                "area_destino": s.area_destino or "",
            })

        return JsonResponse({"data": data, "en_prestamo": en_prestamo_actual})

    except Exception as e:
        logger.error(f"Error en historial_prestamos_expediente_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# ============================================
# HISTORIAL DE SOLICITUDES (Admin)
# ============================================

class HistorialSolicitudesView(SExpAdminMixin, TemplateView):
    template_name = 's_exp/historial_solicitudes.html'


@require_GET
def historial_solicitudes_api(request):
    """Lista todas las solicitudes (historico) con paginación server-side."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        draw = int(request.GET.get('draw', 0))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 25))
        search_value = request.GET.get('search[value]', '').strip()
        estado_filtro = request.GET.get('estado', '')

        qs = SolicitudPrestamo.objects.select_related(
            'usuario', 'estado_flujo', 'motivo'
        ).annotate(cant_exp=Count('detalles'))

        if estado_filtro:
            qs = qs.filter(estado_flujo_id=estado_filtro)

        if search_value:
            qs = qs.filter(
                Q(usuario__username__icontains=search_value) |
                Q(usuario__first_name__icontains=search_value) |
                Q(usuario__last_name__icontains=search_value) |
                Q(id__icontains=search_value) |
                Q(motivo__nombre__icontains=search_value)
            )

        total_records = SolicitudPrestamo.objects.count()
        filtered_records = qs.count()
        solicitudes = qs.order_by('-fecha_creacion')[start:start + length]

        data = []
        for s in solicitudes:
            numeros = list(
                s.detalles.values_list('expediente_prestamo__expediente__numero', flat=True)
            )
            # Eventos resumen (incompleta, devuelto fuera de tiempo)
            evento = None
            prestamo = s.prestamos.first()
            if s.estado_flujo_id == 'SOL_INCOMPLETA':
                faltantes = s.detalles.filter(devuelto=False).count()
                evento = f"⚠️ Incompleta: {faltantes} expediente(s) sin devolver"
            elif prestamo and prestamo.estado == 'DevueltoVencido':
                evento = "🕒 Devuelto fuera del tiempo acordado"
            elif s.estado_flujo_id == 'SOL_FINALIZADA':
                evento = "✅ Finalizada correctamente"

            data.append({
                "id": s.id,
                "usuario": s.usuario.username,
                "usuario_nombre": f"{s.usuario.first_name} {s.usuario.last_name}".strip() or s.usuario.username,
                "fecha_creacion": s.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
                "estado_flujo": s.estado_flujo_id,
                "estado_flujo_nombre": s.estado_flujo.nombre,
                "motivo": s.motivo.nombre if s.motivo else "",
                "area_destino": s.area_destino or "",
                "expedientes": numeros,
                "evento_resumen": evento,
            })

        return JsonResponse({
            "draw": draw,
            "recordsTotal": total_records,
            "recordsFiltered": filtered_records,
            "data": data,
        })
    except Exception as e:
        logger.error(f"Error en historial_solicitudes_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@require_GET
def historial_solicitud_detalle_api(request, solicitud_id):
    """Retorna el detalle completo de una solicitud para el modal del historial."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        from .models import ExpedienteEstadoLog
        s = SolicitudPrestamo.objects.select_related(
            'usuario', 'estado_flujo', 'motivo'
        ).get(id=solicitud_id)

        # Expedientes con estado físico actual
        expedientes_data = []
        for d in s.detalles.select_related('expediente_prestamo__expediente', 'expediente_prestamo__estado'):
            ep = d.expediente_prestamo
            expedientes_data.append({
                "numero": ep.expediente.numero,
                "paciente": d.paciente_nombre or "",
                "estado_fisico": ep.estado.nombre if ep.estado else "—",
                "devuelto": d.devuelto,
            })

        # Logs de cambios de estado de expedientes en esta solicitud
        logs = ExpedienteEstadoLog.objects.filter(
            solicitud=s
        ).select_related('usuario', 'estado_anterior', 'estado_nuevo').order_by('fecha')

        logs_data = [{
            "fecha": l.fecha.strftime("%d/%m/%Y %H:%M"),
            "accion": f"Exp #{l.expediente_id}: {l.estado_anterior.nombre if l.estado_anterior else '—'} → {l.estado_nuevo.nombre}",
            "usuario": l.usuario.username,
            "observacion": l.observacion or "",
        } for l in logs]

        prestamo = s.prestamos.first()
        return JsonResponse({"data": {
            "id": s.id,
            "usuario": s.usuario.username,
            "usuario_nombre": f"{s.usuario.first_name} {s.usuario.last_name}".strip() or s.usuario.username,
            "fecha_creacion": s.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
            "estado_flujo": s.estado_flujo_id,
            "estado_flujo_nombre": s.estado_flujo.nombre,
            "motivo": s.motivo.nombre if s.motivo else "",
            "area_destino": s.area_destino or "",
            "expedientes": expedientes_data,
            "logs": logs_data,
            "prestamo": {"id": prestamo.id, "estado": prestamo.estado} if prestamo else None,
        }})
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada"}, status=404)
    except Exception as e:
        logger.error(f"Error en historial_solicitud_detalle_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# ============================================
# EXPORTACIÓN DE REPORTES
# ============================================

def _obtener_datos_reporte_areas_motivos(fecha_inicio='', fecha_fin=''):
    """
    Construye una matriz de áreas (filas) x motivos (columnas) con conteos.
    Retorna: {
        'areas': ['Area1', 'Area2', ...],
        'motivos': ['Motivo1', 'Motivo2', ...],
        'datos': [[count, count, ...], ...],  // filas = áreas, columnas = motivos
        'totales_filas': [total_area1, total_area2, ...],
        'totales_columnas': [total_motivo1, total_motivo2, ...],
        'total_general': int
    }
    """
    # Filtrar solicitudes por rango de fechas
    sol_filtros = {}
    if fecha_inicio:
        sol_filtros['fecha_creacion__gte'] = fecha_inicio
    if fecha_fin:
        sol_filtros['fecha_creacion__lte'] = fecha_fin + ' 23:59:59'

    qs_solicitudes = SolicitudPrestamo.objects.filter(**sol_filtros).select_related('motivo')

    # Obtener todas las áreas y motivos únicos
    areas = sorted(set(
        s.area_destino or 'Sin Área'
        for s in qs_solicitudes.values_list('area_destino', flat=True).distinct()
    ))

    motivos = sorted(set(
        s.motivo.nombre if s.motivo else 'Sin Motivo'
        for s in qs_solicitudes
    ))

    # Construir matriz de conteos
    datos = {}
    for area in areas:
        datos[area] = {}
        for motivo in motivos:
            count = qs_solicitudes.filter(
                area_destino=area if area != 'Sin Área' else '',
                motivo__nombre=motivo if motivo != 'Sin Motivo' else None
            ).count()
            datos[area][motivo] = count

    # Construir filas de datos y calcular totales
    matriz_datos = []
    totales_filas = []
    for area in areas:
        fila = [datos[area].get(motivo, 0) for motivo in motivos]
        matriz_datos.append(fila)
        totales_filas.append(sum(fila))

    # Calcular totales por columna
    totales_columnas = []
    for i in range(len(motivos)):
        total = sum(fila[i] for fila in matriz_datos)
        totales_columnas.append(total)

    total_general = sum(totales_filas)

    return {
        'areas': areas,
        'motivos': motivos,
        'datos': matriz_datos,
        'totales_filas': totales_filas,
        'totales_columnas': totales_columnas,
        'total_general': total_general,
    }


def exportar_reporte_excel(request):
    """Exporta el reporte de áreas x motivos a Excel."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    if not Workbook:
        return JsonResponse({"error": "openpyxl no está instalado"}, status=400)

    try:
        fecha_inicio = request.GET.get('fecha_inicio', '')
        fecha_fin = request.GET.get('fecha_fin', '')

        # Obtener datos
        datos_reporte = _obtener_datos_reporte_areas_motivos(fecha_inicio, fecha_fin)

        # Crear workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Reporte Expedientes"

        # Estilos
        titulo_font = Font(name='Times New Roman', size=14, bold=True)
        encabezado_fill = PatternFill(start_color='008B8B', end_color='008B8B', fill_type='solid')
        encabezado_font = Font(bold=True, color='FFFFFF')
        total_fill = PatternFill(start_color='D3D3D3', end_color='D3D3D3', fill_type='solid')
        total_font = Font(bold=True)
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)

        # Título
        ws['A1'] = "REPORTE EXPEDIENTES PRESTADOS"
        ws['A1'].font = titulo_font
        ws.merge_cells('A1:F1')
        ws['A1'].alignment = center_align

        # Rango de fechas
        fecha_texto = f"Período: {fecha_inicio or 'Inicio'} a {fecha_fin or 'Hoy'}"
        if not fecha_inicio and not fecha_fin:
            fecha_texto = "Período: Todos"
        ws['A2'] = fecha_texto
        ws.merge_cells('A2:F2')
        ws['A2'].alignment = center_align

        ws.append([])  # Espacio

        # Encabezados de tabla
        encabezados = ['Área'] + datos_reporte['motivos'] + ['TOTAL']
        ws.append(encabezados)

        header_row = ws.max_row
        for col in range(1, len(encabezados) + 1):
            cell = ws.cell(row=header_row, column=col)
            cell.fill = encabezado_fill
            cell.font = encabezado_font
            cell.border = border
            cell.alignment = center_align

        # Datos
        for idx, area in enumerate(datos_reporte['areas']):
            fila = [area] + datos_reporte['datos'][idx] + [datos_reporte['totales_filas'][idx]]
            ws.append(fila)

            # Aplicar estilos a esta fila
            row_num = ws.max_row
            for col in range(1, len(fila) + 1):
                cell = ws.cell(row=row_num, column=col)
                cell.border = border
                cell.alignment = center_align if col > 1 else Alignment(horizontal='left', vertical='center')

        # Fila de totales
        totales_fila = ['TOTAL'] + datos_reporte['totales_columnas'] + [datos_reporte['total_general']]
        ws.append(totales_fila)

        totales_row = ws.max_row
        for col in range(1, len(totales_fila) + 1):
            cell = ws.cell(row=totales_row, column=col)
            cell.fill = total_fill
            cell.font = total_font
            cell.border = border
            cell.alignment = center_align if col > 1 else Alignment(horizontal='left', vertical='center')

        # Ajustar ancho de columnas
        ws.column_dimensions['A'].width = 20
        for i in range(2, len(encabezados) + 1):
            ws.column_dimensions[chr(64 + i)].width = 15

        # Guardar en memoria
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)

        # Retornar como descarga
        response = HttpResponse(
            buf.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="reporte_expedientes_prestados.xlsx"'
        return response

    except Exception as e:
        logger.error(f"Error en exportar_reporte_excel: {e}", exc_info=True)
        return JsonResponse({"error": "Error al generar Excel"}, status=500)


def exportar_reporte_pdf(request):
    """Exporta el reporte de áreas x motivos a PDF."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        fecha_inicio = request.GET.get('fecha_inicio', '')
        fecha_fin = request.GET.get('fecha_fin', '')

        # Obtener datos desde la BD
        datos_reporte = _obtener_datos_reporte_areas_motivos(fecha_inicio, fecha_fin)

        # Crear PDF
        page_size = landscape(LETTER)
        margen_top = 3 * cm
        margen_bot = 2.5 * cm
        margen_lat = 1.5 * cm

        buf = BytesIO()

        # Canvas personalizado para encabezado/pie
        class _PdfCanvas(rl_canvas.Canvas):
            def __init__(self, *args, draw_footer=None, **kwargs):
                super().__init__(*args, **kwargs)
                self._saved_states = []
                self._draw_footer = draw_footer

            def showPage(self):
                self._saved_states.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                total = len(self._saved_states)
                for state in self._saved_states:
                    self.__dict__.update(state)
                    if self._draw_footer:
                        self._draw_footer(self, total)
                    super().showPage()
                super().save()

        doc = BaseDocTemplate(
            buf,
            pagesize=page_size,
            leftMargin=margen_lat, rightMargin=margen_lat,
            topMargin=margen_top, bottomMargin=margen_bot,
            title='Reporte Expedientes Prestados',
        )

        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='contenido')

        # Header
        def dibujar_header(canvas_obj, doc):
            canvas_obj.saveState()
            ancho, alto = doc.pagesize
            y_top = alto - 0.5 * cm
            canvas_obj.setFont('Times-Bold', 11)
            canvas_obj.drawCentredString(ancho / 2, y_top - 0.75 * cm, 'REPORTE EXPEDIENTES PRESTADOS')
            canvas_obj.restoreState()

        # Footer
        def dibujar_footer(canvas_obj, total_pages):
            canvas_obj.saveState()
            ancho, alto = canvas_obj._pagesize
            y_bot = 1.2 * cm
            canvas_obj.setFont('Helvetica', 8)
            canvas_obj.setFillColor(colors.black)
            page_num = canvas_obj.getPageNumber()
            canvas_obj.drawCentredString(ancho / 2, y_bot, f'Página {page_num} de {total_pages}')
            canvas_obj.restoreState()

        doc.addPageTemplates([PageTemplate(id='main', frames=[frame], onPage=dibujar_header)])

        # Estilos
        styles = getSampleStyleSheet()
        st_titulo = ParagraphStyle('titulo', parent=styles['Title'], fontName='Times-Bold', fontSize=14, alignment=TA_CENTER, spaceAfter=6)
        st_fecha = ParagraphStyle('fecha', parent=styles['Normal'], fontName='Helvetica', fontSize=10, alignment=TA_CENTER, spaceAfter=12)
        st_tabla_head = ParagraphStyle('tabla_head', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=TA_CENTER)
        st_tabla_cell = ParagraphStyle('tabla_cell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, alignment=TA_CENTER)

        elementos = []

        # Título y período
        elementos.append(Paragraph('REPORTE EXPEDIENTES PRESTADOS', st_titulo))
        fecha_texto = f"Período: {fecha_inicio or 'Todos'} a {fecha_fin or 'Hoy'}"
        elementos.append(Paragraph(fecha_texto, st_fecha))
        elementos.append(Spacer(1, 10))

        # Construir tabla: Áreas x Motivos
        # Encabezados: ['Área', 'Motivo1', 'Motivo2', ..., 'TOTAL']
        encabezados = ['Área'] + datos_reporte['motivos'] + ['TOTAL']
        filas = [[Paragraph(str(h), st_tabla_head) for h in encabezados]]

        # Filas de datos
        for idx, area in enumerate(datos_reporte['areas']):
            fila = [Paragraph(str(area), st_tabla_cell)]
            # Agregar conteos por motivo
            for col_idx in range(len(datos_reporte['motivos'])):
                count = datos_reporte['datos'][idx][col_idx]
                fila.append(Paragraph(str(count), st_tabla_cell))
            # Total de la fila
            fila.append(Paragraph(str(datos_reporte['totales_filas'][idx]), st_tabla_cell))
            filas.append(fila)

        # Fila de totales
        fila_total = [Paragraph('TOTAL', st_tabla_cell)]
        for total_col in datos_reporte['totales_columnas']:
            fila_total.append(Paragraph(str(total_col), st_tabla_cell))
        fila_total.append(Paragraph(str(datos_reporte['total_general']), st_tabla_cell))
        filas.append(fila_total)

        # Crear tabla
        num_cols = len(encabezados)
        col_width = doc.width / num_cols
        tabla = Table(filas, colWidths=[col_width] * num_cols, repeatRows=1)

        tabla_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#008b8b')),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#444444')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f1f5f5')]),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d3d3d3')),
        ]
        tabla.setStyle(TableStyle(tabla_styles))
        elementos.append(tabla)

        # Build PDF
        def make_canvas(*args, **kwargs):
            return _PdfCanvas(*args, draw_footer=dibujar_footer, **kwargs)

        doc.build(elementos, canvasmaker=make_canvas)

        # Retornar descarga
        pdf_bytes = buf.getvalue()
        buf.close()

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="reporte_expedientes_prestados.pdf"'
        return response

    except Exception as e:
        logger.error(f"Error en exportar_reporte_pdf: {e}", exc_info=True)
        return JsonResponse({"error": f"Error al generar PDF: {str(e)}"}, status=500)

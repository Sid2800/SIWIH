from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q, Subquery
from django.utils.timezone import localtime, now

from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import log_error, log_warning
from ingreso.models import Ingreso
from mapeo_camas.constants.view_constants import (
    OBS_AJUSTE_MAPEO_SIN_ALTA,
    ESTADOS_OCUPADA_PREALTA,
    OBS_REASIGNACION_SIN_ORIGEN_DETALLE,
    OBS_REASIGNACION_SIN_ORIGEN_HISTORIAL,
)
from mapeo_camas.models import AsignacionCamaPaciente, HistorialEstadoCama, EstadoMapeo, get_observacion_mapeo
from mapeo_camas.models import MapeoSesionCama, MapeoSesionServicio  # [2026-05-29] Bloqueo de ingreso por sesion de mapeo en curso
from paciente.models import Paciente
from servicio.models import Cama


class MapeoCamasService:
    @staticmethod
    def get_estado_mapeo(codigo, categoria):
        from mapeo_camas.models import EstadoMapeo
        return EstadoMapeo.objects.get(codigo=codigo, categoria=categoria)

    @staticmethod
    def obtener_camas_historial_filtro():
        from mapeo_camas._helpers import _ubicacion_desde_cama

        camas = (
            Cama.objects.filter(estado=1)
            .select_related("sala__servicio", "cubiculo")
            .order_by("numero_cama")
        )
        return [
            {
                "id": str(cama.numero_cama),
                "numero_cama": str(cama.numero_cama),
                "ubicacion": _ubicacion_desde_cama(cama),
            }
            for cama in camas
        ]

    @staticmethod
    def buscar_pacientes_para_mapa(termino="", tipo_busqueda="dni"):
        # [2026-06-01] ORM centralizado del buscador de pacientes para mapa.
        from mapeo_camas._helpers import _paciente_payload

        ingreso_activo = Exists(
            Ingreso.objects.filter(
                paciente_id=OuterRef("pk"),
                estado=1,
                fecha_egreso__isnull=True,
            )
        )
        ingreso_activo_id = Subquery(
            Ingreso.objects.filter(
                paciente_id=OuterRef("pk"),
                estado=1,
                fecha_egreso__isnull=True,
            )
            .order_by("-fecha_ingreso", "-id")
            .values("id")[:1]
        )
        pacientes_qs = (
            Paciente.objects.filter(estado__in=["A", "P"])
            .annotate(ingreso_activo_id=ingreso_activo_id)
            .filter(ingreso_activo)
        )

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

        pacientes = pacientes_qs.order_by("primer_nombre", "primer_apellido")[:20]
        return [_paciente_payload(p, ingreso_id=getattr(p, "ingreso_activo_id", None)) for p in pacientes]

    @staticmethod
    def obtener_camas_disponibles_para_mapa(*, excluir_cama=None, servicio_restringido_id=None):
        # [2026-06-01] ORM centralizado de camas disponibles para reasignación en mapa.
        ultima_asignacion_id = (
            AsignacionCamaPaciente.objects
            .filter(cama_id=OuterRef("pk"))
            .order_by("-fecha_inicio", "-id")
            .values("id")[:1]
        )

        todas_camas = (
            Cama.objects.filter(estado=1)
            .select_related("sala__servicio", "cubiculo")
            .annotate(ultima_asignacion_id=Subquery(ultima_asignacion_id))
            .order_by("sala__servicio__nombre_servicio", "sala__nombre_sala", "numero_cama")
        )

        if excluir_cama:
            todas_camas = todas_camas.exclude(numero_cama=excluir_cama)

        asig_ids = [c.ultima_asignacion_id for c in todas_camas if c.ultima_asignacion_id]
        asig_por_id = {
            a.id: a
            for a in AsignacionCamaPaciente.objects.select_related("estado").filter(id__in=asig_ids)
        }

        estado_vacia = MapeoCamasService.get_estado_mapeo("VACIA", "ESTADO_CAMA")
        resultados = []
        for cama in todas_camas:
            asig = asig_por_id.get(cama.ultima_asignacion_id)
            estado = asig.estado if asig else estado_vacia
            if getattr(estado, "codigo", estado) == "VACIA":
                if servicio_restringido_id and getattr(cama.sala, "servicio_id", None) != servicio_restringido_id:
                    continue
                resultados.append(
                    {
                        "numero_cama": cama.numero_cama,
                        "sala": cama.sala.nombre_sala,
                        "servicio": cama.sala.servicio.nombre_servicio,
                        "cubiculo": cama.cubiculo.nombre_cubiculo if cama.cubiculo else None,
                    }
                )
        return resultados

    @staticmethod
    def obtener_ultimas_asignaciones_por_cama(cama_ids=None):
        """[2026-06-09 REFACTOR] Retorna dict {cama_id: AsignacionCamaPaciente} con asignación más reciente."""
        try:
            ultima_asignacion_id = (
                AsignacionCamaPaciente.objects
                .filter(cama_id=OuterRef("cama_id"))
                .order_by("-fecha_inicio", "-id")
                .values("id")[:1]
            )
            qs = (
                AsignacionCamaPaciente.objects
                .select_related("ingreso", "estado")
                .filter(id=Subquery(ultima_asignacion_id))
            )
            if cama_ids:
                qs = qs.filter(cama_id__in=cama_ids)
            return {asig.cama_id: asig for asig in qs}
        except Exception as exc:
            log_error(
                "Error al obtener ultimas asignaciones por cama",
                app=LogApp.INGRESOS,
                camas_filtradas=len(cama_ids) if cama_ids else 0,
                error=str(exc),
            )
            raise

    @staticmethod
    def obtener_ultimos_historiales_por_cama(cama_ids=None):
        """[2026-06-09 REFACTOR] Retorna dict {cama_id: HistorialEstadoCama} con historial más reciente."""
        try:
            ultima_historial_id = (
                HistorialEstadoCama.objects
                .filter(cama_id=OuterRef("cama_id"))
                .order_by("-fecha_hora", "-id")
                .values("id")[:1]
            )
            qs = (
                HistorialEstadoCama.objects
                .select_related("usuario")
                .filter(id=Subquery(ultima_historial_id))
            )
            if cama_ids:
                qs = qs.filter(cama_id__in=cama_ids)
            return {historial.cama_id: historial for historial in qs}
        except Exception as exc:
            log_error(
                "Error al obtener ultimos historiales por cama",
                app=LogApp.INGRESOS,
                camas_filtradas=len(cama_ids) if cama_ids else 0,
                error=str(exc),
            )
            raise

    @staticmethod
    def liberar_cama_reasignacion_sin_origen(*, usuario, cama, asignacion, estado_anterior, sesion_mapeo):
        """[2026-06-09 FEATURE] Libera cama ocupada cuando la reasignacion no encuentra paciente en otra cama."""
        from mapeo_camas._sesion import _registrar_detalle_mapeo, _registrar_historial_mapeo

        estado_vacia = MapeoCamasService.get_estado_mapeo("VACIA", "ESTADO_CAMA")

        with transaction.atomic():
            asignacion.estado = estado_vacia
            asignacion.ingreso = None
            asignacion.usuario_asignacion = usuario
            asignacion.save(update_fields=["estado", "ingreso", "usuario_asignacion"])

            historial = _registrar_historial_mapeo(
                cama=cama,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_vacia,
                ingreso=None,
                usuario=usuario,
                observacion=get_observacion_mapeo(OBS_REASIGNACION_SIN_ORIGEN_HISTORIAL),
                sesion_mapeo=sesion_mapeo,
            )

            from mapeo_camas.models import DetalleMapeoCama

            _registrar_detalle_mapeo(
                usuario=usuario,
                cama=cama,
                asignacion=asignacion,
                tipo_accion=DetalleMapeoCama.TipoAccion.CORRECCION,
                hubo_cambio=True,
                observacion=get_observacion_mapeo(OBS_REASIGNACION_SIN_ORIGEN_DETALLE),
                sesion_mapeo=sesion_mapeo,
            )

        log_warning(
            "Cama liberada por reasignacion sin origen",
            app=LogApp.INGRESOS,
            cama_id=getattr(cama, "pk", None),
            usuario_id=getattr(usuario, "id", None),
            sesion_mapeo_id=getattr(sesion_mapeo, "id", None),
        )

        return {"asignacion": asignacion, "historial": historial, "estado_vacia": estado_vacia}

    @staticmethod
    def obtener_historiales_data(tipo, cama_id="", fecha_inicio=None, fecha_fin=None):
        from mapeo_camas._helpers import (
            _hora_local_iso,
            _nombre_cama,
            _nombre_usuario,
            _observacion_codigo,
            _paciente_payload,
            _ubicacion_desde_cama,
        )
        from mapeo_camas.models import DetalleMapeoCama, HistorialEstadoCama, MapeoSesionCama, MapeoSesionServicio, MovimientoCama

        def _estructura_desde_servicios(servicios_map):
            estructura = []
            for servicio_data in servicios_map.values():
                salas_data = []
                for sala_data in servicio_data["salas"].values():
                    salas_data.append(
                        {
                            "nombre": sala_data["nombre"],
                            "cubiculos": list(sala_data["cubiculos"].values()),
                            "camas_directas": sala_data["camas_directas"],
                        }
                    )
                estructura.append({"nombre": servicio_data["nombre"], "salas": salas_data})
            return estructura

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
                        "estado": sesion.estado.codigo if hasattr(sesion.estado, "codigo") else str(sesion.estado),
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
            return {"ok": True, "results": results}, 200

        if tipo == "historial":
            historial_qs = HistorialEstadoCama.objects.select_related(
                "cama__sala__servicio", "cama__cubiculo", "ingreso__paciente", "usuario"
            )
            if fecha_inicio:
                historial_qs = historial_qs.filter(fecha_hora__gte=fecha_inicio)
            if fecha_fin:
                historial_qs = historial_qs.filter(fecha_hora__lte=fecha_fin)
            if cama_id:
                historial_qs = historial_qs.filter(cama_id=cama_id)

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
                paciente = _paciente_payload(item.ingreso.paciente if item.ingreso_id else None, ingreso_id=item.ingreso_id)
                results.append(
                    {
                        "id": item.cama_id,
                        "referencia": f"Cama {_nombre_cama(item.cama)}",
                        "tipo": "HISTORIAL",
                        "estado": item.estado_nuevo.codigo if hasattr(item.estado_nuevo, "codigo") else str(item.estado_nuevo),
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
            return {"ok": True, "results": results}, 200

        if tipo == "movimiento":
            movimientos = (
                MovimientoCama.objects.select_related(
                    "cama_origen__sala__servicio",
                    "cama_origen__cubiculo",
                    "cama_destino__sala__servicio",
                    "cama_destino__cubiculo",
                    "ingreso__paciente",
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
                paciente = _paciente_payload(ultimo.ingreso.paciente if ultimo.ingreso_id else None, ingreso_id=ultimo.ingreso_id)
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
            return {"ok": True, "results": results}, 200

        return {"ok": False, "error": "Tipo no soportado."}, 400

    @staticmethod
    def obtener_historiales_cards_data(tipo, registro_id, page=1, page_size=50):
        from mapeo_camas._helpers import (
            _hora_local_iso,
            _nombre_cama,
            _nombre_usuario,
            _observacion_codigo,
            _paciente_payload,
            _ubicacion_desde_cama,
        )
        from mapeo_camas.models import DetalleMapeoCama, HistorialEstadoCama, MapeoSesionCama, MapeoSesionServicio, MovimientoCama

        def _estructura_desde_servicios(servicios_map):
            estructura = []
            for servicio_data in servicios_map.values():
                salas_data = []
                for sala_data in servicio_data["salas"].values():
                    salas_data.append(
                        {
                            "nombre": sala_data["nombre"],
                            "cubiculos": list(sala_data["cubiculos"].values()),
                            "camas_directas": sala_data["camas_directas"],
                        }
                    )
                estructura.append({"nombre": servicio_data["nombre"], "salas": salas_data})
            return estructura

        if not registro_id:
            return {"ok": False, "error": "Debe indicar id."}, 400

        if tipo == "mapeo":
            sesion = MapeoSesionCama.objects.filter(pk=registro_id).first()
            if not sesion:
                return {"ok": False, "error": "Sesion no encontrada."}, 404

            detalles = (
                DetalleMapeoCama.objects.filter(sesion_mapeo=sesion)
                .select_related("cama__sala__servicio", "cama__cubiculo__sala__servicio", "ingreso_actual__paciente", "usuario", "estado_actual", "tipo_accion")
                .order_by("cama__sala__nombre_sala", "cama__cubiculo__numero", "cama__numero_cama", "fecha_hora")
            )

            detalles_list = list(detalles)
            ultimo_estado_por_cama = {}
            tipo_accion_display_map = {}

            for item in detalles_list:
                estado_actual_codigo = item.estado_actual.codigo if item.estado_actual else ""
                estado_anterior_codigo = ultimo_estado_por_cama.get(item.cama_id, None)

                if estado_anterior_codigo is None:
                    tipo_accion_display = "Confirmación"
                else:
                    tipo_accion_display = f"{estado_anterior_codigo} \u2192 {estado_actual_codigo}"

                tipo_accion_display_map[(item.cama_id, item.fecha_hora.isoformat())] = tipo_accion_display
                ultimo_estado_por_cama[item.cama_id] = estado_actual_codigo

            detalles_list_ordenados = sorted(detalles_list, key=lambda x: x.fecha_hora, reverse=True)

            cards = []
            servicios_map = {}
            camas_vistas_estructura = set()

            for item in detalles_list_ordenados:
                paciente = _paciente_payload(item.ingreso_actual.paciente if item.ingreso_actual_id else None, ingreso_id=item.ingreso_actual_id)
                cama_numero = _nombre_cama(item.cama)
                cubiculo_obj = getattr(item.cama, "cubiculo", None)
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

                tipo_accion_display = tipo_accion_display_map.get((item.cama_id, item.fecha_hora.isoformat()), "Confirmación")

                cama_item = {
                    "numero_cama": cama_numero,
                    "estado": item.estado_actual.codigo if item.estado_actual else "",
                    "paciente": paciente["nombre"] if paciente else "Sin paciente",
                    "dni": paciente["dni"] if paciente else "",
                    "usuario": _nombre_usuario(item.usuario),
                    "fecha": _hora_local_iso(item.fecha_hora),
                    "tipo_accion": tipo_accion_display,
                    "hubo_cambio": bool(item.hubo_cambio),
                    "fue_validada": bool(item.fue_validada),
                    "observacion": _observacion_codigo(item.observacion),
                }

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
                        "subtitulo": tipo_accion_display,
                        "estado": item.estado_actual.codigo if item.estado_actual else "",
                        "paciente": paciente["nombre"] if paciente else "Sin paciente",
                        "usuario": _nombre_usuario(item.usuario),
                        "fecha": _hora_local_iso(item.fecha_hora),
                        "detalle_1": f"Ubicacion: {_ubicacion_desde_cama(item.cama)}",
                        "detalle_2": f"Validada: {'SI' if item.fue_validada else 'NO'}",
                        "detalle_3": f"Hubo cambio: {'SI' if item.hubo_cambio else 'NO'}",
                        "observacion": _observacion_codigo(item.observacion),
                    }
                )

            estructura = _estructura_desde_servicios(servicios_map)
            servicios_sesion = [
                ss.servicio.nombre_servicio
                for ss in MapeoSesionServicio.objects.select_related("servicio")
                .filter(sesion_mapeo=sesion)
                .order_by("servicio__nombre_servicio")
            ]

            return {
                "ok": True,
                "cards": cards,
                "estructura": estructura,
                "servicios_sesion": servicios_sesion,
                "sesion_observacion": sesion.observacion_texto if sesion.observacion_texto else None,
                "paginacion": {
                    "page": 1,
                    "page_size": page_size,
                    "total_items": len(cards),
                    "total_pages": 1,
                },
            }, 200

        if tipo == "historial":
            timeline_qs = (
                HistorialEstadoCama.objects.select_related(
                    "cama__sala__servicio", "cama__cubiculo__sala__servicio",
                    "estado_anterior", "estado_nuevo", "ingreso__paciente", "usuario",
                )
                .filter(cama_id=registro_id)
                .order_by("cama__sala__nombre_sala", "cama__cubiculo__numero", "cama__numero_cama", "-fecha_hora")
            )
            total_items = timeline_qs.count()
            if total_items == 0:
                return {"ok": False, "error": "Historial no encontrado para esta cama."}, 404

            total_pages = max(1, (total_items + page_size - 1) // page_size)
            if page > total_pages:
                page = total_pages
            inicio = (page - 1) * page_size
            timeline_page = timeline_qs[inicio:inicio + page_size]

            servicios_map = {}
            for item in timeline_page:
                paciente = _paciente_payload(item.ingreso.paciente if item.ingreso_id else None, ingreso_id=item.ingreso_id)
                estado_nuevo_codigo = item.estado_nuevo.codigo if hasattr(item.estado_nuevo, "codigo") else str(item.estado_nuevo)
                estado_anterior_codigo = (
                    item.estado_anterior.codigo if hasattr(item.estado_anterior, "codigo") else str(item.estado_anterior)
                ) if item.estado_anterior else "SIN_ESTADO"

                cubiculo_obj = getattr(item.cama, "cubiculo", None)
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
                    "observacion": _observacion_codigo(item.observacion),
                }

                if cubiculo_nombre == "SIN_CUBICULO":
                    servicios_map[servicio_nombre]["salas"][sala_nombre]["camas_directas"].append(cama_item)
                else:
                    cubiculos_map = servicios_map[servicio_nombre]["salas"][sala_nombre]["cubiculos"]
                    if cubiculo_nombre not in cubiculos_map:
                        cubiculos_map[cubiculo_nombre] = {"nombre": cubiculo_nombre, "camas": []}
                    cubiculos_map[cubiculo_nombre]["camas"].append(cama_item)

            estructura = _estructura_desde_servicios(servicios_map)
            return {
                "ok": True,
                "cards": [],
                "estructura": estructura,
                "paginacion": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                },
            }, 200

        if tipo == "movimiento":
            movimientos_qs = (
                MovimientoCama.objects.select_related(
                    "cama_origen__sala__servicio", "cama_origen__cubiculo__sala__servicio",
                    "cama_destino__sala__servicio", "cama_destino__cubiculo__sala__servicio",
                    "ingreso__paciente", "usuario",
                )
                .filter(Q(cama_origen_id=registro_id) | Q(cama_destino_id=registro_id))
                .order_by("-fecha_hora")
            )
            total_items = movimientos_qs.count()
            if total_items == 0:
                return {"ok": False, "error": "No se encontraron movimientos para esta cama."}, 404

            total_pages = max(1, (total_items + page_size - 1) // page_size)
            if page > total_pages:
                page = total_pages
            inicio = (page - 1) * page_size
            movimientos_page = movimientos_qs[inicio:inicio + page_size]

            primer_mov = movimientos_qs.first()
            cama_ref = (
                primer_mov.cama_origen
                if str(primer_mov.cama_origen_id) == str(registro_id)
                else primer_mov.cama_destino
            )

            cubiculo_obj_ref = getattr(cama_ref, "cubiculo", None)
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

            for mov in movimientos_page:
                paciente = _paciente_payload(mov.ingreso.paciente if mov.ingreso_id else None, ingreso_id=mov.ingreso_id)
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
                    "observacion": _observacion_codigo(mov.observacion),
                }

                if cubiculo_nombre == "SIN_CUBICULO":
                    servicios_map[servicio_nombre]["salas"][sala_nombre]["camas_directas"].append(cama_item)
                else:
                    cubiculos_map = servicios_map[servicio_nombre]["salas"][sala_nombre]["cubiculos"]
                    if cubiculo_nombre not in cubiculos_map:
                        cubiculos_map[cubiculo_nombre] = {"nombre": cubiculo_nombre, "camas": []}
                    cubiculos_map[cubiculo_nombre]["camas"].append(cama_item)

            estructura = _estructura_desde_servicios(servicios_map)
            return {
                "ok": True,
                "cards": [],
                "estructura": estructura,
                "paginacion": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                },
            }, 200

        return {"ok": False, "error": "Tipo no soportado."}, 400

    # [2026-05-29] Helper: ids de servicios cubiertos por alguna sesion de mapeo EN_PROGRESO.
    # Mientras haya una sesion iniciada sobre esos servicios, los ingresos asociados
    # no pueden crearse, editarse ni inactivarse para preservar la consistencia del mapeo.
    @staticmethod
    def servicios_en_sesion_mapeo_activa():
        try:
            estado_en_progreso = EstadoMapeo.objects.get(
                codigo="EN_PROGRESO",
                categoria=EstadoMapeo.Categoria.ESTADO_SESION,
            )
        except EstadoMapeo.DoesNotExist:
            return set()

        sesiones_activas_ids = MapeoSesionCama.objects.filter(
            estado=estado_en_progreso,
            fecha_fin__isnull=True,
        ).values_list("id", flat=True)

        if not sesiones_activas_ids:
            return set()

        return set(
            MapeoSesionServicio.objects.filter(
                sesion_mapeo_id__in=sesiones_activas_ids,
            ).values_list("servicio_id", flat=True)
        )

    # [2026-05-29] Devuelve mensaje de bloqueo si el ingreso (o el cambio de sala) afecta
    # un servicio con sesion de mapeo en curso. Retorna None si esta permitido.
    # El mensaje incluye el nombre del/los servicios con mapeo activo para guiar al usuario.
    @staticmethod
    def validar_ingreso_no_bloqueado_por_mapeo(*, ingreso_id=None, sala_id=None):
        from servicio.models import Sala, Servicio

        servicios_bloqueados = MapeoCamasService.servicios_en_sesion_mapeo_activa()
        if not servicios_bloqueados:
            return None

        servicios_afectados = set()

        if ingreso_id:
            servicio_ingreso = (
                Ingreso.objects.filter(pk=ingreso_id)
                .values_list("sala__servicio_id", flat=True)
                .first()
            )
            if servicio_ingreso:
                servicios_afectados.add(servicio_ingreso)

        if sala_id:
            servicio_sala = (
                Sala.objects.filter(pk=sala_id)
                .values_list("servicio_id", flat=True)
                .first()
            )
            if servicio_sala:
                servicios_afectados.add(servicio_sala)

        conflicto = servicios_afectados & servicios_bloqueados
        if not conflicto:
            return None

        nombres = list(
            Servicio.objects.filter(id__in=conflicto)
            .order_by("nombre_servicio")
            .values_list("nombre_servicio", flat=True)
        )
        servicios_txt = ", ".join(nombres) if nombres else "el servicio asociado"
        return (
            f"Operacion bloqueada: hay un mapeo de camas en curso sobre {servicios_txt}. "
            "Espere a que termine la sesion de mapeo antes de modificar este ingreso."
        )

    @staticmethod
    def registrar_historial_estado_cama(
        cama_id,
        estado_anterior,
        estado_nuevo,
        usuario,
        ingreso_id=None,
        observacion="",
    ):
        """
        Registra un cambio de estado físico de cama.
        ingreso_id es opcional porque hay estados donde la cama no está
        asociada a ningún ingreso activo (por ejemplo: vacia o fuera de servicio).
        """
        return HistorialEstadoCama.objects.create(
            cama_id=cama_id,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            ingreso_id=ingreso_id,
            usuario=usuario,
            observacion=get_observacion_mapeo(observacion),
        )

    @staticmethod
    def validar_consistencia_minima(cama_id, ingreso_id):
        """
        [2026-05-26 AUDIT] Validación mínima con pivote operativo ingreso_id.
        - La cama no debe tener otra asignación OCUPADA.
        - El ingreso no debe tener otra cama OCUPADA.
        """
        errores = {}

        estado_ocupada = MapeoCamasService.get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
        asignacion_activa_cama = AsignacionCamaPaciente.objects.filter(
            cama_id=cama_id,
            estado=estado_ocupada,
        ).first()
        if asignacion_activa_cama:
            errores["cama_id"] = (
                f"La cama #{cama_id} ya tiene una asignacion activa "
                f"(registro #{asignacion_activa_cama.id})."
            )

        if ingreso_id is not None:
            asignacion_activa_ingreso = AsignacionCamaPaciente.objects.filter(
                ingreso_id=ingreso_id,
                estado=estado_ocupada,
            ).first()
            if asignacion_activa_ingreso:
                errores["ingreso_id"] = (
                    f"El ingreso #{ingreso_id} ya tiene una cama activa "
                    f"(registro #{asignacion_activa_ingreso.id})."
                )

        if errores:
            # [2026-06-01] Logging funcional para auditoría de validaciones de negocio.
            log_warning(
                "Validacion de consistencia fallida en mapeo de camas",
                app=LogApp.INGRESOS,
                cama_id=cama_id,
                ingreso_id=ingreso_id,
                errores=errores,
            )
            raise ValidationError(errores)

    @staticmethod
    def sincronizar_cama_con_ingreso(cama_id, ingreso_id, usuario):
        """
        [2026-05-26 AUDIT] Activación del módulo de camas usando ingreso_id.
        Al recibir un nuevo ingreso:
        - Si ya existe registro para la cama, se actualiza ese registro a ACTIVA.
        - Si no existe, se crea uno nuevo.
        """
        if not cama_id or not ingreso_id or not usuario:
            log_warning(
                "Sincronizacion cama-ingreso omitida por parametros incompletos",
                app=LogApp.INGRESOS,
                cama_id=cama_id,
                ingreso_id=ingreso_id,
                usuario_id=getattr(usuario, "id", None),
            )
            return None

        try:
            with transaction.atomic():
                # Bloquea registros base para serializar asignaciones concurrentes.
                Cama.objects.select_for_update().get(pk=cama_id)
                Ingreso.objects.select_for_update().get(pk=ingreso_id)

                # Revalidar dentro del bloqueo para evitar carrera entre transacciones.
                MapeoCamasService.validar_consistencia_minima(cama_id, ingreso_id)

                estado_ocupada = MapeoCamasService.get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
                estado_vacia = MapeoCamasService.get_estado_mapeo("VACIA", "ESTADO_CAMA")

                asignacion = (
                    AsignacionCamaPaciente.objects.select_for_update()
                    .filter(cama_id=cama_id)
                    .order_by("-fecha_inicio")
                    .first()
                )

                if asignacion:
                    asignacion.ingreso_id = ingreso_id
                    asignacion.usuario_asignacion = usuario
                    asignacion.estado = estado_ocupada
                    asignacion.fecha_inicio = now()
                    asignacion.save(
                        update_fields=[
                            "ingreso",
                            "usuario_asignacion",
                            "estado",
                            "fecha_inicio",
                        ]
                    )
                else:
                    asignacion = AsignacionCamaPaciente(
                        cama_id=cama_id,
                        ingreso_id=ingreso_id,
                        usuario_asignacion=usuario,
                        estado=estado_ocupada,
                    )
                    asignacion.save()

                # FASE 6: registrar en historial de estado
                # Ingreso: la cama pasa de Vacia → Ocupada
                MapeoCamasService.registrar_historial_estado_cama(
                    cama_id=cama_id,
                    estado_anterior=estado_vacia,
                    estado_nuevo=estado_ocupada,
                    ingreso_id=ingreso_id,
                    usuario=usuario,
                    observacion="Ingreso",
                )

                return asignacion
        except IntegrityError as exc:
            log_error(
                "Conflicto de concurrencia al sincronizar cama con ingreso",
                app=LogApp.INGRESOS,
                cama_id=cama_id,
                ingreso_id=ingreso_id,
                usuario_id=getattr(usuario, "id", None),
            )
            raise ValidationError(
                "Conflicto de concurrencia: la cama o el ingreso ya tienen asignacion activa."
            ) from exc

    @staticmethod
    def cerrar_asignacion_activa_paciente(ingreso_id, usuario, cama_id=None):
        """
        [2026-05-26 AUDIT] Cierra la asignación activa por ingreso (compatibilidad de nombre).
        """
        estado_ocupada = MapeoCamasService.get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
        filtros = {
            "ingreso_id": ingreso_id,
            "estado": estado_ocupada,
        }
        if cama_id is not None:
            filtros["cama_id"] = cama_id

        asignacion_activa = (
            AsignacionCamaPaciente.objects.select_for_update()
            .filter(**filtros)
            .order_by("-fecha_inicio")
            .first()
        )
        if not asignacion_activa:
            return None

        estado_vacia = MapeoCamasService.get_estado_mapeo("VACIA", "ESTADO_CAMA")
        ingreso_id_anterior = asignacion_activa.ingreso_id
        asignacion_activa.estado = estado_vacia
        asignacion_activa.ingreso = None
        asignacion_activa.save(update_fields=["estado", "ingreso"])

        # FASE 6: registrar en historial de estado
        # Cierre: la cama pasa de Ocupada -> Vacia (libera la cama)
        MapeoCamasService.registrar_historial_estado_cama(
            cama_id=asignacion_activa.cama_id,
            estado_anterior=estado_ocupada,
            estado_nuevo=estado_vacia,
            ingreso_id=ingreso_id_anterior,
            usuario=usuario,
            observacion="Cierre de asignacion",
        )

        return asignacion_activa

    @staticmethod
    def sincronizar_cambio_cama_en_ingreso(cama_anterior_id, cama_nueva_id, ingreso_id, usuario):
        """
        [2026-05-26 AUDIT] Sincroniza cambio de cama por ingreso_id.
        - Si cambia la cama, cierra la asignacion activa actual.
        - Luego reutiliza el registro historico de la cama nueva si existe.
        - Si la cama nueva no tiene registro previo, crea uno nuevo.
        - Si queda sin cama, solo cierra la asignacion activa.
        """
        if not ingreso_id or not usuario:
            log_warning(
                "Cambio de cama omitido por parametros incompletos",
                app=LogApp.INGRESOS,
                cama_anterior_id=cama_anterior_id,
                cama_nueva_id=cama_nueva_id,
                ingreso_id=ingreso_id,
                usuario_id=getattr(usuario, "id", None),
            )
            return None

        if cama_anterior_id == cama_nueva_id:
            return None

        with transaction.atomic():
            # [2026-05-26 AUDIT] Bloquea el ingreso para serializar cambios de cama.
            Ingreso.objects.select_for_update().get(pk=ingreso_id)

            estado_ocupada = MapeoCamasService.get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
            estado_vacia = MapeoCamasService.get_estado_mapeo("VACIA", "ESTADO_CAMA")

            asignacion_activa = (
                AsignacionCamaPaciente.objects.select_for_update()
                .filter(
                    ingreso_id=ingreso_id,
                    estado=estado_ocupada,
                )
                .order_by("-fecha_inicio")
                .first()
            )

            if cama_nueva_id is None:
                if cama_anterior_id is not None:
                    Cama.objects.select_for_update().get(pk=cama_anterior_id)
                MapeoCamasService.cerrar_asignacion_activa_paciente(
                    ingreso_id=ingreso_id,
                    usuario=usuario,
                    cama_id=cama_anterior_id,
                )
                return None

            Cama.objects.select_for_update().get(pk=cama_nueva_id)
            if cama_anterior_id is not None:
                Cama.objects.select_for_update().get(pk=cama_anterior_id)

            if asignacion_activa is None:
                return MapeoCamasService.sincronizar_cama_con_ingreso(
                    cama_id=cama_nueva_id,
                    ingreso_id=ingreso_id,
                    usuario=usuario,
                )

            cama_ocupada = AsignacionCamaPaciente.objects.filter(
                cama_id=cama_nueva_id,
                estado=estado_ocupada,
            ).exclude(pk=asignacion_activa.pk).first()
            if cama_ocupada:
                log_warning(
                    "Cambio de cama bloqueado: cama destino ocupada",
                    app=LogApp.INGRESOS,
                    cama_nueva_id=cama_nueva_id,
                    ingreso_id=ingreso_id,
                    asignacion_ocupada_id=cama_ocupada.id,
                )
                raise ValidationError(
                    {"cama_id": f"La cama #{cama_nueva_id} ya tiene una asignacion activa."}
                )

            if cama_anterior_id is not None:
                MapeoCamasService.registrar_historial_estado_cama(
                    cama_id=cama_anterior_id,
                    estado_anterior=estado_ocupada,
                    estado_nuevo=estado_vacia,
                    ingreso_id=ingreso_id,
                    usuario=usuario,
                    observacion="Cambio de cama - salida",
                )

            # La fila vieja se conserva para historial: solo se cierra.
            asignacion_activa.estado = estado_vacia
            asignacion_activa.ingreso = None
            asignacion_activa.save(update_fields=["estado", "ingreso"])

            # La nueva cama reutiliza su ultimo registro historico si existe.
            nueva_asignacion = (
                AsignacionCamaPaciente.objects.select_for_update()
                .filter(cama_id=cama_nueva_id)
                .order_by("-fecha_inicio")
                .first()
            )

            if nueva_asignacion:
                nueva_asignacion.ingreso_id = ingreso_id
                nueva_asignacion.usuario_asignacion = usuario
                nueva_asignacion.estado = estado_ocupada
                nueva_asignacion.fecha_inicio = now()
                nueva_asignacion.save(
                    update_fields=[
                        "ingreso",
                        "usuario_asignacion",
                        "estado",
                        "fecha_inicio",
                    ]
                )
            else:
                nueva_asignacion = AsignacionCamaPaciente.objects.create(
                    cama_id=cama_nueva_id,
                    ingreso_id=ingreso_id,
                    usuario_asignacion=usuario,
                    estado=estado_ocupada,
                )

            MapeoCamasService.registrar_historial_estado_cama(
                cama_id=cama_nueva_id,
                estado_anterior=estado_vacia,
                estado_nuevo=estado_ocupada,
                ingreso_id=ingreso_id,
                usuario=usuario,
                observacion="Cambio de cama - entrada",
            )

            return nueva_asignacion

        return None

    # Alias explicito para mantener el nombre funcional solicitado.
    SINCRONIZAR_CAMA_CON_INGRESO = sincronizar_cama_con_ingreso
    SINCRONIZAR_CAMBIO_CAMA_EN_INGRESO = sincronizar_cambio_cama_en_ingreso


# =============================================================================
# 2026-05-29: Refactor B - operaciones pesadas del mapa de camas migradas
# desde mapeo_camas/views.py al servicio. Las vistas pasan a ser wrappers
# de parsing + permisos + armado de respuesta.
# Imports diferidos para evitar ciclos con mapeo_camas._sesion/_helpers.
# =============================================================================


def _mc_constants():
    # [2026-06-01] Constantes del flujo de mapeo centralizadas en core.
    from core.constants.mapeo_camas_constants import (
        OBSERVACION_CAMBIO_MANUAL_MAPA,
        OBSERVACION_CAMBIO_TRASLADO_MAPEO,
        OBSERVACION_MOVIMIENTO_PACIENTE_MAPA,
        OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_DETALLE,
        OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_SUPERADMIN,
    )
    return {
        "CAMBIO_MANUAL": OBSERVACION_CAMBIO_MANUAL_MAPA,
        "CAMBIO_TRASLADO": OBSERVACION_CAMBIO_TRASLADO_MAPEO,
        "MOV_PAC": OBSERVACION_MOVIMIENTO_PACIENTE_MAPA,
        "MOV_PAC_DETALLE": OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_DETALLE,
        "MOV_PAC_SUPERADMIN": OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_SUPERADMIN,
    }


def _mc_sesion_helpers():
    from mapeo_camas._sesion import (
        _registrar_detalle_mapeo,
        _registrar_historial_mapeo,
        _sincronizar_cama_en_ingreso_activo,
    )
    return _registrar_historial_mapeo, _registrar_detalle_mapeo, _sincronizar_cama_en_ingreso_activo


def _sala_real_id(cama):
    sala = getattr(cama, "sala", None)
    return getattr(sala, "id", None) or getattr(sala, "pk", None)


class MapeoOperacionesMapaService:
    """[2026-05-29] Operaciones transaccionales del mapa de camas (refactor B)."""

    # -------------------------------------------------------------------------
    # mover_paciente_entre_camas
    # -------------------------------------------------------------------------
    @staticmethod
    def mover_paciente_entre_camas(*, usuario, cama_origen, cama_destino, sesion_mapeo, es_superadmin):
        registrar_historial, registrar_detalle, sincronizar_cama = _mc_sesion_helpers()
        OBS = _mc_constants()

        asig_origen = (
            AsignacionCamaPaciente.objects
            .filter(cama_id=cama_origen.pk)
            .order_by("-fecha_inicio", "-id")
            .first()
        )
        asig_destino = (
            AsignacionCamaPaciente.objects
            .filter(cama_id=cama_destino.pk)
            .order_by("-fecha_inicio", "-id")
            .first()
        )

        estado_ocupada = MapeoCamasService.get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
        estado_vacia = MapeoCamasService.get_estado_mapeo("VACIA", "ESTADO_CAMA")

        if not asig_origen or asig_origen.estado is None or asig_origen.estado.codigo not in {"OCUPADA", "PRE_ALTA"}:
            log_warning(
                "Movimiento bloqueado: cama origen sin paciente operativo",
                app=LogApp.INGRESOS,
                cama_origen_id=getattr(cama_origen, "pk", None),
                cama_destino_id=getattr(cama_destino, "pk", None),
            )
            raise ValidationError("La cama origen no tiene paciente asignado (debe estar OCUPADA o PRE_ALTA).")

        ingreso_operativo = asig_origen.ingreso
        if not ingreso_operativo:
            log_warning(
                "Movimiento bloqueado: cama origen sin ingreso operativo",
                app=LogApp.INGRESOS,
                cama_origen_id=getattr(cama_origen, "pk", None),
            )
            raise ValidationError("La cama origen no tiene un ingreso activo valido. Datos incompletos.")

        if asig_destino and (asig_destino.estado is not None and asig_destino.estado.codigo != "VACIA"):
            log_warning(
                "Movimiento bloqueado: cama destino no disponible",
                app=LogApp.INGRESOS,
                cama_destino_id=getattr(cama_destino, "pk", None),
                estado_destino=getattr(getattr(asig_destino, "estado", None), "codigo", None),
            )
            raise ValidationError("La cama destino no esta disponible (no esta vacia).")

        sala_origen_id = _sala_real_id(cama_origen)
        sala_destino_id = _sala_real_id(cama_destino)

        estado_anterior_origen = asig_origen.estado
        estado_anterior_destino = asig_destino.estado if asig_destino else estado_vacia

        obs_origen = (
            get_observacion_mapeo(OBS["MOV_PAC_SUPERADMIN"])
            if es_superadmin
            else get_observacion_mapeo(OBS["MOV_PAC"])
        )
        obs_destino = (
            get_observacion_mapeo(OBS["MOV_PAC_SUPERADMIN"])
            if es_superadmin
            else (
                get_observacion_mapeo(OBS["MOV_PAC"])
                if sala_destino_id != sala_origen_id
                else get_observacion_mapeo(OBS["MOV_PAC_DETALLE"])
            )
        )

        from mapeo_camas.models import DetalleMapeoCama, MovimientoCama

        with transaction.atomic():
            asig_origen.estado = estado_vacia
            asig_origen.save()

            if not asig_destino:
                asig_destino = AsignacionCamaPaciente(
                    cama=cama_destino,
                    estado=estado_ocupada,
                    ingreso=ingreso_operativo,
                    usuario_asignacion=usuario,
                )
            else:
                asig_destino.estado = estado_ocupada
                asig_destino.ingreso = ingreso_operativo
                asig_destino.usuario_asignacion = usuario
            asig_destino.save()

            sincronizar_cama(ingreso_id=ingreso_operativo.id, cama_id=cama_destino.pk)

            historial_origen = registrar_historial(
                cama=cama_origen, estado_anterior=estado_anterior_origen, estado_nuevo=estado_vacia,
                ingreso=None, usuario=usuario, observacion=obs_origen, sesion_mapeo=sesion_mapeo,
            )
            historial_destino = registrar_historial(
                cama=cama_destino, estado_anterior=estado_anterior_destino, estado_nuevo=estado_ocupada,
                ingreso=ingreso_operativo, usuario=usuario, observacion=obs_destino, sesion_mapeo=sesion_mapeo,
            )

            MovimientoCama.objects.create(
                tipo_movimiento="TRASLADO",
                cama_origen_id=cama_origen.pk,
                cama_destino_id=cama_destino.pk,
                ingreso=ingreso_operativo,
                usuario=usuario,
                observacion=get_observacion_mapeo("Movimiento desde mapa de camas"),
            )

            registrar_detalle(
                usuario=usuario, cama=cama_origen, asignacion=asig_origen,
                tipo_accion=DetalleMapeoCama.TipoAccion.TRASLADO, hubo_cambio=True,
                observacion=get_observacion_mapeo("Traslado de paciente desde mapa (cama origen)."),
            )
            registrar_detalle(
                usuario=usuario, cama=cama_destino, asignacion=asig_destino,
                tipo_accion=DetalleMapeoCama.TipoAccion.TRASLADO, hubo_cambio=True,
                observacion=get_observacion_mapeo("Traslado de paciente desde mapa (cama destino)."),
            )

        return {
            "asig_origen": asig_origen,
            "asig_destino": asig_destino,
            "historial_origen": historial_origen,
            "historial_destino": historial_destino,
            "ingreso_operativo": ingreso_operativo,
            "estado_ocupada": estado_ocupada,
            "estado_vacia": estado_vacia,
            "sala_origen_id": sala_origen_id,
            "sala_destino_id": sala_destino_id,
        }


    # -------------------------------------------------------------------------
    # aplicar_actualizacion_manual_cama (refactor B - actualizar_cama_mapa)
    # -------------------------------------------------------------------------
    @staticmethod
    def aplicar_actualizacion_manual_cama(
        *,
        usuario,
        cama,
        estado_codigo,
        estado_nuevo_obj,
        ingreso_nuevo,
        sesion_mapeo,
        asig_previa_paciente,
        asignacion,
        estado_anterior,
        ingreso_anterior,
        requiere_cierre_prealta,
        requiere_cierre_ocupada_a_ocupada,
        requiere_registro_alta_a_vacia,
    ):
        registrar_historial, _registrar_detalle, sincronizar_cama = _mc_sesion_helpers()
        OBS = _mc_constants()
        from mapeo_camas.models import DetalleMapeoCama, MovimientoCama

        estado_vacia = MapeoCamasService.get_estado_mapeo("VACIA", "ESTADO_CAMA")
        estado_alta = MapeoCamasService.get_estado_mapeo("ALTA", "ESTADO_CAMA")

        with transaction.atomic():
            estado_historial_anterior = estado_anterior

            # [2026-06-09 FIX] Si el ingreso saliente ya tiene cama activa en otro lugar,
            # no corresponde registrar ALTA: corresponde salida por traslado del origen.
            asig_ingreso_anterior_en_otra_cama = None
            if requiere_cierre_ocupada_a_ocupada and ingreso_anterior:
                asig_ingreso_anterior_en_otra_cama = (
                    AsignacionCamaPaciente.objects
                    .select_related("cama", "estado")
                    .filter(
                        ingreso_id=ingreso_anterior.id,
                        estado__codigo__in=ESTADOS_OCUPADA_PREALTA,
                        estado__categoria="ESTADO_CAMA",
                    )
                    .exclude(cama_id=cama.pk)
                    .order_by("-fecha_inicio", "-id")
                    .first()
                )

            if requiere_cierre_prealta:
                registrar_historial(
                    cama=cama, estado_anterior=estado_anterior, estado_nuevo=estado_alta,
                    ingreso=ingreso_anterior, usuario=usuario,
                    observacion=get_observacion_mapeo("Alta historica por reasignacion desde PRE_ALTA"),
                    sesion_mapeo=sesion_mapeo, forzar_nuevo=True,
                )
                registrar_historial(
                    cama=cama, estado_anterior=estado_alta, estado_nuevo=estado_vacia,
                    ingreso=None, usuario=usuario,
                    observacion=get_observacion_mapeo("Liberacion de cama tras alta historica"),
                    sesion_mapeo=sesion_mapeo, forzar_nuevo=True,
                )
                estado_historial_anterior = estado_vacia

            if requiere_cierre_ocupada_a_ocupada:
                if asig_ingreso_anterior_en_otra_cama:
                    registrar_historial(
                        cama=cama, estado_anterior=estado_anterior, estado_nuevo=estado_vacia,
                        ingreso=None, usuario=usuario,
                        observacion=get_observacion_mapeo(OBS_AJUSTE_MAPEO_SIN_ALTA),
                        sesion_mapeo=sesion_mapeo, forzar_nuevo=True,
                    )
                else:
                    registrar_historial(
                        cama=cama, estado_anterior=estado_anterior, estado_nuevo=estado_alta,
                        ingreso=ingreso_anterior, usuario=usuario,
                        observacion=get_observacion_mapeo("Alta historica por reasignacion directa de cama"),
                        sesion_mapeo=sesion_mapeo, forzar_nuevo=True,
                    )
                    registrar_historial(
                        cama=cama, estado_anterior=estado_alta, estado_nuevo=estado_vacia,
                        ingreso=None, usuario=usuario,
                        observacion=get_observacion_mapeo("Liberacion de cama tras alta historica"),
                        sesion_mapeo=sesion_mapeo, forzar_nuevo=True,
                    )
                estado_historial_anterior = estado_vacia

            if requiere_registro_alta_a_vacia:
                registrar_historial(
                    cama=cama, estado_anterior=estado_anterior, estado_nuevo=estado_alta,
                    ingreso=ingreso_anterior, usuario=usuario,
                    observacion=get_observacion_mapeo("Alta historica por cambio manual a VACIA"),
                    sesion_mapeo=sesion_mapeo,
                )
                estado_historial_anterior = estado_alta

            if asig_previa_paciente:
                estado_anterior_previa = asig_previa_paciente.estado
                asig_previa_paciente.estado = estado_vacia
                asig_previa_paciente.save()
                registrar_historial(
                    cama=asig_previa_paciente.cama, estado_anterior=estado_anterior_previa,
                    estado_nuevo=estado_vacia, ingreso=None, usuario=usuario,
                    observacion=get_observacion_mapeo("Cambio de cama: paciente trasladado a otra cama"),
                    sesion_mapeo=sesion_mapeo,
                )
                MovimientoCama.objects.create(
                    tipo_movimiento="TRASLADO",
                    cama_origen=asig_previa_paciente.cama, cama_destino=cama,
                    ingreso=ingreso_nuevo, usuario=usuario,
                    observacion=get_observacion_mapeo("Cambio de cama desde mapa"),
                )

            asignacion.estado = estado_nuevo_obj
            asignacion.ingreso = ingreso_nuevo
            asignacion.usuario_asignacion = usuario
            asignacion.save()

            if ingreso_nuevo:
                sincronizar_cama(ingreso_id=ingreso_nuevo.id, cama_id=cama.pk)

            historial = registrar_historial(
                cama=cama, estado_anterior=estado_historial_anterior,
                estado_nuevo=estado_nuevo_obj, ingreso=asignacion.ingreso,
                usuario=usuario,
                observacion=get_observacion_mapeo(OBS["CAMBIO_MANUAL"]),
                sesion_mapeo=sesion_mapeo,
            )

        return {"asignacion": asignacion, "historial": historial}


    # -------------------------------------------------------------------------
    # procesar_accion_mapeo (refactor B - procesar_cama_mapeo)
    # -------------------------------------------------------------------------
    @staticmethod
    def procesar_accion_mapeo(*, usuario, cama, accion, observacion, ingreso_observado, sesion):
        registrar_historial, registrar_detalle, sincronizar_cama = _mc_sesion_helpers()
        OBS = _mc_constants()
        from mapeo_camas.models import DetalleMapeoCama

        estado_vacia = MapeoCamasService.get_estado_mapeo("VACIA", "ESTADO_CAMA")
        estado_ocupada = MapeoCamasService.get_estado_mapeo("OCUPADA", "ESTADO_CAMA")

        asig_actual = (
            AsignacionCamaPaciente.objects.select_related("ingreso")
            .filter(cama_id=cama.pk)
            .order_by("-fecha_inicio", "-id")
            .first()
        )
        estado_sistema = asig_actual.estado if asig_actual else estado_vacia

        with transaction.atomic():
            if accion == "CONFIRMAR":
                registrar_historial(
                    cama=cama, estado_anterior=estado_sistema, estado_nuevo=estado_sistema,
                    ingreso=asig_actual.ingreso if asig_actual else None,
                    usuario=usuario,
                    observacion=get_observacion_mapeo("Confirmacion de mapeo sin cambios"),
                    sesion_mapeo=sesion,
                )
                registrar_detalle(
                    usuario=usuario, cama=cama, asignacion=asig_actual,
                    tipo_accion=DetalleMapeoCama.TipoAccion.CONFIRMACION, hubo_cambio=False,
                    observacion=get_observacion_mapeo(observacion or "Confirmacion de estado sin cambios."),
                    sesion_mapeo=sesion,
                )
                return {"mensaje": "Cama confirmada sin cambios.", "estado_sistema": estado_sistema.codigo}

            if accion == "CONFIRMAR_ALTA":
                if not asig_actual:
                    log_warning(
                        "Confirmar alta bloqueado: no hay asignacion activa",
                        app=LogApp.INGRESOS,
                        cama_id=getattr(cama, "pk", None),
                        accion=accion,
                    )
                    raise ValidationError("No hay asignacion activa para confirmar alta.")
                estado_anterior = asig_actual.estado
                asig_actual.estado = estado_vacia
                asig_actual.ingreso = None
                asig_actual.save()
                registrar_historial(
                    cama=cama, estado_anterior=estado_anterior, estado_nuevo=estado_vacia,
                    ingreso=None, usuario=usuario,
                    observacion=get_observacion_mapeo("Confirmacion de alta desde mapeo"),
                    sesion_mapeo=sesion,
                )
                registrar_detalle(
                    usuario=usuario, cama=cama, asignacion=asig_actual,
                    tipo_accion=DetalleMapeoCama.TipoAccion.ALTA, hubo_cambio=True,
                    observacion=get_observacion_mapeo(observacion or "Confirmar alta (egreso)."),
                    sesion_mapeo=sesion,
                )
                return {"mensaje": "Alta confirmada. Cama liberada."}

            if accion == "CANCELAR_PREALTA":
                if not asig_actual or not asig_actual.ingreso_id:
                    log_warning(
                        "Cancelar prealta bloqueado: ingreso actual no disponible",
                        app=LogApp.INGRESOS,
                        cama_id=getattr(cama, "pk", None),
                        accion=accion,
                    )
                    raise ValidationError("No existe ingreso actual para cancelar prealta.")
                estado_anterior = asig_actual.estado
                asig_actual.estado = estado_ocupada
                asig_actual.save()
                sincronizar_cama(ingreso_id=asig_actual.ingreso_id, cama_id=cama.pk)
                registrar_historial(
                    cama=cama, estado_anterior=estado_anterior, estado_nuevo=estado_ocupada,
                    ingreso=asig_actual.ingreso, usuario=usuario,
                    observacion=get_observacion_mapeo("Cancelar prealta desde mapeo"),
                    sesion_mapeo=sesion,
                )
                registrar_detalle(
                    usuario=usuario, cama=cama, asignacion=asig_actual,
                    tipo_accion=DetalleMapeoCama.TipoAccion.CORRECCION, hubo_cambio=True,
                    observacion=get_observacion_mapeo(observacion or "Cancelar prealta, paciente permanece."),
                    sesion_mapeo=sesion,
                )
                return {"mensaje": "Prealta cancelada. Cama en OCUPADA."}

            if accion == "CAMBIO_TRASLADO":
                if not ingreso_observado:
                    log_warning(
                        "Cambio/traslado bloqueado: ingreso observado faltante",
                        app=LogApp.INGRESOS,
                        cama_id=getattr(cama, "pk", None),
                        accion=accion,
                    )
                    raise ValidationError("Debe indicar ingreso_observado_id para cambio/traslado.")

                if asig_actual and asig_actual.ingreso_id == ingreso_observado.id:
                    registrar_historial(
                        cama=cama, estado_anterior=estado_sistema, estado_nuevo=estado_sistema,
                        ingreso=asig_actual.ingreso, usuario=usuario,
                        observacion=get_observacion_mapeo("Confirmacion de mapeo sin cambios (paciente coincide)"),
                        sesion_mapeo=sesion,
                    )
                    registrar_detalle(
                        usuario=usuario, cama=cama, asignacion=asig_actual,
                        tipo_accion=DetalleMapeoCama.TipoAccion.CONFIRMACION, hubo_cambio=False,
                        observacion=get_observacion_mapeo(observacion or "Paciente coincide con sistema."),
                        sesion_mapeo=sesion,
                    )
                    return {"mensaje": "Sin cambios: paciente ya coincide con sistema."}

                estado_anterior = asig_actual.estado if asig_actual else estado_vacia
                if asig_actual and asig_actual.ingreso_id:
                    asig_actual.estado = estado_vacia
                    asig_actual.ingreso = None
                    asig_actual.save()

                nueva_asig = AsignacionCamaPaciente.objects.create(
                    cama=cama, ingreso=ingreso_observado, estado=estado_ocupada,
                    usuario_asignacion=usuario,
                )
                sincronizar_cama(ingreso_id=ingreso_observado.id, cama_id=cama.pk)
                registrar_historial(
                    cama=cama, estado_anterior=estado_anterior, estado_nuevo=estado_ocupada,
                    ingreso=ingreso_observado, usuario=usuario,
                    observacion=get_observacion_mapeo(OBS["CAMBIO_TRASLADO"]),
                    sesion_mapeo=sesion,
                )
                registrar_detalle(
                    usuario=usuario, cama=cama, asignacion=nueva_asig,
                    tipo_accion=DetalleMapeoCama.TipoAccion.CAMBIO, hubo_cambio=True,
                    observacion=get_observacion_mapeo(observacion or "Cambio/traslado de paciente."),
                    sesion_mapeo=sesion,
                )
                return {"mensaje": "Cambio/traslado aplicado correctamente."}

            if accion == "ASIGNACION":
                if not ingreso_observado:
                    log_warning(
                        "Asignacion bloqueada: ingreso observado faltante",
                        app=LogApp.INGRESOS,
                        cama_id=getattr(cama, "pk", None),
                        accion=accion,
                    )
                    raise ValidationError("Debe indicar ingreso_observado_id para asignacion.")
                if asig_actual and asig_actual.estado == estado_ocupada:
                    log_warning(
                        "Asignacion bloqueada: cama ya ocupada",
                        app=LogApp.INGRESOS,
                        cama_id=getattr(cama, "pk", None),
                        accion=accion,
                    )
                    raise ValidationError("La cama ya figura ocupada en sistema. Use CAMBIO_TRASLADO.")
                if asig_actual:
                    asig_actual.estado = estado_ocupada
                    asig_actual.ingreso = ingreso_observado
                    asig_actual.usuario_asignacion = usuario
                    asig_actual.save()
                    asignacion_obj = asig_actual
                else:
                    asignacion_obj = AsignacionCamaPaciente.objects.create(
                        cama=cama, ingreso=ingreso_observado, estado=estado_ocupada,
                        usuario_asignacion=usuario,
                    )
                sincronizar_cama(ingreso_id=ingreso_observado.id, cama_id=cama.pk)
                registrar_historial(
                    cama=cama, estado_anterior=estado_vacia, estado_nuevo=estado_ocupada,
                    ingreso=ingreso_observado, usuario=usuario,
                    observacion=get_observacion_mapeo("Asignacion detectada durante mapeo"),
                    sesion_mapeo=sesion,
                )
                registrar_detalle(
                    usuario=usuario, cama=cama, asignacion=asignacion_obj,
                    tipo_accion=DetalleMapeoCama.TipoAccion.CAMBIO, hubo_cambio=True,
                    observacion=get_observacion_mapeo(observacion or "Sistema libre, paciente presente (asignacion)."),
                    sesion_mapeo=sesion,
                )
                return {"mensaje": "Asignacion aplicada correctamente."}

            if accion == "ALTA_FORZADA":
                if not asig_actual or asig_actual.estado != estado_ocupada:
                    log_warning(
                        "Alta forzada bloqueada: no existe ocupacion activa",
                        app=LogApp.INGRESOS,
                        cama_id=getattr(cama, "pk", None),
                        accion=accion,
                    )
                    raise ValidationError("No existe ocupacion activa para forzar alta.")
                asig_actual.estado = estado_vacia
                asig_actual.ingreso = None
                asig_actual.save()
                registrar_historial(
                    cama=cama, estado_anterior=estado_ocupada, estado_nuevo=estado_vacia,
                    ingreso=None, usuario=usuario,
                    observacion=get_observacion_mapeo("Alta forzada desde mapeo"),
                    sesion_mapeo=sesion,
                )
                registrar_detalle(
                    usuario=usuario, cama=cama, asignacion=asig_actual,
                    tipo_accion=DetalleMapeoCama.TipoAccion.ALTA, hubo_cambio=True,
                    observacion=get_observacion_mapeo(observacion or "Sistema ocupado, cama vacia (alta forzada)."),
                    sesion_mapeo=sesion,
                )
                return {"mensaje": "Alta forzada aplicada. Cama liberada."}

        log_warning(
            "Accion de mapeo no procesada",
            app=LogApp.INGRESOS,
            cama_id=getattr(cama, "pk", None),
            accion=accion,
        )
        raise ValidationError("No se pudo procesar la accion solicitada.")

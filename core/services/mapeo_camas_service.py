from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.timezone import localtime, now

from ingreso.models import Ingreso
from mapeo_camas.models import AsignacionCamaPaciente, HistorialEstadoCama, EstadoMapeo, get_observacion_mapeo
from mapeo_camas.models import MapeoSesionCama, MapeoSesionServicio  # [2026-05-29] Bloqueo de ingreso por sesion de mapeo en curso
from servicio.models import Cama


class MapeoCamasService:
    @staticmethod
    def get_estado_mapeo(codigo, categoria):
        from mapeo_camas.models import EstadoMapeo
        return EstadoMapeo.objects.get(codigo=codigo, categoria=categoria)

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
    from mapeo_camas._constants import (
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
            raise ValidationError("La cama origen no tiene paciente asignado (debe estar OCUPADA o PRE_ALTA).")

        ingreso_operativo = asig_origen.ingreso
        if not ingreso_operativo:
            raise ValidationError("La cama origen no tiene un ingreso activo valido. Datos incompletos.")

        if asig_destino and (asig_destino.estado is not None and asig_destino.estado.codigo != "VACIA"):
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
                    raise ValidationError("Debe indicar ingreso_observado_id para asignacion.")
                if asig_actual and asig_actual.estado == estado_ocupada:
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

        raise ValidationError("No se pudo procesar la accion solicitada.")

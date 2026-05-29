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

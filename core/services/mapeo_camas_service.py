from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.timezone import localtime, now

from mapeo_camas.models import AsignacionCamaPaciente, HistorialEstadoCama, EstadoMapeo
from paciente.models import Paciente
from servicio.models import Cama


class MapeoCamasService:
    @staticmethod
    def get_estado_mapeo(codigo, categoria):
        from mapeo_camas.models import EstadoMapeo
        return EstadoMapeo.objects.get(codigo=codigo, categoria=categoria)

    @staticmethod
    def registrar_historial_estado_cama(
        cama_id,
        estado_anterior,
        estado_nuevo,
        usuario,
        paciente_id=None,
        observacion="",
    ):
        """
        Registra un cambio de estado físico de cama.
        paciente_id es opcional porque hay estados donde la cama no está
        asociada a ningún paciente (por ejemplo: vacia o fuera de servicio).
        """
        return HistorialEstadoCama.objects.create(
            cama_id=cama_id,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            paciente_id=paciente_id,
            usuario=usuario,
            observacion=observacion,
        )

    @staticmethod
    def validar_consistencia_minima(cama_id, paciente_id):
        """
        FASE 3: validacion interna minima.
        - La cama no debe tener otra asignacion activa.
        - El paciente no debe tener otra cama activa.
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

        if paciente_id is not None:
            asignacion_activa_paciente = AsignacionCamaPaciente.objects.filter(
                paciente_id=paciente_id,
                estado=estado_ocupada,
            ).first()
            if asignacion_activa_paciente:
                errores["paciente_id"] = (
                    f"El paciente #{paciente_id} ya tiene una cama activa "
                    f"(registro #{asignacion_activa_paciente.id})."
                )

        if errores:
            raise ValidationError(errores)

    @staticmethod
    def sincronizar_cama_con_ingreso(cama_id, paciente_id, usuario):
        """
        FASE 2: activacion del modulo de camas.
        Al recibir un nuevo ingreso:
        - Si ya existe registro para la cama, se actualiza ese registro a ACTIVA.
        - Si no existe, se crea uno nuevo.
        """
        if not cama_id or not paciente_id or not usuario:
            return None

        try:
            with transaction.atomic():
                # Bloquea registros base para serializar asignaciones concurrentes.
                Cama.objects.select_for_update().get(pk=cama_id)
                Paciente.objects.select_for_update().get(pk=paciente_id)

                # Revalidar dentro del bloqueo para evitar carrera entre transacciones.
                MapeoCamasService.validar_consistencia_minima(cama_id, paciente_id)

                estado_ocupada = MapeoCamasService.get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
                estado_vacia = MapeoCamasService.get_estado_mapeo("VACIA", "ESTADO_CAMA")

                asignacion = (
                    AsignacionCamaPaciente.objects.select_for_update()
                    .filter(cama_id=cama_id)
                    .order_by("-fecha_inicio")
                    .first()
                )

                if asignacion:
                    asignacion.paciente_id = paciente_id
                    asignacion.usuario_asignacion = usuario
                    asignacion.estado = estado_ocupada
                    asignacion.fecha_inicio = now()
                    asignacion.save(
                        update_fields=[
                            "paciente",
                            "usuario_asignacion",
                            "estado",
                            "fecha_inicio",
                        ]
                    )
                else:
                    asignacion = AsignacionCamaPaciente(
                        cama_id=cama_id,
                        paciente_id=paciente_id,
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
                    paciente_id=paciente_id,
                    usuario=usuario,
                    observacion="Ingreso",
                )

                return asignacion
        except IntegrityError as exc:
            raise ValidationError(
                "Conflicto de concurrencia: la cama o el paciente ya tienen asignacion activa."
            ) from exc

    @staticmethod
    def cerrar_asignacion_activa_paciente(paciente_id, usuario, cama_id=None):
        """
        Cierra la asignacion activa del paciente (opcionalmente filtrada por cama).
        """
        estado_ocupada = MapeoCamasService.get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
        filtros = {
            "paciente_id": paciente_id,
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
        asignacion_activa.estado = estado_vacia
        asignacion_activa.paciente = None
        asignacion_activa.save(update_fields=["estado", "paciente"])

        # FASE 6: registrar en historial de estado
        # Cierre: la cama pasa de Ocupada -> Vacia (libera la cama)
        MapeoCamasService.registrar_historial_estado_cama(
            cama_id=asignacion_activa.cama_id,
            estado_anterior=estado_ocupada,
            estado_nuevo=estado_vacia,
            paciente_id=asignacion_activa.paciente_id,
            usuario=usuario,
            observacion="Cierre de asignacion",
        )

        return asignacion_activa

    @staticmethod
    def sincronizar_cambio_cama_en_ingreso(cama_anterior_id, cama_nueva_id, paciente_id, usuario):
        """
        Sincroniza asignaciones al editar ingreso.
        - Si cambia la cama, cierra la asignacion activa actual.
        - Luego reutiliza el registro historico de la cama nueva si existe.
        - Si la cama nueva no tiene registro previo, crea uno nuevo.
        - Si queda sin cama, solo cierra la asignacion activa.
        """
        if not paciente_id or not usuario:
            return None

        if cama_anterior_id == cama_nueva_id:
            return None

        with transaction.atomic():
            # Bloquea el paciente para serializar cambios de cama por ingreso.
            Paciente.objects.select_for_update().get(pk=paciente_id)

            estado_ocupada = MapeoCamasService.get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
            estado_vacia = MapeoCamasService.get_estado_mapeo("VACIA", "ESTADO_CAMA")

            asignacion_activa = (
                AsignacionCamaPaciente.objects.select_for_update()
                .filter(
                    paciente_id=paciente_id,
                    estado=estado_ocupada,
                )
                .order_by("-fecha_inicio")
                .first()
            )

            if cama_nueva_id is None:
                if cama_anterior_id is not None:
                    Cama.objects.select_for_update().get(pk=cama_anterior_id)
                MapeoCamasService.cerrar_asignacion_activa_paciente(
                    paciente_id=paciente_id,
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
                    paciente_id=paciente_id,
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
                    paciente_id=paciente_id,
                    usuario=usuario,
                    observacion="Cambio de cama - salida",
                )

            # La fila vieja se conserva para historial: solo se cierra.
            asignacion_activa.estado = estado_vacia
            asignacion_activa.paciente = None
            asignacion_activa.save(update_fields=["estado", "paciente"])

            # La nueva cama reutiliza su ultimo registro historico si existe.
            nueva_asignacion = (
                AsignacionCamaPaciente.objects.select_for_update()
                .filter(cama_id=cama_nueva_id)
                .order_by("-fecha_inicio")
                .first()
            )

            if nueva_asignacion:
                nueva_asignacion.paciente_id = paciente_id
                nueva_asignacion.usuario_asignacion = usuario
                nueva_asignacion.estado = estado_ocupada
                nueva_asignacion.fecha_inicio = now()
                nueva_asignacion.save(
                    update_fields=[
                        "paciente",
                        "usuario_asignacion",
                        "estado",
                        "fecha_inicio",
                    ]
                )
            else:
                nueva_asignacion = AsignacionCamaPaciente.objects.create(
                    cama_id=cama_nueva_id,
                    paciente_id=paciente_id,
                    usuario_asignacion=usuario,
                    estado=estado_ocupada,
                )

            MapeoCamasService.registrar_historial_estado_cama(
                cama_id=cama_nueva_id,
                estado_anterior=estado_vacia,
                estado_nuevo=estado_ocupada,
                paciente_id=paciente_id,
                usuario=usuario,
                observacion="Cambio de cama - entrada",
            )

            return nueva_asignacion

        return None

    # Alias explicito para mantener el nombre funcional solicitado.
    SINCRONIZAR_CAMA_CON_INGRESO = sincronizar_cama_con_ingreso
    SINCRONIZAR_CAMBIO_CAMA_EN_INGRESO = sincronizar_cambio_cama_en_ingreso

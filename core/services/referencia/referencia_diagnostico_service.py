from referencia.models import Referencia_diagnostico, Respuesta_diagnostico
from django.db import transaction
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *

class RefDiagnosticoService:


    @staticmethod
    def obtener_diagnosticos_referencia(referencia_id):
        """
        Obtiene los diagnosticos asociados a la referencia.
        """
        diagnosticos = Referencia_diagnostico.objects.filter(
            referencia_id=referencia_id, estado=True
        ).values(
            'diagnostico__id',
            'id',
            'diagnostico__nombre_diagnostico',
            'diagnostico__cie10__codigo',
            'detalle',
            'confirmada'
        )
        
        return list(diagnosticos)

    @staticmethod
    def procesar_diagnosticos_referencia(referencia_id, diagnosticos):

        if not diagnosticos:
            log_warning(
                f"No se enviaron diagnósticos en referencia {referencia_id}",
                app=LogApp.REFERENCIAS
            )
            raise ValueError("No se enviaron diagnosticos.")

        try:
            with transaction.atomic():

                # Desactivamos todos los diagnósticos
                Referencia_diagnostico.objects.filter(
                    referencia_id=referencia_id
                ).update(estado=False)

                for diagnostico in diagnosticos:
                    diag_id = diagnostico.get('id')
                    diag_ref = diagnostico.get('idDiagDB', 0)
                    detalle = diagnostico.get('detalle')
                    confirmado = diagnostico.get('confirmado', False)

                    if diag_ref and diag_ref > 0:
                        try:
                            referencia_diagnostico = Referencia_diagnostico.objects.get(
                                id=diag_ref,
                                referencia_id=referencia_id
                            )

                            referencia_diagnostico.estado = True
                            referencia_diagnostico.detalle = detalle.strip() if detalle else None
                            referencia_diagnostico.confirmada = confirmado
                            referencia_diagnostico.save()

                        except Referencia_diagnostico.DoesNotExist:
                            log_warning(
                                f"Diagnóstico referencia {diag_ref} no existe en referencia {referencia_id}",
                                app=LogApp.REFERENCIAS
                            )
                            raise ValueError(f"El diagnostico con id {diag_ref} no existe.")

                    else:
                        RefDiagnosticoService.crear_referencia_diagnostico(
                            referencia_id,
                            diag_id,
                            detalle,
                            confirmado
                        )

            # éxito (no logueamos porque así lo definiste)
            return {
                'mensaje': "Diagnosticos procesados correctamente"
            }

        except ValueError:
            raise

        except Exception:
            log_error(
                f"Error procesando diagnósticos referencia {referencia_id}",
                app=LogApp.REFERENCIAS
            )
            raise


    @staticmethod
    def crear_referencia_diagnostico(id_referencia, id_diagnostico, detalle, confirmado=False):
        """
        Crea un objeto Referencia Diagnostico.
        """
        try:
            Referencia_diagnostico.objects.create(
                referencia_id=id_referencia,
                diagnostico_id=id_diagnostico,
                detalle=detalle.upper().strip() if detalle else None,
                confirmada=confirmado
            )

        except Exception:
            log_error(
                f"Error creando diagnóstico referencia {id_referencia} diagnostico {id_diagnostico}",
                app=LogApp.REFERENCIAS
            )
            raise
        

    @staticmethod
    def obtener_diagnosticos_respuesta(respuesta_id):
        """
        Obtiene los diagnosticos asociados a la referencia.
        """
        diagnosticos = Respuesta_diagnostico.objects.filter(
            respuesta_id=respuesta_id, estado=True
        ).values(
            'diagnostico__id',
            'id',
            'diagnostico__nombre_diagnostico',
            'diagnostico__cie10__codigo',
            'detalle',
        )
        
        return list(diagnosticos)
    

    @staticmethod
    def procesar_diagnosticos_respuesta(respuesta_id, diagnosticos):

        if not diagnosticos:
            log_warning(
                f"No se enviaron diagnósticos en respuesta {respuesta_id}",
                app=LogApp.REFERENCIAS
            )
            raise ValueError("No se enviaron diagnósticos.")

        try:
            with transaction.atomic():

                # Desactivar todos
                Respuesta_diagnostico.objects.filter(
                    respuesta_id=respuesta_id
                ).update(estado=False)

                for diagnostico in diagnosticos:
                    diag_id = diagnostico.get('id')
                    diag_res = diagnostico.get('idDiagDB', 0)
                    detalle = diagnostico.get('detalle')

                    if diag_res and diag_res > 0:
                        try:
                            respuesta_diagnostico = Respuesta_diagnostico.objects.get(
                                id=diag_res,
                                respuesta_id=respuesta_id
                            )

                            respuesta_diagnostico.estado = True
                            respuesta_diagnostico.detalle = detalle.strip() if detalle else None
                            respuesta_diagnostico.save()

                        except Respuesta_diagnostico.DoesNotExist:
                            log_warning(
                                f"Diagnóstico respuesta {diag_res} no existe en respuesta {respuesta_id}",
                                app=LogApp.REFERENCIAS
                            )
                            raise ValueError(f"El diagnóstico con id {diag_res} no existe.")

                    else:
                        # nuevo → solo llamar, sin validar resultado
                        RefDiagnosticoService.crear_respuesta_diagnostico(
                            respuesta_id,
                            diag_id,
                            detalle
                        )

            return {
                'mensaje': "Diagnósticos procesados correctamente"
            }

        except ValueError:
            raise

        except Exception:
            log_error(
                f"Error procesando diagnósticos respuesta {respuesta_id}",
                app=LogApp.REFERENCIAS
            )
            raise
    

    #Respuesta 
    @staticmethod
    def crear_respuesta_diagnostico(id_respuesta, id_diagnostico, detalle):

        try:
            Respuesta_diagnostico.objects.create(
                respuesta_id=id_respuesta,
                diagnostico_id=id_diagnostico,
                detalle=detalle.upper().strip() if detalle else None
            )

        except Exception:
            log_error(
                f"Error creando diagnóstico respuesta {id_respuesta} diagnostico {id_diagnostico}",
                app=LogApp.REFERENCIAS
            )
            raise

        
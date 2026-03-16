from referencia.models import Referencia_diagnostico, Respuesta_diagnostico
from django.db import transaction

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
        """
        
        """
        if not diagnosticos:
            return {'error': True, 'mensaje':" No se enviaron diagnosticos."}

        with transaction.atomic():
            #Desactivamos todos los diagnosticos antes de procesarlos
            Referencia_diagnostico.objects.filter(referencia_id=referencia_id).update(estado=False)

            for diagnostico in diagnosticos:
                diag_id = diagnostico.get('id')
                diag_ref = diagnostico.get('idDiagDB', 0) #0 = nuevo 
                detalle = diagnostico.get('detalle')
                confirmado = diagnostico.get('confirmado', False)

                if diag_ref and diag_ref > 0:
                    try:
                        referencia_diagnostico = Referencia_diagnostico.objects.get(id=diag_ref, referencia_id=referencia_id)
                        referencia_diagnostico.estado = True
                        referencia_diagnostico.detalle = detalle.strip() if detalle else None
                        referencia_diagnostico.confirmada = confirmado
                        referencia_diagnostico.save()
                    except Referencia_diagnostico.DoesNotExist:
                        return {'error': True, 'mensaje': f"El diagnostico con id {diag_ref} no existe."}
                else:  # estudio nuevo → crear
                    resultado = RefDiagnosticoService.crear_referencia_diagnostico(referencia_id, diag_id, detalle, confirmado)
                    if resultado['error']:
                        return {'error': True, 'mensaje': resultado['mensaje']}
    
        return {'error': False, 'mensaje': "Diagnosticos procesados correctamente"}
    

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
            return {'error': False, 'mensaje': "Diagnostico procesado correctamente"}
        except Exception as e:
            return {
                'error': True,
                'mensaje': f"Error al crear el detalle: {str(e)}"
            }
        

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
        """
        Crea o actualiza los diagnósticos asociados a una respuesta.
        """
        if not diagnosticos:
            return {'error': True, 'mensaje': "No se enviaron diagnósticos."}

        with transaction.atomic():
            # Desactivar todos los diagnósticos antes de procesarlos
            Respuesta_diagnostico.objects.filter(respuesta_id=respuesta_id).update(estado=False)

            for diagnostico in diagnosticos:
                diag_id = diagnostico.get('id')
                diag_res = diagnostico.get('idDiagDB', 0)  # 0 = nuevo
                detalle = diagnostico.get('detalle')

                if diag_res and diag_res > 0:
                    try:
                        respuesta_diagnostico = Respuesta_diagnostico.objects.get(
                            id=diag_res, respuesta_id=respuesta_id
                        )
                        respuesta_diagnostico.estado = True
                        respuesta_diagnostico.detalle = detalle.strip() if detalle else None
                        respuesta_diagnostico.save()
                    except Respuesta_diagnostico.DoesNotExist:
                        return {'error': True, 'mensaje': f"El diagnóstico con id {diag_res} no existe."}
                else:
                    # Diagnóstico nuevo → crear
                    resultado = RefDiagnosticoService.crear_respuesta_diagnostico(
                        respuesta_id, diag_id, detalle
                    )
                    if resultado['error']:
                        return {'error': True, 'mensaje': resultado['mensaje']}

        return {'error': False, 'mensaje': "Diagnósticos procesados correctamente"}
    

    #Respuesta 
    @staticmethod
    def crear_respuesta_diagnostico(id_respuesta, id_diagnostico, detalle):
        """
        Crea un objeto RespuestaDiagnostico.
        """
        try:
            Respuesta_diagnostico.objects.create(
                respuesta_id=id_respuesta,
                diagnostico_id=id_diagnostico,
                detalle=detalle.upper().strip() if detalle else None
            )
            return {'error': False, 'mensaje': "Diagnóstico procesado correctamente"}
        except Exception as e:
            return {
                'error': True,
                'mensaje': f"Error al crear el detalle del diagnóstico: {str(e)}"
            }

    
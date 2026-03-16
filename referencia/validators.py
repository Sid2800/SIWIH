from django.core.exceptions import ValidationError
from servicio.models import Institucion_salud
from referencia.models import Referencia, Respuesta
import json
from clinico.models import Diagnostico


def validar_instituciones_origen_destino(origen, destino, tipo_ref):
    try:
        tipo_ref = int(tipo_ref)
    except (ValueError, TypeError):
        raise ValidationError("El tipo de referencia es incorrecto.")

    # Institución propia
    institucion_propia = Institucion_salud.objects.get(id=65) # el cerrato

    # Verificar que estén activas
    if origen and not origen.estado == 1:
        raise ValidationError("La institución de origen no está activa.")
    if destino and not destino.estado == 1:
        raise ValidationError("La institución de destino no está activa.")

    if tipo_ref == 0:  # recibida
        destino = institucion_propia
        if origen.id == institucion_propia.id:
            raise ValidationError("El origen de la referencia no puede ser el mismo que el destino.")
        


    elif tipo_ref == 1:  # enviada
        origen = institucion_propia
        if destino.id == institucion_propia.id:
            raise ValidationError("El destino de la referencia no puede ser el mismo que el origen.")
        if destino.proveedor_salud_id in [4, 5]:  # exluimos como posibles detinos a clinica privada y otros 
            raise ValidationError("El destino no puede ser una institución que no pertenezca a la Secretaría de Salud.")

    return origen, destino


def validar_diagnosticos_json(diagnosticos_json):

    if not diagnosticos_json or not isinstance(diagnosticos_json, str):
        raise ValidationError("Debe enviar al menos un diagnostico.")

    try:
        diagnosticos = json.loads(diagnosticos_json)
        codigos = [int(e['id']) for e in diagnosticos]
    except (TypeError, json.JSONDecodeError, KeyError, ValueError):
        raise ValidationError("Los diagnosticos enviados no son válidos.")

    # Comprobar que los estudios existen en la base de datos
    diagnosticos_existentes_ids = set(
        Diagnostico.objects.filter(id__in=codigos).values_list("id", flat=True)
    )

    for codigo in codigos:
        if codigo not in diagnosticos_existentes_ids:
            raise ValidationError(f"El código de diagnostico {codigo} no existe en la base de datos.")

    return diagnosticos



def validar_referencia_para_respuesta(id_referencia, id_paciente, tipo_referencia):
    referencia = Referencia.objects.filter(id=id_referencia,
        paciente_id=id_paciente, 
        tipo=tipo_referencia).first()
    if not referencia:
        raise ValidationError("Los datos indicados no coinciden con ninguna referencia existente.")
    if Respuesta.objects.filter(referencia_id=id_referencia).exists():
        raise ValidationError("Esta referencia ya tiene una respuesta asociada.")
    return referencia

def validar_respuesta_vs_referencia(id_respuesta, id_referencia):
    respuesta = Respuesta.objects.filter(id=id_respuesta,
        referencia_id=id_referencia).first()
    if not respuesta:
        raise ValidationError("Los datos indicados no coinciden con ninguna respuesta existente.")
    return respuesta
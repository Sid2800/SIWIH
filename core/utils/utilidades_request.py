import json
from django.http import JsonResponse

def cargar_json(request):
    """
    Intenta decodificar el JSON del cuerpo de la request.
    Retorna el diccionario o un JsonResponse de error.
    """
    try:
        return dict(json.loads(request.body)), None
    except json.JSONDecodeError:
        error = JsonResponse(
            {'error': 'El cuerpo de la solicitud no contiene JSON válido.'}, 
            status=400
        )
        return None, error
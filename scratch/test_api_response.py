import os
import sys
import django

# Agregar el directorio raíz al path de búsqueda de módulos
sys.path.append(os.getcwd())

# Configurar entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SIWI.settings')
django.setup()

import json
from django.test import RequestFactory
from django.contrib.auth.models import User
from s_exp.views import buscar_expedientes_api

def test_actual_api_call(query):
    print(f"--- Testeando API buscar_expedientes_api para: {query} ---")
    
    rf = RequestFactory()
    user = User.objects.get(username='soli')
    
    request = rf.get(f'/s_exp/api/buscar/?q={query}&tipo=expediente')
    request.user = user
    
    response = buscar_expedientes_api(request)
    print(f"Status: {response.status_code}")
    data = json.loads(response.content)
    
    for item in data.get('data', []):
        print(f"Expediente #{item['numero_expediente']}")
        print(f"  Disponible: {item['disponible']}")
        print(f"  Ubicación: {item['ubicacion_fisica']}")

if __name__ == "__main__":
    test_actual_api_call('47509')

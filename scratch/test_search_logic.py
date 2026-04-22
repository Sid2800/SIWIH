import os
import sys
import django
import json

# Agregar el directorio raíz al path de búsqueda de módulos
sys.path.append(os.getcwd())

# Configurar entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SIWI.settings')
django.setup()

from s_exp.models import SolicitudExpedienteDetalle, ExpedientePrestamo
from expediente.models import Expediente
from django.db.models import Q

def test_search(query):
    print(f"--- Simulando búsqueda para: {query} ---")
    
    # 1. Lógica de 'No Disponibles'
    expedientes_no_disponibles = set(
        ExpedientePrestamo.objects.exclude(estado_id='EXP_DISPONIBLE')
        .values_list('expediente_id', flat=True)
    )
    en_proceso = set(
        SolicitudExpedienteDetalle.objects.filter(
            solicitud__estado_flujo_id__in=['SOL_PENDIENTE', 'SOL_APROBADA_ORGANIZANDO', 'SOL_LISTO_RECOGER', 'SOL_EN_PRESTAMO', 'SOL_EN_DEVOLUCION', 'SOL_INCOMPLETA'],
            devuelto=False
        ).values_list('expediente_prestamo__expediente_id', flat=True)
    )
    prestados_ids = expedientes_no_disponibles | en_proceso
    
    # 2. Buscar expedientes
    qs = Expediente.objects.filter(numero=query)
    print(f"Encontrados {qs.count()} expedientes con ese número.")
    
    for exp in qs:
        esta_prestado = exp.id in prestados_ids
        print(f"Expediente #{exp.numero} (ID: {exp.id})")
        print(f"  ¿Está en prestados_ids? {esta_prestado}")
        if esta_prestado:
            if exp.id in expedientes_no_disponibles:
                print(f"    - Encontrado en expedientes_no_disponibles (Estado != EXP_DISPONIBLE)")
            if exp.id in en_proceso:
                print(f"    - Encontrado en en_proceso (Solicitud abierta)")

if __name__ == "__main__":
    test_search('47509')

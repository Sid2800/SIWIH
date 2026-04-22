import os
import sys
import django

# Agregar el directorio raíz al path de búsqueda de módulos
sys.path.append(os.getcwd())

# Configurar entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SIWI.settings')
django.setup()

from django.contrib.auth.models import User
from s_exp.models import SolicitudPrestamo, ExpedientePrestamo, ExpedienteEstadoLog

def reparar_datos():
    print("--- Diagnosticando expedientes en solicitudes rechazadas ---")
    
    # 1. Buscar solicitudes rechazadas
    solicitudes_rechazadas = SolicitudPrestamo.objects.filter(estado_flujo_id='SOL_RECHAZADA')
    total_solicitudes = solicitudes_rechazadas.count()
    print(f"Encontradas {total_solicitudes} solicitudes con estado SOL_RECHAZADA.")
    
    for solicitud in solicitudes_rechazadas:
        print(f"Revisando Solicitud #{solicitud.id} (Usuario: {solicitud.usuario.username})")
        detalles = solicitud.detalles.select_related('expediente_prestamo__expediente')
        if not detalles:
            print("  No tiene expedientes asociados.")
        for d in detalles:
            ep = d.expediente_prestamo
            print(f"  Expediente #{ep.expediente.numero} - Estado actual: {ep.estado_id} ({ep.estado.nombre})")

if __name__ == "__main__":
    reparar_datos()

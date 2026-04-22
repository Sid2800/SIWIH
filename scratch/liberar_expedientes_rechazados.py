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
    print("--- Iniciando reparación de expedientes en solicitudes rechazadas ---")
    
    # Obtener un usuario para el log (obligatorio por modelo)
    admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
    if not admin_user:
        print("Error: No se encontró ningún usuario en el sistema para realizar el log.")
        return

    # 1. Buscar solicitudes rechazadas
    solicitudes_rechazadas = SolicitudPrestamo.objects.filter(estado_flujo_id='SOL_RECHAZADA')
    total_solicitudes = solicitudes_rechazadas.count()
    print(f"Encontradas {total_solicitudes} solicitudes con estado SOL_RECHAZADA.")
    
    count_liberados = 0
    for solicitud in solicitudes_rechazadas:
        # Detalles de esa solicitud
        detalles = solicitud.detalles.select_related('expediente_prestamo')
        for d in detalles:
            ep = d.expediente_prestamo
            # Si el expediente sigue "Apartado", liberarlo
            if ep.estado_id == 'EXP_APARTADO':
                estado_ant = ep.estado
                ep.estado_id = 'EXP_DISPONIBLE'
                ep.save()
                
                # Registrar el cambio para auditoría
                ExpedienteEstadoLog.objects.create(
                    expediente=ep.expediente,
                    estado_anterior=estado_ant,
                    estado_nuevo_id='EXP_DISPONIBLE',
                    usuario=admin_user, 
                    solicitud=solicitud,
                    observacion="Liberación masiva de datos por solicitud previamente rechazada (Mantenimiento)"
                )
                count_liberados += 1
                print(f"  Expediente #{ep.expediente.numero} liberado (Pertenecía a Solicitud #{solicitud.id})")

    print(f"\n--- Resumen de Operación ---")
    print(f"Solicitudes revisadas: {total_solicitudes}")
    print(f"Expedientes liberados: {count_liberados}")
    print("--- Proceso finalizado ---")

if __name__ == "__main__":
    reparar_datos()

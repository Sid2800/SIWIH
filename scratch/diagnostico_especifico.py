import os
import sys
import django

# Agregar el directorio raíz al path de búsqueda de módulos
sys.path.append(os.getcwd())

# Configurar entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SIWI.settings')
django.setup()

from s_exp.models import SolicitudExpedienteDetalle, SolicitudPrestamo, ExpedientePrestamo

def diagnostico_expediente(numero_expediente):
    print(f"--- Diagnóstico para Expediente #{numero_expediente} ---")
    
    # 1. Información base
    try:
        ep = ExpedientePrestamo.objects.get(expediente__numero=numero_expediente)
        print(f"Estado físico actual: {ep.estado_id} ({ep.estado.nombre})")
    except ExpedientePrestamo.DoesNotExist:
        print("No tiene registro en ExpedientePrestamo.")
        return

    # 2. Solicitudes asociadas
    detalles = SolicitudExpedienteDetalle.objects.filter(expediente_prestamo=ep).select_related('solicitud__estado_flujo')
    print(f"Encontradas {detalles.count()} solicitudes asociadas:")
    for d in detalles:
        s = d.solicitud
        print(f"  Solicitud #{s.id}: Estado={s.estado_flujo_id} ({s.estado_flujo.nombre}), Usuario={s.usuario.username}")

if __name__ == "__main__":
    import sys
    num = sys.argv[1] if len(sys.argv) > 1 else '47509'
    diagnostico_expediente(num)

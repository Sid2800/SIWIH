
import os
import sys
import django

# Agregar el directorio raíz al path de búsqueda de módulos
sys.path.append(os.getcwd())

# Configurar entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SIWI.settings')
django.setup()

from s_exp.models import MotivoSolicitud, EstadoSolicitud, EstadoExpedienteFisico

def poblar_datos():
    print("--- Iniciando población de catálogos s_exp ---")

    # 1. Motivos de Solicitud
    motivos = [
        "ANALISIS", "COMISIÓN QUIRÚRGICA", "COMPLICACIONES NEONATALES", 
        "COMPLICACIONES OBSTÉTRICAS", "CONSTANCIA", "DEFUNCIONES", "FICHAS", 
        "INFECCIÓNES", "INVESTIGACION", "MEDICION", "MONITORIA", 
        "REPOSICIÓN DE CONSTANCIA NACIMIENTO", "REVISION", 
        "REVISIÓN REFERENCIAS", "REVISIÓN SAI", "TESIS"
    ]
    for m in motivos:
        obj, created = MotivoSolicitud.objects.get_or_create(nombre=m)
        if created: print(f"Motivo creado: {m}")

    # 2. Estados de Solicitud
    estados_sol = [
        ('SOL_PENDIENTE', 'Pendiente', 'Solicitud creada por el personal.'),
        ('SOL_RECHAZADA', 'Rechazada', 'Solicitud rechazada por el administrador.'),
        ('SOL_APROBADA_ORGANIZANDO', 'En proceso de organización', 'Aprobada, buscando expedientes físicos.'),
        ('SOL_LISTO_RECOGER', 'Listo para recoger', 'Expedientes listos en ventanilla.'),
        ('SOL_EN_PRESTAMO', 'En préstamo', 'Expedientes entregados al personal.'),
        ('SOL_EN_DEVOLUCION', 'En devolución / Por revisar', 'Personal ha retornado los expedientes.'),
        ('SOL_INCOMPLETA', 'Devolución incompleta', 'Faltan expedientes por entregar.'),
        ('SOL_FINALIZADA', 'Finalizada/Cerrada', 'Todos los expedientes devueltos correctamente.'),
    ]
    for cod, nom, desc in estados_sol:
        obj, created = EstadoSolicitud.objects.update_or_create(
            codigo=cod,
            defaults={'nombre': nom, 'descripcion': desc}
        )
        if created: print(f"Estado Solicitud creado: {cod}")
        else: print(f"Estado Solicitud actualizado: {cod}")

    # 3. Estados de Expediente Físico
    estados_exp = [
        ('EXP_DISPONIBLE', 'Disponible'),
        ('EXP_APARTADO', 'Apartado en solicitud'),
        ('EXP_PRESTADO', 'En préstamo'),
        ('EXP_PERDIDO', 'Perdido'),
        ('EXP_BAJA', 'Retirado / Dado de baja'),
    ]
    for cod, nom in estados_exp:
        obj, created = EstadoExpedienteFisico.objects.update_or_create(
            codigo=cod,
            defaults={'nombre': nom}
        )
        if created: print(f"Estado Físico creado: {cod}")
        else: print(f"Estado Físico actualizado: {cod}")

    print("--- Proceso finalizado ---")

if __name__ == "__main__":
    poblar_datos()

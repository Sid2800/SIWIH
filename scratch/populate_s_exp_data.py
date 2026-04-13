import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SIWI.settings')
django.setup()

from s_exp.models import MotivoSolicitud, EstadoSolicitud, EstadoExpedienteFisico

def populate():
    # 1. Motivos
    motivos = [
        "ANALISIS", "COMISIÓN QUIRÚRGICA", "COMPLICACIONES NEONATALES",
        "COMPLICACIONES OBSTÉTRICAS", "CONSTANCIA", "DEFUNCIONES", "FICHAS",
        "INFECCIÓNES", "INVESTIGACION", "MEDICION", "MONITORIA",
        "REPOSICIÓN DE CONSTANCIA NACIMIENTO", "REVISION", "REVISIÓN REFERENCIAS",
        "REVISIÓN SAI", "TESIS"
    ]
    for m in motivos:
        obj, created = MotivoSolicitud.objects.get_or_create(nombre=m)
        if created:
            print(f"Creado motivo: {m}")
        else:
            print(f"Motivo ya existe: {m}")

    # 2. Estados de Solicitud
    estados_sol = [
        ('SOL_PENDIENTE', 'Pendiente'),
        ('SOL_RECHAZADA', 'Rechazada'),
        ('SOL_APROBADA_ORGANIZANDO', 'En proceso de organización'),
        ('SOL_LISTO_RECOGER', 'Listo para recoger'),
        ('SOL_EN_PRESTAMO', 'En préstamo'),
        ('SOL_EN_DEVOLUCION', 'En devolución / Por revisar'),
        ('SOL_INCOMPLETA', 'Devolución incompleta'),
        ('SOL_FINALIZADA', 'Finalizada/Cerrada'),
    ]
    for codigo, nombre in estados_sol:
        obj, created = EstadoSolicitud.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
        if created:
            print(f"Creado estado solicitud: {nombre} ({codigo})")
        else:
            obj.nombre = nombre
            obj.save()
            print(f"Actualizado estado solicitud: {nombre} ({codigo})")

    # 3. Estados Expediente Físico
    estados_exp = [
        ('EXP_DISPONIBLE', 'Disponible'),
        ('EXP_APARTADO', 'Apartado en solicitud'),
        ('EXP_PRESTADO', 'En préstamo'),
        ('EXP_PERDIDO', 'Perdido'),
        ('EXP_BAJA', 'Retirado / Dado de baja'),
    ]
    for codigo, nombre in estados_exp:
        obj, created = EstadoExpedienteFisico.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
        if created:
            print(f"Creado estado expediente: {nombre} ({codigo})")
        else:
            obj.nombre = nombre
            obj.save()
            print(f"Actualizado estado expediente: {nombre} ({codigo})")

if __name__ == "__main__":
    populate()

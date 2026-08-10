"""
Agrega el estado físico EXP_PENDIENTE_PRESTAMO al catálogo.

Origen del flujo: durante la "Revisión de Entrega" el admin puede marcar un
expediente como "préstamo pendiente" (encontrado pero aún no se entrega). Ese
expediente queda RESERVADO (no disponible para otros) hasta que se entregue o
se cancele el pendiente. Se muestra en morado en los listados.

Se siembra vía migración (no SQL) igual que el resto de catálogos del módulo.
"""
from django.db import migrations


NUEVO_ESTADO = ('EXP_PENDIENTE_PRESTAMO', 'Pendiente de préstamo')


def agregar_estado(apps, schema_editor):
    EstadoExpedienteFisico = apps.get_model('s_exp', 'EstadoExpedienteFisico')
    codigo, nombre = NUEVO_ESTADO
    EstadoExpedienteFisico.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})


def quitar_estado(apps, schema_editor):
    EstadoExpedienteFisico = apps.get_model('s_exp', 'EstadoExpedienteFisico')
    EstadoExpedienteFisico.objects.filter(codigo=NUEVO_ESTADO[0]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('s_exp', '0003_solicitudexpedientedetalle_comentario_usuario_devolucion_and_more'),
    ]

    operations = [
        migrations.RunPython(agregar_estado, quitar_estado),
    ]

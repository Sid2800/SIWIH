"""
Migración de datos (backfill).

Llena el campo `paciente` (FK) en SolicitudExpedienteDetalle para registros
ya existentes, usando la siguiente cascada de resolución:

  1. PacienteAsignacion activa (estado='1') para el expediente del detalle.
  2. Cualquier PacienteAsignacion del expediente (la más reciente).
  3. Búsqueda por DNI usando el campo deprecado `paciente_identidad`.

Si ninguna resuelve, el campo queda en NULL — es nullable por compatibilidad.
"""
from django.db import migrations


def backfill_paciente(apps, schema_editor):
    SolicitudExpedienteDetalle = apps.get_model('s_exp', 'SolicitudExpedienteDetalle')
    Paciente = apps.get_model('paciente', 'Paciente')
    PacienteAsignacion = apps.get_model('expediente', 'PacienteAsignacion')

    actualizados = 0
    sin_resolver = 0

    # Solo procesamos los que aún no tienen paciente
    qs = SolicitudExpedienteDetalle.objects.filter(paciente__isnull=True).select_related(
        'expediente_prestamo__expediente'
    )

    for detalle in qs.iterator():
        paciente = None
        expediente = detalle.expediente_prestamo.expediente if detalle.expediente_prestamo else None

        # Estrategia 1: asignación activa
        if expediente:
            asig = PacienteAsignacion.objects.filter(
                expediente=expediente, estado='1'
            ).select_related('paciente').first()
            if asig:
                paciente = asig.paciente

        # Estrategia 2: cualquier asignación previa del expediente
        if paciente is None and expediente:
            asig = PacienteAsignacion.objects.filter(
                expediente=expediente
            ).select_related('paciente').order_by('-fecha_asignacion').first()
            if asig:
                paciente = asig.paciente

        # Estrategia 3: buscar por DNI del snapshot
        if paciente is None and detalle.paciente_identidad:
            dni_limpio = detalle.paciente_identidad.replace('-', '').replace(' ', '').strip()
            if dni_limpio:
                paciente = Paciente.objects.filter(dni=dni_limpio).first()

        if paciente:
            detalle.paciente = paciente
            detalle.save(update_fields=['paciente'])
            actualizados += 1
        else:
            sin_resolver += 1

    if actualizados or sin_resolver:
        print(f"\n[backfill_paciente_fk] Actualizados: {actualizados}, sin resolver: {sin_resolver}")


def reverse_noop(apps, schema_editor):
    """Reversa: no hace nada (los datos quedan, simplemente)."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('s_exp', '0013_add_paciente_fk_marcar_deprecados'),
        ('paciente', '0001_initial'),
        ('expediente', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill_paciente, reverse_noop),
    ]

"""
Datos: poblar expediente_ubicacion desde las unidades de `servicio`.
=============================================================================

Crea una fila en expediente_ubicacion por cada unidad ACTIVA existente AL
MOMENTO del migrate (snapshot inicial):

  - servicio.Unidad_clinica (estado=1)  → tipo=1 (Clínica)
  - servicio.Unidad         (estado=1)  → tipo=2 (No Clínica)

Guarda SOLO el ID (relación), no texto. A partir de aquí, los signals de
`expediente/signals.py` mantienen el catálogo sincronizado: altas, reactivaciones
y bajas (desactivaciones) de unidades se reflejan automáticamente.

Idempotente: si la unidad ya tiene su fila, la salta (no duplica). Requiere que
las unidades de servicio ya existan (vienen del dump base, restaurado antes del
migrate). Si se corre sin unidades, no crea nada y puede re-ejecutarse luego con
`python manage.py poblar_ubicaciones`.
"""
from django.db import migrations


def poblar(apps, schema_editor):
    ExpedienteUbicacion = apps.get_model('expediente', 'ExpedienteUbicacion')
    Unidad_clinica = apps.get_model('servicio', 'Unidad_clinica')
    Unidad = apps.get_model('servicio', 'Unidad')

    TIPO_CLINICA = 1
    TIPO_NO_CLINICA = 2

    # ---- Clínicas (tipo=1) ----
    ya_clin = set(
        ExpedienteUbicacion.objects
        .filter(unidad_clinica__isnull=False)
        .values_list('unidad_clinica_id', flat=True)
    )
    nuevas = [
        ExpedienteUbicacion(unidad_clinica_id=uid, tipo=TIPO_CLINICA, estado=True)
        for uid in Unidad_clinica.objects.filter(estado=1).values_list('id', flat=True)
        if uid not in ya_clin
    ]
    if nuevas:
        ExpedienteUbicacion.objects.bulk_create(nuevas)


def _noop(apps, schema_editor):
    # No revertir: las ubicaciones pueden estar referenciadas por préstamos.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('expediente', '0008_expediente_ubicacion'),
        ('servicio', '0016_alter_unidad_clinica_options_and_more'),
    ]

    operations = [
        migrations.RunPython(poblar, _noop),
    ]

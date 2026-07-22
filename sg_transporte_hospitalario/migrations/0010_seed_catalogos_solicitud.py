from django.db import migrations


def seed_catalogos_solicitud(apps, schema_editor):
    TipoSolicitud = apps.get_model("sg_transporte_hospitalario", "TipoSolicitud")
    Prioridad = apps.get_model("sg_transporte_hospitalario", "Prioridad")
    PuntoSolicitud = apps.get_model("sg_transporte_hospitalario", "PuntoSolicitud")
    Unidad = apps.get_model("servicio", "Unidad")
    UnidadClinica = apps.get_model("servicio", "Unidad_clinica")

    tipos_solicitud = [
        {"codigo": "ADMINISTRATIVOS", "nombre": "ADMINISTRATIVOS", "descripcion": "Traslado de apoyo administrativo."},
        {"codigo": "INSUMOS", "nombre": "INSUMOS", "descripcion": "Traslado de insumos y materiales."},
        {"codigo": "PACIENTES", "nombre": "PACIENTES", "descripcion": "Traslado de pacientes."},
    ]

    for item in tipos_solicitud:
        TipoSolicitud.objects.update_or_create(
            codigo=item["codigo"],
            defaults={
                "nombre": item["nombre"],
                "descripcion": item["descripcion"],
                "activo": True,
            },
        )

    prioridades = [
        {"codigo": "NORMAL", "nombre": "Normal", "nivel": 1},
        {"codigo": "URGENTE", "nombre": "Urgente", "nivel": 2},
    ]

    for item in prioridades:
        Prioridad.objects.update_or_create(
            codigo=item["codigo"],
            defaults={
                "nombre": item["nombre"],
                "nivel": item["nivel"],
                "descripcion": None,
                "activo": True,
            },
        )

    for unidad in Unidad.objects.filter(estado=1):
        PuntoSolicitud.objects.get_or_create(
            unidad_id=unidad.id,
            defaults={
                "unidad_clinica_id": None,
                "activo": True,
            },
        )

    for unidad_clinica in UnidadClinica.objects.filter(estado=1):
        PuntoSolicitud.objects.get_or_create(
            unidad_clinica_id=unidad_clinica.id,
            defaults={
                "unidad_id": None,
                "activo": True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("sg_transporte_hospitalario", "0009_alter_solicitud_estado_choices"),
        ("servicio", "0018_alter_cama_estado_alter_unidad_tipo"),
    ]

    operations = [
        migrations.RunPython(seed_catalogos_solicitud, migrations.RunPython.noop),
    ]

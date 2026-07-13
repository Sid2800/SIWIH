from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("mapeo_camas", "0002_remove_detallemapeocama_ubicacion"),
    ]

    operations = [
        # Se elimina la restriccion CHECK antes de borrar la columna.
        migrations.RemoveConstraint(
            model_name="asignacioncamapaciente",
            name="chk_asig_fechas_validas",
        ),
        migrations.RemoveField(
            model_name="asignacioncamapaciente",
            name="fecha_fin",
        ),
        migrations.RemoveField(
            model_name="asignacioncamapaciente",
            name="usuario_cierre",
        ),
    ]

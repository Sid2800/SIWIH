from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("mapeo_camas", "0001_squashed_0018_remove_estadomapeo_nombre"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="detallemapeocama",
            name="ubicacion",
        ),
    ]

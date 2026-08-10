from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sg_transporte_hospitalario", "0013_programacion_viaje_recursos"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "UPDATE transporte_hospitalario_viaje "
                "SET tipo_viaje = CASE "
                "WHEN tipo_viaje IN ('REGIONAL', '1') OR tipo_viaje IS NULL OR tipo_viaje = '' THEN '1' "
                "WHEN tipo_viaje IN ('NACIONAL', '2') THEN '2' "
                "ELSE '1' END"
            ),
            reverse_sql=(
                "UPDATE transporte_hospitalario_viaje "
                "SET tipo_viaje = CASE "
                "WHEN tipo_viaje = '1' THEN 'REGIONAL' "
                "WHEN tipo_viaje = '2' THEN 'NACIONAL' "
                "ELSE tipo_viaje END"
            ),
        ),
        migrations.AlterField(
            model_name="viaje",
            name="tipo_viaje",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "Regional"),
                    (2, "Nacional"),
                ],
                db_index=True,
                default=1,
            ),
        ),
        migrations.RemoveField(
            model_name="viaje",
            name="viatico",
        ),
    ]

# Generated manually to keep equipos datetime columns without fractional seconds.

from django.db import migrations


DATETIME_COLUMNS = {
    "equipo_dispositivo": [
        ("fecha_creado", False),
        ("fecha_modificado", False),
    ],
    "equipo_baja_dispositivo": [
        ("fecha_registro", False),
    ],
    "equipo_asignacion_dispositivo": [
        ("fecha_inicio", False),
        ("fecha_fin", True),
        ("fecha_creado", False),
        ("fecha_modificado", False),
    ],
}


def _alter_datetime_precision(schema_editor, column_type):
    # MySQL/Django normally creates DateTimeField as datetime(6). The hospital
    # convention is second precision, so these columns are changed to datetime.
    if schema_editor.connection.vendor != "mysql":
        return

    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        for table, columns in DATETIME_COLUMNS.items():
            alterations = []
            for column, nullable in columns:
                null_sql = "NULL" if nullable else "NOT NULL"
                alterations.append(
                    f"MODIFY {quote(column)} {column_type} {null_sql}"
                )
            cursor.execute(
                f"ALTER TABLE {quote(table)} " + ", ".join(alterations)
            )


def forwards(apps, schema_editor):
    _alter_datetime_precision(schema_editor, "datetime")


def backwards(apps, schema_editor):
    _alter_datetime_precision(schema_editor, "datetime(6)")


class Migration(migrations.Migration):

    dependencies = [
        ("equipos", "0015_alter_dispositivo_estado"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
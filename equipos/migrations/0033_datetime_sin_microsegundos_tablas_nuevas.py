# Generated manually to keep all equipos datetime columns at second precision.

from django.db import migrations


DATETIME_COLUMNS = {
    "equipo_orden_trabajo_baja": [
        ("fecha_creado", False),
    ],
    "equipo_pausa_garantia": [
        ("fecha_creado", False),
        ("fecha_modificado", False),
    ],
}


def _truncate_microseconds(schema_editor):
    """Remove existing fractional seconds before narrowing the columns."""
    if schema_editor.connection.vendor != "mysql":
        return

    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        for table, columns in DATETIME_COLUMNS.items():
            assignments = []
            for column, _nullable in columns:
                quoted_column = quote(column)
                assignments.append(
                    f"{quoted_column} = DATE_SUB("
                    f"{quoted_column}, "
                    f"INTERVAL MICROSECOND({quoted_column}) MICROSECOND)"
                )
            cursor.execute(
                f"UPDATE {quote(table)} SET " + ", ".join(assignments)
            )


def _alter_datetime_precision(schema_editor, column_type):
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
    _truncate_microseconds(schema_editor)
    _alter_datetime_precision(schema_editor, "datetime(0)")


def backwards(apps, schema_editor):
    # Restoring the precision cannot recover fractions already removed.
    _alter_datetime_precision(schema_editor, "datetime(6)")


class Migration(migrations.Migration):

    dependencies = [
        ("equipos", "0032_procedencia_telefono_alterno"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

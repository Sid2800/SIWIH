from django.db import migrations


CODIGO_UNIDAD = "EQ"
NOMBRE_UNIDAD = "EQUIPOS"

# servicio.TipoUnidad.APOYO y core.EstadoRegistro.ACTIVO. Se escriben aqui
# como enteros porque una migracion no debe importar codigo de la aplicacion:
# si manana esos choices cambian, la migracion ya aplicada seguiria valiendo.
TIPO_APOYO = 3
ESTADO_ACTIVO = 1


def crear_unidad_equipos(apps, schema_editor):
    """Da de alta la unidad que autoriza el modulo de Equipos.

    EQ no es un area fisica del hospital: es la unidad a la que se asigna un
    PerfilUnidad para conceder acceso al inventario. Los tecnicos se agregan
    despues desde el admin de Django; aqui solo se crea el contenedor.
    """
    Unidad = apps.get_model("servicio", "Unidad")
    Usuario = apps.get_model("auth", "User")

    # Unidad exige creado_por y modificado_por, que no admiten vacio. En una
    # base de pruebas recien creada todavia no hay usuarios: las migraciones
    # corren antes que los fixtures. En ese caso no se crea nada y es el
    # propio fixture quien da de alta la unidad, que si tiene a quien
    # atribuirsela. En desarrollo y produccion siempre hay usuarios.
    responsable = Usuario.objects.order_by("pk").first()

    if responsable is None:
        return

    Unidad.objects.get_or_create(
        nombre_corto_unidad=CODIGO_UNIDAD,
        defaults={
            "nombre_unidad": NOMBRE_UNIDAD,
            "tipo": TIPO_APOYO,
            "estado": ESTADO_ACTIVO,
            "creado_por": responsable,
            "modificado_por": responsable,
        },
    )


def quitar_unidad_equipos(apps, schema_editor):
    """Retira la unidad solo si nadie la esta usando.

    Si ya hay tecnicos con PerfilUnidad en EQ, borrarla dejaria a esa gente
    sin acceso de forma silenciosa. En ese caso se conserva.
    """
    Unidad = apps.get_model("servicio", "Unidad")
    PerfilUnidad = apps.get_model("usuario", "PerfilUnidad")

    unidad = Unidad.objects.filter(nombre_corto_unidad=CODIGO_UNIDAD).first()

    if unidad and not PerfilUnidad.objects.filter(servicio_unidad=unidad).exists():
        unidad.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("equipos", "0025_remove_dispositivo_bio_disp_garantia_fecha_valida_and_more"),
        ("servicio", "0018_alter_cama_estado_alter_unidad_tipo"),
        ("usuario", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_unidad_equipos, quitar_unidad_equipos),
    ]

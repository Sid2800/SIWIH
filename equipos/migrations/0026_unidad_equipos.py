from django.db import migrations
from django.db.models.deletion import ProtectedError


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
    # base recien creada las migraciones corren antes que exista ningun
    # usuario, asi que aqui no hay a quien atribuirla y la migracion se marca
    # como aplicada sin haber creado nada.
    #
    # Ese hueco lo cierra el receptor post_migrate de equipos/signals.py, que
    # vuelve a intentarlo en cada migrate posterior, cuando ya hay superusuario.
    # Mientras la unidad no exista nadie puede tener PerfilUnidad en EQ, de
    # modo que el modulo queda cerrado, nunca abierto.
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

    Se conserva en dos casos, y en ninguno se interrumpe la marcha atras:

    - Si hay tecnicos con PerfilUnidad en EQ, borrarla les quitaria el acceso
      de forma silenciosa.
    - Si expediente ya le creo su ExpedienteUbicacion. Ese modulo la referencia
      con PROTECT a proposito y su propio codigo advierte que una unidad con
      ubicacion no se puede eliminar. Borrar esa fila seria meter mano en datos
      de otro modulo, asi que se deja la unidad donde esta.

    Una unidad de mas es inofensiva: sin PerfilUnidad que apunte a ella no
    concede nada. Una migracion que revienta a mitad del rollback, no.
    """
    Unidad = apps.get_model("servicio", "Unidad")
    PerfilUnidad = apps.get_model("usuario", "PerfilUnidad")

    unidad = Unidad.objects.filter(nombre_corto_unidad=CODIGO_UNIDAD).first()

    if unidad is None:
        return

    if PerfilUnidad.objects.filter(servicio_unidad=unidad).exists():
        return

    try:
        unidad.delete()
    except ProtectedError:
        # Otro modulo la referencia. Se deja tal cual; el rollback continua.
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("equipos", "0025_remove_dispositivo_bio_disp_garantia_fecha_valida_and_more"),
        ("servicio", "0018_alter_cama_estado_alter_unidad_tipo"),
        # La marcha atras consulta PerfilUnidad.servicio_unidad, que no existe
        # hasta usuario.0004: en 0001 el campo todavia se llama unidad y apunta
        # a un modelo que despues se borra. Se depende de la hoja de usuario
        # para que el estado historico tenga el campo con su nombre actual.
        ("usuario", "0009_merge_0007_delete_unidad_0008_alter_perfilunidad_rol"),
    ]

    operations = [
        migrations.RunPython(crear_unidad_equipos, quitar_unidad_equipos),
    ]

"""El catalogo pasa a ser una cadena: tipo de equipo -> marca -> modelo.

Antes las marcas eran una lista global y los modelos colgaban solo de la
marca. Al registrar un equipo eso obligaba a recorrer todas las marcas del
hospital para encontrar las tres que fabrican el aparato que se tiene delante,
y permitia elegir el modelo de una impresora para una camilla.

Ahora el tipo declara que marcas lo fabrican, y cada modelo pertenece a la
pareja tipo-marca. El formulario ofrece en cada paso solo lo que existe para
lo ya elegido.

Ademas el tipo de tecnologia se muda del equipo al tipo: todas las camillas
son mecanicas y todos los monitores electronicos, asi que no es un dato de
cada aparato. La copia se hace antes de borrar la columna vieja, para no
perder lo que ya estaba registrado.
"""

import django.db.models.deletion
from django.db import migrations, models


# Tipo al que pertenece cada modelo de los datos de prueba sembrados a mano.
# Solo se usa para los que ningun equipo esta usando todavia: cuando hay un
# equipo registrado, su tipo es la fuente fiable y este mapa no se consulta.
TIPO_POR_MODELO = {
    "L3250": "IMPRESORA MULTIFUNCIONAL",
    "L3210": "IMPRESORA MULTIFUNCIONAL",
    "L5290": "IMPRESORA MULTIFUNCIONAL",
    "LASERJET PRO M404DN": "IMPRESORA MULTIFUNCIONAL",
    "PROBOOK 450 G9": "COMPUTADORA PORTATIL",
    "OPTIPLEX 3090": "COMPUTADORA DE ESCRITORIO",
    "BENEVIEW T5": "MONITOR DE SIGNOS VITALES",
    "DUAL INVERTER 12000 BTU": "AIRE ACONDICIONADO",
}

NO_ELECTRONICOS = ["CAMILLA DE TRASLADO"]

TECNOLOGIA_ELECTRONICA = 1
TECNOLOGIA_NO_ELECTRONICA = 2


def reorganizar(apps, schema_editor):
    Dispositivo = apps.get_model("equipos", "Dispositivo")
    ModeloDispositivo = apps.get_model("equipos", "ModeloDispositivo")
    TipoDispositivo = apps.get_model("equipos", "TipoDispositivo")

    # 1. La tecnologia que cada equipo tenia registrada pasa a su tipo. Si dos
    #    equipos del mismo tipo se contradicen gana el primero: el dato
    #    correcto es uno solo y de ahi en adelante lo decide el catalogo.
    for tipo_id, tecnologia in Dispositivo.objects.exclude(
        tipo_tecnologia__isnull=True
    ).values_list("tipo_id", "tipo_tecnologia"):
        TipoDispositivo.objects.filter(pk=tipo_id).update(
            tipo_tecnologia=tecnologia
        )

    TipoDispositivo.objects.filter(nombre__in=NO_ELECTRONICOS).update(
        tipo_tecnologia=TECNOLOGIA_NO_ELECTRONICA
    )

    # 2. Cada modelo necesita su tipo. El primer origen es el equipo que lo
    #    usa, porque es una relacion real ya registrada.
    tipos_por_nombre = dict(
        TipoDispositivo.objects.values_list("nombre", "pk")
    )
    huerfanos = []

    for modelo in ModeloDispositivo.objects.all():
        equipo = Dispositivo.objects.filter(modelo_id=modelo.pk).first()
        tipo_id = equipo.tipo_id if equipo else None

        if tipo_id is None:
            tipo_id = tipos_por_nombre.get(TIPO_POR_MODELO.get(modelo.nombre))

        if tipo_id is None:
            huerfanos.append(modelo)
            continue

        modelo.tipo_id = tipo_id
        modelo.save(update_fields=["tipo"])

    # 3. Los que no se pudieron clasificar se dejan en el primer tipo y
    #    desactivados, para que nadie los elija por error. Aparecen en el
    #    catalogo con su estado inactivo y se corrigen desde ahi.
    if huerfanos:
        tipo_provisional = TipoDispositivo.objects.order_by("pk").first()

        for modelo in huerfanos:
            modelo.tipo_id = tipo_provisional.pk
            modelo.activo = False
            modelo.save(update_fields=["tipo", "activo"])

        print(
            f"\n  {len(huerfanos)} modelo(s) sin tipo reconocible quedaron "
            f"desactivados en '{tipo_provisional.nombre}'. Reasignelos desde "
            f"el catalogo."
        )

    # 4. Las marcas que ya aparecen en algun modelo o equipo se declaran en su
    #    tipo, que es lo que hace visible la cascada.
    relacion = TipoDispositivo.marcas.through
    parejas = set(
        ModeloDispositivo.objects.exclude(tipo_id=None).values_list(
            "tipo_id", "marca_id"
        )
    )
    parejas |= set(
        Dispositivo.objects.exclude(marca_id=None).values_list(
            "tipo_id", "marca_id"
        )
    )

    relacion.objects.bulk_create(
        [
            relacion(tipodispositivo_id=tipo_id, marcadispositivo_id=marca_id)
            for tipo_id, marca_id in sorted(parejas)
        ],
        ignore_conflicts=True,
    )


def revertir(apps, schema_editor):
    """Devuelve la tecnologia al equipo; el resto lo deshace el esquema."""
    Dispositivo = apps.get_model("equipos", "Dispositivo")
    TipoDispositivo = apps.get_model("equipos", "TipoDispositivo")

    for tipo_id, tecnologia in TipoDispositivo.objects.values_list(
        "pk", "tipo_tecnologia"
    ):
        Dispositivo.objects.filter(tipo_id=tipo_id).update(
            tipo_tecnologia=tecnologia
        )


class Migration(migrations.Migration):

    dependencies = [
        ('equipos', '0038_colores_ordenados'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='modelodispositivo',
            options={'ordering': ['tipo__nombre', 'marca__nombre', 'nombre'], 'verbose_name': 'Modelo de equipo', 'verbose_name_plural': 'Modelos de equipo'},
        ),
        migrations.RemoveConstraint(
            model_name='modelodispositivo',
            name='equipo_modelo_unico_por_marca',
        ),
        migrations.AddField(
            model_name='modelodispositivo',
            name='tipo',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='modelos', to='equipos.tipodispositivo', verbose_name='Tipo de equipo'),
        ),
        migrations.AddField(
            model_name='tipodispositivo',
            name='marcas',
            field=models.ManyToManyField(blank=True, db_table='equipo_tipo_marca', related_name='tipos', to='equipos.marcadispositivo', verbose_name='Marcas'),
        ),
        migrations.AddField(
            model_name='tipodispositivo',
            name='tipo_tecnologia',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Electrónico'), (2, 'No electrónico')], db_index=True, default=1, verbose_name='Tipo de tecnología'),
        ),
        # Va antes de borrar la columna vieja: de otro modo la tecnologia ya
        # registrada se perderia sin remedio.
        migrations.RunPython(reorganizar, revertir),
        migrations.RemoveField(
            model_name='dispositivo',
            name='tipo_tecnologia',
        ),
        migrations.AddConstraint(
            model_name='modelodispositivo',
            constraint=models.UniqueConstraint(fields=('tipo', 'marca', 'nombre'), name='equipo_modelo_unico_por_tipo_marca'),
        ),
    ]

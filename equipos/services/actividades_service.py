"""El catalogo de actividades, que se llena solo con el uso.

No hay lista precargada. La primera orden de trabajo de un autoclave se
escribe completa; de ahi en adelante cada linea que alguien escribio queda
guardada y se le ofrece al siguiente. El catalogo acaba describiendo lo que de
verdad se hace en este hospital y no lo que decia una plantilla.

Esa decision tiene un motivo concreto. La hoja de calculo que se venia usando
traia tres tareas del amalgamador -sostenedores de capsula, lubricacion del
motor, verificacion del temporizador- copiadas en casi todas las hojas, unas
ciento cincuenta lineas de seiscientas. Importarlas habria puesto el sistema a
pedir que se lubrique el motor de un glucometro durante anios, y lo que pasa
cuando una lista pide cosas imposibles es que se marca entera sin leerla.

La sugerencia se ordena por uso: lo que mas se hace sale primero. Se consulta
por tipo de equipo, que es lo que hace util la lista, y queda abierta la
posibilidad de abrirla a todo el catalogo sin tocar la base.
"""

from django.db import transaction
from django.db.models import F, Q

from ..models import (
    ActividadMantenimiento,
    ActividadTipoDispositivo,
    normalizar_actividad,
)

# Cuantas sugerencias se devuelven. Una lista mas larga que esto no se lee: se
# vuelve a escribir la linea, que es mas rapido que buscarla.
MAXIMO_SUGERENCIAS = 12

# Minimo de letras antes de sugerir. Con una o dos la lista no discrimina nada
# y solo estorba mientras se escribe.
MINIMO_PARA_SUGERIR = 3


@transaction.atomic
def registrar_actividad(nombre, tipo=None):
    """Devuelve la actividad del catalogo que corresponde a ese texto.

    La crea si es nueva y le suma un uso si ya existia. Dos escrituras de la
    misma linea -con tilde o sin ella, con punto final o sin el- caen en la
    misma fila: para eso esta la clave normalizada.

    No recibe el usuario a proposito. Quien escribio la linea queda en la
    orden de trabajo, que es donde importa; el catalogo es un vocabulario
    compartido y no el diario de nadie.
    """
    clave = normalizar_actividad(nombre)

    if not clave:
        raise ValueError("No se puede guardar una actividad vacía.")

    actividad = ActividadMantenimiento.objects.filter(clave=clave).first()

    if actividad is None:
        actividad = ActividadMantenimiento(nombre=nombre)
        actividad.veces_usada = 1
        actividad.save()
    else:
        # F() en lugar de leer, sumar y guardar: dos personas cerrando ordenes
        # a la vez no deben perderse un uso por pisarse el contador.
        ActividadMantenimiento.objects.filter(pk=actividad.pk).update(
            veces_usada=F("veces_usada") + 1
        )
        actividad.refresh_from_db(fields=["veces_usada"])

        if not actividad.activa:
            # Alguien la habia retirado de las sugerencias y vuelve a
            # escribirla: el uso manda sobre la decision anterior.
            ActividadMantenimiento.objects.filter(pk=actividad.pk).update(
                activa=True
            )
            actividad.activa = True

    if tipo is not None:
        uso, creado = ActividadTipoDispositivo.objects.get_or_create(
            actividad=actividad,
            tipo=tipo,
            defaults={"veces_usada": 1},
        )

        if not creado:
            ActividadTipoDispositivo.objects.filter(pk=uso.pk).update(
                veces_usada=F("veces_usada") + 1
            )

    return actividad


def sugerir(texto, tipo=None, limite=MAXIMO_SUGERENCIAS):
    """Actividades que empiezan o contienen lo que se esta escribiendo.

    Primero las que ya se usaron en equipos de este tipo, porque son las que
    casi siempre acierta; detras, el resto del catalogo, que sirve cuando la
    misma tarea aplica a varios tipos y es la primera vez en este. Las dos
    listas vienen de la misma tabla, asi que limitar la sugerencia al tipo o
    abrirla a todo es una decision de pantalla y no de base de datos.
    """
    texto = (texto or "").strip()
    clave = normalizar_actividad(texto)

    if len(clave) < MINIMO_PARA_SUGERIR:
        return []

    # La busqueda va contra la clave, no contra el nombre: asi "limpieza"
    # encuentra "Limpieza general" escrito como sea, con tilde o sin ella.
    coincide = Q(clave__icontains=clave)
    resultado = []
    vistos = set()

    if tipo is not None:
        del_tipo = (
            ActividadMantenimiento.objects.filter(
                coincide,
                activa=True,
                usos_por_tipo__tipo=tipo,
            )
            .annotate(usos_del_tipo=F("usos_por_tipo__veces_usada"))
            .order_by("-usos_del_tipo", "nombre")[:limite]
        )

        for actividad in del_tipo:
            resultado.append(actividad)
            vistos.add(actividad.pk)

    if len(resultado) < limite:
        resto = (
            ActividadMantenimiento.objects.filter(coincide, activa=True)
            .exclude(pk__in=vistos)
            .order_by("-veces_usada", "nombre")[: limite - len(resultado)]
        )
        resultado.extend(resto)

    return resultado


def habituales_del_tipo(tipo, limite=MAXIMO_SUGERENCIAS):
    """Lo que normalmente se le hace a este tipo de equipo.

    Se ofrece al abrir la orden, antes de que nadie escriba nada, para que la
    primera linea tambien se pueda elegir en lugar de teclearse. No se
    precarga en la orden: se ofrece. La diferencia es que nadie termina
    firmando una tarea que no hizo.
    """
    return list(
        ActividadMantenimiento.objects.filter(
            activa=True,
            usos_por_tipo__tipo=tipo,
        )
        .annotate(usos_del_tipo=F("usos_por_tipo__veces_usada"))
        .order_by("-usos_del_tipo", "nombre")[:limite]
    )

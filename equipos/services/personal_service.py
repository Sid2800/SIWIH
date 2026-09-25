"""Datos del empleado a cargo de un equipo, tomados de RRHH.

El inventario no guarda copia de nada de esto: el equipo apunta al empleado y
todo lo demas se lee de donde ya vive. RRHH separa a la persona (Empleado) de
su relacion laboral, y esa relacion esta en dos tablas distintas segun el tipo
de personal:

    Empleado -> PersonalSalud       -> servicio_unidad   (personal clinico)
    Empleado -> PersonalNoClinico   -> servicio_unidad   (personal no clinico)

De ahi salen las dos cosas que el inventario necesita: en que unidad trabaja y
si es clinico o no. Esa unidad se usa para sugerir la ubicacion, no para
imponerla: la unidad dice a que equipo de trabajo pertenece la persona, y el
aparato puede estar en un punto de atencion mas concreto. Quien registra
confirma o corrige.
"""

from dataclasses import dataclass
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist

from expediente.models import ExpedienteUbicacion


@dataclass(frozen=True)
class DatosPersonal:
    """Lo que el inventario necesita saber de un empleado."""

    #: servicio.Unidad donde esta asignado, o None si RRHH no lo registra.
    unidad: Optional[object] = None
    #: True personal clinico, False no clinico, None sin relacion laboral.
    es_clinico: Optional[bool] = None
    #: Fila de expediente_ubicacion que corresponde a esa unidad, si existe.
    ubicacion_sugerida: Optional[object] = None

    @property
    def tipo_personal(self):
        if self.es_clinico is None:
            return "Sin relación laboral registrada"
        return "Personal clínico" if self.es_clinico else "Personal no clínico"

    @property
    def nombre_unidad(self):
        if not self.unidad:
            return ""
        return self.unidad.nombre_unidad or ""


def resolver_datos_personal(empleado):
    """Lee la relacion laboral del empleado sin fallar si no la tiene.

    Se consulta primero personal de salud porque es el caso mayoritario en el
    hospital. Un empleado puede no tener ninguna de las dos filas (cuenta
    creada antes de completar su ficha en RRHH); entonces se devuelve todo
    vacio y el formulario simplemente no sugiere ubicacion.
    """
    if empleado is None:
        return DatosPersonal()

    for atributo, es_clinico in (
        ("personal_salud_empleado", True),
        ("personal_no_clinico", False),
    ):
        # Un OneToOne inverso ausente lanza la excepcion del propio modelo en
        # lugar de devolver None, y no hay una sola clase que capture las dos.
        try:
            relacion = getattr(empleado, atributo)
        except ObjectDoesNotExist:
            continue

        unidad = relacion.servicio_unidad
        return DatosPersonal(
            unidad=unidad,
            es_clinico=es_clinico,
            ubicacion_sugerida=_ubicacion_de_unidad(unidad),
        )

    return DatosPersonal()


def _ubicacion_de_unidad(unidad):
    """Fila del catalogo compartido que representa a esa unidad.

    Puede no existir: el catalogo se llena con "manage.py poblar_ubicaciones" y
    una unidad creada despues todavia no tendra la suya. No se crea al vuelo
    porque ese catalogo lo comparten otros modulos y no le corresponde al
    inventario decidir que entra en el.
    """
    if unidad is None:
        return None

    return (
        ExpedienteUbicacion.objects
        .filter(unidad_no_clinica_id=unidad.pk, estado=True)
        .first()
    )

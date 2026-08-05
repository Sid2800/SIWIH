from rrhh.models import PersonalSalud, Jornada_laboral
from django.db.models import Value, CharField, F, Case, Q, When
from django.db.models.functions import Concat, Coalesce, NullIf, Cast
from core.constants.choices_constants import EstadoRegistro

class PersonalSaludService:

    @staticmethod
    def obtener_personal_salud_activo_servicio(id_especialidad=0, puede_agendar_citas=True):
        """Obtiene personal de salud activo (opcionalmente filtrado por especialidad)."""

        personal = (
            PersonalSalud.objects
            .annotate(
                nombre=Concat(
                    F("empleado__primer_nombre"),
                    Case(
                        When(empleado__segundo_nombre__gt="", then=Concat(Value(" "), F("empleado__segundo_nombre"))),
                        default=Value("")
                    ),
                    Case(
                        When(empleado__primer_apellido__gt="", then=Concat(Value(" "), F("empleado__primer_apellido"))),
                        default=Value("")
                    ),
                    Case(
                        When(empleado__segundo_apellido__gt="", then=Concat(Value(" "), F("empleado__segundo_apellido"))),
                        default=Value("")
                    ),
                    output_field=CharField(),
                )
            )
            .filter(estado=EstadoRegistro.ACTIVO)
        
        )

        if id_especialidad:
            # Filtramos por el servicio específico
            personal = personal.filter(especialidad_id=id_especialidad)

        if puede_agendar_citas:
            personal = personal.filter(puede_agendar_citas=True)

        personal = personal.values(
            'id',
            'nombre',
            'especialidad__nombre_especialidad'
        ).order_by("nombre")
        
        return list(personal)
    

    @staticmethod
    def obtener_jornada_activo():
        """Obtiene las jornadas  activas ."""

        jornada = (
            Jornada_laboral.objects
            .filter(estado=EstadoRegistro.ACTIVO)
        
        )


        jornada = jornada.values(
            'id',
            'nombre_jornada_laboral',
            'hora_inicio',
            'hora_fin'
        ).order_by("id")
        
        return list(jornada)
from django.shortcuts import render
from django.views import View
from django.http import JsonResponse
from core.services.rrhh.personal_salud_service import PersonalSaludService
from usuario.permisos import verificar_permisos_usuario
from core.utils.utilidades_textos import str_to_bool


# Create your views here.
class ListarPersonalClinico(View):

    def get(self, request):

        id_especialidad = request.GET.get("especialidad")
        puede_agendar = str_to_bool(request.GET.get("puede_agendar"))

        print(f"ID Especialidad: {id_especialidad}, Puede Agendar: {puede_agendar}")

        personal = PersonalSaludService.obtener_personal_salud_activo_servicio(
            id_especialidad=id_especialidad,
            puede_agendar_citas=puede_agendar
        )

        return JsonResponse(personal, safe=False)
    


class ListarJornadaLaboral(View):

    def get(self, request):

        jornada = PersonalSaludService.obtener_jornada_activo()

        return JsonResponse(jornada, safe=False)
    

def guardar_periodo_laboral(request):
    if not verificar_permisos_usuario(request.user):
        pass


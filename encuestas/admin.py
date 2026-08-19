from django.contrib import admin

from encuestas.models import Encuesta, EncuestaRespuesta


class EncuestaRespuestaInline(admin.TabularInline):
    model = EncuestaRespuesta
    extra = 0


@admin.register(Encuesta)
class EncuestaAdmin(admin.ModelAdmin):
    list_display = ('id', 'servicio', 'subservicio', 'fecha',
                    'porcentaje_satisfaccion', 'creado_por')
    list_filter = ('servicio', 'fecha')
    search_fields = ('identidad', 'subservicio')
    inlines = [EncuestaRespuestaInline]

from django import forms
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from .models import Solicitud, PuntoSolicitud, TipoSolicitud, Prioridad
from servicio.models import Institucion_salud


class SolicitudForm(forms.ModelForm):
    area_solicitante = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Solicitud
        fields = [
            "fecha_solicitud",
            "punto_solicitud",
            "tipo_solicitud",
            "prioridad",
            "lugar_salida",
            "lugar_destino",
            "motivo",
            "observaciones",
        ]
        widgets = {
            "fecha_solicitud": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "th-input"},
                format="%Y-%m-%dT%H:%M",
            ),
            "punto_solicitud": forms.Select(attrs={"class": "formularioCampo-select"}),
            "tipo_solicitud": forms.Select(attrs={"class": "formularioCampo-select"}),
            "prioridad": forms.Select(attrs={"class": "formularioCampo-select"}),
            "lugar_salida": forms.Select(attrs={"class": "formularioCampo-select"}),
            "lugar_destino": forms.Select(attrs={"class": "formularioCampo-select"}),
            "motivo": forms.Textarea(attrs={"class": "th-input", "rows": 2, "placeholder": "Describa el motivo del viaje"}),
            "observaciones": forms.Textarea(attrs={"class": "th-input", "rows": 2, "placeholder": "Agregue observaciones adicionales"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_solicitud"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["fecha_solicitud"].initial = timezone.localtime().strftime("%Y-%m-%dT%H:%M")

        self.fields["punto_solicitud"].queryset = (
            PuntoSolicitud.objects
            .filter(activo=True)
            .select_related(
                "unidad",
                "unidad_clinica__area_atencion__servicio",
                "unidad_clinica__sala__servicio",
                "unidad_clinica__servicio_aux",
                "unidad_clinica__establecimiento_ext__nivel_complejidad_institucional",
                "unidad_clinica__establecimiento_ext__region_salud",
            )
        )
        self.fields["punto_solicitud"].empty_label = "Seleccione un punto"
        self.fields["tipo_solicitud"].queryset = TipoSolicitud.objects.filter(activo=True)
        self.fields["tipo_solicitud"].empty_label = "Seleccione un tipo de solicitud"
        self.fields["prioridad"].queryset = Prioridad.objects.filter(activo=True)
        self.fields["prioridad"].empty_label = "Seleccione una prioridad"

        # 2026-07-22: dejar la institución solicitada como opción predeterminada y priorizar HESP-ESCUELA solo en destino.
        preferred_text = "HESP-ESCUELA"
        secondary_text = "HESP-ESCUELA"
        instituciones_qs = (
            Institucion_salud.objects
            .filter(estado=1)
            .select_related("nivel_complejidad_institucional", "region_salud")
            .order_by("nombre_institucion_salud")
        )
        preferred_institucion = instituciones_qs.filter(nombre_institucion_salud__icontains=preferred_text).first()
        destino_preferred = instituciones_qs.filter(nombre_institucion_salud__icontains=secondary_text).first()

        salida_qs = instituciones_qs.annotate(
            prioridad_salida=Case(
                When(nombre_institucion_salud__icontains=preferred_text, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by("prioridad_salida", "nombre_institucion_salud")
        destino_qs = instituciones_qs.annotate(
            prioridad_destino=Case(
                When(nombre_institucion_salud__icontains=secondary_text, then=Value(0)),
                When(nombre_institucion_salud__icontains=preferred_text, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        ).order_by("prioridad_destino", "nombre_institucion_salud")

        self.fields["lugar_salida"].queryset = salida_qs
        self.fields["lugar_salida"].empty_label = "Seleccione un lugar de salida"
        self.fields["lugar_salida"].label_from_instance = lambda obj: obj.nombre_institucion_salud
        self.fields["lugar_destino"].queryset = destino_qs
        self.fields["lugar_destino"].empty_label = "Seleccione un lugar de destino"
        self.fields["lugar_destino"].label_from_instance = lambda obj: obj.nombre_institucion_salud
        if preferred_institucion:
            self.initial["lugar_salida"] = preferred_institucion.pk
            self.initial["lugar_destino"] = preferred_institucion.pk
        elif destino_preferred:
            self.initial["lugar_destino"] = destino_preferred.pk


SolicitudCreateForm = SolicitudForm

import json
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Case, Exists, IntegerField, OuterRef, Value, When
from django.utils import timezone

from core.constants.choices_constants import EstadoRegistro
from rrhh.models import Empleado

from .models import Motorista, Prioridad, PuntoSolicitud, Solicitud, TipoSolicitud, Viaje, ViajePersonal, Vehiculo, Viatico
from servicio.models import Institucion_salud


def _nombre_empleado(empleado):
    return " ".join(x for x in [getattr(empleado, "primer_nombre", ""), getattr(empleado, "primer_apellido", "")] if x).strip() or str(empleado)


def _viajes_activos_qs():
    return Viaje.objects.filter(activo=True, estado__in=["PROGRAMADA", "EN_EJECUCION"])


def _vehiculos_disponibles_qs():
    viajes_activos = _viajes_activos_qs().filter(vehiculo_id=OuterRef("pk"))
    return (
        Vehiculo.objects.filter(activo=True)
        .annotate(tiene_viaje_activo=Exists(viajes_activos))
        .filter(tiene_viaje_activo=False)
        .order_by("codigo", "placa")
    )


def _motoristas_disponibles_qs():
    viajes_activos = _viajes_activos_qs().filter(motorista_id=OuterRef("pk"))
    return (
        Motorista.objects.select_related("empleado")
        .filter(activo=True, empleado__estado=EstadoRegistro.ACTIVO)
        .annotate(tiene_viaje_activo=Exists(viajes_activos))
        .filter(tiene_viaje_activo=False)
        .order_by("empleado__primer_nombre", "empleado__primer_apellido")
    )


def _viaticos_disponibles_qs():
    return Viatico.objects.filter(activo=True).order_by("codigo", "nombre")


def _empleados_operativos_disponibles_qs():
    viajes_activos = ViajePersonal.objects.filter(viaje__activo=True, viaje__estado__in=["PROGRAMADA", "EN_EJECUCION"], empleado_id=OuterRef("pk"))
    return (
        Empleado.objects.filter(estado=EstadoRegistro.ACTIVO)
        .annotate(tiene_viaje_activo=Exists(viajes_activos))
        .filter(tiene_viaje_activo=False)
        .order_by("primer_nombre", "primer_apellido")
    )


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

        preferred_salida_pk = 65
        preferred_destino_text = "HESP-ESCUELA"
        instituciones_qs = (
            Institucion_salud.objects
            .filter(estado=1)
            .select_related("nivel_complejidad_institucional", "region_salud")
            .order_by("nombre_institucion_salud")
        )
        preferred_institucion = instituciones_qs.filter(pk=preferred_salida_pk).first()
        destino_preferred = instituciones_qs.filter(nombre_institucion_salud__icontains=preferred_destino_text).first()

        salida_qs = instituciones_qs.annotate(
            prioridad_salida=Case(
                When(pk=preferred_salida_pk, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by("prioridad_salida", "nombre_institucion_salud")
        destino_qs = instituciones_qs.annotate(
            prioridad_destino=Case(
                When(nombre_institucion_salud__icontains=preferred_destino_text, then=Value(0)),
                When(pk=preferred_salida_pk, then=Value(1)),
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
        elif destino_preferred:
            self.initial["lugar_destino"] = destino_preferred.pk

    def clean(self):
        cleaned_data = super().clean()
        lugar_salida = cleaned_data.get("lugar_salida")
        lugar_destino = cleaned_data.get("lugar_destino")

        if lugar_salida and lugar_destino and lugar_salida == lugar_destino:
            mensaje = "El lugar de salida y el lugar de destino no pueden ser iguales."
            self.add_error("lugar_salida", mensaje)
            self.add_error("lugar_destino", mensaje)

        return cleaned_data


class ViajeProgramacionForm(forms.ModelForm):
    viatico = forms.ModelChoiceField(
        queryset=_viaticos_disponibles_qs(),
        required=False,
        widget=forms.Select(attrs={"class": "th-input"}),
    )
    personal_operativo_ids = forms.CharField(
        required=True,
        widget=forms.HiddenInput(attrs={"data-programacion-personal-operativo": "1"}),
    )

    class Meta:
        model = Viaje
        fields = ["vehiculo", "motorista", "tipo_viaje", "centro_costo"]
        widgets = {
            "vehiculo": forms.Select(attrs={"class": "th-input"}),
            "motorista": forms.Select(attrs={"class": "th-input"}),
            "tipo_viaje": forms.Select(attrs={"class": "th-input"}),
            "centro_costo": forms.NumberInput(attrs={"class": "th-input", "min": "1", "step": "1", "placeholder": "Centro de costo"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehiculo"].queryset = _vehiculos_disponibles_qs()
        self.fields["vehiculo"].empty_label = "Seleccione una ambulancia"
        self.fields["vehiculo"].label_from_instance = lambda obj: f"{obj.codigo} - {obj.placa} | {obj.descripcion or 'Sin descripción'}"
        self.fields["vehiculo"].required = True

        self.fields["motorista"].queryset = _motoristas_disponibles_qs()
        self.fields["motorista"].empty_label = "Seleccione un motorista"
        self.fields["motorista"].label_from_instance = lambda obj: f"{obj.empleado.dni} - {_nombre_empleado(obj.empleado)}"
        self.fields["motorista"].required = True

        self.fields["tipo_viaje"].choices = Viaje.TipoProgramacion.choices
        self.fields["tipo_viaje"].required = True
        self.fields["viatico"].queryset = _viaticos_disponibles_qs()
        self.fields["viatico"].empty_label = "Seleccione un viático"
        self.fields["viatico"].label_from_instance = lambda obj: f"{obj.codigo} - {obj.nombre}"
        self.fields["viatico"].required = False
        self.fields["viatico"].help_text = "Campo de referencia institucional; no se almacena en el viaje."
        self.fields["centro_costo"].required = True

    def clean_personal_operativo_ids(self):
        raw_value = self.cleaned_data.get("personal_operativo_ids")
        if isinstance(raw_value, list):
            raw_value = json.dumps(raw_value)
        raw_value = (raw_value or "").strip()
        if not raw_value:
            raise ValidationError("Seleccione al menos un integrante operativo.")

        try:
            parsed = json.loads(raw_value)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValidationError("El personal operativo seleccionado no es válido.") from exc

        if not isinstance(parsed, list):
            raise ValidationError("El personal operativo seleccionado no es válido.")

        ids = []
        seen = set()
        for item in parsed:
            try:
                value = int(item)
            except (TypeError, ValueError):
                raise ValidationError("El personal operativo seleccionado no es válido.")
            if value in seen:
                raise ValidationError("No se permiten integrantes operativos duplicados.")
            seen.add(value)
            ids.append(value)

        disponibles = set(
            _empleados_operativos_disponibles_qs().filter(pk__in=ids).values_list("pk", flat=True)
        )
        if len(disponibles) != len(ids):
            raise ValidationError("Uno o más integrantes operativos no están disponibles.")

        return ids

    def clean(self):
        cleaned_data = super().clean()
        vehiculo = cleaned_data.get("vehiculo")
        motorista = cleaned_data.get("motorista")
        personal_operativo_ids = cleaned_data.get("personal_operativo_ids") or []

        if vehiculo and not _vehiculos_disponibles_qs().filter(pk=vehiculo.pk).exists():
            self.add_error("vehiculo", "La ambulancia seleccionada no está disponible.")

        if motorista and not _motoristas_disponibles_qs().filter(pk=motorista.pk).exists():
            self.add_error("motorista", "El motorista seleccionado no está disponible.")

        if personal_operativo_ids:
            ocupados = set(
                ViajePersonal.objects.filter(
                    viaje__activo=True,
                    viaje__estado__in=["PROGRAMADA", "EN_EJECUCION"],
                    empleado_id__in=personal_operativo_ids,
                ).values_list("empleado_id", flat=True)
            )
            if ocupados:
                self.add_error("personal_operativo_ids", "Uno o más integrantes operativos no están disponibles.")

        return cleaned_data


class EjecucionViajeForm(forms.Form):
    viaje_id = forms.IntegerField(widget=forms.HiddenInput())
    modo = forms.CharField(widget=forms.HiddenInput())
    fecha_salida = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "th-input"}),
    )
    kilometraje_salida = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "th-input", "min": "0", "step": "0.01"}),
    )
    precio_litro_salida = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "th-input", "min": "0", "step": "0.01"}),
    )
    litros_cargados_salida = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "th-input", "min": "0", "step": "0.01"}),
    )
    total_combustible = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "th-input", "readonly": "readonly", "tabindex": "-1"}),
    )
    observaciones_salida = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "th-input", "rows": 2, "placeholder": "Observaciones de salida"}),
    )
    fecha_retorno = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "th-input"}),
    )
    kilometraje_retorno = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "th-input", "min": "0", "step": "0.01"}),
    )
    observaciones_retorno = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "th-input", "rows": 2, "placeholder": "Observaciones de retorno"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        precio = cleaned_data.get("precio_litro_salida")
        litros = cleaned_data.get("litros_cargados_salida")
        kilometraje_salida = cleaned_data.get("kilometraje_salida")
        kilometraje_retorno = cleaned_data.get("kilometraje_retorno")

        if precio is not None and litros is not None:
            cleaned_data["total_combustible"] = (Decimal(precio) * Decimal(litros)).quantize(Decimal("0.01"))
        else:
            cleaned_data["total_combustible"] = None

        if kilometraje_salida is not None and kilometraje_salida < 0:
            self.add_error("kilometraje_salida", "El kilometraje de salida debe ser mayor o igual a cero.")

        if kilometraje_retorno is not None and kilometraje_retorno < 0:
            self.add_error("kilometraje_retorno", "El kilometraje de retorno debe ser mayor o igual a cero.")

        if kilometraje_salida is not None and kilometraje_retorno is not None and kilometraje_retorno < kilometraje_salida:
            self.add_error("kilometraje_retorno", "El kilometraje de retorno debe ser mayor o igual al de salida.")

        return cleaned_data


SolicitudCreateForm = SolicitudForm
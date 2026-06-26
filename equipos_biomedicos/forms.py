from datetime import date

from django import forms
from django.db.models import Q

from core.constants.choices_constants import EstadoRegistro, TipoUnidad
from rrhh.models import Empleado
from servicio.models import Area_atencion, Unidad

from .models import (
    BajaDispositivo,
    CriticidadDispositivo,
    Dispositivo,
    EstadoDispositivo,
    MarcaDispositivo,
    ModeloDispositivo,
    TipoDispositivo,
    TipoTecnologiaDispositivo,
    normalizar_inventario_bienes_nacionales,
    normalizar_inventario_numero_ficha,
)


# Personaliza la etiqueta visible del select de empleados.
# Select2 usa este texto cuando ya hay un responsable seleccionado.
class EmpleadoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, empleado):
        return f"{empleado.dni} - {empleado.nombre_completo}"


class BajaDispositivoForm(forms.ModelForm):
    # Formulario corto para crear el registro de baja administrativa.
    # La vista se encarga despues de cambiar el estado del equipo a DADO_DE_BAJA.
    class Meta:
        model = BajaDispositivo
        fields = ["fecha_baja", "motivo"]
        widgets = {
            "fecha_baja": forms.DateInput(
                attrs={
                    "class": "formularioCampo-date",
                    "id": "fecha_baja_dispositivo",
                    "type": "date",
                    "max": date.today().strftime("%Y-%m-%d"),
                },
                format="%Y-%m-%d",
            ),
            "motivo": forms.Textarea(
                attrs={
                    "class": "formularioCampo-text no-resize",
                    "id": "motivo_baja_dispositivo",
                    "rows": 4,
                    "placeholder": "Describa el motivo por el que se da de baja el equipo.",
                }
            ),
        }

    def clean_fecha_baja(self):
        fecha_baja = self.cleaned_data["fecha_baja"]
        if fecha_baja and fecha_baja > date.today():
            raise forms.ValidationError("La fecha de baja no puede ser futura.")
        return fecha_baja

    def clean_motivo(self):
        motivo = (self.cleaned_data.get("motivo") or "").strip()
        if not motivo:
            raise forms.ValidationError("Debe ingresar el motivo de baja.")
        return motivo


class DispositivoCreateForm(forms.ModelForm):
    # Este mismo formulario se reutiliza para registrar y editar equipos.
    # Ademas de campos de Dispositivo, maneja la asignacion inicial/actual.
    TIPO_AREA_CHOICES = [
        ("clinica", "Área clínica"),
        ("no_clinica", "Área no clínica"),
    ]
    FRECUENCIA_CHOICES = [
        (1, "Mensual"),
        (3, "Trimestral"),
        (6, "Semestral"),
        (12, "Anual"),
    ]

    tipo_area = forms.ChoiceField(
        choices=TIPO_AREA_CHOICES,
        label="Tipo de área",
        widget=forms.Select(
            attrs={
                "class": "formularioCampo-select",
                "id": "tipo_area_dispositivo",
            }
        ),
    )
    area_clinica = forms.ModelChoiceField(
        queryset=Area_atencion.objects.none(),
        required=False,
        label="Área clínica",
        widget=forms.Select(
            attrs={
                "class": "formularioCampo-select",
                "id": "area_clinica_dispositivo",
            }
        ),
    )
    unidad_no_clinica = forms.ModelChoiceField(
        queryset=Unidad.objects.none(),
        required=False,
        label="Área no clínica",
        widget=forms.Select(
            attrs={
                "class": "formularioCampo-select",
                "id": "area_no_clinica_dispositivo",
            }
        ),
    )
    responsable = EmpleadoChoiceField(
        queryset=Empleado.objects.none(),
        label="Empleado a cargo",
        widget=forms.Select(
            attrs={
                "class": "formularioCampo-select",
                "id": "responsable_dispositivo",
                "data-placeholder": "Buscar por ID, DNI o nombre",
            }
        ),
    )
    frecuencia_mantenimiento_meses = forms.TypedChoiceField(
        choices=[("", "Sin frecuencia definida"), *FRECUENCIA_CHOICES],
        coerce=int,
        empty_value=None,
        required=False,
        label="Frecuencia de mantenimiento",
        widget=forms.Select(
            attrs={
                "class": "formularioCampo-select",
                "id": "frecuencia_dispositivo",
            }
        ),
    )

    class Meta:
        model = Dispositivo
        fields = [
            "tipo",
            "tipo_tecnologia",
            "marca",
            "modelo",
            "numero_serie",
            "inventario_bienes_nacionales",
            "inventario_numero_ficha",
            "estado",
            "criticidad",
            "frecuencia_mantenimiento_meses",
            "fecha_instalacion",
            "fin_garantia",
            "costo_adquisicion",
            "observaciones",
        ]
        widgets = {
            "tipo": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "tipo_dispositivo",
                }
            ),
            "tipo_tecnologia": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "tipo_tecnologia_dispositivo",
                }
            ),
            "marca": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "marca_dispositivo",
                }
            ),
            "modelo": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "modelo_dispositivo",
                }
            ),
            "numero_serie": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "serie_dispositivo",
                    "placeholder": "Opcional; se mostrará como Indefinido",
                }
            ),
            "inventario_bienes_nacionales": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "inventario_bienes_nacionales",
                    "placeholder": "Ej. F/212300 (opcional)",
                }
            ),
            "inventario_numero_ficha": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "inventario_numero_ficha",
                    "placeholder": "Opcional",
                }
            ),
            "estado": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "estado_dispositivo",
                }
            ),
            "criticidad": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "criticidad_dispositivo",
                }
            ),
            "fecha_instalacion": forms.DateInput(
                attrs={
                    "class": "formularioCampo-date",
                    "id": "instalacion_dispositivo",
                    "type": "date",
                },
                format="%Y-%m-%d",
            ),
            "fin_garantia": forms.DateInput(
                attrs={
                    "class": "formularioCampo-date",
                    "id": "garantia_dispositivo",
                    "type": "date",
                },
                format="%Y-%m-%d",
            ),
            "costo_adquisicion": forms.NumberInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "costo_dispositivo",
                    "min": 0,
                    "step": "0.01",
                    "placeholder": "Ingrese el costo (opcional)",
                }
            ),
            "observaciones": forms.Textarea(
                attrs={
                    "class": "formularioCampo-text no-resize",
                    "id": "observaciones_dispositivo",
                    "rows": 4,
                    "placeholder": "Ingrese observaciones adicionales (opcional)",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        # En edicion la vista envia asignacion_actual para precargar ubicacion
        # y responsable. En registro ese valor llega vacio.
        self.asignacion_actual = kwargs.pop("asignacion_actual", None)
        formulario_vinculado = (
            (args and args[0] is not None)
            or kwargs.get("data") is not None
            or kwargs.get("files") is not None
        )

        if self.asignacion_actual and not formulario_vinculado:
            initial = kwargs.get("initial", {}).copy()

            if self.asignacion_actual.area_clinica_id:
                initial.setdefault("tipo_area", "clinica")
                initial.setdefault(
                    "area_clinica",
                    self.asignacion_actual.area_clinica_id,
                )
            elif self.asignacion_actual.unidad_no_clinica_id:
                initial.setdefault("tipo_area", "no_clinica")
                initial.setdefault(
                    "unidad_no_clinica",
                    self.asignacion_actual.unidad_no_clinica_id,
                )

            initial.setdefault("responsable", self.asignacion_actual.responsable_id)
            kwargs["initial"] = initial

        super().__init__(*args, **kwargs)

        # Los catalogos inactivos no se muestran para nuevos registros, pero si
        # el equipo ya usa uno, se conserva en la edicion para no romper historico.
        filtro_tipo = Q(activo=True)
        filtro_marca = Q(activo=True)
        filtro_modelo = Q(activo=True)

        if self.instance and self.instance.pk:
            if self.instance.tipo_id:
                filtro_tipo |= Q(pk=self.instance.tipo_id)
            if self.instance.marca_id:
                filtro_marca |= Q(pk=self.instance.marca_id)
            if self.instance.modelo_id:
                filtro_modelo |= Q(pk=self.instance.modelo_id)

        self.fields["tipo"].queryset = TipoDispositivo.objects.filter(filtro_tipo)
        self.fields["tipo"].empty_label = "Seleccione el tipo de equipo"
        self.fields["marca"].queryset = MarcaDispositivo.objects.filter(filtro_marca)
        self.fields["marca"].empty_label = "Seleccione la marca o deje INDEFINIDO"
        self.fields["modelo"].queryset = ModeloDispositivo.objects.filter(filtro_modelo)
        self.fields["modelo"].empty_label = "Seleccione el modelo o deje INDEFINIDO"
        self.fields["tipo_tecnologia"].choices = [
            ("", "Seleccione el tipo de tecnología"),
            *TipoTecnologiaDispositivo.choices,
        ]
        self.fields["estado"].choices = [
            ("", "Seleccione el estado inicial"),
            (EstadoDispositivo.OPERATIVO, EstadoDispositivo.OPERATIVO.label),
            (
                EstadoDispositivo.EN_MANTENIMIENTO,
                EstadoDispositivo.EN_MANTENIMIENTO.label,
            ),
            (
                EstadoDispositivo.FUERA_DE_SERVICIO,
                EstadoDispositivo.FUERA_DE_SERVICIO.label,
            ),
        ]
        self.fields["criticidad"].choices = [
            ("", "Seleccione la criticidad"),
            *CriticidadDispositivo.choices,
        ]
        filtro_area_clinica = Q(estado=EstadoRegistro.ACTIVO)
        filtro_unidad_no_clinica = Q(estado=EstadoRegistro.ACTIVO)

        if self.asignacion_actual:
            if self.asignacion_actual.area_clinica_id:
                filtro_area_clinica |= Q(pk=self.asignacion_actual.area_clinica_id)
            if self.asignacion_actual.unidad_no_clinica_id:
                filtro_unidad_no_clinica |= Q(
                    pk=self.asignacion_actual.unidad_no_clinica_id
                )

        self.fields["area_clinica"].queryset = Area_atencion.objects.filter(
            filtro_area_clinica
        ).select_related("servicio")
        self.fields["unidad_no_clinica"].queryset = Unidad.objects.filter(
            filtro_unidad_no_clinica
        ).exclude(tipo=TipoUnidad.CLINICA).order_by("nombre_unidad")

        responsable_id = None
        if self.is_bound:
            responsable_id = self.data.get(self.add_prefix("responsable"))
        else:
            responsable_id = self.initial.get("responsable")

        # Para no cargar miles de empleados en el HTML, el select inicia vacio.
        # Select2 consulta buscar_empleados() por AJAX y aqui solo se acepta el
        # empleado seleccionado cuando el formulario se envia.
        if responsable_id and str(responsable_id).isdigit():
            filtro_responsable = Q(pk=responsable_id)

            if self.is_bound:
                filtro_responsable &= Q(estado=EstadoRegistro.ACTIVO)

            self.fields["responsable"].queryset = Empleado.objects.filter(
                filtro_responsable
            )

        self.fields["area_clinica"].empty_label = "Seleccione el área clínica"
        self.fields["unidad_no_clinica"].empty_label = "Seleccione el área no clínica"
        self.fields["responsable"].empty_label = "Buscar empleado a cargo"

    def clean_numero_serie(self):
        # Una cadena vacia se guarda como NULL para permitir varios equipos sin serie.
        return (self.cleaned_data.get("numero_serie") or "").strip() or None

    def clean_inventario_bienes_nacionales(self):
        return normalizar_inventario_bienes_nacionales(
            self.cleaned_data.get("inventario_bienes_nacionales")
        )

    def clean_inventario_numero_ficha(self):
        return normalizar_inventario_numero_ficha(
            self.cleaned_data.get("inventario_numero_ficha")
        )

    def clean(self):
        # Valida la ubicacion segun el tipo de area seleccionado por el usuario.
        # El modelo vuelve a proteger la regla exacta antes de guardar.
        cleaned_data = super().clean()
        tipo_area = cleaned_data.get("tipo_area")
        area_clinica = cleaned_data.get("area_clinica")
        unidad_no_clinica = cleaned_data.get("unidad_no_clinica")

        if tipo_area == "clinica":
            if not area_clinica:
                self.add_error("area_clinica", "Debe seleccionar un área clínica.")
            cleaned_data["unidad_no_clinica"] = None
        elif tipo_area == "no_clinica":
            if not unidad_no_clinica:
                self.add_error(
                    "unidad_no_clinica",
                    "Debe seleccionar un área no clínica.",
                )
            cleaned_data["area_clinica"] = None

        return cleaned_data

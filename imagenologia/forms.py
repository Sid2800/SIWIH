from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404
from .models import EvaluacionRx, EvaluacionRxDetalle, Estudio
from paciente.models import Paciente
from core.services.paciente_service import PacienteService
from core.services.imagenologia_service import EvaluacionService
from core.services.servicio_service import ServicioService
from django.core.exceptions import ValidationError
from core.validators.fecha_validator import validar_fecha
from core.validators.paciente import validar_paciente
from core.validators.image_validator import validar_imagen_basica
from core.constants.media_constants import AccionImagen
from core.constants.domain_constants import AccionEstudio
from django import forms
from django.utils import timezone
import json
import re
from datetime import date
from datetime import datetime, date
fecha_hoy = timezone.localdate()


class EvaluacionRXCreateForm(forms.ModelForm):
    # Campos auxiliares (paciente y unidad clinca)
    idPaciente = forms.CharField(required=False)
    dniPaciente = forms.CharField(required=False)
    numeroExpediente = forms.CharField(required=False)
    edadPaciente = forms.CharField(required=False)
    nombreCompletoPaciente = forms.CharField(required=False)
    fechaNacimientoPaciente = forms.CharField(required=False)
    sexoPaciente = forms.CharField(required=False)
    telefonoPaciente = forms.CharField(required=False)
    direccionPaciente = forms.CharField(required=False)



    fecha = forms.DateField(
        initial=date.today, 
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "formularioCampo-date",
                "min": "1900-01-01"#,
                #"max": timezone.localdate().strftime("%Y-%m-%d"),#.strftime("%Y-%m-%d"),
            },
            format="%Y-%m-%d",
        ),
        input_formats=["%Y-%m-%d"],
        required=True,
        validators=[validar_fecha] 
    )

    class Meta:
        model = EvaluacionRx
        fields = ["fecha", "observaciones", "maquinarx", "unidad_clinica"]

    def asignar_propiedades_campos_paciente(self):
        """Asigna estilos a los campos auxiliares del paciente (sólo lectura)."""
        campos = [
            'dniPaciente',
            'numeroExpediente',
            'nombreCompletoPaciente',
            'fechaNacimientoPaciente',
            'edadPaciente',
            'sexoPaciente',
            'telefonoPaciente',
            'direccionPaciente',
        ]

        for campo in campos:
            if campo in self.fields:
                self.fields[campo].widget.attrs.update({
                    'class': 'formularioCampo-select',
                    'placeholder': campo.replace("Paciente", "").replace("_", " ").capitalize(),
                    'disabled': True
                })

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        
        unidad_clinica = ServicioService.obtener_unidades_clinicas(incluir_externo=True)

        unidad_clinica = [
            (d['clave'], f"{d['nombre']} ({d['tipo']})")
            for d in unidad_clinica
        ]

        self.fields['unidad_clinica'].choices = unidad_clinica
        if not self.instance.pk:  # solo si es creación
            self.fields['unidad_clinica'].initial = "1"

        self.fields['observaciones'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Observaciones'
        })

        self.fields['unidad_clinica'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Unidad Clinica'
        })

        self.fields['maquinarx'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Máquina'
        })

        self.fields['idPaciente'] = forms.CharField(
            widget=forms.HiddenInput(attrs={'required': 'required'}),
            initial=None,
            required=False
        )

        self.asignar_propiedades_campos_paciente()


    def clean(self):
        cleaned_data = super().clean()
        id_paciente = cleaned_data.get('idPaciente')
        unidad_clinica = cleaned_data.get('unidad_clinica')
        estudios_json = self.data.get("estudios_json")

        # trabajamos con paciente y paciente interno
        p_externo = self.data.get('paciente_externo_data')
        p_ligado = self.data.get('paciente_ligado_id')

        #valirdad imagenes 
        for nombre, imagen in self.files.items():
            if not nombre.startswith("archivo__"):
                continue
            validar_imagen_basica(imagen)
    
        if not any([id_paciente, p_ligado, p_externo]):
            raise forms.ValidationError("Debe indicar al menos un tipo de paciente")

        if id_paciente:  # primero verificamos si es un paciente normal
            paciente = validar_paciente(id_paciente)
            cleaned_data['paciente'] = paciente

        elif p_ligado:
            paciente = validar_paciente(p_ligado)
            cleaned_data['paciente'] = paciente

        elif p_externo:
            try:
                p_externo = json.loads(p_externo)
            except (TypeError, json.JSONDecodeError):
                raise forms.ValidationError("Los datos del paciente externo no son válidos.")

            p_externo = self.validar_paciente_externo(p_externo)
            self.externo = p_externo
            cleaned_data['paciente'] = None

        # Procesar unida_clinica
        if unidad_clinica.estado != 1:
            raise forms.ValidationError("Unidad clínica inactiva")


        # Validar que estudios_json no esté vacío y sea string válido
        if not estudios_json or not isinstance(estudios_json, str):
            raise forms.ValidationError("Debe enviar al menos un estudio.")

        try:
            estudios = json.loads(estudios_json)
        except (TypeError, json.JSONDecodeError):
            raise forms.ValidationError("Los estudios enviados no son válidos.")

        if not estudios:
            raise forms.ValidationError("Debe enviar al menos un estudio.")


        try:
            codigos = [int(e['id']) for e in estudios]
        except (ValueError, TypeError):
            raise forms.ValidationError("Uno o más estudios tienen un ID inválido.")

        estudios_activos = [
            e for e in estudios
            if e.get('accionEstudio') != AccionEstudio.DELETE
        ]

        if len(estudios_activos) > 10:
            raise forms.ValidationError(
                "No se permiten más de 10 estudios por evaluación."
            )

        #if len(codigos) != len(set(codigos)): REGLA DUPLICIDADA DE ESTUDIOS EN UNA EVALUCION, SUSPENDIDA
        #    raise forms.ValidationError("Hay estudios repetidos.")

        # Comprobar que los estudios existen en la base de datos
        estudios_existentes_ids = set(
            Estudio.objects.filter(id__in=codigos).values_list("id", flat=True)
        )

        for codigo in codigos:
            if codigo not in estudios_existentes_ids:
                raise forms.ValidationError(f"El código de estudio {codigo} no existe en la base de datos.")
            
        #ACCIONES DE IMAGENES
        for e in estudios:

            try:
                AccionImagen(e.get("accionImagen"))
                AccionEstudio(e.get("accionEstudio"))
            except Exception:
                raise forms.ValidationError(
                    "Se detectó un problema estructural en los datos enviados. "
                    "Por favor contacte a soporte técnico."
                )

        self.estudios_validados = estudios
        return cleaned_data


    def validar_paciente_externo(self, paciente_externo):
        """Verifica que el paciente exista, esté activo y no fallecido."""
        regex_dni = r"^([0-3][0-9])([0-9][0-9])-(19|20)[0-9]{2}-[0-9]{5}$"
        regex_validacion = r"^[A-ZÑ.](?!.*\s{2})[A-ZÑ.\-\s]*$"


        # --- Validar DNI ---
        dni = paciente_externo.get('dni')
        if dni and len(dni) == 15 and re.match(regex_dni, dni):
            paciente_externo['dni'] = dni.replace('-', '')
        else:
            paciente_externo['dni'] = None

        # --- Procesar nombres y apellidos ---
        campos = ['nombre1', 'nombre2', 'apellido1', 'apellido2']
        for campo in campos:
            valor = str(paciente_externo.get(campo)).strip().upper()
            if valor and re.match(regex_validacion, valor):
                paciente_externo[campo] = valor
            else:
                # Solo nombre1 y apellido1 son obligatorios
                if campo in ('nombre1', 'apellido1'):
                    raise forms.ValidationError(f'{campo} contiene caracteres no permitidos.')
                paciente_externo[campo] = None

        # --- Validar fecha de nacimiento ---
        fecha_nacimiento = paciente_externo.get('fechaNacimiento')

        if fecha_nacimiento:
            if isinstance(fecha_nacimiento, str):
                try:
                    fecha_nacimiento = datetime.strptime(fecha_nacimiento, "%Y-%m-%d").date()
                except ValueError:
                    raise forms.ValidationError(f'Formato de fecha inválido. Debe ser AAAA-MM-DD.')

            elif not isinstance(fecha_nacimiento, date):
                raise forms.ValidationError(f'Tipo de dato inválido para la fecha.')


            fecha_actual =  timezone.localdate()
            fecha_minima = date(1900, 1, 1)
                
            if fecha_nacimiento:
                if fecha_nacimiento < fecha_minima or fecha_nacimiento > fecha_actual:
                    raise forms.ValidationError(f'La fecha debe estar entre {fecha_minima} y {fecha_actual}.')
            
        return paciente_externo
    

    def clean_maquinarx(self):
        """Valida que se haya seleccionado una máquina."""
        maquina = self.cleaned_data.get('maquinarx')
        if not maquina:
            raise forms.ValidationError("Debe seleccionar una máquina válida.")
        return maquina



class EvaluacionRXEditForm(EvaluacionRXCreateForm):
    """Formulario para editar EvaluaciónRx, hereda de CreateForm porque comparte toda la lógica."""
    pass
    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


        #agregar la sala aunque no este activa o este oculta
        info = ServicioService.encontrar_unidad_clinica_en_instance(self.instance)

        if info:
            clave_actual = info["clave"]
            label = f"{info['nombre']} ({info['tipo']})"
            

            # Revisar si ya está en choices
            if clave_actual not in dict(self.fields['unidad_clinica'].choices):
                # Agregarlo al principio
                self.fields['unidad_clinica'].choices = [(clave_actual, f"{label})")] + list(self.fields['unidad_clinica'].choices)

            self.fields['unidad_clinica'].initial = clave_actual
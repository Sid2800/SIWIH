from django import forms
from django.shortcuts import get_object_or_404
from servicio.models import Sala, Zona
from ubicacion.models import Departamento
from paciente.models import Paciente
from core.services.paciente_service import PacienteService
from core.services.ingreso.ingreso_service import IngresoService
from . import models
from dal import autocomplete
from datetime import date
import re


class IngresoCreateForm(forms.ModelForm):

    idPaciente = forms.CharField(required=True)
    dniPaciente = forms.CharField(required=False)
    numeroExpediente = forms.CharField(required=False)
    edadPaciente = forms.CharField(required=False)
    nombreCompletoPaciente = forms.CharField(required=False)
    fechaNacimientoPaciente = forms.CharField(required=False)
    sexoPaciente = forms.CharField(required=False)
    telefonoPaciente = forms.CharField(required=False)
    direccionPaciente = forms.CharField(required=False)

    acompanianteId = forms.CharField(required=False)
    acompanianteDni = forms.CharField(required=False)
    telefono = forms.CharField(required=False)
    acompanianteNombre1 = forms.CharField(required=False)
    acompanianteNombre2 = forms.CharField(required=False)
    acompanianteApellido1 = forms.CharField(required=False)
    acompanianteApellido2 = forms.CharField(required=False)
    sector = forms.CharField(required=False)
    



    departamento = forms.ModelChoiceField(
        queryset=Departamento.objects.all(),
        required=False,
        label="Departamento",
        widget=forms.Select(attrs={"class": "formularioCampo-select", "id": "id_departamento"})
    )

    municipio = forms.CharField(
        required=False,
        widget=forms.Select(attrs={"class": "formularioCampo-select", "id": "id_municipio"})
    )

    zona = forms.ModelChoiceField(
        queryset=Zona.objects.filter(estado=1),
        required=True,
        label="Zona",
        empty_label=None,
        widget=forms.Select(attrs={"class": "formularioCampo-select", "id": "id_zona"})
    )

    sala = forms.ModelChoiceField(
        queryset=Sala.objects.filter(estado=1),
        required=True,
        label="Sala",
        widget=forms.Select(attrs={"class": "formularioCampo-select", "id": "id_sala"})
    )

    class Meta:
        model = models.Ingreso
        fields = ["sala","cama","observaciones","zona",]

        widgets = {
            "cama": autocomplete.ModelSelect2(
                url='camaAutocomplete',
                attrs={"class": "formularioCampo-select"}
            ),
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs) 





    def clean(self):
        cleaned_data = super().clean()
        id_paciente = cleaned_data.get('idPaciente')

        #validacion del paciente
        if id_paciente:
            paciente = get_object_or_404(Paciente, id=id_paciente)
            cleaned_data['paciente'] = paciente  # Agregamos el objeto en lugar del ID

            # Verificar si está inactivo
            if PacienteService.comprobar_inactivo(paciente.id):
                self.add_error(None, 'No puedes registrar un ingreso para un paciente inactivo')
                

            # Verificar si está fallecido
            if PacienteService.comprobar_defuncion(paciente):    
                self.add_error(None, 'No puedes registrar un ingreso para un paciente fallecido.')


            if IngresoService.tiene_ingreso_activo(paciente.id):
                self.add_error(None, 'El paciente seleccionado ya cuenta con un ingreso activo.')
                
        else:
            self.add_error(None, 'El paciente es obligatorio para realizar un ingreso.')


        #validacion de los campos relacionadoas al acompaniante

        #dni acompanianteDni
        dni_acompaniante = cleaned_data.get('acompanianteDni')
        if dni_acompaniante:
            regex_dni = r"^([0-3][0-9])([0-8][0-9])-(19|20)[0-9]{2}-[0-9]{5}$"
            if not re.match(regex_dni, dni_acompaniante):
                self.add_error(None, 'el formato de DNI es incorrecto')

        #nombre y apellidos
        
        self.validar_nombres(self.cleaned_data.get("acompanianteNombre1"))
        self.validar_nombres(self.cleaned_data.get("acompanianteNombre2"))
        self.validar_nombres(self.cleaned_data.get("acompanianteApellido1"))
        self.validar_nombres(self.cleaned_data.get("acompanianteApellido2"))



        return cleaned_data

    def clean_sala(self):
        sala = self.cleaned_data.get("sala")

        if not sala:
            raise forms.ValidationError("Debe seleccionar una sala.")

        # Verificar que exista y esté activa
        if not Sala.objects.filter(id=sala.id, estado=1).exists():
            raise forms.ValidationError("La sala seleccionada no está disponible o ha sido deshabilitada.")

        return sala
    

    def clean_zona(self):
        zona = self.cleaned_data.get("zona")
        
        if not zona:
            raise forms.ValidationError("Debe seleccionar una zona.")
        # Verificar que exista y esté activa
        if not Zona.objects.filter(codigo=zona.codigo, estado=1).exists():
            raise forms.ValidationError("La zona seleccionada no está disponible o ha sido deshabilitada.")

        return zona
    
    def validar_nombres(self, texto):
        regex_validacion = r"^[A-ZÑ.](?!.*\s{2})[A-ZÑ.\-\s]*$"
        texto = texto.upper()
        if texto and not re.match(regex_validacion, texto):
            self.add_error(None, 'El nombre o apellido del acompaniante contiene caracteres no permitidos')
        return texto
    



class IngresoEditForm(forms.ModelForm):

    idPaciente = forms.CharField(required=True)
    dniPaciente = forms.CharField(required=False)
    numeroExpediente = forms.CharField(required=False)
    edadPaciente = forms.CharField(required=False)
    nombreCompletoPaciente = forms.CharField(required=False)
    fechaNacimientoPaciente = forms.CharField(required=False)
    sexoPaciente = forms.CharField(required=False)
    telefonoPaciente = forms.CharField(required=False)
    direccionPaciente = forms.CharField(required=False)

    acompanianteId = forms.CharField(required=False)
    acompanianteDni = forms.CharField(required=False)
    telefono = forms.CharField(required=False)
    acompanianteNombre1 = forms.CharField(required=False)
    acompanianteNombre2 = forms.CharField(required=False)
    acompanianteApellido1 = forms.CharField(required=False)
    acompanianteApellido2 = forms.CharField(required=False)
    sector = forms.CharField(required=False)

    departamento = forms.ModelChoiceField(
        queryset=Departamento.objects.all(),
        required=False,
        label="Departamento",
        widget=forms.Select(attrs={"class": "formularioCampo-select", "id": "id_departamento"})
    )

    municipio = forms.CharField(
        required=False,
        widget=forms.Select(attrs={"class": "formularioCampo-select", "id": "id_municipio"})
    )

    zona = forms.ModelChoiceField(
        queryset=Zona.objects.filter(),
        required=True,
        label="Zona",
        empty_label=None,
        widget=forms.Select(attrs={"class": "formularioCampo-select", "id": "id_zona"})
    )

    sala = forms.ModelChoiceField(
        queryset=Sala.objects.filter(estado=1),
        required=True,
        label="Sala",
        widget=forms.Select(attrs={"class": "formularioCampo-select", "id": "id_sala"})
    )

    class Meta:
        model = models.Ingreso
        fields = ["sala", "cama", "observaciones","zona"]

        widgets = {
            "cama": autocomplete.ModelSelect2(
                url='camaAutocomplete',
                attrs={"class": "formularioCampo-select"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs) 
            


    def clean(self):
        cleaned_data = super().clean()
        id_paciente = cleaned_data.get('idPaciente')

        #validacion del paciente
        if id_paciente:
            paciente = get_object_or_404(Paciente, id=id_paciente)
            cleaned_data['paciente'] = paciente  # Agregamos el objeto en lugar del ID

        # Acceder al objeto actual
        ingreso = self.instance
    
        #validacion de que no se puede editar un ingreso finalizado o sea un ingreso que retorno a Archivo
        if ingreso.fecha_recepcion_sdgi is not None:
            self.add_error(None, 'No es posible editar un ingreso que finalizo su ciclo')
        if ingreso.estado == 2:
            self.add_error(None, 'No es posible editar un ingreso que fue reversado')

        
        #dni acompanianteDni
        dni_acompaniante = cleaned_data.get('acompanianteDni')
        if dni_acompaniante:
            regex_dni = r"^([0-3][0-9])([0-8][0-9])-(19|20)[0-9]{2}-[0-9]{5}$"
            if not re.match(regex_dni, dni_acompaniante):
                self.add_error(None, 'el formato de DNI es incorrecto')


        self.validar_nombres(self.cleaned_data.get("acompanianteNombre1"))
        self.validar_nombres(self.cleaned_data.get("acompanianteNombre2"))
        self.validar_nombres(self.cleaned_data.get("acompanianteApellido1"))
        self.validar_nombres(self.cleaned_data.get("acompanianteApellido2"))

        return cleaned_data



    def clean_sala(self):
        sala = self.cleaned_data.get("sala")

        if not sala:
            raise forms.ValidationError("Debe seleccionar una sala.")

        # Verificar que exista y esté activa
        if not Sala.objects.filter(id=sala.id, estado=1).exists():
            raise forms.ValidationError("La sala seleccionada no está disponible o ha sido deshabilitada.")

        return sala
    
    def clean_zona(self):
        zona = self.cleaned_data.get("zona")
        
        if not zona:
            raise forms.ValidationError("Debe seleccionar una zona.")
        # Verificar que exista 
        if not Zona.objects.filter(codigo=zona.codigo).exists():
            raise forms.ValidationError("La zona seleccionada no está disponible o ha sido deshabilitada.")

        return zona
    
    def validar_nombres(self, texto):
        regex_validacion = r"^[A-ZÑ.](?!.*\s{2})[A-ZÑ.\-\s]*$"
        texto = texto.upper()
        if texto and not re.match(regex_validacion, texto):
            self.add_error(None, 'El nombre o apellido del acompaniante contiene caracteres no permitidos')
        return texto
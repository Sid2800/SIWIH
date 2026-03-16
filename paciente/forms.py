from datetime import date, timedelta
from dateutil.relativedelta import relativedelta  
from dal import autocomplete
from django import forms
from . import models
from core.services.paciente_service import  PacienteService
from core.services.ingreso.ingreso_service  import  IngresoService
from core.services.atencion_service import  AtencionService

from ubicacion.models import Departamento, Sector
from django.core.exceptions import ObjectDoesNotExist
import re
from . import forms as misForm
from django.utils import timezone

class PacienteCreateForm(forms.ModelForm):

    
    # agregados para los recien nacidos y hijos de
    madreId = forms.CharField(required=False)
    madreDni = forms.CharField(required=False)
    madreNombre1 = forms.CharField(required=False)  
    madreApellido1 = forms.CharField(required=False)
    madreNombre2 = forms.CharField(required=False)  
    madreApellido2 = forms.CharField(required=False)

    padreId = forms.CharField(required=False) 
    padreDni = forms.CharField(required=False)
    padreNombre1 = forms.CharField(required=False)  
    padreApellido1 = forms.CharField(required=False)
    padreNombre2 = forms.CharField(required=False)  
    padreApellido2 = forms.CharField(required=False)

    departamento = forms.ModelChoiceField(
        queryset=Departamento.objects.all(),
        required=False,
        label="Departamento",
        widget=forms.Select(attrs={"class": "formularioCampo-select", "id": "id_departamento"})
    )

    # Campo de municipio, solo visible en el formulario, no relacionado al modelo
    municipio = forms.CharField(
        required=False,
        widget=forms.Select(attrs={"class": "formularioCampo-select", "id": "id_municipio"})
    )


    class Meta:
        def input_text(placeholder):
            return forms.TextInput(attrs={
                'class': 'formularioCampo-text',
                'placeholder': placeholder
            })

        def select_field():
            return forms.Select(attrs={
                'class': 'formularioCampo-select'
            })

        def textarea_field(placeholder):
            return forms.Textarea(attrs={
                'class': 'formularioCampo-text',
                'placeholder': placeholder,
                'rows': 3
            })
        

        model = models.Paciente
        fields = ["dni","primer_nombre", "segundo_nombre", "primer_apellido","segundo_apellido", "fecha_nacimiento","telefono", "sexo","madre","estado_civil","ocupacion","tipo","nacionalidad","sector","observaciones","sai","fecha_sai","orden_gemelar","adolescente", "etnia"]

        widgets = {

        'dni': input_text('Numero'),
        'primer_nombre': input_text('Primer Nombre'),
        'segundo_nombre': input_text('Segundo Nombre'),
        'primer_apellido': input_text('Primer Apellido'),
        'segundo_apellido': input_text('Segundo Apellido'),
        'telefono': input_text('Telefono'),
        'orden_gemelar': input_text('Orden Gemelar'),

        'tipo': select_field(),
        'nacionalidad': select_field(),
        'sexo': select_field(),
        'estado_civil': select_field(),
        'ocupacion': select_field(),
        'etnia': select_field(),

        'observaciones': textarea_field('Observaciones'),

        "fecha_nacimiento": forms.DateInput(
            attrs={
                "class": "formularioCampo-date",
                "type": "date",
                "min": "1900-01-01",
                "max": date.today().strftime("%Y-%m-%d"),
            },
            format="%Y-%m-%d",
        ),

        "sector": autocomplete.ModelSelect2(
            url='sectorAutocomplete',
            attrs={"class": "formularioCampo-select"}
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['estado_civil'].queryset = models.Estado_civil.objects.filter(estado=True)
    """metodo que sobreescribe al metodo que verifica los campos antes de ser guardados
    agregamos las validaciones depennnndeintes, las individaules ser realizan en su propio metodo
    """   
    def clean(self):
        cleaned_data = super().clean()

        # Obtener datos del formulario
        tipo_identificacion = cleaned_data.get('tipo')
        nacionalidad = cleaned_data.get('nacionalidad')
        dni = cleaned_data.get('dni')

        # Verificar si tipo_identificacion y nacionalidad existen antes de acceder a sus IDs
        tipo_id = getattr(tipo_identificacion, "id", None)
        nacionalidad_id = getattr(nacionalidad, "id", None)
        
        # Si el tipo de identificación es "IDENTIDAD" (ID = 1) y la nacionalidad es hondureña (ID = 1)
        regex_dni = r"^([0-3][0-9])([0-9][0-9])-(19|20)[0-9]{2}-[0-9]{5}$"
        if tipo_id == 1 and nacionalidad_id == 1:
            if dni:
                if not re.match(regex_dni, dni):
                    raise forms.ValidationError({'dni': 'El DNI no es válido para la nacionalidad.'})
                
                # Si pasa la validación, eliminar guiones y actualizar el campo
                cleaned_data['dni'] = dni.replace('-', '')

        #asegueramos que un rn y hijo de  no se registre si no tiene los campos minimos madre
        
        nombre1Madre = cleaned_data.get('madreNombre1')
        apellido1Madre = cleaned_data.get('madreApellido1')
        nombre2Madre = cleaned_data.get('madreNombre2')
        apellido2Madre = cleaned_data.get('madreApellido2')


                    
        nombre1Padre = cleaned_data.get('padreNombre1')
        apellido1Padre = cleaned_data.get('padreApellido1')
        nombre2Padre = cleaned_data.get('padreNombre2')
        apellido2Padre = cleaned_data.get('padreApellido2')

        
        #validar 
        #dni mdare y padre si no coicide con nada establcere como none
        def validar_dni(dni):
            if dni:
                dni = dni.strip()
                if len(dni) == 15 and re.match(regex_dni, dni):
                    return dni.replace('-', '')
            return None


        cleaned_data['madreDni'] = validar_dni(cleaned_data.get('madreDni'))
        cleaned_data['padreDni'] = validar_dni(cleaned_data.get('padreDni'))


        # Aplicar la función validar_nombres si el campo tiene un valor
        cleaned_data['madreNombre1'] = self.validar_nombres(nombre1Madre.upper()) if nombre1Madre else nombre1Madre
        cleaned_data['madreApellido1'] = self.validar_nombres(apellido1Madre.upper()) if apellido1Madre else apellido1Madre
        cleaned_data['madreNombre2'] = self.validar_nombres(nombre2Madre.upper()) if nombre2Madre else nombre2Madre
        cleaned_data['madreApellido2'] = self.validar_nombres(apellido2Madre.upper()) if apellido2Madre else apellido2Madre

        cleaned_data['padreNombre1'] = self.validar_nombres(nombre1Padre.upper()) if nombre1Padre else nombre1Padre
        cleaned_data['padreApellido1'] = self.validar_nombres(apellido1Padre.upper()) if apellido1Padre else apellido1Padre
        cleaned_data['padreNombre2'] = self.validar_nombres(nombre2Padre.upper()) if nombre2Padre else nombre2Padre
        cleaned_data['padreApellido2'] = self.validar_nombres(apellido2Padre.upper()) if apellido2Padre else apellido2Padre



        #VERIFICAR QUE UN RN O UN HIJO DE NO SE REGISTR SI NO SE INDICA  LA MADRE
        if tipo_id in [3, 4]:
            if not nombre1Madre or not apellido1Madre:  # Requiere ambos
                self.add_error('madre', f'Un recién nacido o hijo no registrado no puede crearse sin una madre.')
            # SOBRE ESCRITURA DE LOS CMAPOS NOMBRES Y APELLIDOS DEL PACIENTE 
            prefijo = "RN" if tipo_id == 3 else "HIJO DE"
            cleaned_data['primer_nombre'] = f"{prefijo} {nombre1Madre.upper()}"
            cleaned_data['segundo_nombre'] = cleaned_data.get('madreNombre2').upper() if cleaned_data.get('madreNombre2') else None
            cleaned_data['primer_apellido'] = apellido1Madre.upper()
            cleaned_data['segundo_apellido'] = cleaned_data.get('madreApellido2').upper() if cleaned_data.get('madreApellido2') else None
            cleaned_data['dni'] = None


        # EL TIPO 5 ES DESCONOCIDO POR LOGICA NO CONOCESMOS SU DNI
        if tipo_id == 5:
            cleaned_data['dni'] = None


        # Validar la fecha según el tipo
        fecha_actual = date.today()
        fecha_minima = date(1900, 1, 1)
        fecha_maxima = None

        if tipo_id == 3:  # RN (Recién Nacido)
            fecha_minima = fecha_actual - timedelta(days=28)
        elif tipo_id == 4:  # HIJO DE
            # Fecha mínima: 18 años atrás
            fecha_minima = fecha_actual - relativedelta(years=18)
            # Fecha máxima: 45 días atrás desde hoy
            fecha_maxima = fecha_actual - timedelta(days=28)

        # Obtención de la fecha de nacimiento
        fecha_nacimiento = cleaned_data.get('fecha_nacimiento')
        if fecha_nacimiento:
            if tipo_id == 4:  # Validación para HIJO DE
                if fecha_nacimiento < fecha_minima or fecha_nacimiento > fecha_maxima:
                    self.add_error('fecha_nacimiento', f'La fecha debe estar entre {fecha_minima} y {fecha_maxima}.')
            elif fecha_nacimiento < fecha_minima or fecha_nacimiento > fecha_actual:
                    self.add_error('fecha_nacimiento', f'La fecha debe estar entre {fecha_minima} y la fecha actual.')

        #SAI
        sai = cleaned_data.get("sai")
        # Si SAI está marcado y no hay fecha, la asignamos
        if sai:
            cleaned_data["fecha_sai"] = timezone.now()

        # Si SAI está desmarcado, limpiamos la fecha
        if not sai:
            cleaned_data["fecha_sai"] = None

        return cleaned_data

    #Funcion que valida los nombres y apellidos
    def validar_nombres(self, texto):
        regex_validacion = r"^[A-ZÑ.](?!.*\s{2})[A-ZÑ.\-\s]*$"
        if texto and not re.match(regex_validacion, texto):
            raise forms.ValidationError('Contiene caracteres no permitidos.')
        return texto
    
    
    def clean_primer_nombre(self):
        primer_nombre = self.cleaned_data.get("primer_nombre")
        return self.validar_nombres(primer_nombre.upper()) if primer_nombre else primer_nombre

    def clean_segundo_nombre(self):
        segundo_nombre = self.cleaned_data.get("segundo_nombre")
        return self.validar_nombres(segundo_nombre.upper()) if segundo_nombre else segundo_nombre

    def clean_primer_apellido(self):
        primer_apellido = self.cleaned_data.get("primer_apellido")
        return self.validar_nombres(primer_apellido.upper()) if primer_apellido else primer_apellido

    def clean_segundo_apellido(self):
        segundo_apellido = self.cleaned_data.get("segundo_apellido")
        return self.validar_nombres(segundo_apellido.upper()) if segundo_apellido else segundo_apellido
    
    def clean_etnia(self):
        etnia = self.cleaned_data.get("etnia")

        if not etnia:
            raise forms.ValidationError("Debe seleccionar una etnia.")

        return etnia


class PacienteEditForm(misForm.PacienteCreateForm):

    class Meta(PacienteCreateForm.Meta):
        fields = PacienteCreateForm.Meta.fields + ["clasificacion", "estado"] 

    def clean(self):
        cleaned_data = super().clean()

        TIPO_DESCONOCIDO_ID = 5
        ESTADO_ACTIVO = "A"
        ESTADO_INACTIVO = "I"

        tipo_actual = self.instance.tipo
        nuevo_tipo = cleaned_data.get("tipo")

        if tipo_actual and nuevo_tipo:
            if tipo_actual.id != TIPO_DESCONOCIDO_ID and nuevo_tipo.id == TIPO_DESCONOCIDO_ID:
                raise forms.ValidationError({
                    'tipo': "No puedes cambiar un paciente registrado a desconocido."
                })

        estado_actual = self.instance.estado
        nuevo_estado = cleaned_data.get("estado")

        if (
            estado_actual != ESTADO_ACTIVO and
            nuevo_estado == ESTADO_ACTIVO and
            PacienteService.comprobar_defuncion(self.instance)
        ):
            raise forms.ValidationError({
                'estado': "Este paciente fue marcado como fallecido. No puede volver a estar activo, la defunción es irreversible."
            })

        if (
            estado_actual == ESTADO_ACTIVO and
            nuevo_estado == ESTADO_INACTIVO and
            IngresoService.tiene_ingreso_activo(self.instance.id)
        ):
            raise forms.ValidationError({
                'estado': "Este paciente aún tiene ingresos sin finalizar. Finalice el ciclo del ingreso e intente de nuevo."
            })

        if (
            estado_actual == ESTADO_ACTIVO and
            nuevo_estado == ESTADO_INACTIVO and
            AtencionService.tiene_atencion_activo(self.instance.id)
        ):
            raise forms.ValidationError({
                'estado': "Este paciente aún tiene atenciones sin finalizar. Finalice el ciclo de atención e intente de nuevo."
            })

        return cleaned_data


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # nos aseguramos que no este presente la opcion de desconocido
        #  al editar un registro que es dni o rn o hijo de
        if self.instance.pk and self.instance.tipo_id != 5:
            self.fields['tipo'].queryset = models.Tipo.objects.exclude(id=5)
        
        # Si está fallecido, no permitir Activo
        if PacienteService.comprobar_defuncion(self.instance):
            self.fields["estado"].choices = [
            choice for choice in self.fields["estado"].choices if choice[0] != "A"
        ]
            
        # Asegurar estilos para campos agregados en Edit
        self.fields["clasificacion"].widget.attrs.update({
            "class": "formularioCampo-select"
        })

        self.fields["estado"].widget.attrs.update({
            "class": "formularioCampo-select"
        })

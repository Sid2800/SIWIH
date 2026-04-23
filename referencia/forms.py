import json
from django import forms
from datetime import date
from django.utils.timezone import localtime, localdate
from .models import Referencia, Respuesta
from clinico.models import Diagnostico
from servicio.models import Institucion_salud, Area_atencion
from referencia.models import Referencia_especialidad
from core.services.paciente_service import PacienteService
from core.services.servicio_service import ServicioService
from core.validators.fecha_validator import validar_fecha
from core.validators.paciente import validar_paciente
from .validators import validar_instituciones_origen_destino, validar_diagnosticos_json, validar_referencia_para_respuesta
from django.db.models import Q


class ReferenciaCreateForm(forms.ModelForm):
    # Campos auxiliares (paciente y dependencia)
    idPaciente = forms.CharField(required=False)
    dniPaciente = forms.CharField(required=False)
    numeroExpediente = forms.CharField(required=False)
    edadPaciente = forms.CharField(required=False)
    nombreCompletoPaciente = forms.CharField(required=False)
    fechaNacimientoPaciente = forms.CharField(required=False)
    sexoPaciente = forms.CharField(required=False)
    telefonoPaciente = forms.CharField(required=False)
    direccionPaciente = forms.CharField(required=False)
    idReferencia = forms.CharField(widget=forms.HiddenInput(), required=False)
    idSeguimiento = forms.CharField(widget=forms.HiddenInput(), required=False)


    
    fecha_elaboracion = forms.DateTimeField(
        initial=localtime,  # devuelve datetime con tu zona local
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",  # HTML5 datetime input
                "class": "formularioCampo-date",
                " title" :"Fecha de elaboracion"
            },
            format="%Y-%m-%dT%H:%M",  # formato que entiende el input datetime-local
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
        required=True,
        validators=[validar_fecha] 
    )
    
    fecha_recepcion = forms.DateTimeField(
        initial=localtime,  # devuelve datetime con tu zona local
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",  # HTML5 datetime input
                "class": "formularioCampo-date",
                " title" :"Fecha de recepcion"
            },
            format="%Y-%m-%dT%H:%M",  # formato que entiende el input datetime-local
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
        validators=[validar_fecha] 
    )

    area_refiere = forms.ChoiceField(
        required=False,
        choices=[],
        widget=forms.Select(
            attrs={
                'class': 'formularioCampo-select',
                'id': 'id_area_refiere',
                'name': 'area_responde'
            }
        ),
        label='Area que refiere'
    ) 


    class Meta:
        model = Referencia
        fields = ["fecha_elaboracion", "fecha_recepcion", "tipo","institucion_origen", "institucion_destino", "atencion_requerida", "motivo","motivo_detalle","elaborada_por","oportuna","justificada","observaciones","especialidad_destino","area_refiere","motivo_no_atencion"]


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
            'direccionPaciente'
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

        # Solo instituciones activas
        qs_activas = Institucion_salud.objects.filter(estado=True)
        qs_especialidad = Referencia_especialidad.objects.filter(estado=True)
        qs_dependencias = ServicioService.obtener_dependencias(incluir_externo=False)

        areas_refieren = [
            (d['clave'], f"{d['nombre']} ({d['tipo']})")
            for d in qs_dependencias
        ]

        self.fields['area_refiere'].choices = areas_refieren
        self.fields['motivo_no_atencion'].widget = forms.HiddenInput()


        if self.instance and self.instance.pk:
            self.fields['idReferencia'].initial = self.instance.pk

            # Verificar si existe seguimiento TIC asociado
            if hasattr(self.instance, 'seguimiento_tic'):
                self.fields['idSeguimiento'].initial = self.instance.seguimiento_tic.id
            else:
                self.fields['idSeguimiento'].initial = 0

            self.fields['motivo_no_atencion'].initial = self.instance.motivo_no_atencion or 0

        else:
            self.fields['idReferencia'].initial = 0
            self.fields['idSeguimiento'].initial = 0
            self.fields['motivo_no_atencion'].initial = 0
    

        self.fields['fecha_recepcion'].required = False

        self.fields['institucion_origen'].queryset = qs_activas
        self.fields['institucion_origen'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Institucion Origen'
        })

        self.fields['institucion_destino'].queryset = qs_activas
        self.fields['institucion_destino'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Institucion Destino'
        })

        self.fields['atencion_requerida'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Atencion requerida'
        })

        self.fields['especialidad_destino'].queryset = qs_especialidad
        self.fields['especialidad_destino'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Especialidad Destino'
        })


        self.fields['observaciones'].widget = forms.Textarea(
            attrs={
                'class': 'formularioCampo-text',
                'placeholder': 'Observaciones',
                'rows': 1,
            }
        )

        self.fields['elaborada_por'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Elaborada por'
        })
        #self.fields['elaborada_por'].empty_label = None

        self.fields['motivo'].widget.attrs.update({
        'class': 'formularioCampo-select',
        'placeholder': 'Motivo'
        })


        self.fields['motivo_detalle'].widget = forms.Textarea(
            attrs={
                'class': 'formularioCampo-text',
                'placeholder': 'Detalle motivo',
                'rows': 1,
            }
        )

        self.fields['idPaciente'] = forms.CharField(
            widget=forms.HiddenInput(attrs={'required': 'required'}),
            initial=None,
            required=False
        )

        self.asignar_propiedades_campos_paciente()

    #validad informacion enviada desde fronted 
    def clean(self):
        cleaned_data = super().clean()

        id_paciente = cleaned_data.get('idPaciente')
        diagnosticos_json = self.data.get("diagnostico_json")
        origen = cleaned_data.get('institucion_origen')
        destino = cleaned_data.get('institucion_destino')
        tipo_ref = cleaned_data.get('tipo')
        motivo_detalle = cleaned_data.get('motivo_detalle')
        observaciones = cleaned_data.get('observaciones')
        fecha_elaboracion = cleaned_data.get("fecha_elaboracion")
        fecha_recepcion = cleaned_data.get("fecha_recepcion")
        area_refiere = cleaned_data.get("area_refiere")
        especialidad_destino = cleaned_data.get("especialidad_destino")

        atencion_requerida = self.cleaned_data.get("atencion_requerida")
        if atencion_requerida is None:
            raise forms.ValidationError("Debe indicar la atencion requerida")
        
            

        if motivo_detalle is not None and motivo_detalle.strip():
            cleaned_data['motivo_detalle'] = motivo_detalle.upper()
        else:
            cleaned_data['motivo_detalle'] = None

        if observaciones is not None and observaciones.strip():
            cleaned_data['observaciones'] = observaciones.upper()
        else:
            cleaned_data['observaciones'] = None
                


        if fecha_elaboracion and fecha_recepcion:
            if fecha_elaboracion > fecha_recepcion:
                raise forms.ValidationError("La fecha de elaboración debe ser anterior a la fecha de recepción.")


        if tipo_ref == 1:  # Enviada
            cleaned_data['justificada'] = None
            cleaned_data['oportuna'] = None
            cleaned_data['fecha_recepcion'] = None
            cleaned_data['motivo_no_atencion'] = None

            if not especialidad_destino:
                raise forms.ValidationError("Debe indicar el área a la que el paciente es referido")

            if area_refiere:
                try:
                    obj, campo = ServicioService.obtener_dependencia_y_campo(area_refiere)
                except forms.ValidationError as e:
                    raise forms.ValidationError(str(e))

                # Limpiar campos de área de respuesta
                cleaned_data['area_refiere_sala'] = None
                cleaned_data['area_refiere_area_atencion'] = None
                cleaned_data['area_refiere_servicio_auxiliar'] = None

                campo = f"area_refiere_{campo}"
                cleaned_data[campo] = obj
            else:
                raise forms.ValidationError("Debe indicar el área que refiere")

        else: #recibida
            cleaned_data['especialidad_destino'] = None
            cleaned_data['area_refiere_sala'] = None
            cleaned_data['area_refiere_area_atencion'] = None
            cleaned_data['area_refiere_servicio_auxiliar'] = None

            try:
                justificada = int(self.data.get('justificada', 0))
                oportuna = int(self.data.get('oportuna', 0))
            except (ValueError, TypeError):
                raise forms.ValidationError("Debe indicar los datos de calidad (Justificada, Oportuna).")
            
            if justificada in [1, 2, 3] and oportuna in [1, 2, 3]:
                cleaned_data['justificada'] = justificada
                cleaned_data['oportuna'] = oportuna
            else:
                raise forms.ValidationError("Debe indicar los datos de calidad (Justificada, Oportuna).")
            
    


        #verificamos si es un paciente aceptable 
        cleaned_data['paciente'] = validar_paciente(id_paciente)

        #verificamos las instituciones activas y que no se repitan
        origen, destino = validar_instituciones_origen_destino(origen,destino,tipo_ref)
        cleaned_data['institucion_origen'] = origen
        cleaned_data['institucion_destino'] = destino

        # Validar que estudios_json 
        self.diagnosticos_validados = validar_diagnosticos_json(diagnosticos_json)

        return cleaned_data


class ReferenciaEditForm(ReferenciaCreateForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Obtener solo las activas
        qs_activas = Institucion_salud.objects.filter(estado=True)
        dependencias = ServicioService.obtener_dependencias(incluir_externo=False)

        # Si hay una instancia en edición
        if self.instance and self.instance.pk:
            # Agregar la institución origen aunque esté inactiva
            if self.instance.institucion_origen:
                qs_activas = qs_activas | Institucion_salud.objects.filter(pk=self.instance.institucion_origen.pk) # union de resultados 

            # Agregar la institución destino aunque esté inactiva
            if self.instance.institucion_destino:
                qs_activas = qs_activas | Institucion_salud.objects.filter(pk=self.instance.institucion_destino.pk)

            #agregar la sala aunque no este activa o este oculta
            info = ServicioService.encontrar_dependencia_en_instance(self.instance,prefijo="area_refiere_")

            if info:
                clave_actual = info["clave"]
                label = f"{info['nombre']} ({info['tipo']})"
            
                # Revisar si ya está en choices
                if clave_actual not in dict(self.fields['area_refiere'].choices):
                    # Agregarlo al principio
                    self.fields['area_refiere'].choices = [(clave_actual, f"{label})")] + list(self.fields['area_refiere'].choices)

                self.fields['area_refiere'].initial = clave_actual

        self.fields['institucion_origen'].queryset = qs_activas.distinct()
        self.fields['institucion_origen'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Institución Origen'
        })

        self.fields['institucion_destino'].queryset = qs_activas.distinct()
        self.fields['institucion_destino'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Institución Destino'
        })


    def clean(self):
        cleaned_data = super().clean()
        id_paciente = cleaned_data.get('idPaciente')
        tipo = cleaned_data.get('tipo')
        referencia_vieja = self.instance

        

        try:
            id_paciente = int(id_paciente)
        except ValueError:
            raise forms.ValidationError("Existe un problema con paciente indicado")

        # verificamos que no se cambio el paciente
        if id_paciente != referencia_vieja.paciente.id:
            raise forms.ValidationError("No se permite cambiar el paciente propietario de la referencia.")
        
        # verficamos que no se cambio el tipo de paciente
        if tipo != referencia_vieja.tipo:
            raise forms.ValidationError("No se permite cambiar el tipo de referencia.")
        
        # Validar motivo de no atencion unicmente para las ref recibidas 
        if tipo == 0:
            try:
                motivoNo = int(self.data.get('MotivoNoAtencion', 0))
            except (ValueError, TypeError):
                raise forms.ValidationError("Existe un erro con la no Atencion")
            cleaned_data['motivo_no_atencion'] = None if motivoNo == 0 else motivoNo 

            # Si intenta poner motivo de No Atención y la referencia ya tiene respuesta registrada
            if motivoNo != 0 and hasattr(referencia_vieja, "respuesta"):
                raise forms.ValidationError(
                    "No es posible asignar un motivo de NO ATENCIÓN porque esta referencia ya tiene una respuesta registrada."
                )

        else:
            cleaned_data['motivo_no_atencion'] = None

        return cleaned_data
    


class RespuestaCreateForm(forms.ModelForm):

    fecha_atencion = forms.DateTimeField(
        initial=localtime,  # devuelve datetime con tu zona local
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",  # HTML5 datetime input
                "class": "formularioCampo-date",
                " title" :"Fecha de atencion"
            },
            format="%Y-%m-%dT%H:%M",  # formato que entiende el input datetime-local
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
        required=False,
        validators=[validar_fecha] 
    )
    
    fecha_elaboracion = forms.DateTimeField(
        initial=localtime,  # devuelve datetime con tu zona local
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",  # HTML5 datetime input
                "class": "formularioCampo-date",
                " title" :"Fecha de elaboracion"
            },
            format="%Y-%m-%dT%H:%M",  # formato que entiende el input datetime-local
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
        required=False,
        validators=[validar_fecha]
    )
    
    fecha_recepcion = forms.DateTimeField(
        initial=localtime,  # devuelve datetime con tu zona local
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",  # HTML5 datetime input
                "class": "formularioCampo-date",
                " title" :"Fecha de recepcion"
            },
            format="%Y-%m-%dT%H:%M",  # formato que entiende el input datetime-local
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
        validators=[validar_fecha],
        required=False
    )

    fecha_cita = forms.DateField(
        initial=localdate,  # devuelve solo la fecha local actual
        widget=forms.DateInput(
            attrs={
                "type": "date",  # HTML5 date input
                "class": "formularioCampo-date",
                "title": "Fecha de cita",
            },
            format="%Y-%m-%d",  # formato compatible con el input type="date"
        ),
        input_formats=["%Y-%m-%d"],
        required=False
    )
    
    institucion_responde = forms.CharField(required=False)

    area_responde = forms.ChoiceField(
        required=False,
        choices=[],
        widget=forms.Select(
            attrs={
                'class': 'formularioCampo-select',
                'id': 'id_area_responde',
                'name': 'area_responde'
            }
        ),
        label='Area que responde'
    )

    idRespuesta = forms.CharField(widget=forms.HiddenInput(), required=False)

    # campos si es que repeusta inicia una referncia enviada
    seguimiento_referencia_institucion_destino = forms.ModelChoiceField(
        queryset=Institucion_salud.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'formularioCampo-select',
            'id': 'id_seguimiento_referencia_institucion_destino',
        }),
        label="Institución Destino"
    )

    seguimiento_referencia_especialidad_destino = forms.ModelChoiceField(
        queryset=Referencia_especialidad.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'formularioCampo-select',
            'id': 'id_seguimiento_referencia_especialidad_destino',
        }),
        label="Especialidad Destino"
    )


    class Meta:
        model = Respuesta
        fields = [
            'fecha_atencion',
            'fecha_elaboracion',
            'fecha_recepcion',
            'area_capta',
            'area_seguimiento_area_atencion',
            'institucion_destino',
            'observaciones',
            'motivo',
            'motivo_detalle',
            'elaborada_por',
            'atencion_requerida',
            'fecha_cita'
        ]

    def __init__(self, *args, principal_instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.principal_instance = principal_instance
        self.referencia = principal_instance 

        dependencias = ServicioService.obtener_dependencias(incluir_externo=False)
        qs_areas_atencion_activas = Area_atencion.objects.filter(estado=True)
        qs_instituciones_activa_1erNivel = Institucion_salud.objects.filter(Q(estado=True, nivel_atencion=1) | Q(id=65) # INCLUIMOS AL CERRATO
                                                        )



        
        if self.instance and self.instance.pk:
            self.fields['idRespuesta'].initial = self.instance.pk
        else: 
            self.fields['idRespuesta'].initial = 0



        qs_instituciones_activa_mayor_igual_complejidad = Institucion_salud.objects.filter(
            estado=True, 
            nivel_atencion__gte=2
        )
        qs_especialidades_referencia = Referencia_especialidad.objects.filter(estado=True)

        initial_institucion = None
        initial_especialidad = None
        readonly = False  

        if self.instance and self.instance.pk:
            if self.instance.seguimiento_referencia:
                # ---- Institución destino ----
                qs_extra = Institucion_salud.objects.filter(
                    pk=self.instance.seguimiento_referencia.institucion_destino.pk
                )
                qs_instituciones_activa_mayor_igual_complejidad |= qs_extra
                initial_institucion = self.instance.seguimiento_referencia.institucion_destino.pk

                # ---- Especialidad destino ----
                if self.instance.seguimiento_referencia.especialidad_destino:
                    initial_especialidad = self.instance.seguimiento_referencia.especialidad_destino.pk

                readonly = True

        # Asignar querysets
        self.fields['seguimiento_referencia_especialidad_destino'].queryset = qs_especialidades_referencia.distinct()
        self.fields['seguimiento_referencia_institucion_destino'].queryset = qs_instituciones_activa_mayor_igual_complejidad.distinct()

        # Asignar valores iniciales
        if initial_institucion:
            self.fields['seguimiento_referencia_institucion_destino'].initial = initial_institucion
        if initial_especialidad:
            self.fields['seguimiento_referencia_especialidad_destino'].initial = initial_especialidad

        # Aplicar readonly 
        if readonly:
            self.fields['seguimiento_referencia_institucion_destino'].widget.attrs['readonly'] = True
            self.fields['seguimiento_referencia_especialidad_destino'].widget.attrs['readonly'] = True


        areas_responden = [
            (d['clave'], f"{d['nombre']} ({d['tipo']})")
            for d in dependencias
        ]

        self.fields['area_responde'].choices = areas_responden
        if not self.instance.pk:  # solo si es creación
            self.fields['area_responde'].initial = "S-710" #obstetricia
        #self.fields['area_responde'].initial = "S-710"


        self.fields['area_capta'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Area que capta la referencia',
        })
        self.fields['area_capta'].initial = 3
        
        self.fields['institucion_responde'].widget.attrs.update({
            'class': 'formularioCampo-text',
            'placeholder': 'Institucion Responde',
            'disabled': True
        })

        self.fields['area_seguimiento_area_atencion'].queryset = qs_areas_atencion_activas
        self.fields['area_seguimiento_area_atencion'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Area de seguimiento'
        })

        self.fields['institucion_destino'].queryset = qs_instituciones_activa_1erNivel
        self.fields['institucion_destino'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Institucion Destino'
        })

        self.fields['motivo'].widget.attrs.update({
        'class': 'formularioCampo-select',
        'placeholder': 'Motivo'
        })
        self.fields['motivo'].initial = 3

        self.fields['motivo_detalle'].widget = forms.Textarea(
            attrs={
                'class': 'formularioCampo-text',
                'placeholder': 'Detalle motivo',
                'rows': 1,
            }
        )

        self.fields['elaborada_por'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Elaborada por'
        })
        self.fields['elaborada_por'].initial = 2

        self.fields['atencion_requerida'].widget.attrs.update({
            'class': 'formularioCampo-select',
            'placeholder': 'Atencion requerida'
        })

        self.fields['observaciones'].widget = forms.Textarea(
            attrs={
                'class': 'formularioCampo-text',
                'placeholder': 'Observaciones',
                'rows': 2,
            }
        )

        if principal_instance:
            # Se asigna dinámicamente el valor inicial del campo
            self.fields['institucion_responde'].initial = principal_instance.institucion_destino

        # prefijo para los id  de los campos de las referecinas

        for field_name, field in self.fields.items():
            field.widget.attrs['id'] = f"respuesta_{field_name}"

    def clean(self):
        cleaned_data = super().clean()

        # Campos clave
        tipo_referencia = int(self.data.get("tipo")) if self.data.get("tipo") is not None else None

        # Fechas
        fecha_elaboracion = cleaned_data.get("fecha_elaboracion")  # datetime
        fecha_atencion = cleaned_data.get("fecha_atencion")        # datetime
        fecha_cita = cleaned_data.get("fecha_cita")                # date

        # Áreas y seguimiento
        area_capta = cleaned_data.get("area_capta")
        area_responde = cleaned_data.get("area_responde")
        seguimiento = int(self.data.get("seguimiento")) if self.data.get("seguimiento") is not None else 1
        area_atencion_seguimiento = cleaned_data.get("area_seguimiento_area_atencion")
        institucion_destino = cleaned_data.get("institucion_destino")
        # referencia 
 
        seguimiento_referencia_especialidad_destino = cleaned_data.get("seguimiento_referencia_especialidad_destino")
        seguimiento_referencia_institucion_destino = cleaned_data.get("seguimiento_referencia_institucion_destino")
        # Diagnósticos JSON
        diagnostico_json = self.data.get("diagnostico_json")
        # Validacion de referencia verificada previamente.

        # Validaciones según tipo de referencia
        if tipo_referencia == 0 : # recibida
            if fecha_atencion and fecha_elaboracion and fecha_atencion > fecha_elaboracion:
                raise forms.ValidationError("La fecha de atención no puede ser posterior a la fecha de elaboración.")

            if not area_capta:
                raise forms.ValidationError("El área que capta la referencia es obligatoria.")
            
            if area_responde:
                try:
                    obj, campo = ServicioService.obtener_dependencia_y_campo(area_responde)
                except forms.ValidationError as e:
                    raise forms.ValidationError(str(e))

                # Limpiar campos de área de respuesta
                cleaned_data['area_reponde_sala'] = None
                cleaned_data['area_reponde_area_atencion'] = None
                cleaned_data['area_reponde_servicio_auxiliar'] = None

                campo = f"area_reponde_{campo}"
                cleaned_data[campo] = obj
            else:
                raise forms.ValidationError("Debe indicar un área de respuesta para la referencia.")


            # BLOQUEO DE CAMBIO SI YA EXISTE UNA REFERENCIA ENVIADA
            if self.instance.pk and self.instance.seguimiento_referencia:
                if seguimiento != 2:  # solo válido si mantiene tipo "referencia enviada"
                    raise forms.ValidationError(
                        "No puede cambiar el tipo de seguimiento porque ya existe una referencia enviada asociada."
                    )

            # Manejo de seguimiento
            if seguimiento in [1,0,2]:
                if seguimiento == 1:  # seguimiento interno
                    cleaned_data['institucion_destino'] = None
                    cleaned_data['seguimiento_referencia'] = None
                    if area_atencion_seguimiento is None:
                        raise forms.ValidationError("Debe indicar un área de seguimiento.")
                    if fecha_atencion and fecha_cita and fecha_cita < fecha_atencion.date():
                        raise forms.ValidationError("La fecha de cita debe ser posterior a la fecha de atención.")
                elif seguimiento == 0:  # manejo fuera de institución
                    cleaned_data['area_seguimiento_especialidad'] = None
                    cleaned_data['fecha_cita'] = None
                    cleaned_data['seguimiento_referencia'] = None
                    if not institucion_destino:
                        raise forms.ValidationError("Debe indicar la institución de seguimiento.")
                elif seguimiento == 2:
                    cleaned_data['area_seguimiento_especialidad'] = None
                    cleaned_data['fecha_cita'] = None
                    cleaned_data['institucion_destino'] = None

                    if not self.instance.seguimiento_referencia:
                        if not seguimiento_referencia_institucion_destino:
                            raise forms.ValidationError("Debe indicar la institución destino para el seguimiento por referencia")
                        if not seguimiento_referencia_especialidad_destino:
                            raise forms.ValidationError("Debe indicar destino para el seguimiento por referencia ")
                cleaned_data['seguimiento'] = seguimiento
            else:
                raise forms.ValidationError("Debe indicar al menos un tipo de seguimiento")

                
        elif tipo_referencia == 1:  # enviada
            # Validaciones futuras para tipo enviada
            if not institucion_destino:
                raise forms.ValidationError("Debe indicar la institución de seguimiento.")


        # Validación básica del tipo y contenido
        if not diagnostico_json or not isinstance(diagnostico_json, str):
            raise forms.ValidationError("Debe enviar al menos un diagnóstico.")

        try:
            diagnosticos = json.loads(diagnostico_json)
        except (TypeError, json.JSONDecodeError):
            raise forms.ValidationError("Los diagnósticos no son válidos.")

        if not diagnosticos:
            raise forms.ValidationError("Debe enviar al menos un estudio.")

        try:
            codigos = [int(e['id']) for e in diagnosticos]
        except (ValueError, TypeError, KeyError):
            raise forms.ValidationError("Uno o más diagnósticos tienen un ID inválido o faltante.")

        if len(codigos) != len(set(codigos)):
            raise forms.ValidationError("Hay diagnósticos repetidos.")

        estudios_existentes_ids = set(
            Diagnostico.objects.filter(id__in=codigos).values_list("id", flat=True)
        )

        for codigo in codigos:
            if codigo not in estudios_existentes_ids:
                raise forms.ValidationError(f"El código de diagnostico {codigo} no existe en la base de datos.")

        self.diagnosticos_validados = diagnosticos
        
        return cleaned_data


    def clean_observaciones(self):
        observaciones = self.cleaned_data.get('observaciones')

        if observaciones:
            observaciones = observaciones.strip().upper()
            if observaciones == "":  # En caso de solo espacios
                return None
            return observaciones
        return None


    def clean_motivo_detalle(self):
        motivo_detalle = self.cleaned_data.get('motivo_detalle')

        if motivo_detalle:
            motivo_detalle = motivo_detalle.strip().upper()
            # Si el usuario solo deja espacios, lo tratamos como None
            if not motivo_detalle:
                return None
            return motivo_detalle
        return None
    


class RespuestaEditForm(RespuestaCreateForm):
    """Formulario para editar una respuesta."""
    class Meta(RespuestaCreateForm.Meta):
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)   

        #agregar la sala aunque no este activa o este oculta
        info = ServicioService.encontrar_dependencia_en_instance(self.instance,prefijo="area_reponde_")

        if info:
            clave_actual = info["clave"]
            label = f"{info['nombre']} ({info['tipo']})"
        
            # Revisar si ya está en choices
            if clave_actual not in dict(self.fields['area_responde'].choices):
                # Agregarlo al principio
                self.fields['area_responde'].choices = [(clave_actual, f"{label})")] + list(self.fields['area_responde'].choices)

            self.fields['area_responde'].initial = clave_actual
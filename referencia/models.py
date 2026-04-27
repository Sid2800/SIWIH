from django.db import models
from paciente.models import Paciente
from servicio.models import Institucion_salud, Sala, Area_atencion, ServiciosAux, Unidad_clinica
from clinico.models import Tipo_personal_salud, Diagnostico, Condicion_paciente
from core.constants.choices_constants import AtencionRequerida, MetodoSeguimiento, FuenteSeguimiento
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.

class Motivo_envio(models.Model):
    nombre_motivo_envio = models.CharField(max_length=100, unique=True)
    estado = models.BooleanField(default=1, verbose_name="Estado")
    
    class Meta:
        verbose_name = "Motivo de envio"
        verbose_name_plural = "Motivos de envio"
        ordering = ['nombre_motivo_envio']

    def __str__(self):
        return self.nombre_motivo_envio
    

class Referencia_especialidad(models.Model):
    nombre_referencia_especialidad = models.CharField(max_length=100, unique=True, verbose_name="nombre referencia especialidad")
    estado = models.BooleanField(default=True, verbose_name="Estado")

    class Meta:
        verbose_name = "Referencia especialidad"
        verbose_name_plural = "Especialidades de referencia"
        ordering = ['nombre_referencia_especialidad']

    def __str__(self):
        return self.nombre_referencia_especialidad


class Respuesta_Area_Capta(models.Model):
    nombre_area = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="Area que capta"
    )
    estado = models.BooleanField(default=True, verbose_name="Estado")

    class Meta:
        verbose_name = "Area que capta"
        verbose_name_plural = "Areas que captan"
        ordering = ['nombre_area']
    
    def __str__(self):
        return self.nombre_area


class Referencia(models.Model):
    fecha_elaboracion = models.DateTimeField(default=timezone.now, verbose_name="Fecha de elaboracion")
    fecha_recepcion = models.DateTimeField(verbose_name="Fecha de recepcion", null=True, blank=True)
    paciente = models.ForeignKey(Paciente, related_name="referencias", on_delete=models.PROTECT) 
    tipo = models.SmallIntegerField(
        verbose_name="Tipo",
        choices=[(0,"Recibida"),(1,"Enviada")],
        default=0
    )
    institucion_origen = models.ForeignKey(
        Institucion_salud,
        related_name="referencias_enviadas",
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    institucion_destino = models.ForeignKey(
        Institucion_salud,
        related_name="referencias_recibidas",
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    motivo = models.ForeignKey(
        Motivo_envio,
        related_name="referencias",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    motivo_detalle = models.TextField(verbose_name="Detalle del envio", null=True, blank=True)
    

    atencion_requerida = models.SmallIntegerField(
        verbose_name="Atencion requerida",
        choices=AtencionRequerida.choices,
        null=True,
        blank=True,
    )

    elaborada_por = models.ForeignKey(
        Tipo_personal_salud,
        related_name="referencias_elaboradas",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    # Área que refiere (solo para referencias tipo enviada)
    unidad_clinica_refiere = models.ForeignKey(Unidad_clinica, on_delete=models.PROTECT, null=True, blank=True, related_name="referencias_enviadas")
    
        
    especialidad_destino = models.ForeignKey(
        Referencia_especialidad,
        null = True,
        blank= True,
        on_delete=models.PROTECT,
        related_name="referencias_destino",
        verbose_name="Especialidad a la que se refiere"
    )

    OPCIONES_CALIDAD = (
        (1, "SI"),
        (2, "NO"),
        (3, "N/C"),
    )
    oportuna =  models.PositiveSmallIntegerField(
        choices=OPCIONES_CALIDAD, null=True, blank=True, verbose_name="Oportuna"
        )
    justificada = models.PositiveSmallIntegerField(
        choices=OPCIONES_CALIDAD, null=True, blank=True, verbose_name="Justificada"
        )
    
    MOTIVO_NO_ATENCION_CHOICES = [
        (1, "Fuga"),
        (2, "Alta exigida"),
        (3, "Otros")
    ]

    motivo_no_atencion = models.PositiveSmallIntegerField(
        choices=MOTIVO_NO_ATENCION_CHOICES,
        null=True,
        blank=True,
        verbose_name="Motivo de no atención"
    )

    observaciones = models.TextField(verbose_name="Observaciones", null=True,blank=True)
    estado = models.BooleanField(default=1, verbose_name="Estado")
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='referencias_creadas') 
    fecha_modificado = models.DateTimeField(verbose_name="Fecha Editado", auto_now=True)
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='referencias_modificadas')
    
    @property
    def area_refiere(self):
        """
        Retorna el área que refiere solo si la referencia es tipo 'Enviada'.
        """
        if self.tipo == 1:  # Enviada
            return self.area_refiere_sala or self.area_refiere_area_atencion or self.area_refiere_servicio_auxiliar
        return None  # No aplica para referencias tipo 'Recibida'
    
    @property
    def tipo_texto(self):
        return self.get_tipo_display()

    class Meta:
        verbose_name = "Referencia"
        verbose_name_plural = "Referencias"
        ordering = ['paciente__primer_nombre']

    def __str__(self):
        return f"Referencia de {self.paciente}"
    

class Referencia_diagnostico(models.Model):
    referencia = models.ForeignKey(
        Referencia,
        on_delete=models.CASCADE,
        related_name="diagnosticos"
    )
    diagnostico = models.ForeignKey(
        Diagnostico,
        on_delete=models.PROTECT,
        related_name="referencias"
    )
    confirmada = models.BooleanField(default=True, verbose_name="Confirmada")
    detalle = models.TextField(null=True, blank=True, verbose_name="Detalle diagnostico")
    estado = models.BooleanField(default=True, verbose_name="Estado")

    class Meta:
        verbose_name = "Diagnostico de referencia"
        verbose_name_plural = "Diagnosticos de referencia"
        unique_together = ("referencia", "diagnostico")  # evita duplicados
        ordering = ["referencia"]

    def __str__(self):
        return f"{self.referencia_id} - {self.diagnostico.nombre_diagnostico}"


class SeguimientoTic(models.Model):

    referencia = models.OneToOneField(
        Referencia,
        on_delete=models.CASCADE,
        related_name='seguimiento_tic'
    )
    metodo_comunicacion = models.PositiveSmallIntegerField(choices=MetodoSeguimiento.choices, verbose_name="Metodo de comunicacion", null=False, blank=False)
    establece_comunicacion = models.BooleanField(default=False, verbose_name="Establece Comunicacion", help_text="Indica si se logró establecer comunicación con el paciente" )
    asistio_referencia = models.BooleanField(default=False, null=True, blank=True)
    fuente_info = models.PositiveSmallIntegerField(choices=FuenteSeguimiento.choices, null=True, blank=True , verbose_name="Fuente de información")
    condicion_paciente = models.ForeignKey(Condicion_paciente, verbose_name="Condicion del paciente", on_delete=models.PROTECT, null=True, blank=True)
    observaciones = models.TextField(verbose_name="Observaciones", null=True, blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='seguimientos_creados') 

    class Meta:
        verbose_name = "Seguimiento TIC"
        verbose_name_plural = "Seguimientos TIC"

    def __str__(self):
        return f"Seguiento de {self.referencia.paciente}"
    
    
class Respuesta(models.Model):
    referencia = models.OneToOneField(
        Referencia,
        on_delete=models.CASCADE,
        related_name='respuesta'  # permite acceder desde Referencia.respuesta
    ) 
    fecha_elaboracion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de elaboracion")
    fecha_atencion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de atencion")
    fecha_recepcion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de recepcion")

    # Áreas que capta la referencia recibida
    area_capta = models.ForeignKey(
        Respuesta_Area_Capta,
        on_delete=models.PROTECT,
        related_name="referencias_recibidas_area",
        verbose_name="Are que capta la referencia",
        null=True,
        blank=True
    )

    # Área que da la respuesta
    unidad_clinica_responde = models.ForeignKey(Unidad_clinica, on_delete=models.PROTECT, null=True, blank=True, related_name="respuestas_emitidas")

    # Área de seguimiento (null indica que el seguimiento no lo damos nosotros)
    area_seguimiento_area_atencion = models.ForeignKey(
        Area_atencion, null=True, blank=True, on_delete=models.PROTECT,
        related_name="respuestas_seguimiento_area_atencion"
    )

    fecha_cita = models.DateField(null=True, blank=True, verbose_name="Fecha cita seguimiento")

    # Institución que dará seguimiento si no lo hacemos nosotros
    institucion_destino = models.ForeignKey(
        Institucion_salud,
        related_name="respuestas_enviadas_seguimiento",
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    #la repuesta deriva en referencia
    seguimiento_referencia = models.ForeignKey(
            Referencia,
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            related_name="respuestas_que_derivan_en_referencia",
            verbose_name="Referencia generada por el seguimiento"
        )

    elaborada_por = models.ForeignKey(
        Tipo_personal_salud,
        related_name="respuestas_elaboradas",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    motivo = models.ForeignKey(
        Motivo_envio,
        related_name="respuestas",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    motivo_detalle = models.TextField(verbose_name="Detalle del envio", null=True, blank=True)
    atencion_requerida = models.SmallIntegerField(
        verbose_name="Atencion requerida",
        choices=AtencionRequerida.choices,
        null=True,
        blank=True,
    )
    
    observaciones = models.TextField(verbose_name="Observaciones", null=True, blank=True)
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='respuestas_creadas') 
    fecha_modificado = models.DateTimeField(verbose_name="Fecha Editado", auto_now=True)
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='respuestas_modificadas')

    @property
    def institucion_responde(self):
        """
        Devuelve la institución que responde.
        """
        # Aquí puedes personalizar la lógica según tu negocio
        return self.referencia.institucion_destino

    @property
    def tipo(self):
        return self.referencia.tipo  

    class Meta:
        verbose_name = "Respuesta"
        verbose_name_plural = "Respuestas"
        ordering = ['referencia__paciente__primer_nombre']

    def __str__(self):
        return f"Respuesta de {self.referencia.paciente}"
    

# Modelo de diagnósticos de la respuesta
class Respuesta_diagnostico(models.Model):
    respuesta = models.ForeignKey(
        Respuesta,
        on_delete=models.CASCADE,
        related_name="diagnosticos"
    )
    diagnostico = models.ForeignKey(
        Diagnostico,
        on_delete=models.PROTECT,
        related_name="referencias_respuesta"
    )
    detalle = models.TextField(null=True, blank=True, verbose_name="Detalle diagnostico")
    estado = models.BooleanField(default=True, verbose_name="Estado")

    class Meta:
        verbose_name = "Diagnostico de respuesta"
        verbose_name_plural = "Diagnosticos de respuesta"
        unique_together = ("respuesta", "diagnostico")
        ordering = ["respuesta"]

    def __str__(self):
        return f"{self.respuesta.id} - {self.diagnostico.nombre_diagnostico}"
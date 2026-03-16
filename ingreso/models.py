from django.db import models
from paciente import models as modelosPaciente
from servicio import models as modelosServicio
from ubicacion import models as modelosUbicacion
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.

class Acompanante(models.Model):
    dni = models.CharField(max_length=50, unique=True, verbose_name="Numero de identificacion", blank=True, null=True)
    primer_nombre = models.CharField(verbose_name="Primer nombre", max_length=100)
    segundo_nombre = models.CharField(
        verbose_name="Segundo nombre", max_length=100,
        blank=True, null=True)
    primer_apellido = models.CharField(
        verbose_name="Primer apellido",max_length=100)
    segundo_apellido = models.CharField(
        verbose_name="Segundo apellido",max_length=100,
        blank=True, null=True)
    telefono = models.CharField(max_length=15, verbose_name="Teléfono", null=True, blank=True)
    sector = models.ForeignKey(modelosUbicacion.Sector, on_delete=models.PROTECT, verbose_name="Domicilio", null=True,blank=True)  
    

    class Meta:
        verbose_name = "Acompañante"
        verbose_name_plural = "Acompañantes"
        ordering = ["primer_nombre"]

    def __str__(self):
        return f"{self.primer_nombre} {self.primer_apellido}"


class Ingreso(models.Model):
    paciente  = models.ForeignKey(modelosPaciente.Paciente, on_delete=models.PROTECT, related_name="pacientes_ingresados", verbose_name="Paciente")
    sala = models.ForeignKey(modelosServicio.Sala, on_delete=models.PROTECT, related_name="ingresos_sala")
    cama = models.ForeignKey(modelosServicio.Cama, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_ingreso = models.DateTimeField(default=timezone.now)
    fecha_egreso = models.DateTimeField(null=True, blank=True)
    fecha_recepcion_sdgi = models.DateTimeField(null=True, blank=True)
    zona = models.ForeignKey(modelosServicio.Zona, on_delete=models.PROTECT)
    acompaniante = models.ForeignKey(Acompanante, on_delete=models.SET_NULL, related_name="acompaniantes_ingreso",null=True, blank=True)
    observaciones = models.TextField(verbose_name="Observaciones", null=True,blank=True)
    
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='ingreso_registrado')  # Corregido related_name
    fecha_modificado = models.DateTimeField(verbose_name="Fecha Editado", auto_now=True)
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='ingreso_modificadas')  # Corregido related_name
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=[(1, "Activo"), (2, "Inactivo")],
        default=1
    )



    class Meta:
        verbose_name = "Ingreso"
        verbose_name_plural = "Ingresos"
        ordering = ["fecha_ingreso"]

    def __str__(self):
        return f"{self.paciente.primer_nombre} {self.paciente.primer_apellido} {self.sala.nombre_sala}"
    

class RecepcionIngresoSala(models.Model):
    fecha_recepcion = models.DateTimeField(auto_now_add=True)
    recibido_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='recepciones_ingresos_sala_recibidas'  # más legible y tipo snake_case
    )
    fecha_modificado = models.DateTimeField(
        verbose_name="Fecha de modificación",
        auto_now=True
    )
    modificado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='recepciones_ingresos_sala_modificadas'
    )
    observaciones = models.TextField(
        verbose_name="Observaciones",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Recepción de ingreso sala"
        verbose_name_plural = "Recepciones de ingresos sala"
        ordering = ["-fecha_recepcion"]  # Lo más reciente primero (opcional)

    def __str__(self):
        return f"Recepción #{self.id} - {self.fecha_recepcion.date()} por {self.recibido_por.username}"

class RecepcionIngresoDetalleSala(models.Model):
    recepcion = models.ForeignKey(
        RecepcionIngresoSala,
        on_delete=models.CASCADE,
        related_name='detalles'
    )

    ingreso = models.ForeignKey(
        Ingreso,
        on_delete=models.PROTECT,
        related_name='recepcion_detalles_sala'  # nombre más claro
    )

    class Meta:
        verbose_name = "Detalle de recepción"
        verbose_name_plural = "Detalles de recepción"
        unique_together = ('recepcion', 'ingreso')  # evita ingresos duplicados en la misma recepción

    def __str__(self):
        return f"Ingreso #{self.ingreso.id} en recepción #{self.recepcion.id}"
    

class RecepcionIngresoSDGI(models.Model):
    fecha_recepcion = models.DateTimeField(auto_now_add=True)

    recibido_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='recepciones_ingresos_sdgi_recibidas'
    )

    fecha_modificado = models.DateTimeField(
        verbose_name="Fecha de modificación",
        auto_now=True
    )

    modificado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='recepciones_ingresos_sdgi_modificadas'
    )

    observaciones = models.TextField(
        verbose_name="Observaciones",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Recepción de ingreso SDGI"
        verbose_name_plural = "Recepciones de ingresos SDGI"
        ordering = ["-fecha_recepcion"]

    def __str__(self):
        return f"Recepción SDGI #{self.id} - {self.fecha_recepcion.date()} por {self.recibido_por.username}"


class RecepcionIngresoDetalleSDGI(models.Model):
    recepcion = models.ForeignKey(
        RecepcionIngresoSDGI,
        on_delete=models.CASCADE,
        related_name='detalles'
    )

    ingreso = models.ForeignKey(
        Ingreso,
        on_delete=models.PROTECT,
        related_name='recepcion_detalles_sdgi'
    )

    class Meta:
        verbose_name = "Detalle de recepción SDGI"
        verbose_name_plural = "Detalles de recepción SDGI"
        unique_together = ('recepcion', 'ingreso')

    def __str__(self):
        return f"Ingreso #{self.ingreso.id} en recepción SDGI #{self.recepcion.id}"
    

class ReversionRecepcionIngreso(models.Model):
    ingreso = models.ForeignKey(Ingreso, on_delete=models.PROTECT, related_name='reversiones')
    motivo = models.TextField()
    revertido_por = models.ForeignKey(User, on_delete=models.PROTECT)
    fecha_reversion = models.DateTimeField(auto_now_add=True)

    # Opcionalmente, puedes marcar qué se revirtió
    reverso_recepcion_sala = models.BooleanField(default=False)
    reverso_recepcion_sdgi = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Reversión de Ingreso"
        verbose_name_plural = "Reversiones de Ingresos"

    def __str__(self):
        return f"Reversión #{self.id} de ingreso #{self.ingreso.id} por {self.revertido_por.username}"
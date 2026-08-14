from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db import transaction
from django.db.models import Q
from django.core.validators import MinValueValidator
from django.utils import timezone


class TipoSolicitud(models.Model):
    codigo = models.CharField(max_length=30, unique=True, db_index=True)
    nombre = models.CharField(max_length=120, db_index=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transporte_hospitalario_tipo_solicitud"
        ordering = ["nombre"]
        verbose_name = "Tipo solicitud"
        verbose_name_plural = "Tipos solicitud"

    def __str__(self):
        return self.nombre


class Prioridad(models.Model):
    codigo = models.CharField(max_length=30, unique=True, db_index=True)
    nombre = models.CharField(max_length=120, db_index=True)
    nivel = models.PositiveSmallIntegerField(db_index=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transporte_hospitalario_prioridad"
        ordering = ["nivel", "nombre"]
        verbose_name = "Prioridad"
        verbose_name_plural = "Prioridades"

    def __str__(self):
        return self.nombre


class TipoViaje(models.Model):
    codigo = models.CharField(max_length=30, unique=True, db_index=True)
    nombre = models.CharField(max_length=120, db_index=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transporte_hospitalario_tipo_viaje"
        ordering = ["nombre"]
        verbose_name = "Tipo viaje"
        verbose_name_plural = "Tipos viaje"

    def __str__(self):
        return self.nombre


class Viatico(models.Model):
    codigo = models.CharField(max_length=30, unique=True, db_index=True)
    nombre = models.CharField(max_length=120, db_index=True)
    descripcion = models.TextField(blank=True, null=True)
    monto_vigente = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    activo = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transporte_hospitalario_viatico"
        ordering = ["nombre"]
        verbose_name = "Viatico"
        verbose_name_plural = "Viaticos"

    def __str__(self):
        return self.nombre

    @staticmethod
    def _formatear_codigo(pk):
        return f"VIA-{pk:03d}"

    def save(self, *args, **kwargs):
        codigo_original = None
        if self.pk:
            codigo_original = (
                type(self).objects.filter(pk=self.pk).values_list("codigo", flat=True).first()
            )

        if not self.pk and not self.codigo:
            with transaction.atomic():
                self.codigo = f"TMP-{uuid.uuid4().hex[:12]}"
                super().save(*args, **kwargs)
                self.codigo = self._formatear_codigo(self.pk)
                super().save(update_fields=["codigo"])
            return

        if codigo_original and self.codigo != codigo_original:
            self.codigo = codigo_original

        super().save(*args, **kwargs)

    @staticmethod
    def _normalizar_monto(monto):
        if monto is None:
            return None
        if isinstance(monto, Decimal):
            return monto
        return Decimal(str(monto))

    @classmethod
    def crear_con_historial(cls, *, codigo, nombre, monto_vigente=None, descripcion=None, activo=True, cambiado_por=None, motivo=None):
        if monto_vigente is not None and not motivo:
            raise ValidationError("El motivo es obligatorio para registrar el monto inicial del viático.")

        monto_vigente = cls._normalizar_monto(monto_vigente)

        with transaction.atomic():
            viatico = cls.objects.create(
                codigo=codigo,
                nombre=nombre,
                descripcion=descripcion,
                monto_vigente=monto_vigente,
                activo=activo,
            )
            if monto_vigente is not None:
                ViaticoHistorial.objects.create(
                    viatico=viatico,
                    monto_anterior=None,
                    monto_nuevo=monto_vigente,
                    cambiado_por=cambiado_por,
                    motivo=motivo,
                )
        return viatico

    def registrar_cambio_monto(self, nuevo_monto, *, cambiado_por=None, motivo):
        if not motivo:
            raise ValidationError("El motivo es obligatorio para modificar el monto vigente.")

        nuevo_monto = self._normalizar_monto(nuevo_monto)
        monto_anterior = self.monto_vigente

        with transaction.atomic():
            self.monto_vigente = nuevo_monto
            self.save(update_fields=["monto_vigente", "updated_at"])
            ViaticoHistorial.objects.create(
                viatico=self,
                monto_anterior=monto_anterior,
                monto_nuevo=nuevo_monto,
                cambiado_por=cambiado_por,
                motivo=motivo,
            )

        return self


class ViaticoHistorial(models.Model):
    viatico = models.ForeignKey(
        Viatico,
        on_delete=models.PROTECT,
        related_name="historial_cambios",
    )
    monto_anterior = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    monto_nuevo = models.DecimalField(max_digits=12, decimal_places=2)
    cambiado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="viaticos_historial_cambios",
        null=True,
        blank=True,
    )
    motivo = models.TextField()
    fecha_cambio = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "transporte_hospitalario_viatico_historial"
        ordering = ["-fecha_cambio", "-id"]
        verbose_name = "Viatico historial"
        verbose_name_plural = "Viaticos historial"

    def __str__(self):
        return f"Viatico {self.viatico_id} - {self.fecha_cambio:%Y-%m-%d %H:%M}"


class ViajeViatico(models.Model):
    viaje = models.ForeignKey(
        "Viaje",
        on_delete=models.PROTECT,
        related_name="viaje_viaticos",
    )
    viatico = models.ForeignKey(
        Viatico,
        on_delete=models.PROTECT,
        related_name="viaje_viaticos",
    )
    monto_aplicado = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_asignacion = models.DateTimeField(default=timezone.now, db_index=True)
    observacion = models.TextField(blank=True, null=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="viajes_viaticos_creados",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "transporte_hospitalario_viaje_viatico"
        ordering = ["-fecha_asignacion", "-id"]
        verbose_name = "Viaje viatico"
        verbose_name_plural = "Viajes viatico"

    def __str__(self):
        return f"Viaje {self.viaje_id} - Viatico {self.viatico_id}"

    @classmethod
    def registrar_asignacion(cls, *, viaje, viatico, creado_por=None, observacion=None, fecha_asignacion=None):
        monto_aplicado = Viatico._normalizar_monto(viatico.monto_vigente)
        if monto_aplicado is None:
            raise ValidationError("El viático no tiene un monto vigente para asignarse al viaje.")

        return cls.objects.create(
            viaje=viaje,
            viatico=viatico,
            monto_aplicado=monto_aplicado,
            fecha_asignacion=fecha_asignacion or timezone.now(),
            observacion=observacion,
            creado_por=creado_por,
        )


class Vehiculo(models.Model):
    codigo = models.CharField(max_length=30, unique=True, db_index=True)
    placa = models.CharField(max_length=20, unique=True, db_index=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transporte_hospitalario_vehiculo"
        ordering = ["codigo"]
        verbose_name = "Vehiculo"
        verbose_name_plural = "Vehiculos"

    def __str__(self):
        return f"{self.codigo} - {self.placa}"

    @staticmethod
    def _formatear_codigo(pk):
        return f"VEH-{pk:03d}"

    def save(self, *args, **kwargs):
        codigo_original = None
        if self.pk:
            codigo_original = (
                type(self).objects.filter(pk=self.pk).values_list("codigo", flat=True).first()
            )

        if not self.pk and not self.codigo:
            with transaction.atomic():
                self.codigo = f"TMP-{uuid.uuid4().hex[:12]}"
                super().save(*args, **kwargs)
                self.codigo = self._formatear_codigo(self.pk)
                super().save(update_fields=["codigo"])
            return

        if codigo_original and self.codigo != codigo_original:
            self.codigo = codigo_original

        super().save(*args, **kwargs)


class Motorista(models.Model):
    empleado = models.OneToOneField(
        "rrhh.Empleado",
        on_delete=models.PROTECT,
        related_name="motorista",
    )
    activo = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transporte_hospitalario_motorista"
        ordering = ["id"]
        verbose_name = "Motorista"
        verbose_name_plural = "Motoristas"

    def __str__(self):
        return str(self.empleado)


class PuntoSolicitud(models.Model):
    unidad_clinica = models.ForeignKey(
        "servicio.Unidad_clinica",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="puntos_solicitud_clinica",
    )
    unidad = models.ForeignKey(
        "servicio.Unidad",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="puntos_solicitud_unidad",
    )
    activo = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transporte_hospitalario_punto_solicitud"
        ordering = ["id"]
        verbose_name = "Punto solicitud"
        verbose_name_plural = "Puntos solicitud"
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(unidad_clinica__isnull=False, unidad__isnull=True)
                    | Q(unidad_clinica__isnull=True, unidad__isnull=False)
                ),
                name="ck_th_punto_solicitud_xor",
            )
        ]

    def __str__(self):
        if self.unidad_clinica:
            return str(self.unidad_clinica)
        if self.unidad:
            return str(self.unidad)
        return f"Punto solicitud {self.pk}"


class Solicitud(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        PROGRAMADA = "PROGRAMADA", "Programada"
        EN_EJECUCION = "EN_EJECUCION", "En ejecución"
        FINALIZADA = "FINALIZADA", "Finalizada"
        ANULADA = "ANULADA", "Anulada"

    numero_solicitud = models.CharField(max_length=30, unique=True, db_index=True)
    fecha_solicitud = models.DateTimeField(default=timezone.now, db_index=True)
    solicitante_empleado = models.ForeignKey(
        "rrhh.Empleado",
        on_delete=models.PROTECT,
        related_name="solicitudes_emitidas",
    )
    punto_solicitud = models.ForeignKey(
        PuntoSolicitud,
        on_delete=models.PROTECT,
        related_name="solicitudes",
    )
    tipo_solicitud = models.ForeignKey(
        TipoSolicitud,
        on_delete=models.PROTECT,
        related_name="solicitudes",
    )
    prioridad = models.ForeignKey(
        Prioridad,
        on_delete=models.PROTECT,
        related_name="solicitudes",
    )
    lugar_salida = models.ForeignKey(
        "servicio.Institucion_salud",
        on_delete=models.PROTECT,
        related_name="solicitudes_salida",
    )
    lugar_destino = models.ForeignKey(
        "servicio.Institucion_salud",
        on_delete=models.PROTECT,
        related_name="solicitudes_destino",
    )
    motivo = models.TextField()
    observaciones = models.TextField(blank=True, null=True)
    motivo_anulacion = models.TextField(blank=True, null=True)
    observacion_anulacion = models.TextField(blank=True, null=True)
    anulada_en = models.DateTimeField(blank=True, null=True)
    anulada_por = models.ForeignKey(
        "auth.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitudes_anuladas",
    )
    estado = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        db_index=True,
    )
    activo = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transporte_hospitalario_solicitud"
        ordering = ["-fecha_solicitud", "numero_solicitud"]
        verbose_name = "Solicitud"
        verbose_name_plural = "Solicitudes"

    def __str__(self):
        return self.numero_solicitud

    @property
    def esta_asociada_autorizacion(self):
        tiene_viaje_solicitud_activa = getattr(self, "tiene_viaje_solicitud_activa", None)
        if tiene_viaje_solicitud_activa is not None:
            return bool(tiene_viaje_solicitud_activa)
        return self.viaje_solicitudes.filter(activo=True).exists()

    @property
    def proceso_funcional(self):
        if self.estado == self.Estado.ANULADA:
            return "Anulada"
        if self.estado == self.Estado.FINALIZADA:
            return "Finalizada"
        if self.estado == self.Estado.EN_EJECUCION:
            return "En ejecución"
        if self.estado == self.Estado.PROGRAMADA:
            return "Programada"
        if self.esta_asociada_autorizacion:
            return "En proceso"
        return "Pendiente"

    @property
    def puede_editar(self):
        return self.estado == self.Estado.PENDIENTE and not self.esta_asociada_autorizacion
        if self.estado != self.Estado.PENDIENTE:
            return False
        return not self.esta_asociada_autorizacion


class SolicitudPaciente(models.Model):
    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.PROTECT,
        related_name="solicitud_pacientes",
    )
    paciente = models.ForeignKey(
        "paciente.Paciente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitudes_transporte",
    )
    ingreso = models.ForeignKey(
        "ingreso.Ingreso",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitudes_transporte",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "transporte_hospitalario_solicitud_paciente"
        ordering = ["-created_at", "id"]
        verbose_name = "Solicitud paciente"
        verbose_name_plural = "Solicitudes paciente"
        constraints = [
            models.CheckConstraint(
                check=(Q(paciente__isnull=False) | Q(ingreso__isnull=False)),
                name="ck_th_solicitud_paciente_ref",
            )
        ]

    def __str__(self):
        return f"Solicitud {self.solicitud_id}"


class SolicitudPersonal(models.Model):
    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.PROTECT,
        related_name="solicitud_personal",
    )
    empleado = models.ForeignKey(
        "rrhh.Empleado",
        on_delete=models.PROTECT,
        related_name="solicitudes_personal_transporte",
    )
    observacion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "transporte_hospitalario_solicitud_personal"
        ordering = ["id"]
        verbose_name = "Solicitud personal"
        verbose_name_plural = "Solicitudes personal"

    def __str__(self):
        return f"Solicitud {self.solicitud_id} - {self.empleado_id}"


class Viaje(models.Model):
    class TipoProgramacion(models.IntegerChoices):
        REGIONAL = 1, "Regional"
        NACIONAL = 2, "Nacional"

    numero_viaje = models.CharField(max_length=30, unique=True, db_index=True)
    fecha_programacion = models.DateTimeField(default=timezone.now, db_index=True)
    motorista = models.ForeignKey(
        Motorista,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="viajes",
    )
    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="viajes",
    )
    centro_costo = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    tipo_viaje = models.PositiveSmallIntegerField(
        choices=TipoProgramacion.choices,
        db_index=True,
    )
    estado = models.CharField(max_length=30, db_index=True)
    activo = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transporte_hospitalario_viaje"
        ordering = ["-fecha_programacion", "numero_viaje"]
        verbose_name = "Viaje"
        verbose_name_plural = "Viajes"

    def __str__(self):
        return self.numero_viaje


class ViajeSolicitud(models.Model):
    viaje = models.ForeignKey(
        Viaje,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="viaje_solicitudes",
    )
    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.PROTECT,
        related_name="viaje_solicitudes",
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="viajes_solicitud_creados",
        null=True,
        blank=True,
    )
    fecha_asignacion = models.DateTimeField(default=timezone.now, db_index=True)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "transporte_hospitalario_viaje_solicitud"
        ordering = ["-fecha_asignacion", "id"]
        verbose_name = "Viaje solicitud"
        verbose_name_plural = "Viajes solicitud"
        constraints = [
            models.UniqueConstraint(
                fields=["solicitud"],
                name="uq_th_viaje_solicitud_solicitud",
            )
        ]

    def __str__(self):
        return f"Viaje {self.viaje_id} - Solicitud {self.solicitud_id}"


class ViajePersonal(models.Model):
    viaje = models.ForeignKey(
        Viaje,
        on_delete=models.PROTECT,
        related_name="viaje_personal",
    )
    empleado = models.ForeignKey(
        "rrhh.Empleado",
        on_delete=models.PROTECT,
        related_name="viajes_personal_transporte",
    )
    tipo_participacion = models.CharField(max_length=30)

    class Meta:
        db_table = "transporte_hospitalario_viaje_personal"
        ordering = ["viaje_id", "id"]
        verbose_name = "Viaje personal"
        verbose_name_plural = "Viajes personal"

    def __str__(self):
        return f"Viaje {self.viaje_id} - Empleado {self.empleado_id}"


class EjecucionViaje(models.Model):
    viaje = models.OneToOneField(
        Viaje,
        on_delete=models.PROTECT,
        related_name="ejecucion_viaje",
    )
    fecha_salida = models.DateTimeField(db_index=True, blank=True, null=True)
    fecha_retorno = models.DateTimeField(db_index=True, blank=True, null=True)
    kilometraje_salida = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    kilometraje_retorno = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    combustible_salida = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    combustible_retorno = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    precio_litro_salida = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    litros_cargados_salida = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    total_combustible = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    observaciones_salida = models.TextField(blank=True, null=True)
    observaciones_retorno = models.TextField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transporte_hospitalario_ejecucion_viaje"
        ordering = ["-fecha_salida", "id"]
        verbose_name = "Ejecucion viaje"
        verbose_name_plural = "Ejecuciones viaje"

    def __str__(self):
        return f"Ejecucion viaje {self.viaje_id}"

    @property
    def salida_registrada(self):
        return bool(self.fecha_salida)

    @property
    def retorno_registrado(self):
        return bool(self.fecha_retorno)

    @property
    def etapa_ejecucion(self):
        if not self.fecha_salida:
            return "PROGRAMADO"
        if not self.fecha_retorno:
            return "EN_EJECUCION"
        return "FINALIZADO"
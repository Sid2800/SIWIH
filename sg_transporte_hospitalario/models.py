from django.db import models
from django.db.models import Q
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
        EN_PROCESO = "EN_PROCESO", "En proceso"
        FINALIZADA = "FINALIZADA", "Finalizada"
        CANCELADA = "CANCELADA", "Cancelada"

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
        return self.viaje_solicitudes.filter(activo=True).exists()

    @property
    def puede_editar(self):
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
    numero_viaje = models.CharField(max_length=30, unique=True, db_index=True)
    fecha_programacion = models.DateTimeField(default=timezone.now, db_index=True)
    motorista = models.ForeignKey(
        Motorista,
        on_delete=models.PROTECT,
        related_name="viajes",
    )
    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.PROTECT,
        related_name="viajes",
    )
    tipo_viaje = models.ForeignKey(
        TipoViaje,
        on_delete=models.PROTECT,
        related_name="viajes",
    )
    viatico = models.ForeignKey(
        Viatico,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="viajes",
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
        related_name="viaje_solicitudes",
    )
    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.PROTECT,
        related_name="viaje_solicitudes",
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
                fields=["viaje", "solicitud"],
                name="uq_th_viaje_solicitud",
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
    fecha_salida = models.DateTimeField(db_index=True)
    fecha_retorno = models.DateTimeField(db_index=True)
    kilometraje_salida = models.DecimalField(max_digits=10, decimal_places=2)
    kilometraje_retorno = models.DecimalField(max_digits=10, decimal_places=2)
    combustible_salida = models.DecimalField(max_digits=10, decimal_places=2)
    combustible_retorno = models.DecimalField(max_digits=10, decimal_places=2)
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
from django.db import models, transaction
from django.core.exceptions import ValidationError
from paciente.models import Paciente
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator

from datetime import datetime

# Modelo de Ubicación
class Localizacion(models.Model):
    descripcion_localizacion = models.CharField(max_length=100, unique=True, verbose_name="Localizacion")
    estado = models.BooleanField(default=True) 

    class Meta:
        verbose_name = "Localizacion"
        verbose_name_plural = "Localizaciones"
        ordering = ["descripcion_localizacion"]

    def __str__(self):
        return self.descripcion_localizacion



# Modelo de Expediente
class Expediente(models.Model):
    numero = models.PositiveIntegerField(
        verbose_name="Número de expediente",
        help_text="Número de expediente único (máximo 199999)",
        validators=[MaxValueValidator(199999)],
        unique=True
    )
    localizacion = models.ForeignKey(
        Localizacion,
        on_delete=models.PROTECT,
        default=1
    )
    estado = models.IntegerField(
        verbose_name="Estado",
        choices=[(1, "Asignado"), (2, "Libre")],
        default=2
    )
    fecha_creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='expedientes_creados')
    fecha_modificado = models.DateTimeField(auto_now=True)
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='expedientes_modificados')

    class Meta:
        verbose_name = "Expediente"
        verbose_name_plural = "Expedientes"
        ordering = ["numero"]

    def __str__(self):
        return str(self.numero)  




# Modelo de Paciente Asignación
class PacienteAsignacion(models.Model):
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.PROTECT
    )
    expediente = models.ForeignKey(
        Expediente,
        on_delete=models.PROTECT,
        related_name="expedienteAsignados"
    )
    estado = models.CharField(max_length=10, choices=[("1", "Actual"), ("0", "Historico")], default="1")
    fecha_asignacion = models.DateField(auto_now_add=True)
    fecha_liberacion = models.DateField(null=True, blank=True)

    def clean(self):
        super().clean()
        
        # Si el estado es 'Actual', valida que no haya otro registro 'Actual' para el mismo paciente
        if self.estado == '1':
            # Busca otras asignaciones 'Actuales' para el mismo paciente
            qs = PacienteAsignacion.objects.filter(
                paciente=self.paciente,
                estado='1'
            )
            
            # Si estamos editando un objeto existente, lo excluimos de la búsqueda
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            
            # Si se encuentra algún otro registro, lanza un error
            if qs.exists():
                raise ValidationError({
                    'estado': 'Este paciente ya tiene una asignación "Actual". Solo puede haber una asignación actual por paciente.'
                })

    def __str__(self):
        return f"{self.paciente.primer_nombre} f{self.paciente.primer_apellido} - Expediente {self.expediente.numero}"


# ============================================================
# CATÁLOGO UNIFICADO DE UBICACIONES (expediente_ubicacion)
# ============================================================
# Tabla relacional que unifica las posibles ubicaciones de un expediente,
# tanto CLÍNICAS como NO CLÍNICAS, capturando SOLO IDs (no texto).
#
# ¿Por qué existe?
# ----------------
# El catálogo viejo `Localizacion` guarda texto suelto (ARCHIVO, EMERGENCIA...)
# y no se vincula con las tablas reales de servicio. Esta tabla resuelve eso:
#
#   - Unidades CLÍNICAS  → FK a servicio.Unidad_clinica
#                          (que a su vez es polimórfica: area_atencion / sala /
#                           servicio_aux / establecimiento_ext)
#   - Unidades NO CLÍNICAS → FK a servicio.Unidad
#                          (ej: ESTADÍSTICA, ADMISIÓN, UAU)
#
# Igual que servicio_unidad_clinica, esta tabla es polimórfica: solo UNA de las
# dos FK está llena; la otra queda NULL. El campo `tipo` indica cuál:
#   tipo = 1 → CLÍNICA      (usar unidad_clinica)
#   tipo = 2 → NO CLÍNICA   (usar unidad_no_clinica)
#
# Beneficio: si se agrega una unidad nueva (clínica o no), basta crear una fila
# aquí y queda con un ID único, enlazada por relación (no por texto). Esto
# acelera búsquedas por índice y mantiene la integridad referencial.
#
# Convivencia: por ahora NO reemplaza a `Localizacion`. El módulo expediente
# sigue usando `Localizacion` para atenciones/ingresos. Esta tabla es para el
# módulo de Solicitud de Expedientes (préstamos hacia unidades específicas).
class ExpedienteUbicacion(models.Model):
    # Tipos como enteros (no texto) — relacional y compacto.
    TIPO_CLINICA = 1
    TIPO_NO_CLINICA = 2
    TIPO_CHOICES = [
        (TIPO_CLINICA, 'Clínica'),
        (TIPO_NO_CLINICA, 'No Clínica'),
    ]

    # FK a unidad clínica (servicio_unidad_clinica). NULL si es no-clínica.
    unidad_clinica = models.ForeignKey(
        'servicio.Unidad_clinica',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='ubicaciones_expediente',
        verbose_name='Unidad Clínica',
        help_text='FK a servicio_unidad_clinica. Solo si tipo=1 (Clínica).'
    )

    # FK a unidad no-clínica (servicio_unidad). NULL si es clínica.
    unidad_no_clinica = models.ForeignKey(
        'servicio.Unidad',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='ubicaciones_expediente',
        verbose_name='Unidad No Clínica',
        help_text='FK a servicio_unidad. Solo si tipo=2 (No Clínica).'
    )

    # Tipo: 1=Clínica, 2=No Clínica. Permite filtrar sin inspeccionar las FK.
    tipo = models.SmallIntegerField(
        choices=TIPO_CHOICES,
        verbose_name='Tipo de Ubicación',
        help_text='1=Clínica (usa unidad_clinica), 2=No Clínica (usa unidad_no_clinica)'
    )

    estado = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )

    class Meta:
        db_table = 'expediente_ubicacion'
        verbose_name = 'Ubicación de Expediente'
        verbose_name_plural = 'Ubicaciones de Expediente'
        ordering = ['tipo', 'id']
        constraints = [
            # Integridad a nivel BD: exactamente UNA de las dos FK debe estar
            # llena, coherente con el `tipo`. (CheckConstraint funciona en
            # MySQL 8.0.16+; en versiones viejas se ignora silenciosamente,
            # por eso ADEMÁS validamos en clean()).
            models.CheckConstraint(
                name='expubic_clinica_xor_noclinica',
                check=(
                    models.Q(tipo=1, unidad_clinica__isnull=False, unidad_no_clinica__isnull=True) |
                    models.Q(tipo=2, unidad_clinica__isnull=True, unidad_no_clinica__isnull=False)
                ),
            ),
        ]

    def clean(self):
        """
        Valida a nivel de aplicación:
          1. Exactamente una FK debe estar llena (clínica XOR no-clínica).
          2. No debe existir otra fila con la misma unidad (evita duplicados).
             Reemplaza al UniqueConstraint condicional que MySQL no soporta.
        """
        super().clean()
        tiene_clinica = self.unidad_clinica_id is not None
        tiene_noclinica = self.unidad_no_clinica_id is not None

        # Regla 1: exactamente una FK
        if tiene_clinica == tiene_noclinica:
            raise ValidationError(
                'Debe especificar exactamente una unidad: clínica O no clínica.'
            )

        # Sincronizar el tipo con la FK presente
        self.tipo = self.TIPO_CLINICA if tiene_clinica else self.TIPO_NO_CLINICA

        # Regla 2: unicidad de la unidad (no se puede registrar dos veces)
        if tiene_clinica:
            dup = ExpedienteUbicacion.objects.filter(unidad_clinica_id=self.unidad_clinica_id)
        else:
            dup = ExpedienteUbicacion.objects.filter(unidad_no_clinica_id=self.unidad_no_clinica_id)
        if self.pk:
            dup = dup.exclude(pk=self.pk)
        if dup.exists():
            raise ValidationError('Ya existe una ubicación registrada para esta unidad.')

    def save(self, *args, **kwargs):
        # Aseguramos que `tipo` siempre sea coherente con la FK presente,
        # incluso si se crea sin pasar por full_clean().
        if self.unidad_clinica_id is not None:
            self.tipo = self.TIPO_CLINICA
        elif self.unidad_no_clinica_id is not None:
            self.tipo = self.TIPO_NO_CLINICA
        super().save(*args, **kwargs)

    @property
    def es_clinica(self):
        return self.tipo == self.TIPO_CLINICA

    @property
    def descripcion(self):
        """
        Nombre legible de la ubicación, consultado EN VIVO (sin texto duplicado).
        - Clínica   → usa Unidad_clinica.get_descripcion()
        - No clínica → usa Unidad.nombre_unidad
        """
        if self.unidad_clinica_id and self.unidad_clinica:
            return self.unidad_clinica.get_descripcion()
        if self.unidad_no_clinica_id and self.unidad_no_clinica:
            return self.unidad_no_clinica.nombre_unidad
        return 'Sin ubicación'

    def __str__(self):
        etiqueta = 'CLÍNICA' if self.es_clinica else 'NO CLÍNICA'
        return f"[{etiqueta}] {self.descripcion}"

    


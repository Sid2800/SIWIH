"""
Modelos del módulo de EGRESOS (censo de egresos hospitalarios).

Contexto (lenguaje llano):
  Cada vez que un paciente sale del hospital, Estadística registra su egreso en
  un "censo" que hasta ahora se llevaba en un Excel con una hoja por área
  (Obstetricia, Pediatría, Medicina de Mujeres, Observación de Adultos, etc.).
  Este módulo digitaliza ese censo.

Decisiones de diseño (acordadas):
  1. UN solo modelo `Egreso` para todas las áreas. Las hojas tipo "censo" y las
     de "observación" (OA/OP) comparten la mayoría de campos; los que no aplican
     a un área quedan vacíos y el formulario muestra solo lo pertinente.
  2. Diagnósticos ILIMITADOS en una tabla aparte (`EgresoDiagnostico`), cada uno
     con su código CIE10 (reutilizado de la app `clinico`) y su descripción.
  3. La "lista" de expedientes que Estadística toma y Admisión devuelve se
     modela como un LOTE (`LoteEgreso` + `LoteEgresoDetalle`).

Principios que seguimos en todo el sistema:
  - Los movimientos/relaciones van por FK (id entero, indexado), no por texto.
  - Las fechas del egreso son SOLO fecha (sin horas), según las notas.
"""
from django.db import models
from django.conf import settings

from clinico.models import CIE10
from paciente.models import Paciente
from expediente.models import Expediente
from ingreso.models import Ingreso
from servicio.models import Servicio


# =============================================================================
# CATÁLOGOS
# =============================================================================
class AreaEgreso(models.Model):
    """
    Área del censo de egresos (una por hoja del Excel).

    El usuario la ELIGE al digitar con un combobox (puede diferir del área de
    ingreso). Sirve además para clasificar y filtrar los egresos.

    'tipo' distingue las dos plantillas:
      - CENSO       : formulario completo (diagnósticos con CIE10, sexo, peso,
                      operación, procedencia por depto/muni/localidad, etc.).
      - OBSERVACION : formulario reducido (OA/OP): procedencia en un solo campo,
                      diagnósticos de texto sin codificar, epicrisis, etc.
    """
    TIPO_CENSO = 'CENSO'
    TIPO_OBSERVACION = 'OBSERVACION'
    TIPOS = [
        (TIPO_CENSO, 'Censo'),
        (TIPO_OBSERVACION, 'Observación'),
    ]

    codigo = models.CharField(max_length=20, unique=True, verbose_name='Código')
    nombre = models.CharField(max_length=80, verbose_name='Nombre del área')
    tipo = models.CharField(max_length=12, choices=TIPOS, default=TIPO_CENSO)
    # Vínculo opcional al servicio correspondiente (las áreas especiales como
    # OA/OP/DENGUE pueden no tener un servicio directo).
    servicio = models.ForeignKey(
        Servicio, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='areas_egreso', verbose_name='Servicio relacionado'
    )
    activo = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0, verbose_name='Orden de despliegue')

    class Meta:
        db_table = 'egresos_area'
        verbose_name = 'Área de Egreso'
        verbose_name_plural = 'Áreas de Egreso'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class Procedimiento(models.Model):
    """
    Catálogo de procedimientos / operaciones (la "tabla aparte" acordada).

    En el censo, si el paciente fue operado, el usuario escribe SOLO el código y
    con él se clasifica la operación (ej. 7499 → Cesárea).
    """
    codigo = models.CharField(max_length=20, unique=True, verbose_name='Código')
    descripcion = models.CharField(max_length=200, verbose_name='Descripción')
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'egresos_procedimiento'
        verbose_name = 'Procedimiento'
        verbose_name_plural = 'Procedimientos'
        ordering = ['descripcion']

    def __str__(self):
        return f'{self.codigo} - {self.descripcion}'


# =============================================================================
# LOTE (captura de expedientes por Estadística → devolución por Admisión)
# =============================================================================
class LoteEgreso(models.Model):
    """
    Lista de expedientes que Estadística toma prestados para llenar egresos.

    Flujo:
      1. Estadística captura varios expedientes (que están disponibles) en un
         lote, con su fecha. Los expedientes quedan ubicados "en Estadística".
      2. Cuando terminan, se devuelven a Admisión NO uno por uno, sino por lote:
         Admisión revisa la lista completa y marca los pendientes hasta que se
         devuelven todos; ahí el lote se cierra y queda su fecha de captura por
         Admisión.
    """
    ABIERTO = 'ABIERTO'          # Estadística lo tiene, aún digitando/devolviendo
    CERRADO = 'CERRADO'          # todos devueltos y revisados por Admisión
    ESTADOS = [
        (ABIERTO, 'Abierto'),
        (CERRADO, 'Cerrado'),
    ]

    estado = models.CharField(max_length=10, choices=ESTADOS, default=ABIERTO)

    # Captura por Estadística (quién y cuándo tomó los expedientes).
    usuario_estadistica = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='lotes_egreso_capturados', verbose_name='Capturó (Estadística)'
    )
    fecha_captura_estadistica = models.DateTimeField(auto_now_add=True)

    # Cierre por Admisión (al recibir toda la lista de vuelta).
    usuario_admision = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='lotes_egreso_recibidos', verbose_name='Recibió (Admisión)'
    )
    fecha_captura_admision = models.DateTimeField(null=True, blank=True)

    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'egresos_lote'
        verbose_name = 'Lote de Egresos'
        verbose_name_plural = 'Lotes de Egresos'
        ordering = ['-fecha_captura_estadistica']

    def __str__(self):
        return f'Lote #{self.id} ({self.get_estado_display()})'


class LoteEgresoDetalle(models.Model):
    """
    Un expediente dentro de un lote. Es la unidad que Admisión marca al devolver.
    """
    PRESTADO = 'PRESTADO'    # está en Estadística
    DEVUELTO = 'DEVUELTO'    # ya volvió a Admisión y se verificó
    ESTADOS = [
        (PRESTADO, 'Prestado a Estadística'),
        (DEVUELTO, 'Devuelto'),
    ]

    lote = models.ForeignKey(
        LoteEgreso, on_delete=models.CASCADE, related_name='detalles'
    )
    expediente = models.ForeignKey(
        Expediente, on_delete=models.PROTECT, related_name='lotes_egreso_detalle'
    )
    # Paciente vinculado al momento de la captura (para mostrar sin depender de
    # la asignación actual, que puede cambiar).
    paciente = models.ForeignKey(
        Paciente, on_delete=models.PROTECT, null=True, blank=True,
        related_name='lotes_egreso_detalle'
    )
    estado = models.CharField(max_length=10, choices=ESTADOS, default=PRESTADO)
    fecha_devolucion = models.DateTimeField(null=True, blank=True)
    comentario = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'egresos_lote_detalle'
        verbose_name = 'Detalle de Lote de Egresos'
        verbose_name_plural = 'Detalles de Lote de Egresos'
        unique_together = ('lote', 'expediente')

    def __str__(self):
        return f'Lote #{self.lote_id} → Exp {self.expediente_id}'


# =============================================================================
# EGRESO (el registro del censo)
# =============================================================================
class Egreso(models.Model):
    """
    Un egreso hospitalario en el censo.

    Se apoya en el INGRESO (para traer paciente, fecha de ingreso y contexto) y
    en el EXPEDIENTE físico que Estadística tomó. Los datos generales del
    paciente (nombre, identidad, departamento/municipio/localidad) se leen en
    vivo desde 'paciente'; aquí solo se guarda lo que es propio del egreso o lo
    que es punto-en-el-tiempo (edad, procedencia de observación).
    """
    SEXO_HOMBRE = 'H'
    SEXO_MUJER = 'M'
    SEXOS = [(SEXO_HOMBRE, 'Hombre'), (SEXO_MUJER, 'Mujer')]

    COND_VIVO = 'V'
    COND_MUERTO = 'M'
    CONDICIONES = [(COND_VIVO, 'Vivo'), (COND_MUERTO, 'Muerto')]

    # Referencia: en el Excel "Trae referencia" y "Referido a" son excluyentes.
    REF_TRAE = 'TRAE'
    REF_REFERIDO = 'REFERIDO'
    TIPOS_REFERENCIA = [
        (REF_TRAE, 'Trae referencia'),
        (REF_REFERIDO, 'Referido a'),
    ]

    # ---- Vínculos ----
    area = models.ForeignKey(
        AreaEgreso, on_delete=models.PROTECT, related_name='egresos',
        verbose_name='Área del censo (elegida al digitar)'
    )
    ingreso = models.ForeignKey(
        Ingreso, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='egresos', verbose_name='Ingreso de origen'
    )
    paciente = models.ForeignKey(
        Paciente, on_delete=models.PROTECT, null=True, blank=True,
        related_name='egresos', verbose_name='Paciente'
    )
    expediente = models.ForeignKey(
        Expediente, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='egresos', verbose_name='Expediente'
    )

    # ---- Encabezado del renglón (como en el Excel) ----
    numero = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='N.º (correlativo del día en el registro de Estadística)'
    )
    pagina = models.CharField(
        max_length=20, blank=True, null=True,
        verbose_name='Página del libro de Estadística (manual)'
    )
    # SOLO fecha (sin horas), según las notas.
    fecha_egreso = models.DateField(verbose_name='Fecha de egreso')
    fecha_ingreso = models.DateField(
        null=True, blank=True, verbose_name='Fecha de ingreso'
    )

    # ---- Datos del paciente (punto-en-el-tiempo / propios del censo) ----
    edad = models.PositiveIntegerField(null=True, blank=True, verbose_name='Edad')
    # Observación (OA/OP) usa UNA procedencia; el censo usa depto/muni/localidad
    # del paciente (se leen en vivo desde 'paciente').
    procedencia = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name='Procedencia (áreas de observación)'
    )

    # ---- Datos clínicos del censo ----
    sexo = models.CharField(max_length=1, choices=SEXOS, blank=True, null=True)
    condicion = models.CharField(
        max_length=1, choices=CONDICIONES, blank=True, null=True,
        verbose_name='Condición al egreso (Vivo/Muerto)'
    )
    peso_gramos = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Peso (gramos)'
    )
    # Solo si fue operado; el usuario escribe el código y se clasifica.
    operacion = models.ForeignKey(
        Procedimiento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='egresos', verbose_name='Operación (procedimiento)'
    )

    # ---- Referencia (uno u otro, no ambos) ----
    tipo_referencia = models.CharField(
        max_length=10, choices=TIPOS_REFERENCIA, blank=True, null=True
    )
    # Destino/origen de la referencia. Por ahora texto; a futuro se enlazará al
    # módulo de Referencias con un combobox de búsqueda (acordado).
    referencia_texto = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name='Institución de la referencia'
    )

    # ---- Solo áreas de observación (OA/OP) ----
    epicrisis = models.BooleanField(
        null=True, blank=True, verbose_name='¿Tiene epicrisis? (Sí/No)'
    )
    deberia_ir_sala = models.BooleanField(
        null=True, blank=True, verbose_name='¿Debería ir a sala? (Sí/No)'
    )

    # ---- Estado del censo ----
    en_censo = models.BooleanField(
        default=False,
        verbose_name='Incluido en el censo'
    )
    # Nota de las especificaciones: "incluido en censo pero no ha egresado".
    comentario = models.TextField(blank=True, null=True, verbose_name='Comentario')

    # ---- Auditoría ----
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='egresos_creados', null=True, blank=True
    )
    fecha_creado = models.DateTimeField(auto_now_add=True)
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='egresos_modificados', null=True, blank=True
    )
    fecha_modificado = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'egresos_egreso'
        verbose_name = 'Egreso'
        verbose_name_plural = 'Egresos'
        ordering = ['-fecha_egreso', 'numero']

    def __str__(self):
        return f'Egreso #{self.id} — {self.fecha_egreso}'

    @property
    def dias_estancia(self):
        """
        Días de estancia: se calculan automáticamente entre ingreso y egreso.

        Es una propiedad (no un campo) para que nunca quede desactualizada si se
        editan las fechas. Devuelve None si falta alguna fecha.
        """
        if self.fecha_ingreso and self.fecha_egreso:
            return (self.fecha_egreso - self.fecha_ingreso).days
        return None


class EgresoDiagnostico(models.Model):
    """
    Diagnóstico de un egreso. Un egreso tiene VARIOS (sin límite de 4).

    'tipo' distingue el diagnóstico de ingreso de los del egreso:
      - INGRESO : el diagnóstico con que ingresó (una fila).
      - EGRESO  : los diagnósticos de egreso (Diagnóstico 1..N del Excel).

    En áreas de censo se usa el código CIE10 (FK a clinico.CIE10) + descripción.
    En observación (OA/OP) el diagnóstico es texto manual sin codificar (cie10
    queda vacío); a futuro se le podrá asignar código.
    """
    TIPO_INGRESO = 'INGRESO'
    TIPO_EGRESO = 'EGRESO'
    TIPOS = [
        (TIPO_INGRESO, 'Diagnóstico de ingreso'),
        (TIPO_EGRESO, 'Diagnóstico de egreso'),
    ]

    egreso = models.ForeignKey(
        Egreso, on_delete=models.CASCADE, related_name='diagnosticos'
    )
    tipo = models.CharField(max_length=8, choices=TIPOS, default=TIPO_EGRESO)
    # Orden de aparición (Diagnóstico 1, 2, 3, ...).
    orden = models.PositiveSmallIntegerField(default=1)
    cie10 = models.ForeignKey(
        CIE10, on_delete=models.PROTECT, null=True, blank=True,
        related_name='egreso_diagnosticos', verbose_name='Código CIE10'
    )
    # Descripción del diagnóstico. En censo suele venir del CIE10; en observación
    # se escribe a mano.
    descripcion = models.CharField(max_length=300, blank=True, null=True)

    class Meta:
        db_table = 'egresos_diagnostico'
        verbose_name = 'Diagnóstico de Egreso'
        verbose_name_plural = 'Diagnósticos de Egreso'
        ordering = ['egreso', 'tipo', 'orden']

    def __str__(self):
        cod = self.cie10.codigo if self.cie10 else '(sin código)'
        return f'{self.get_tipo_display()} — {cod}'

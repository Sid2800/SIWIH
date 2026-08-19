"""
Modelos del módulo de ENCUESTAS de satisfacción (Unidad de Atención al Usuario).

Contexto (lenguaje llano):
  La UAU levanta 4 encuestas de satisfacción: Consulta Externa, Hospitalización,
  Emergencia y Usuario Externo. Hasta ahora se llenaban en Formularios de Google
  y se exportaban a Excel, y un script (procesarencuestas.py) las calificaba por
  puntos y generaba reportes/consolidados. Este módulo digitaliza ese ingreso y
  reproduce la calificación dentro del sistema.

Decisiones de diseño:
  1. UNA sola tabla `Encuesta` para las 4 encuestas (se distinguen por `servicio`).
     Las preguntas/opciones y su puntaje viven como definición (encuestas.catalogos),
     no como catálogo en BD, porque son formatos fijos del formulario.
  2. Las respuestas van en `EncuestaRespuesta` (una fila por pregunta), guardando
     el puntaje calculado y si la pregunta cuenta para el consolidado (solo las
     preguntas numeradas de CE/Hospitalización/Emergencia).
  3. El "encuestador" NO se pide: es el usuario de SIWIH que ingresa la encuesta
     (`creado_por`). Cada usuario solo ve sus encuestas; el personal `is_staff`
     (p. ej. supervisión de UAU) las ve todas.
"""
from django.db import models
from django.conf import settings


class Encuesta(models.Model):
    """Una encuesta de satisfacción levantada por la UAU."""
    CE = 'CE'            # Consulta Externa
    HOSP = 'HOSP'        # Hospitalización
    EMER = 'EMER'        # Emergencia
    EXT = 'EXT'          # Usuario Externo (no entra al consolidado)
    SERVICIOS = [
        (CE, 'Consulta Externa'),
        (HOSP, 'Hospitalización'),
        (EMER, 'Emergencia'),
        (EXT, 'Usuario Externo'),
    ]

    PACIENTE = 'Paciente'
    FAMILIAR = 'Familiar'
    TIPOS_ENCUESTADO = [(PACIENTE, 'Paciente'), (FAMILIAR, 'Familiar')]

    servicio = models.CharField(max_length=6, choices=SERVICIOS, db_index=True)
    # Subservicio/sala (depende del servicio). En Emergencia suele ser único.
    subservicio = models.CharField(max_length=60, blank=True, null=True)

    fecha = models.DateField(db_index=True, verbose_name='Fecha de la encuesta')
    tipo_encuestado = models.CharField(
        max_length=10, choices=TIPOS_ENCUESTADO, blank=True, null=True
    )
    identidad = models.CharField(max_length=50, blank=True, null=True)
    comentario = models.TextField(blank=True, null=True)

    # Resultado (instantánea para reportes rápidos; se recalcula al guardar).
    porcentaje_satisfaccion = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    # Auditoría. `creado_por` es el ENCUESTADOR (usuario de SIWIH).
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='encuestas_creadas', verbose_name='Encuestador'
    )
    fecha_creado = models.DateTimeField(auto_now_add=True)
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='encuestas_modificadas'
    )
    fecha_modificado = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'encuestas_encuesta'
        verbose_name = 'Encuesta'
        verbose_name_plural = 'Encuestas'
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'Encuesta #{self.id} — {self.get_servicio_display()} ({self.fecha})'


class EncuestaRespuesta(models.Model):
    """
    Respuesta a una pregunta de la encuesta. Una fila por pregunta contestada.

    `puntaje` guarda el valor calculado (100/85/70/55 u otro) según el catálogo;
    `cuenta_consolidado` marca las preguntas numeradas que entran al cálculo de
    satisfacción del consolidado (las abiertas/de texto/de letra no cuentan).
    """
    encuesta = models.ForeignKey(
        Encuesta, on_delete=models.CASCADE, related_name='respuestas'
    )
    # Código del campo en el formato (ej. 'p1', '1a', 'p0', 'tipo').
    codigo = models.CharField(max_length=20)
    # Número de la pregunta (para las numeradas); null en las de texto/letra.
    numero = models.PositiveSmallIntegerField(null=True, blank=True)
    # Instantánea del enunciado, para reportes independientes del catálogo.
    texto_pregunta = models.CharField(max_length=300, blank=True, null=True)
    respuesta = models.CharField(max_length=200, blank=True, null=True)
    puntaje = models.PositiveSmallIntegerField(null=True, blank=True)
    cuenta_consolidado = models.BooleanField(default=False)

    class Meta:
        db_table = 'encuestas_respuesta'
        verbose_name = 'Respuesta de Encuesta'
        verbose_name_plural = 'Respuestas de Encuesta'
        ordering = ['encuesta', 'numero', 'codigo']

    def __str__(self):
        return f'Enc #{self.encuesta_id} — {self.codigo}: {self.respuesta}'

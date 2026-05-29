"""
Signals del módulo expediente.
=============================================================================

Mantienen sincronizado el catálogo unificado `expediente_ubicacion` con las
tablas origen de servicio:

  - servicio.Unidad_clinica  (unidades CLÍNICAS)
  - servicio.Unidad          (unidades NO CLÍNICAS)

Cuando se CREA una unidad nueva (o se reactiva una existente), se crea
automáticamente su fila correspondiente en ExpedienteUbicacion, tomando su
ID. Así, al agregar áreas nuevas en el sistema, el catálogo de ubicaciones
queda actualizado sin intervención manual.

Idempotente: usa get_or_create, por lo que nunca duplica filas.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='servicio.Unidad_clinica')
def sincronizar_ubicacion_clinica(sender, instance, created, **kwargs):
    """
    Al guardar una Unidad_clinica activa, asegura su fila en
    expediente_ubicacion (tipo=1, Clínica).

    Se ejecuta tanto en creación como en actualización: si la unidad pasó
    a estado activo y aún no tenía ubicación, la crea.
    """
    from expediente.models import ExpedienteUbicacion

    # Solo unidades activas (estado=1). Si está inactiva, no la registramos.
    if getattr(instance, 'estado', None) != 1:
        return

    ExpedienteUbicacion.objects.get_or_create(
        unidad_clinica=instance,
        defaults={'tipo': ExpedienteUbicacion.TIPO_CLINICA},
    )


@receiver(post_save, sender='servicio.Unidad')
def sincronizar_ubicacion_no_clinica(sender, instance, created, **kwargs):
    """
    Al guardar una Unidad (no clínica) activa, asegura su fila en
    expediente_ubicacion (tipo=2, No Clínica).
    """
    from expediente.models import ExpedienteUbicacion

    if getattr(instance, 'estado', None) != 1:
        return

    ExpedienteUbicacion.objects.get_or_create(
        unidad_no_clinica=instance,
        defaults={'tipo': ExpedienteUbicacion.TIPO_NO_CLINICA},
    )

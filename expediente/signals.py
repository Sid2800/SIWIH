"""
Signals del módulo expediente.
=============================================================================

Mantienen sincronizado el catálogo unificado `expediente_ubicacion` con las
tablas origen de servicio:

  - servicio.Unidad_clinica  (unidades CLÍNICAS)
  - servicio.Unidad          (unidades NO CLÍNICAS)

Sincroniza en AMBOS sentidos (alta y baja), por ID:

  - Unidad ACTIVA (estado=1)   → asegura su fila en expediente_ubicacion y la
                                 deja ACTIVA (la crea si falta, la reactiva si
                                 estaba desactivada).
  - Unidad INACTIVA (estado≠1) → DESACTIVA su fila (estado=False) si existe.
    No se borra físicamente porque la FK es PROTECT (puede estar referenciada
    por préstamos/expedientes); desactivar conserva la integridad y el id.

Nota sobre borrado físico: una Unidad con ubicación NO se puede eliminar en
duro (FK PROTECT). El "quitar" real del sistema es la desactivación (estado=0),
que sí se refleja aquí. Idempotente: nunca duplica filas.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


def _sincronizar_ubicacion(filtro, tipo, instance):
    """
    Lógica común: refleja el estado (activo/inactivo) de una unidad de servicio
    en su fila de expediente_ubicacion, identificada por la FK (`filtro`).

    Args:
        filtro: dict con la FK, p.ej. {'unidad_clinica': instance}.
        tipo:   ExpedienteUbicacion.TIPO_CLINICA o TIPO_NO_CLINICA.
        instance: la unidad guardada (se lee su .estado).
    """
    from expediente.models import ExpedienteUbicacion

    activa = getattr(instance, 'estado', None) == 1

    if activa:
        # Crear si falta; reactivar si existía desactivada.
        obj, created = ExpedienteUbicacion.objects.get_or_create(
            defaults={'tipo': tipo, 'estado': True}, **filtro
        )
        if not created and not obj.estado:
            obj.estado = True
            obj.save(update_fields=['estado'])
    else:
        # Unidad dada de baja: desactivar su ubicación (sin borrar, por PROTECT).
        ExpedienteUbicacion.objects.filter(estado=True, **filtro).update(estado=False)


@receiver(post_save, sender='servicio.Unidad_clinica')
def sincronizar_ubicacion_clinica(sender, instance, created, **kwargs):
    """Sincroniza la ubicación CLÍNICA (tipo=1) con el estado de la Unidad_clinica."""
    from expediente.models import ExpedienteUbicacion
    _sincronizar_ubicacion({'unidad_clinica': instance},
                           ExpedienteUbicacion.TIPO_CLINICA, instance)


@receiver(post_save, sender='servicio.Unidad')
def sincronizar_ubicacion_no_clinica(sender, instance, created, **kwargs):
    """Sincroniza la ubicación NO CLÍNICA (tipo=2) con el estado de la Unidad."""
    from expediente.models import ExpedienteUbicacion
    _sincronizar_ubicacion({'unidad_no_clinica': instance},
                           ExpedienteUbicacion.TIPO_NO_CLINICA, instance)

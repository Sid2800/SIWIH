"""
Servicio de acceso al catálogo unificado de ubicaciones (ExpedienteUbicacion).
=============================================================================

Encapsula la lectura y resolución de ubicaciones de expedientes, sean
CLÍNICAS (servicio.Unidad_clinica) o NO CLÍNICAS (servicio.Unidad).

Igual que el resto del refactor: NO se duplica texto, todo se consulta en vivo
desde las FK. Estas clases son el ÚNICO punto de acceso recomendado para que
otros módulos (s_exp, etc.) lean/escriban ubicaciones.

Convenciones:
- Métodos estáticos (clases-namespace).
- Cada método documenta el origen del dato.
- Se devuelve cadena vacía en lugar de None para evitar errores en templates.
"""
from typing import Optional


class DatosUbicacion:
    """
    Acceso a los datos de una fila de ExpedienteUbicacion.

    Resuelve el nombre legible y el tipo (clínica / no clínica) consultando
    en vivo la unidad relacionada.
    """

    @staticmethod
    def descripcion(ubicacion) -> str:
        """
        Nombre legible de la ubicación.
          - Clínica    → Unidad_clinica.get_descripcion()
          - No clínica → Unidad.nombre_unidad
        """
        if ubicacion is None:
            return ''
        return ubicacion.descripcion  # property del modelo (ya resuelve en vivo)

    @staticmethod
    def tipo_codigo(ubicacion) -> Optional[int]:
        """Devuelve 1 (clínica) o 2 (no clínica)."""
        return ubicacion.tipo if ubicacion else None

    @staticmethod
    def tipo_legible(ubicacion) -> str:
        """Devuelve 'Clínica' o 'No Clínica'."""
        if ubicacion is None:
            return ''
        return ubicacion.get_tipo_display()

    @staticmethod
    def enriquecer(ubicacion) -> dict:
        """
        Dict con los datos de la ubicación, listo para respuestas JSON.
        {
            "id":          int,
            "descripcion": str,
            "tipo":        int,   # 1=clínica, 2=no clínica
            "tipo_nombre": str,
        }
        """
        if ubicacion is None:
            return {"id": None, "descripcion": "", "tipo": None, "tipo_nombre": ""}
        return {
            "id": ubicacion.id,
            "descripcion": DatosUbicacion.descripcion(ubicacion),
            "tipo": ubicacion.tipo,
            "tipo_nombre": ubicacion.get_tipo_display(),
        }


class CatalogoUbicaciones:
    """
    Operaciones sobre el catálogo completo de ubicaciones.
    Útil para poblar selects/dropdowns en el frontend.
    """

    @staticmethod
    def listar(solo_activas: bool = True, tipo: Optional[int] = None):
        """
        Devuelve un QuerySet de ExpedienteUbicacion con las relaciones
        precargadas (select_related) para evitar N+1.

        Args:
            solo_activas: si True, filtra estado=True.
            tipo: 1=clínicas, 2=no clínicas, None=todas.
        """
        from expediente.models import ExpedienteUbicacion

        qs = ExpedienteUbicacion.objects.select_related(
            'unidad_clinica__area_atencion__servicio',
            'unidad_clinica__sala',
            'unidad_clinica__servicio_aux',
            'unidad_clinica__establecimiento_ext',
            'unidad_no_clinica',
        )
        if solo_activas:
            qs = qs.filter(estado=True)
        if tipo is not None:
            qs = qs.filter(tipo=tipo)
        return qs


    @staticmethod
    def listar_dict(solo_activas: bool = True, tipo: Optional[int] = None) -> list:
        """Igual que listar() pero devuelve lista de dicts (para JSON/selects)."""
        return [DatosUbicacion.enriquecer(u) for u in CatalogoUbicaciones.listar(solo_activas, tipo)]


    @staticmethod
    def obtener_o_crear_por_unidad_clinica(unidad_clinica):
        """
        Devuelve la fila de ExpedienteUbicacion para una Unidad_clinica;
        la crea si no existe. Útil al registrar ubicaciones bajo demanda.
        """
        from expediente.models import ExpedienteUbicacion
        obj, _ = ExpedienteUbicacion.objects.get_or_create(
            unidad_clinica=unidad_clinica,
            defaults={'tipo': ExpedienteUbicacion.TIPO_CLINICA},
        )
        return obj


    @staticmethod
    def obtener_o_crear_por_unidad_no_clinica(unidad):
        """
        Devuelve la fila de ExpedienteUbicacion para una Unidad (no clínica);
        la crea si no existe.
        """
        from expediente.models import ExpedienteUbicacion
        obj, _ = ExpedienteUbicacion.objects.get_or_create(
            unidad_no_clinica=unidad,
            defaults={'tipo': ExpedienteUbicacion.TIPO_NO_CLINICA},
        )
        return obj


    @staticmethod
    def ubicacion_del_solicitante(solicitud):
        """
        Resuelve la ubicación destino de un préstamo según el SOLICITANTE (Opción A).

        El expediente se mueve a la unidad de servicio del usuario que pidió el
        préstamo. Esa unidad es NO CLÍNICA (servicio.Unidad), capturada en
        SolicitudPrestamo.servicio_unidad al crear la solicitud.

        Devuelve la fila ExpedienteUbicacion correspondiente (la crea si falta),
        o None si la solicitud no tiene servicio_unidad asociada.
        """
        unidad = getattr(solicitud, 'servicio_unidad', None)
        if not unidad:
            return None
        return CatalogoUbicaciones.obtener_o_crear_por_unidad_no_clinica(unidad)



    @staticmethod
    def ubicacion_admision():
        """
        Devuelve la ubicación 'ADMISION' (donde regresan los expedientes al
        devolverse). ADMISION es una Unidad no-clínica en servicio_unidad.

        Si no existe la unidad ADMISION, devuelve None (el llamador decide
        el fallback). No la inventa para no crear datos basura.
        """
        from servicio.models import Unidad
        unidad = Unidad.objects.filter(
            nombre_unidad__iexact='ADMISION', estado=1
        ).first()
        if not unidad:
            # intento alterno por si está con tilde u otra grafía
            unidad = Unidad.objects.filter(
                nombre_unidad__icontains='ADMIS', estado=1
            ).first()
        if not unidad:
            return None
        return CatalogoUbicaciones.obtener_o_crear_por_unidad_no_clinica(unidad)

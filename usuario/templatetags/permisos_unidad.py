from django import template
from usuario.models import PerfilUnidad
from core.services.usuario_service import UsuarioService
from core.constants import permisos
register = template.Library()

@register.filter
def tiene_rol(user, valores):
    """
    Recibe un valor o una lista de valores separados por coma.
    Cada valor debe tener formato "ROL:UNIDAD".
    Devuelve True si el usuario tiene alguno de ellos.
    
    Ejemplos:
        "auditor:DIRECTIVOS"
        "ADMIN:Admision,digitador:Admision,auditor:DIRECTIVOS"
    """
    gbal = False

    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True
    
    if UsuarioService.es_global(user):
        gbal = True

    # Aseguramos que sea lista
    if isinstance(valores, str):
        valores = valores.split(',')

    for valor in valores:
        try:
            rol, unidad = valor.split(':', 1)
            if gbal:
                if PerfilUnidad.objects.filter(usuario=user, rol=rol, ).exists():
                    return True
            else:
                if PerfilUnidad.objects.filter(usuario=user, rol=rol, servicio_unidad__nombre_corto_unidad=unidad).exists():
                    return True
        except ValueError:
            continue

    return False
    


@register.filter
def tiene_unidad(user, unidades_str):
    """
    Uso:
        user|tiene_unidad:"imagenologia"
        user|tiene_unidad:"imagenologia:Referencia:DIRECTIVOS"
    Evalúa si el usuario pertenece a cualquiera de esas unidades.
    """

    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True
    
    if UsuarioService.es_global(user):
        return True

    # Separar unidades por ':'
    unidades = unidades_str.split(':')

    for unidad in unidades:
        unidad = unidad.strip()
        if not unidad:
            continue

        if PerfilUnidad.objects.filter(
            usuario=user,
            servicio_unidad__nombre_corto_unidad=unidad
        ).exists():
            return True

    return False


@register.filter
def es_no_clinico(user):
    """
    True si el usuario pertenece a una unidad NO CLÍNICA (personal
    administrativo: Estadística, Admisión, UAU, Archivo, etc.).

    ORIGEN DEL DATO (fuente de verdad, sin nombres escritos a mano):
        auth_user
          -> rrhh_empleado (usuario_id)
            -> rrhh_personalnoclinico (empleado_id) con servicio_unidad
    Si el empleado está en PersonalNoClinico con unidad asignada, es no clínico.
    El personal de salud (rrhh_personalsalud) NO cumple, por lo que no ve el
    acceso a "Préstamos de Expedientes".

    Uso en plantilla:
        {% if request.user|es_no_clinico %} ... {% endif %}

    Reemplaza al patrón frágil:
        {% if request.user|tiene_unidad:"Estadistica:Sala:Admision:UAU" %}
    que obligaba a enumerar cada unidad nueva. Ahora cualquier unidad no
    clínica que exista en RRHH obtiene acceso automáticamente.

    Superusuarios siempre True (para administración).

    RENDIMIENTO: dos consultas indexadas por id (empleado y personalnoclinico),
    sin joins pesados; se evalúa una vez al renderizar el menú.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        from rrhh.models import Empleado, PersonalNoClinico
        empleado = Empleado.objects.filter(usuario_id=user.id).only('id').first()
        if not empleado:
            return False
        return PersonalNoClinico.objects.filter(
            empleado_id=empleado.id,
            servicio_unidad_id__isnull=False
        ).exists()
    except Exception:
        return False


@register.filter
def en_grupo(user, grupos_str):
    """
    Verifica si el usuario pertenece a alguno de los grupos indicados.
    Uso:
        user|en_grupo:"Solicitantes"
        user|en_grupo:"Solicitantes:Exp_Administradores"
    Superusuarios y staff siempre retornan True.
    """
    if not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    grupos = [g.strip() for g in grupos_str.split(':') if g.strip()]
    return user.groups.filter(name__in=grupos).exists()


@register.filter
def tiene_rol_global(user, roles_str):
    """
    Verifica si el usuario tiene alguno de los roles indicados en CUALQUIER unidad.
    Uso:
        user|tiene_rol_global:"exp_solicitante"
        user|tiene_rol_global:"exp_solicitante:admin"
    Superusuarios y staff siempre retornan True.
    """
    if not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    roles = [r.strip() for r in roles_str.split(':') if r.strip()]
    return PerfilUnidad.objects.filter(usuario=user, rol__in=roles).exists()


from django.conf import settings


@register.filter
def tiene_unidades_config(user, nombre_constante):
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    if UsuarioService.es_global(user):
        return True

    unidades = getattr(permisos, nombre_constante, None)

    if not unidades:
        return False

    return PerfilUnidad.objects.filter(
        usuario=user,
        servicio_unidad__nombre_corto_unidad__in=unidades
    ).exists()
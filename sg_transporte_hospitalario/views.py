import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.generic import ListView, TemplateView

from core.services.usuario_service import UsuarioService
from core.utils.utilidades_mensajes import mostrar_mensaje
from ingreso.models import Ingreso
from paciente.models import Paciente
from rrhh.models import Empleado

from .forms import SolicitudCreateForm, SolicitudForm
from .models import Solicitud, SolicitudPaciente, SolicitudPersonal, TipoSolicitud


def puede_ver_modulo(usuario):
    return bool(
        usuario
        and (
            usuario.is_superuser
            or UsuarioService.es_directivo(usuario)
            or UsuarioService.es_admin_global(usuario)
        )
    )


def puede_gestionar_modulo(usuario):
    return bool(usuario and (usuario.is_superuser or UsuarioService.es_admin_global(usuario)))


def construir_contexto_dashboard(usuario):
    return {
        "titulo": "SG-transporte_hospitalario",
        "subtitulo": "Módulo de gestión de transporte hospitalario.",
        "fecha_actual": timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M"),
        "puede_ver": puede_ver_modulo(usuario),
        "puede_escribir": puede_gestionar_modulo(usuario),
    }


TAB_SECTIONS = [
    {"key": "inicio", "label": "Inicio", "icon": "bi-house-door"},
    {"key": "solicitud", "label": "Solicitud", "icon": "bi-journal-text"},
    {"key": "autorizacion", "label": "Autorización", "icon": "bi-check2-circle"},
    {"key": "ejecucion", "label": "Ejecución", "icon": "bi-truck"},
    {"key": "resumen", "label": "Resumen", "icon": "bi-card-list"},
    {"key": "historial", "label": "Historial", "icon": "bi-clock-history"},
]


def _area_solicitante_desde_punto(punto):
    if not punto:
        return "-"
    if punto.unidad_clinica:
        return str(punto.unidad_clinica)
    if punto.unidad:
        return punto.unidad.nombre_unidad
    return "-"


def _generar_numero_solicitud():
    ultimo = Solicitud.objects.order_by("-id").values_list("id", flat=True).first() or 0
    return f"SOL-{ultimo + 1:06d}"


def _proceso_solicitud_label(estado):
    etiquetas = {
        Solicitud.Estado.PENDIENTE: "PENDIENTE",
        Solicitud.Estado.EN_PROCESO: "EN_PROCESO",
        Solicitud.Estado.FINALIZADA: "FINALIZADA",
        Solicitud.Estado.CANCELADA: "CANCELADA",
    }
    return etiquetas.get(estado, estado or "-")


def _obtener_qs_solicitudes_activas(usuario):
    qs = (
        Solicitud.objects
        .filter(activo=True)
        .select_related(
            "solicitante_empleado",
            "solicitante_empleado__personal_salud_empleado__servicio_unidad",
            "solicitante_empleado__personal_no_clinico__servicio_unidad",
            "punto_solicitud__unidad",
            "punto_solicitud__unidad_clinica",
            "punto_solicitud__unidad_clinica__area_atencion__servicio",
            "punto_solicitud__unidad_clinica__sala__servicio",
            "punto_solicitud__unidad_clinica__servicio_aux",
            "punto_solicitud__unidad_clinica__establecimiento_ext__nivel_complejidad_institucional",
            "punto_solicitud__unidad_clinica__establecimiento_ext__region_salud",
            "tipo_solicitud",
            "prioridad",
            "lugar_salida__nivel_complejidad_institucional",
            "lugar_salida__region_salud",
            "lugar_destino__nivel_complejidad_institucional",
            "lugar_destino__region_salud",
        )
        .prefetch_related(
            Prefetch(
                "solicitud_pacientes",
                queryset=SolicitudPaciente.objects.select_related("paciente", "ingreso__sala"),
            ),
            Prefetch(
                "solicitud_personal",
                queryset=SolicitudPersonal.objects.select_related(
                    "empleado",
                    "empleado__personal_salud_empleado__tipo_personal_salud",
                    "empleado__personal_no_clinico",
                ),
            ),
        )
        .order_by("-fecha_solicitud")
    )

    if usuario.is_superuser or UsuarioService.es_admin_global(usuario) or UsuarioService.es_directivo(usuario):
        return qs

    empleado_id = getattr(getattr(usuario, "empleado", None), "id", None)
    if not empleado_id:
        return qs.none()

    return qs.filter(solicitante_empleado_id=empleado_id)


def _parse_payload_json(valor):
    if not valor:
        return []
    try:
        data = json.loads(valor)
        return data if isinstance(data, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _nombre_empleado(empleado):
    if not empleado:
        return "-"
    return " ".join(x for x in [empleado.primer_nombre, empleado.primer_apellido] if x) or "-"


def _cargo_empleado(empleado):
    if not empleado:
        return "Personal"
    try:
        return empleado.personal_salud_empleado.tipo_personal_salud.descripcion_tipo_personal_salud
    except Exception:
        try:
            return empleado.personal_no_clinico.get_tipo_display()
        except Exception:
            return "Personal"


def _unidad_empleado(empleado):
    if not empleado:
        return None
    try:
        return empleado.personal_salud_empleado.servicio_unidad
    except Exception:
        try:
            return empleado.personal_no_clinico.servicio_unidad
        except Exception:
            return None


def _info_empleado_solicitante(empleado):
    unidad = _unidad_empleado(empleado)
    return {
        "nombre": _nombre_empleado(empleado),
        "unidad": getattr(unidad, "nombre_unidad", "-") or "-",
        "nombre_corto": getattr(unidad, "nombre_corto_unidad", "-") or "-",
    }


def _texto_nivel_complejidad(institucion):
    nivel = getattr(institucion, "nivel_complejidad_institucional", None)
    if not nivel:
        return "-"
    if getattr(nivel, "siglas", None):
        return f"Nivel {nivel.siglas}"
    if getattr(nivel, "nivel_complejidad", None):
        return f"Nivel {nivel.nivel_complejidad}"
    return "-"


def _info_institucion(institucion):
    if not institucion:
        return {"nombre": "-", "alias": "", "nivel": "-", "region": "-"}
    return {
        "nombre": institucion.nombre_institucion_salud,
        "alias": "",
        "nivel": _texto_nivel_complejidad(institucion),
        "region": getattr(institucion.region_salud, "nombre_region_salud", "-") or "-",
    }


def _info_punto_solicitud(punto):
    if not punto:
        return {"nombre": "-", "nombre_corto": "-", "tipo": "-"}

    if punto.unidad:
        return {
            "nombre": punto.unidad.nombre_unidad,
            "nombre_corto": punto.unidad.nombre_corto_unidad or punto.unidad.nombre_unidad,
            "tipo": "Unidad Administrativa",
        }

    unidad_clinica = punto.unidad_clinica
    if not unidad_clinica:
        return {"nombre": "-", "nombre_corto": "-", "tipo": "Unidad Clínica"}

    if unidad_clinica.area_atencion:
        return {
            "nombre": unidad_clinica.area_atencion.nombre_area_atencion,
            "nombre_corto": unidad_clinica.area_atencion.nombre_corto_area_atencion or unidad_clinica.area_atencion.servicio.nombre_corto,
            "tipo": "Unidad Clínica",
        }

    if unidad_clinica.sala:
        return {
            "nombre": unidad_clinica.sala.nombre_sala,
            "nombre_corto": unidad_clinica.sala.nombre_corto_sala or unidad_clinica.sala.nombre_sala,
            "tipo": "Unidad Clínica",
        }

    if unidad_clinica.servicio_aux:
        return {
            "nombre": unidad_clinica.servicio_aux.nombre_servicio_a,
            "nombre_corto": unidad_clinica.servicio_aux.nombre_corto_servicio_a or unidad_clinica.servicio_aux.nombre_servicio_a,
            "tipo": "Unidad Clínica",
        }

    if unidad_clinica.establecimiento_ext:
        establecimiento = unidad_clinica.establecimiento_ext
        return {
            "nombre": establecimiento.nombre_institucion_salud,
            "nombre_corto": getattr(establecimiento.nivel_complejidad_institucional, "siglas", None) or establecimiento.nombre_institucion_salud,
            "tipo": "Unidad Clínica",
        }

    return {"nombre": str(unidad_clinica), "nombre_corto": str(unidad_clinica), "tipo": "Unidad Clínica"}


def _metadata_opciones_formulario(form, solicitud, usuario):
    destinos = {
        str(destino.pk): _info_institucion(destino)
        for destino in form.fields["lugar_destino"].queryset
    }
    puntos = {
        str(punto.pk): _info_punto_solicitud(punto)
        for punto in form.fields["punto_solicitud"].queryset
    }
    empleado_solicitante = getattr(solicitud, "solicitante_empleado", None) or getattr(usuario, "empleado", None)
    return {
        "destinos_info_json": json.dumps(destinos),
        "puntos_info_json": json.dumps(puntos),
        "solicitante_info": _info_empleado_solicitante(empleado_solicitante),
    }


def _normalizar_pacientes_payload(pacientes_payload):
    pacientes_ids_guardados = set()
    pacientes_unicos = []

    for item in pacientes_payload or []:
        paciente_id = item.get("paciente_id")
        ingreso_id = item.get("ingreso_id")
        if not paciente_id and not ingreso_id:
            continue

        key = f"{paciente_id or 0}:{ingreso_id or 0}"
        if key in pacientes_ids_guardados:
            continue

        pacientes_ids_guardados.add(key)
        pacientes_unicos.append(item)

    return pacientes_unicos


def _validar_reglas_pacientes(form, pacientes_payload):
    pacientes_unicos = _normalizar_pacientes_payload(pacientes_payload)
    tipo_solicitud = form.cleaned_data.get("tipo_solicitud")
    tipo_codigo = (getattr(tipo_solicitud, "codigo", "") or "").upper()

    if len(pacientes_unicos) > 3:
        form.add_error(None, "Una solicitud permite como máximo 3 pacientes.")

    if tipo_codigo != "PACIENTES" and pacientes_unicos:
        form.add_error("tipo_solicitud", "Solo el tipo de solicitud PACIENTES permite asociar pacientes.")

    return pacientes_unicos


class SGTransporteHospitalarioDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "sg_transporte_hospitalario/dashboard.html"

    def _active_tab(self):
        active_tab = self.request.GET.get("tab", "solicitud")
        tab_keys = {tab["key"] for tab in TAB_SECTIONS}
        return active_tab if active_tab in tab_keys else "solicitud"

    def dispatch(self, request, *args, **kwargs):
        if not puede_ver_modulo(request.user):
            return redirect("acceso_denegado")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not puede_gestionar_modulo(request.user):
            return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

        form = SolicitudCreateForm(request.POST)
        pacientes_payload = _parse_payload_json(request.POST.get("pacientes_json"))
        personal_payload = _parse_payload_json(request.POST.get("empleados_json"))

        empleado_usuario = getattr(request.user, "empleado", None)
        if empleado_usuario is None:
            form.add_error(None, "El usuario actual no tiene empleado asociado.")

        if form.is_valid() and empleado_usuario is not None:
            pacientes_unicos = _validar_reglas_pacientes(form, pacientes_payload)

        if form.is_valid() and empleado_usuario is not None:
            with transaction.atomic():
                solicitud = form.save(commit=False)
                solicitud.numero_solicitud = _generar_numero_solicitud()
                solicitud.solicitante_empleado = empleado_usuario
                solicitud.estado = "PENDIENTE"
                solicitud.activo = True
                solicitud.save()

                for item in pacientes_unicos:
                    paciente_id = item.get("paciente_id")
                    ingreso_id = item.get("ingreso_id")

                    SolicitudPaciente.objects.create(
                        solicitud=solicitud,
                        paciente_id=paciente_id or None,
                        ingreso_id=ingreso_id or None,
                    )

                empleados_ids_guardados = set()
                for item in personal_payload:
                    empleado_id = item.get("empleado_id")
                    if not empleado_id or empleado_id in empleados_ids_guardados:
                        continue
                    empleados_ids_guardados.add(empleado_id)
                    SolicitudPersonal.objects.create(
                        solicitud=solicitud,
                        empleado_id=empleado_id,
                        observacion=item.get("observacion") or None,
                    )

            mostrar_mensaje(request, "success", f"Solicitud {solicitud.numero_solicitud} creada con estado PENDIENTE.")
            return redirect(f"{reverse('sg_transporte_hospitalario_dashboard')}?tab=solicitud")

        mostrar_mensaje(request, "error", "No se pudo guardar la solicitud. Revisa los datos ingresados.")
        self.form = form
        self.pacientes_payload = pacientes_payload
        self.personal_payload = personal_payload
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(construir_contexto_dashboard(self.request.user))
        active_tab = self._active_tab()
        solicitudes_activas = list(_obtener_qs_solicitudes_activas(self.request.user))

        context["tabs"] = TAB_SECTIONS
        context["active_tab"] = active_tab
        context["tabs_url_base"] = reverse("sg_transporte_hospitalario_dashboard")
        context["solicitud_form"] = getattr(self, "form", SolicitudCreateForm())
        context["solicitudes_activas"] = solicitudes_activas
        context["filtro_estados"] = list(Solicitud.Estado.choices)
        context["filtro_areas"] = sorted(
            {
                _area_solicitante_desde_punto(solicitud.punto_solicitud)
                for solicitud in solicitudes_activas
                if _area_solicitante_desde_punto(solicitud.punto_solicitud) != "-"
            }
        )
        context["filtro_tipos"] = sorted(
            {
                solicitud.tipo_solicitud.nombre
                for solicitud in solicitudes_activas
                if solicitud.tipo_solicitud_id
            }
        )
        context["pacientes_payload"] = json.dumps(getattr(self, "pacientes_payload", []))
        context["personal_payload"] = json.dumps(getattr(self, "personal_payload", []))
        return context


@require_GET
def api_estado_modulo(request):
    if not puede_ver_modulo(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    return JsonResponse(
        {
            "ok": True,
            "modulo": "SG-transporte_hospitalario",
            "lectura": True,
            "escritura": puede_gestionar_modulo(request.user),
        }
    )


@require_GET
def api_buscar_pacientes(request):
    if not puede_ver_modulo(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    termino = (request.GET.get("q") or "").strip()
    tipo = (request.GET.get("tipo") or "nombre").strip().lower()
    if len(termino) < 2:
        return JsonResponse({"data": []})

    if tipo == "identidad":
        q_base = Q(dni__icontains=termino)
    else:
        # Reutiliza el patrón de búsqueda por nombre compuesto usado en s_exp:
        # divide por palabras y exige coincidencia de cada palabra en algún campo nominal.
        palabras = [p for p in termino.split() if p]
        q_base = Q()
        for palabra in palabras:
            q_base &= (
                Q(primer_nombre__icontains=palabra)
                | Q(segundo_nombre__icontains=palabra)
                | Q(primer_apellido__icontains=palabra)
                | Q(segundo_apellido__icontains=palabra)
            )
        q_base = q_base | Q(dni__icontains=termino)

    if termino.isdigit():
        q_base = q_base | Q(expediente_numero=int(termino))

    ingresos_prefetch = Prefetch(
        "pacientes_ingresados",
        queryset=Ingreso.objects.filter(estado=1).select_related("sala").order_by("-fecha_ingreso"),
    )

    pacientes = (
        Paciente.objects
        .filter(q_base)
        .prefetch_related(ingresos_prefetch)
        .order_by("primer_nombre", "primer_apellido")[:20]
    )

    data = []
    for p in pacientes:
        ingreso_activo = p.pacientes_ingresados.first()
        data.append(
            {
                "paciente_id": p.id,
                "nombre": " ".join(
                    x for x in [p.primer_nombre, p.segundo_nombre, p.primer_apellido, p.segundo_apellido] if x
                ),
                "expediente": str(p.expediente_numero or "-"),
                "ingreso_id": ingreso_activo.id if ingreso_activo else None,
                "ingreso": f"ING-{ingreso_activo.id}" if ingreso_activo else "-",
                "sala": ingreso_activo.sala.nombre_sala if ingreso_activo and ingreso_activo.sala else "-",
            }
        )

    return JsonResponse({"data": data})


@require_GET
def api_buscar_empleados(request):
    if not puede_ver_modulo(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    termino = (request.GET.get("q") or "").strip()
    tipo = (request.GET.get("tipo") or "nombre").strip().lower()
    if len(termino) < 2:
        return JsonResponse({"data": []})

    if tipo == "identidad":
        filtro = Q(dni__icontains=termino)
    else:
        palabras = [p for p in termino.split() if p]
        filtro = Q()
        for palabra in palabras:
            filtro &= (
                Q(primer_nombre__icontains=palabra)
                | Q(segundo_nombre__icontains=palabra)
                | Q(primer_apellido__icontains=palabra)
                | Q(segundo_apellido__icontains=palabra)
            )
        filtro = filtro | Q(dni__icontains=termino)

    empleados = (
        Empleado.objects
        .filter(filtro)
        .select_related("personal_salud_empleado__tipo_personal_salud", "personal_no_clinico")
        .order_by("primer_nombre", "primer_apellido")[:20]
    )

    data = []
    for e in empleados:
        data.append(
            {
                "empleado_id": e.id,
                "nombre": _nombre_empleado(e),
                "cargo": _cargo_empleado(e),
                "dni": e.dni,
                "unidad": getattr(_unidad_empleado(e), "nombre_unidad", "-") or "-",
                "unidad_corta": getattr(_unidad_empleado(e), "nombre_corto_unidad", "-") or "-",
            }
        )

    return JsonResponse({"data": data})


@require_GET
def api_solicitudes_activas(request):
    if not puede_ver_modulo(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    draw = int(request.GET.get("draw", 0))
    start = int(request.GET.get("start", 0))
    length = int(request.GET.get("length", 10))
    search = (request.GET.get("search[value]") or "").strip()
    estado_filtro = (request.GET.get("estado") or "").strip()

    qs = _obtener_qs_solicitudes_activas(request.user)

    total = qs.count()
    if estado_filtro:
        qs = qs.filter(estado=estado_filtro)

    if search:
        qs = qs.filter(
            Q(numero_solicitud__icontains=search)
            | Q(tipo_solicitud__nombre__icontains=search)
            | Q(prioridad__nombre__icontains=search)
            | Q(estado__icontains=search)
        )

    filtered = qs.count()
    rows = qs[start:start + length]

    data = []
    for s in rows:
        data.append(
            {
                "id": s.id,
                "numero_solicitud": s.numero_solicitud,
                "fecha": timezone.localtime(s.fecha_solicitud).strftime("%d/%m/%Y %H:%M"),
                "area_solicitante": _area_solicitante_desde_punto(s.punto_solicitud),
                "tipo_solicitud": s.tipo_solicitud.nombre,
                "prioridad": s.prioridad.nombre,
                "proceso": _proceso_solicitud_label(s.estado),
                "puede_editar": s.puede_editar,
                "url_ver": reverse("sg_transporte_hospitalario_solicitud_ver", kwargs={"pk": s.id}),
                "url_editar": reverse("sg_transporte_hospitalario_solicitud_editar", kwargs={"pk": s.id}),
            }
        )

    return JsonResponse(
        {
            "draw": draw,
            "recordsTotal": total,
            "recordsFiltered": filtered,
            "data": data,
        }
    )


@require_GET
def api_detalle_solicitud(request):
    if not puede_ver_modulo(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    solicitud_id = request.GET.get("id")
    if not solicitud_id:
        return JsonResponse({"ok": False, "error": "El parametro id es requerido."}, status=400)

    try:
        solicitud = _obtener_qs_solicitudes_activas(request.user).get(pk=solicitud_id)
    except Solicitud.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Solicitud no encontrada."}, status=404)

    pacientes = []
    for item in solicitud.solicitud_pacientes.select_related("paciente", "ingreso__sala"):
        nombre = "-"
        if item.paciente:
            nombre = " ".join(
                x for x in [
                    item.paciente.primer_nombre,
                    item.paciente.segundo_nombre,
                    item.paciente.primer_apellido,
                    item.paciente.segundo_apellido,
                ] if x
            )
        pacientes.append(
            {
                "paciente": nombre,
                "expediente": str(getattr(item.paciente, "expediente_numero", "-")),
                "ingreso": f"ING-{item.ingreso_id}" if item.ingreso_id else "-",
                "sala": item.ingreso.sala.nombre_sala if item.ingreso and item.ingreso.sala else "-",
            }
        )

    personal = [
        {
            "empleado": f"{p.empleado.primer_nombre} {p.empleado.primer_apellido}",
            "observacion": p.observacion or "-",
        }
        for p in solicitud.solicitud_personal.select_related("empleado")
    ]

    return JsonResponse(
        {
            "ok": True,
            "data": {
                "id": solicitud.id,
                "numero_solicitud": solicitud.numero_solicitud,
                "fecha_solicitud": timezone.localtime(solicitud.fecha_solicitud).strftime("%d/%m/%Y %H:%M"),
                "area_solicitante": _area_solicitante_desde_punto(solicitud.punto_solicitud),
                "tipo_solicitud": solicitud.tipo_solicitud.nombre,
                "prioridad": solicitud.prioridad.nombre,
                "estado": solicitud.estado,
                "proceso": _proceso_solicitud_label(solicitud.estado),
                "puede_editar": solicitud.puede_editar,
                "motivo": solicitud.motivo,
                "observaciones": solicitud.observaciones or "",
                "pacientes": pacientes,
                "personal": personal,
            },
        }
    )


class SolicitudListView(LoginRequiredMixin, ListView):
    model = Solicitud
    template_name = "sg_transporte_hospitalario/solicitud_list.html"
    context_object_name = "solicitudes_activas"

    def dispatch(self, request, *args, **kwargs):
        if not puede_ver_modulo(request.user):
            return redirect("acceso_denegado")
        return redirect(f"{reverse('sg_transporte_hospitalario_dashboard')}?tab=solicitud")

    def get_queryset(self):
        return _obtener_qs_solicitudes_activas(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(construir_contexto_dashboard(self.request.user))
        context["tabs"] = TAB_SECTIONS
        context["active_tab"] = "solicitud"
        context["estados"] = Solicitud.Estado.choices
        return context


class SolicitudFormView(LoginRequiredMixin, TemplateView):
    template_name = "sg_transporte_hospitalario/solicitud_form.html"
    modo = "crear"

    def dispatch(self, request, *args, **kwargs):
        if not puede_ver_modulo(request.user):
            return redirect("acceso_denegado")
        return super().dispatch(request, *args, **kwargs)

    def _get_solicitud(self):
        pk = self.kwargs.get("pk")
        if not pk:
            return None
        return get_object_or_404(_obtener_qs_solicitudes_activas(self.request.user), pk=pk)

    def get(self, request, *args, **kwargs):
        solicitud = self._get_solicitud()
        form = SolicitudForm(instance=solicitud)
        if self.modo == "ver":
            for field in form.fields.values():
                field.disabled = True

        pacientes_payload = []
        personal_payload = []
        if solicitud:
            solicitud_pacientes = solicitud.solicitud_pacientes.all()
            pacientes_payload = [
                {
                    "paciente_id": item.paciente_id,
                    "ingreso_id": item.ingreso_id,
                    "nombre": " ".join(
                        x for x in [
                            getattr(item.paciente, "primer_nombre", None),
                            getattr(item.paciente, "segundo_nombre", None),
                            getattr(item.paciente, "primer_apellido", None),
                            getattr(item.paciente, "segundo_apellido", None),
                        ] if x
                    ) or "-",
                    "expediente": str(getattr(item.paciente, "expediente_numero", "-") or "-"),
                    "ingreso": f"ING-{item.ingreso_id}" if item.ingreso_id else "-",
                    "sala": item.ingreso.sala.nombre_sala if item.ingreso and item.ingreso.sala else "-",
                }
                for item in solicitud_pacientes
            ]

            solicitud_personal = solicitud.solicitud_personal.all()
            personal_payload = [
                {
                    "empleado_id": item.empleado_id,
                    "nombre": _nombre_empleado(item.empleado),
                    "cargo": _cargo_empleado(item.empleado),
                    "observacion": item.observacion or "",
                }
                for item in solicitud_personal
            ]

        context = self.get_context_data(
            form=form,
            solicitud=solicitud,
            pacientes_payload=json.dumps(pacientes_payload),
            personal_payload=json.dumps(personal_payload),
        )
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        if not puede_gestionar_modulo(request.user):
            return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

        solicitud = self._get_solicitud()
        if solicitud and not solicitud.puede_editar:
            mostrar_mensaje(request, "warning", "La solicitud ya está asociada a una autorización y no puede editarse.")
            return redirect("sg_transporte_hospitalario_solicitud_list")

        form = SolicitudForm(request.POST, instance=solicitud)
        pacientes_payload = _parse_payload_json(request.POST.get("pacientes_json"))
        personal_payload = _parse_payload_json(request.POST.get("empleados_json"))

        empleado_usuario = getattr(request.user, "empleado", None)
        if empleado_usuario is None:
            form.add_error(None, "El usuario actual no tiene empleado asociado.")

        if form.is_valid() and empleado_usuario is not None:
            pacientes_unicos = _validar_reglas_pacientes(form, pacientes_payload)

        if form.is_valid() and empleado_usuario is not None:
            with transaction.atomic():
                solicitud_guardada = form.save(commit=False)
                if not solicitud_guardada.pk:
                    solicitud_guardada.numero_solicitud = _generar_numero_solicitud()
                    solicitud_guardada.solicitante_empleado = empleado_usuario
                    solicitud_guardada.estado = Solicitud.Estado.PENDIENTE
                    solicitud_guardada.activo = True
                solicitud_guardada.save()

                SolicitudPaciente.objects.filter(solicitud=solicitud_guardada).delete()
                SolicitudPersonal.objects.filter(solicitud=solicitud_guardada).delete()

                for item in pacientes_unicos:
                    paciente_id = item.get("paciente_id")
                    ingreso_id = item.get("ingreso_id")
                    SolicitudPaciente.objects.create(
                        solicitud=solicitud_guardada,
                        paciente_id=paciente_id or None,
                        ingreso_id=ingreso_id or None,
                    )

                empleados_ids_guardados = set()
                for item in personal_payload:
                    empleado_id = item.get("empleado_id")
                    if not empleado_id or empleado_id in empleados_ids_guardados:
                        continue
                    empleados_ids_guardados.add(empleado_id)
                    SolicitudPersonal.objects.create(
                        solicitud=solicitud_guardada,
                        empleado_id=empleado_id,
                        observacion=item.get("observacion") or None,
                    )

            accion = "actualizada" if solicitud else "creada"
            mostrar_mensaje(request, "success", f"Solicitud {solicitud_guardada.numero_solicitud} {accion} correctamente.")
            return redirect("sg_transporte_hospitalario_solicitud_list")

        context = self.get_context_data(
            form=form,
            solicitud=solicitud,
            pacientes_payload=json.dumps(pacientes_payload),
            personal_payload=json.dumps(personal_payload),
        )
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(construir_contexto_dashboard(self.request.user))
        context["tabs"] = TAB_SECTIONS
        context["active_tab"] = "solicitud"
        context["modo"] = self.modo
        context["titulo_form"] = {
            "crear": "Nueva solicitud",
            "editar": "Editar solicitud",
            "ver": "Detalle de solicitud",
        }.get(self.modo, "Solicitud")
        context["form_action"] = self.request.path
        context["solicitud"] = kwargs.get("solicitud")
        context["form"] = kwargs.get("form")
        context["pacientes_payload"] = kwargs.get("pacientes_payload", "[]")
        context["personal_payload"] = kwargs.get("personal_payload", "[]")
        context["tipo_pacientes_id"] = (
            TipoSolicitud.objects
            .filter(codigo__iexact="PACIENTES", activo=True)
            .values_list("id", flat=True)
            .first()
            or ""
        )
        context.update(_metadata_opciones_formulario(context["form"], context["solicitud"], self.request.user))
        return context


class SolicitudCreateView(SolicitudFormView):
    modo = "crear"

    def post(self, request, *args, **kwargs):
        if not puede_gestionar_modulo(request.user):
            return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

        form = SolicitudForm(request.POST)
        pacientes_payload = _parse_payload_json(request.POST.get("pacientes_json"))
        personal_payload = _parse_payload_json(request.POST.get("empleados_json"))

        empleado_usuario = getattr(request.user, "empleado", None)
        if empleado_usuario is None:
            form.add_error(None, "El usuario actual no tiene empleado asociado.")

        if form.is_valid() and empleado_usuario is not None:
            pacientes_unicos = _validar_reglas_pacientes(form, pacientes_payload)

        if form.is_valid() and empleado_usuario is not None:
            with transaction.atomic():
                solicitud = form.save(commit=False)
                solicitud.numero_solicitud = _generar_numero_solicitud()
                solicitud.solicitante_empleado = empleado_usuario
                solicitud.estado = Solicitud.Estado.PENDIENTE
                solicitud.activo = True
                solicitud.save()

                for item in pacientes_unicos:
                    paciente_id = item.get("paciente_id")
                    ingreso_id = item.get("ingreso_id")

                    SolicitudPaciente.objects.create(
                        solicitud=solicitud,
                        paciente_id=paciente_id or None,
                        ingreso_id=ingreso_id or None,
                    )

                empleados_ids_guardados = set()
                for item in personal_payload:
                    empleado_id = item.get("empleado_id")
                    if not empleado_id or empleado_id in empleados_ids_guardados:
                        continue
                    empleados_ids_guardados.add(empleado_id)
                    SolicitudPersonal.objects.create(
                        solicitud=solicitud,
                        empleado_id=empleado_id,
                        observacion=item.get("observacion") or None,
                    )

            mostrar_mensaje(request, "success", f"Solicitud {solicitud.numero_solicitud} creada correctamente.")
            return redirect("sg_transporte_hospitalario_solicitud_list")

        context = self.get_context_data(
            form=form,
            solicitud=None,
            pacientes_payload=json.dumps(pacientes_payload),
            personal_payload=json.dumps(personal_payload),
        )
        return self.render_to_response(context)


class SolicitudUpdateView(SolicitudFormView):
    modo = "editar"

    def post(self, request, *args, **kwargs):
        if not puede_gestionar_modulo(request.user):
            return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

        solicitud = self._get_solicitud()
        if solicitud is None:
            return JsonResponse({"ok": False, "error": "Solicitud no encontrada."}, status=404)

        if not solicitud.puede_editar:
            mostrar_mensaje(request, "warning", "La solicitud ya está asociada a una autorización y no puede editarse.")
            return redirect("sg_transporte_hospitalario_solicitud_list")

        form = SolicitudForm(request.POST, instance=solicitud)
        pacientes_payload = _parse_payload_json(request.POST.get("pacientes_json"))
        personal_payload = _parse_payload_json(request.POST.get("empleados_json"))

        if form.is_valid():
            pacientes_unicos = _validar_reglas_pacientes(form, pacientes_payload)

        if form.is_valid():
            with transaction.atomic():
                solicitud_actualizada = form.save()

                SolicitudPaciente.objects.filter(solicitud=solicitud_actualizada).delete()
                SolicitudPersonal.objects.filter(solicitud=solicitud_actualizada).delete()

                for item in pacientes_unicos:
                    paciente_id = item.get("paciente_id")
                    ingreso_id = item.get("ingreso_id")

                    SolicitudPaciente.objects.create(
                        solicitud=solicitud_actualizada,
                        paciente_id=paciente_id or None,
                        ingreso_id=ingreso_id or None,
                    )

                empleados_ids_guardados = set()
                for item in personal_payload:
                    empleado_id = item.get("empleado_id")
                    if not empleado_id or empleado_id in empleados_ids_guardados:
                        continue
                    empleados_ids_guardados.add(empleado_id)
                    SolicitudPersonal.objects.create(
                        solicitud=solicitud_actualizada,
                        empleado_id=empleado_id,
                        observacion=item.get("observacion") or None,
                    )

            mostrar_mensaje(request, "success", f"Solicitud {solicitud_actualizada.numero_solicitud} actualizada correctamente.")
            return redirect("sg_transporte_hospitalario_solicitud_list")

        context = self.get_context_data(
            form=form,
            solicitud=solicitud,
            pacientes_payload=json.dumps(pacientes_payload),
            personal_payload=json.dumps(personal_payload),
        )
        return self.render_to_response(context)


class SolicitudDetailView(SolicitudFormView):
    modo = "ver"

    def post(self, request, *args, **kwargs):
        return redirect("sg_transporte_hospitalario_solicitud_ver", pk=kwargs.get("pk"))

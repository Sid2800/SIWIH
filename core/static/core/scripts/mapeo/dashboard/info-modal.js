/* =========================================================================
  Dashboard Mapeo de Camas — modal de guía operativa
  Fecha: 2026-06-01
  Prioriza lectura administrativa y deja detalle técnico colapsable.
  Reutiliza SweetAlert2 (ya cargado por core/base.html).
  ========================================================================= */
(function (global) {
  "use strict";

  // 2026-06-09: endpoints de guía derivados de configuración inyectada por template.
  const DASH_URLS = (global.DASHBOARD_CFG && global.DASHBOARD_CFG.urls) || {};
  const ENDPOINTS = {
    KPIS: "GET " + (DASH_URLS.kpis || "[url_kpis_no_configurada]"),
    OCUPACION_SERVICIO: "GET " + (DASH_URLS.ocupacionServicio || "[url_ocupacion_servicio_no_configurada]"),
    DISTRIBUCION_CAMAS: "GET " + (DASH_URLS.distribucionCamas || "[url_distribucion_camas_no_configurada]"),
    OCUPACION_HORA: "GET " + (DASH_URLS.ocupacionHora || "[url_ocupacion_hora_no_configurada]"),
    SATURACION_SALA: "GET " + (DASH_URLS.saturacionSala || "[url_saturacion_sala_no_configurada]"),
    ULTIMOS_MOVIMIENTOS: "GET " + (DASH_URLS.ultimosMovimientos || "[url_ultimos_movimientos_no_configurada]"),
    TODOS: "Aplicado a TODOS los endpoints del dashboard",
    HELPER: "Helper interno",
  };

  // [2026-06-01] Mantener en sincronía con mapeo_camas/views_dashboard.py.
  // La UI muestra primero una guía de negocio y deja lo técnico como apoyo opcional.
  const SECCIONES = [
    {
      grupo: "KPIs principales",
      items: [
        {
          nombre: "Total camas",
          endpoint: ENDPOINTS.KPIS,
          metodo: "dashboard_kpis() — views.py",
          origen: ["Tabla base: Cama", "Filtro estructural: estado=1"],
          campos: ["Cama.id", "Cama.estado"],
          formula: "total_camas = count(Cama where estado = 1)",
          pasos: [
            "Se consulta el universo de camas activas del hospital.",
            "No depende del rango temporal: representa capacidad instalada activa.",
          ],
          salida: "Numero entero usado como denominador general del dashboard.",
        },
        {
          nombre: "Ocupadas / Disponibles / Fuera servicio",
          endpoint: ENDPOINTS.KPIS,
          metodo: "dashboard_kpis() → _snapshot_estado_camas(hasta)",
          origen: [
            "Fuente actual: AsignacionCamaPaciente vigente cuando hasta esta a 60 s o menos del ahora.",
            "Fuente historica: HistorialEstadoCama con ultimo estado por cama hasta la fecha solicitada.",
          ],
          campos: [
            "AsignacionCamaPaciente.cama_id",
            "HistorialEstadoCama.cama_id",
            "HistorialEstadoCama.estado_nuevo",
            "HistorialEstadoCama.fecha_hora",
          ],
          formula: "snapshot_estado(hasta) = ultimo estado conocido por cama al cierre del rango",
          pasos: [
            "Si abs(ahora - hasta) <= 60 segundos, se usa la asignacion vigente para respuesta rapida.",
            "Si no, se reconstruye el estado con el ultimo HistorialEstadoCama por cama con fecha_hora <= hasta.",
            "Los codigos se agrupan en OCUPADA, VACIA/LIBRE y FUERA_SERVICIO/MANTENIMIENTO.",
          ],
          salida: "Tres contadores absolutos que alimentan tarjetas KPI y el radial resumen.",
        },
        {
          nombre: "% Ocupación",
          endpoint: ENDPOINTS.KPIS,
          metodo: "dashboard_kpis()",
          origen: ["Resultado derivado de Total camas y Ocupadas del mismo endpoint."],
          campos: ["ocupadas", "total_camas"],
          formula: "porcentaje_ocupacion = round((ocupadas / total_camas) * 100, 1)",
          pasos: [
            "Se toma el conteo de camas ocupadas del snapshot de cierre.",
            "Se divide entre el total de camas activas.",
            "Si total_camas = 0, el resultado se fuerza a 0 para evitar division por cero.",
          ],
          salida: "Porcentaje con un decimal mostrado como KPI principal.",
        },
        {
          nombre: "Altas del rango",
          endpoint: ENDPOINTS.KPIS,
          metodo: "dashboard_kpis()",
          origen: ["Tabla clinica: Ingreso"],
          campos: ["Ingreso.fecha_egreso"],
          formula: "altas = count(Ingreso where fecha_egreso between desde and hasta)",
          pasos: [
            "Se filtran egresos dentro del rango seleccionado.",
            "Cada egreso contado representa una alta ocurrida en el periodo.",
          ],
          salida: "Conteo absoluto de altas del periodo.",
        },
        {
          nombre: "Traslados",
          endpoint: ENDPOINTS.KPIS,
          metodo: "dashboard_kpis()",
          origen: ["Tabla operativa: MovimientoCama"],
          campos: ["MovimientoCama.fecha_hora"],
          formula: "traslados = count(MovimientoCama where fecha_hora between desde and hasta)",
          pasos: [
            "Se toman los cambios de cama registrados en el rango.",
            "El indicador representa actividad de movilidad, no ocupacion neta.",
          ],
          salida: "Conteo absoluto de movimientos de cama.",
        },
        {
          nombre: "Cambios detectados / Camas validadas",
          endpoint: ENDPOINTS.KPIS,
          metodo: "dashboard_kpis() → _obtener_sesion_mapeo_activa(user)",
          origen: ["Tabla operativa: DetalleMapeoCama de la sesion activa del usuario."],
          campos: ["DetalleMapeoCama.hubo_cambio", "DetalleMapeoCama.fue_validada", "DetalleMapeoCama.cama_id"],
          formula: "cambios = count(hubo_cambio = true); validadas = count(distinct cama_id where fue_validada = true)",
          pasos: [
            "Se obtiene primero la sesion ACTIVA del usuario autenticado.",
            "Cambios detectados cuenta filas marcadas con hubo_cambio = true.",
            "Camas validadas cuenta camas distintas marcadas con fue_validada = true.",
            "Este KPI no depende del rango temporal; depende del trabajo actual de mapeo.",
          ],
          salida: "Dos totales operativos mostrados como avance de validacion.",
        },
        {
          nombre: "Tiempo promedio ocupación",
          endpoint: ENDPOINTS.KPIS,
          metodo: "dashboard_kpis()  +  Avg(ExpressionWrapper(F('fecha_egreso')-F('fecha_ingreso')))",
          origen: ["Tabla clinica: Ingreso con fecha_ingreso y fecha_egreso."],
          campos: ["Ingreso.fecha_ingreso", "Ingreso.fecha_egreso"],
          formula: "promedio_estancia = avg(fecha_egreso - fecha_ingreso)",
          pasos: [
            "Se consideran ingresos egresados dentro del rango.",
            "Para cada fila se calcula la duracion entre ingreso y egreso.",
            "Luego se promedia la duracion total.",
            "La UI lo expresa en horas si es menor a 24 h o en dias si es mayor o igual a 24 h.",
          ],
          salida: "Duracion promedio de ocupacion mostrada como indicador resumido.",
        },
      ],
    },
    {
      grupo: "Resumen radial (superior derecha)",
      items: [
        {
          nombre: "RadialBar Ocupadas / Disponibles / Fuera servicio",
          endpoint: ENDPOINTS.KPIS + " (sin request extra)",
          metodo: "DashboardChartEstadosResumen.update(data_kpis)",
          origen: ["Reutiliza el JSON de dashboard_kpis(); no hace una consulta adicional."],
          campos: ["ocupadas", "disponibles", "fuera_servicio", "total_camas"],
          formula: "serie_pct = round((valor / total_camas) * 1000) / 10",
          pasos: [
            "Cada anillo transforma conteo absoluto a porcentaje sobre el total de camas.",
            "El valor central muestra la ocupacion porque toma la primera serie: ocupadas.",
            "El tooltip revierte el porcentaje a cantidad estimada de camas para lectura rapida.",
          ],
          salida: "Visual de composicion instantanea del estado hospitalario.",
        },
      ],
    },
    {
      grupo: "Ocupación por servicio (barras apiladas)",
      items: [
        {
          nombre: "Ocupadas vs Disponibles por servicio",
          endpoint: ENDPOINTS.OCUPACION_SERVICIO,
          metodo: "dashboard_ocupacion_servicio() → _snapshot_estado_por_cama(hasta)",
          origen: ["Cama + relacion Sala -> Servicio + snapshot por cama al cierre del rango."],
          campos: ["Cama.estado", "Sala.estado", "Servicio.estado", "cama.sala.servicio", "estado_snapshot"],
          formula: "por_servicio = group by servicio -> conteo de ocupadas, disponibles y otras",
          pasos: [
            "Se filtran solo camas, salas y servicios activos.",
            "A cada cama se le asigna su ultimo estado en snapshot(hasta).",
            "Luego se agrupa por servicio y se cuentan categorias operativas.",
          ],
          salida: "Series apiladas para comparar carga entre servicios.",
        },
      ],
    },
    {
      grupo: "Distribución por estado (donut)",
      items: [
        {
          nombre: "Conteo global por código de estado",
          endpoint: ENDPOINTS.DISTRIBUCION_CAMAS,
          metodo: "dashboard_distribucion_camas() → _snapshot_estado_camas(hasta)",
          origen: ["Snapshot consolidado de estado por cama al cierre del rango."],
          campos: ["codigo_estado", "cantidad"],
          formula: "distribucion = {codigo_estado: cantidad_en_snapshot}",
          pasos: [
            "Se obtiene el snapshot historico o actual al final del rango.",
            "Se agrupan todas las camas por codigo de estado.",
            "La respuesta se serializa ordenada para que el donut mantenga consistencia visual.",
          ],
          salida: "Donut global con el peso relativo de cada estado.",
        },
      ],
    },
    {
      grupo: "Ocupación en el tiempo (línea)",
      items: [
        {
          nombre: "Serie temporal de % ocupación",
          endpoint: ENDPOINTS.OCUPACION_HORA,
          metodo: "dashboard_ocupacion_hora() → _dashboard_granularidad(desde, hasta)",
          origen: ["HistorialEstadoCama dentro del rango + snapshot inicial en desde."],
          campos: ["HistorialEstadoCama.fecha_hora", "HistorialEstadoCama.estado_nuevo", "snapshot_inicial_por_cama", "total_camas"],
          formula: "ocupadas_bin = camas_con_estado_OCUPADA_en_bin",
          pasos: [
            "Se define granularidad adaptativa: <= 2 dias = hora; <= 60 dias = dia; > 60 dias = mes.",
            "Se calcula el estado inicial por cama con el snapshot en desde.",
            "Cada bin aplica los eventos del historial ocurridos dentro del intervalo y deja el estado final de cada cama.",
            "Solo OCUPADA cuenta como ocupación para esta serie temporal.",
            "Luego cada bin se transforma a porcentaje sobre total_camas y se redondea a un decimal.",
          ],
          salida: "Curva temporal de ocupacion porcentual del hospital.",
        },
      ],
    },
    {
      grupo: "Saturación por sala",
      items: [
        {
          nombre: "% Ocupación por sala dentro de cada servicio",
          endpoint: ENDPOINTS.SATURACION_SALA,
          metodo: "dashboard_saturacion_sala() → _snapshot_estado_por_cama(hasta)",
          origen: ["Cama activa agrupada por Sala y Servicio + snapshot de estado por cama."],
          campos: ["Sala.nombre", "Servicio.nombre", "estado_snapshot", "cama_id"],
          formula: "pct_sala = round((ocupadas_sala / total_camas_sala) * 100, 1)",
          pasos: [
            "Se agrupan camas activas por la dupla servicio-sala.",
            "Dentro de cada sala se cuentan camas totales y camas ocupadas segun snapshot(hasta).",
            "El porcentaje se calcula por sala y luego se organiza por servicio.",
            "Las salas se ordenan por nombre para mantener comparabilidad entre recargas.",
          ],
          salida: "Comparacion de saturacion interna entre salas de un mismo servicio.",
        },
      ],
    },
    {
      grupo: "Tabla de movimientos",
      items: [
        {
          nombre: "Movimientos de cama en el rango",
          endpoint: ENDPOINTS.ULTIMOS_MOVIMIENTOS + "?limit=N",
          metodo: "dashboard_ultimos_movimientos()",
          origen: ["Tabla MovimientoCama con relaciones precargadas."],
          campos: ["fecha_hora", "cama_origen", "cama_destino", "ingreso.paciente", "usuario"],
          formula: "movimientos = MovimientoCama filtrado por rango, ordenado descendente y truncado por limit",
          pasos: [
            "Se filtra por fecha_hora dentro del rango.",
            "Se hace select_related para evitar consultas extra al serializar paciente, usuario y camas.",
            "Se ordena del mas reciente al mas antiguo.",
            "El limite maximo permitido por backend es 500.",
          ],
          salida: "Tabla cronologica para auditoria operativa de cambios de cama.",
        },
      ],
    },
    {
      grupo: "Filtro temporal",
      items: [
        {
          nombre: "Parser de rango (?desde, ?hasta)",
          endpoint: ENDPOINTS.TODOS,
          metodo: "_dashboard_parse_range(request)",
          origen: ["Parametros de query string recibidos por request.GET."],
          campos: ["desde", "hasta"],
          formula: "rango_final = normalizar(desde, hasta, timezone_proyecto)",
          pasos: [
            "Si no llegan parametros, se toma hoy 00:00 -> ahora.",
            "Si las fechas vienen naive, se convierten a timezone aware con la zona del proyecto.",
            "Si hasta < desde, se invierten para mantener coherencia temporal.",
          ],
          salida: "Rango consistente usado por todos los endpoints del dashboard.",
        },
        {
          nombre: "Snapshot histórico de camas",
          endpoint: ENDPOINTS.HELPER,
          metodo: "_snapshot_estado_camas(hasta) / _snapshot_estado_por_cama(hasta)",
          origen: ["AsignacionCamaPaciente vigente o HistorialEstadoCama por cama segun cercania temporal."],
          campos: ["cama_id", "estado_nuevo", "fecha_hora"],
          formula: "estado_cama(hasta) = ultimo evento conocido por cama; si no existe historial, se asume VACIA",
          pasos: [
            "Fast path: si hasta esta muy cerca del ahora, se usa estado vigente para mayor rendimiento.",
            "Modo historico: una subconsulta obtiene el ultimo evento por cama con fecha_hora <= hasta.",
            "Si una cama no tiene historial previo, se clasifica como VACIA.",
          ],
          salida: "Base metodologica comun para KPIs y graficas de distribucion, servicio y saturacion.",
        },
      ],
    },
  ];

  function renderHtml() {
    const parts = ['<div class="dash-info-modal">'];
    parts.push(
      '<div class="dash-info-modal__intro">' +
        '<p><strong>Objetivo:</strong> explicar de forma simple que representa cada tarjeta y grafico del dashboard.</p>' +
        '<p><strong>Como usarlo:</strong> primero lea "Que muestra" y "Como interpretarlo". Si necesita auditoria tecnica, abra "Ver detalle tecnico".</p>' +
        '<p><strong>Importante:</strong> todos los paneles usan el mismo rango de fechas para mantener coherencia.</p>' +
      '</div>'
    );
    SECCIONES.forEach((sec) => {
      parts.push('<section class="dash-info-modal__grupo">');
      parts.push('<h3 class="dash-info-modal__titulo">' + escapeHtml(sec.grupo) + '</h3>');
      sec.items.forEach((it) => {
        parts.push('<article class="dash-info-modal__item">');
        parts.push('<div class="dash-info-modal__head">');
        parts.push('<h4>' + escapeHtml(it.nombre) + '</h4>');
        parts.push('<span class="dash-info-modal__badge">Guia rapida</span>');
        parts.push('</div>');

        parts.push('<div class="dash-info-modal__bloque">');
        parts.push('<div class="dash-info-modal__subtitulo">Que muestra</div>');
        parts.push('<p class="dash-info-modal__salida">' + escapeHtml(it.salida) + '</p>');
        parts.push('</div>');

        parts.push('<div class="dash-info-modal__bloque">');
        parts.push('<div class="dash-info-modal__subtitulo">Como interpretarlo</div>');
        parts.push(renderList((it.pasos || []).slice(0, 2), 'dash-info-modal__pasos')); 
        parts.push('</div>');

        parts.push('<details class="dash-info-modal__detalle">');
        parts.push('<summary>Ver detalle tecnico</summary>');
        parts.push('<dl class="dash-info-modal__meta">');
        parts.push('<dt>Endpoint</dt><dd><code>' + escapeHtml(it.endpoint) + '</code></dd>');
        parts.push('<dt>Metodo backend</dt><dd><code>' + escapeHtml(it.metodo) + '</code></dd>');
        parts.push('</dl>');
        parts.push('<div class="dash-info-modal__bloque">');
        parts.push('<div class="dash-info-modal__subtitulo">Fuente de datos</div>');
        parts.push(renderList(it.origen, 'dash-info-modal__lista')); 
        parts.push('</div>');
        parts.push('<div class="dash-info-modal__bloque">');
        parts.push('<div class="dash-info-modal__subtitulo">Campos utilizados</div>');
        parts.push(renderList(it.campos, 'dash-info-modal__campos')); 
        parts.push('</div>');
        parts.push('<div class="dash-info-modal__bloque">');
        parts.push('<div class="dash-info-modal__subtitulo">Formula base</div>');
        parts.push('<div class="dash-info-modal__formula"><code>' + escapeHtml(it.formula) + '</code></div>');
        parts.push('</div>');
        parts.push('<div class="dash-info-modal__bloque">');
        parts.push('<div class="dash-info-modal__subtitulo">Pasos del calculo</div>');
        parts.push(renderList(it.pasos, 'dash-info-modal__pasos')); 
        parts.push('</div>');
        parts.push('<div class="dash-info-modal__bloque">');
        parts.push('<div class="dash-info-modal__subtitulo">Salida visible</div>');
        parts.push('<p class="dash-info-modal__salida">' + escapeHtml(it.salida) + '</p>');
        parts.push('</div>');
        parts.push('</details>');
        parts.push('</article>');
      });
      parts.push('</section>');
    });
    parts.push('</div>');
    return parts.join("");
  }

  function renderList(items, className) {
    return (
      '<ul class="' + className + '">' +
      items.map((item) => '<li>' + escapeHtml(item) + '</li>').join('') +
      '</ul>'
    );
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function open() {
    if (typeof Swal === "undefined") {
      window.alert("SweetAlert2 no disponible.");
      return;
    }
    Swal.fire({
      title: "Guia de lectura del dashboard",
      html: renderHtml(),
      width: "min(960px, 96vw)",
      customClass: { popup: "dash-info-modal-popup" },
      confirmButtonText: "Cerrar",
      showCloseButton: true,
      focusConfirm: false,
    });
  }

  function init() {
    const btn = document.getElementById("dash-info-btn");
    if (btn) btn.addEventListener("click", open);
  }

  global.DashboardInfoModal = { init, open };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window);

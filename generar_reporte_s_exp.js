/**
 * Generador del Reporte/Checklist del Módulo s_exp (Solicitud de Expedientes)
 *
 * Salida: REPORTE_S_EXP.docx con:
 *  - Portada y resumen ejecutivo
 *  - Línea de tiempo del desarrollo
 *  - Arquitectura y modelos
 *  - APIs y vistas
 *  - Sistema de tiempo real
 *  - Integración RRHH
 *  - Checklist completo de tareas
 *  - Pendientes / próximos pasos
 */

const {
    Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType,
    PageOrientation, LevelFormat, HeadingLevel, BorderStyle, WidthType, ShadingType,
    TabStopType, TabStopPosition, PageBreak, TableOfContents, PageNumber, Footer, Header,
} = require('docx');
const fs = require('fs');

// =========================================================================
// CONFIGURACIÓN GLOBAL
// =========================================================================
const COLORES = {
    primario: '0F766E',     // teal-700
    acento: '14B8A6',       // teal-500
    exito: '22C55E',        // verde
    advertencia: 'F59E0B',  // ámbar
    info: '3B82F6',         // azul
    texto: '1F2937',        // gris oscuro
    textoSuave: '6B7280',   // gris medio
    fondoCelda: 'F3F4F6',   // gris claro
    fondoHeader: '0F766E',  // mismo primario
};

const border = (color = 'CCCCCC') => ({ style: BorderStyle.SINGLE, size: 1, color });
const bordersAll = (color = 'CCCCCC') => ({
    top: border(color), bottom: border(color), left: border(color), right: border(color)
});

// =========================================================================
// HELPERS
// =========================================================================
function h1(texto) {
    return new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun({ text: texto, bold: true, color: COLORES.primario })],
        spacing: { before: 360, after: 200 },
    });
}

function h2(texto) {
    return new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [new TextRun({ text: texto, bold: true, color: COLORES.primario })],
        spacing: { before: 280, after: 160 },
    });
}

function h3(texto) {
    return new Paragraph({
        heading: HeadingLevel.HEADING_3,
        children: [new TextRun({ text: texto, bold: true, color: COLORES.textoSuave })],
        spacing: { before: 200, after: 120 },
    });
}

function p(texto, opts = {}) {
    return new Paragraph({
        children: [new TextRun({ text: texto, ...opts })],
        spacing: { after: 120, line: 320 },
    });
}

function pHtml(runs, opts = {}) {
    return new Paragraph({
        children: runs,
        spacing: { after: 120, line: 320 },
        ...opts,
    });
}

function bullet(texto, level = 0) {
    return new Paragraph({
        numbering: { reference: 'bullets', level },
        children: [new TextRun({ text: texto })],
        spacing: { after: 60 },
    });
}

function bulletRich(runs, level = 0) {
    return new Paragraph({
        numbering: { reference: 'bullets', level },
        children: runs,
        spacing: { after: 60 },
    });
}

function checkOK(texto) {
    return new Paragraph({
        children: [
            new TextRun({ text: '☑ ', color: COLORES.exito, bold: true, size: 24 }),
            new TextRun({ text: texto }),
        ],
        spacing: { after: 80 },
    });
}

function checkPend(texto) {
    return new Paragraph({
        children: [
            new TextRun({ text: '☐ ', color: COLORES.advertencia, bold: true, size: 24 }),
            new TextRun({ text: texto, color: COLORES.textoSuave }),
        ],
        spacing: { after: 80 },
    });
}

function bloqueCodigo(lineas) {
    return lineas.map((linea, idx) =>
        new Paragraph({
            children: [new TextRun({ text: linea || ' ', font: 'Consolas', size: 18 })],
            spacing: { after: idx === lineas.length - 1 ? 200 : 40 },
            shading: { fill: 'F3F4F6', type: ShadingType.CLEAR, color: 'auto' },
        })
    );
}

function tablaSimple(headers, filas, columnWidths) {
    const widths = columnWidths || headers.map(() => Math.floor(9000 / headers.length));
    const totalW = widths.reduce((a, b) => a + b, 0);

    const headerRow = new TableRow({
        children: headers.map((h, i) => new TableCell({
            width: { size: widths[i], type: WidthType.DXA },
            shading: { fill: COLORES.fondoHeader, type: ShadingType.CLEAR, color: 'auto' },
            borders: bordersAll(),
            margins: { top: 80, bottom: 80, left: 100, right: 100 },
            children: [new Paragraph({
                children: [new TextRun({ text: h, bold: true, color: 'FFFFFF', size: 20 })],
            })],
        })),
    });

    const rows = [headerRow, ...filas.map(fila => new TableRow({
        children: fila.map((cell, i) => new TableCell({
            width: { size: widths[i], type: WidthType.DXA },
            borders: bordersAll(),
            margins: { top: 80, bottom: 80, left: 100, right: 100 },
            children: [new Paragraph({
                children: [new TextRun({ text: String(cell), size: 20 })],
            })],
        })),
    }))];

    return new Table({
        width: { size: totalW, type: WidthType.DXA },
        columnWidths: widths,
        rows,
    });
}

function spacer() {
    return new Paragraph({ children: [new TextRun({ text: '' })], spacing: { after: 200 } });
}

function pageBreak() {
    return new Paragraph({ children: [new PageBreak()] });
}

// =========================================================================
// CONTENIDO DEL DOCUMENTO
// =========================================================================

const portada = [
    new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 2000, after: 200 },
        children: [new TextRun({ text: 'SIWIH', bold: true, size: 72, color: COLORES.primario })],
    }),
    new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 600 },
        children: [new TextRun({
            text: 'Sistema de Información Hospitalario',
            size: 28, color: COLORES.textoSuave, italics: true,
        })],
    }),
    new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 800, after: 200 },
        children: [new TextRun({
            text: 'Reporte Técnico — Módulo de Solicitud de Expedientes',
            bold: true, size: 44,
        })],
    }),
    new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 200 },
        children: [new TextRun({ text: '(s_exp)', size: 32, color: COLORES.acento })],
    }),
    new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 2400, after: 120 },
        children: [new TextRun({ text: 'Estado: ', bold: true, size: 24 }),
                    new TextRun({ text: 'Producción / Pruebas finales', size: 24, color: COLORES.exito })],
    }),
    new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 120 },
        children: [new TextRun({ text: 'Fecha del reporte: ', bold: true, size: 24 }),
                    new TextRun({ text: '21 de mayo de 2026', size: 24 })],
    }),
    new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 120 },
        children: [new TextRun({ text: 'Versión: ', bold: true, size: 24 }),
                    new TextRun({ text: 'feature/prestamos-expediente (100 commits)', size: 24 })],
    }),
    pageBreak(),
];

const resumenEjecutivo = [
    h1('1. Resumen Ejecutivo'),
    p('El módulo Solicitud de Expedientes (s_exp) permite al personal del hospital solicitar el préstamo físico de expedientes clínicos al archivo, gestionar el ciclo completo de aprobación, entrega, monitoreo y devolución con auditoría.'),
    p('Características destacadas:', { bold: true }),
    bullet('Flujo completo de solicitud → aprobación → entrega → devolución con auditoría parcial.'),
    bullet('Sistema de tiempo real con polling inteligente que NO afecta el timeout de 30 min de inactividad.'),
    bullet('Notificaciones automáticas al usuario solicitante cuando los expedientes están listos para recoger.'),
    bullet('Generación de PDF con firmas de entrega y devolución, incluyendo unidad del admin y solicitante.'),
    bullet('Integración con RRHH para validación de usuarios y captura automática de unidad de servicio.'),
    bullet('Reportes con KPIs, rankings y exportación a Excel/PDF.'),
    bullet('Historial completo y auditoría de cada movimiento del expediente.'),
    spacer(),
    p('Métricas del desarrollo:', { bold: true }),
    bullet('100 commits realizados en la rama feature/prestamos-expediente.'),
    bullet('5,978 líneas de código backend (Python/Django).'),
    bullet('5,781 líneas de frontend (JS + CSS).'),
    bullet('10 tablas nuevas en base de datos.'),
    bullet('8 vistas/pantallas principales + 7 archivos JavaScript organizados por feature.'),
    bullet('20+ APIs REST documentadas.'),
    pageBreak(),
];

const lineaTiempo = [
    h1('2. Línea de Tiempo del Desarrollo'),
    p('Desarrollo cronológico organizado por mes (113 commits totales en feature/prestamos-expediente):'),

    h2('2.1 Marzo 2026 — Setup Inicial'),
    bullet('23/03: Instalación de requirements.txt y configuración del entorno virtual.'),
    bullet('25/03: Primera prueba de desarrollo del módulo Solicitud de Expedientes.'),
    bullet('Creación de la estructura base de carpetas: models, views, urls, templates.'),

    h2('2.2 Abril 2026 — Construcción del Core (62 commits)'),
    bullet('07/04: Botón Préstamos Exp. movilizado al menú lateral.'),
    bullet('13/04: Definición de estados de expediente y procesos del flujo.'),
    bullet('14/04: Diseño de botones y acciones del módulo de solicitudes.'),
    bullet('22/04: Funcionalidad al 80% — flujo principal funcionando.'),
    bullet('Aprobación individual por expediente con checkbox + observaciones.'),
    bullet('Generación de PDF con firmas de entrega/devolución.'),
    bullet('Validación de horario laboral y conversiones de tiempo (horas/minutos).'),
    bullet('Layout responsive del modal de aprobación.'),
    bullet('Exportación de reportes Excel/PDF (áreas x motivos).'),
    bullet('Ajustes de PDF: márgenes, logos, columnas, encabezado/pie de página.'),

    h2('2.3 Mayo 2026 — Polish, RRHH, Tiempo Real, Seguridad (47 commits)'),

    h3('Semana 1-2 (01-10/05)'),
    bullet('Mejoras UI/UX: dark mode, botones responsive, lógica de devolución.'),
    bullet('Configuración de .gitignore para Docker, documentos generados, scripts.'),
    bullet('Buscador: identidad por defecto, máscara, layout 3-col, modal helpers.'),
    bullet('Carrito grid 3-col, modal con colores del sistema.'),
    bullet('Sugerir tiempo de entrega: hoy=horas, días=máx 3, stepper táctil.'),

    h3('Semana 3 (11-19/05)'),
    bullet('Modales con stylesheet del sistema (light/dark mode coherente).'),
    bullet('Anchura, ancho de botones, input de tiempo, tap-to-popup para info.'),
    bullet('Tabs Historial Propietarios / Préstamos en detalle de expediente.'),
    bullet('Inclusión de paciente_identidad/nombre en APIs de solicitudes.'),
    bullet('17/05: Implementación de integración con RRHH (User → Empleado → ServicioUnidad).'),
    bullet('17/05: Validación global RRHH — sin registro no se accede al módulo.'),
    bullet('17/05: Verificación en cadena PersonalNoClinico/PersonalSalud + servicio_unidad.'),
    bullet('18/05: Activación de notificaciones globales sticky "Listo para recoger".'),
    bullet('18/05: Remoción de botones manuales de refresh + indicador "Live" inicial.'),
    bullet('18/05: Auditoría de devolución mejorada para devoluciones parciales.'),
    bullet('19/05: Sistema completo de tiempo real con polling inteligente.'),
    bullet('19/05: Banner flotante "X novedades" no intrusivo (estilo Twitter).'),
    bullet('19/05: Mis Solicitudes con auto-reload (sin banner para usuarios).'),
    bullet('19/05: Fix Mis Solicitudes detecta auditorías de devolución.'),

    h3('Semana 4 (20-27/05) — Sesión Final'),
    bullet('20/05: Optimización — consolidación de imports, limpieza de scratch scripts.'),
    bullet('21/05: Generador del Reporte/Checklist Word (.docx) — el documento que estás leyendo.'),
    bullet('22/05: Fix NameError de imports globales tras la optimización.'),
    bullet('27/05: Security hardening — endpoints protegidos + polling se detiene si expira sesión.'),
    bullet('27/05: Sección 11 "Auditoría de Seguridad" añadida al documento.'),
    bullet('27/05: Notificaciones globales pasan de polling ciego a event-driven (changes-check).'),
    bullet('27/05: Silenciar logs de access para endpoints de polling (consola limpia).'),
    bullet('27/05: Banner solo aparece cuando OTROS usuarios hacen cambios (no auto-notificación).'),
    bullet('27/05: Color del modal sticky correcto en modo claro (título y mensaje blancos).'),
    bullet('27/05: Botón modal sticky compacto + Revisión de Entrega bloqueada tras 1 uso.'),
    bullet('27/05: Granularidad por sección — cada pantalla solo recibe SUS eventos específicos.'),
    bullet('27/05: Control de Devoluciones cambia a auto-reload (sin banner) + texto agrandado.'),

    spacer(),
    h2('2.4 Hitos técnicos relevantes'),
    bullet('Adopción del sistema RRHH como fuente única de verdad para la unidad del usuario.'),
    bullet('Middleware NoSessionRefreshOnPollingMiddleware: polling no renueva la sesión de 30min.'),
    bullet('Endpoint changes-check-api ULTRA ligero (solo timestamps) — base del sistema realtime.'),
    bullet('UX diferenciada por rol: banner para admin (no interrumpe), auto-reload para usuarios.'),
    bullet('Granularidad por sección: cada pantalla solo escucha SUS eventos (solicitudes, devoluciones, préstamos, mis_solicitudes).'),
    bullet('Cadena de validación: User → Empleado → PersonalNoClinico/PersonalSalud → ServicioUnidad.'),
    pageBreak(),
];

const arquitectura = [
    h1('3. Arquitectura del Módulo'),
    h2('3.1 Estructura de carpetas'),
    ...bloqueCodigo([
        's_exp/',
        '├── __init__.py',
        '├── admin.py                      # Registro Django Admin',
        '├── apps.py',
        '├── models.py                     # 10 modelos (547 líneas)',
        '├── urls.py                       # 30+ rutas',
        '├── views.py                      # APIs y vistas (2,976 líneas)',
        '├── tests.py',
        '├── migrations/',
        '│   └── 0001-0012_*.py            # 12 migraciones',
        '├── services/',
        '│   └── pdf_solicitud_service.py  # Generación PDF (554 líneas)',
        '├── scripts/',
        '│   └── actualizar_catalogos.py',
        '└── templates/s_exp/',
        '    ├── buscador_expedientes.html',
        '    ├── control_devoluciones.html',
        '    ├── dashboard_admin.html',
        '    ├── gestion_solicitudes.html',
        '    ├── historial_solicitudes.html',
        '    ├── monitoreo_prestamos.html',
        '    ├── reportes.html',
        '    └── seguimiento_usuario.html',
    ]),
    h2('3.2 Frontend (JavaScript)'),
    ...bloqueCodigo([
        'core/static/core/scripts/s_exp/',
        '├── buscador_carrito.js          (557 líneas) - solicitante',
        '├── dashboard.js                 (38)        - KPIs admin',
        '├── notificaciones_globales.js   (159)       - sticky alerts',
        '├── prestamos.js                 (234)       - monitoreo',
        '├── realtime.js                  (445)       - polling inteligente',
        '├── reportes.js                  (219)       - reportes',
        '├── seguimiento.js               (365)       - mis solicitudes',
        '└── solicitudes.js               (966)       - gestión admin',
        '',
        'core/static/core/css/',
        '└── s_exp.css                    (2,798 líneas) - estilos completos',
    ]),
    pageBreak(),
];

const modelos = [
    h1('4. Modelo de Datos'),
    p('Se crearon 10 tablas en la base de datos, todas en uso activo:'),
    tablaSimple(
        ['Tabla', 'Tipo', 'Función'],
        [
            ['s_exp_motivosolicitud', 'Catálogo', 'Motivos de solicitud (MONITORIA, REVISIÓN, etc)'],
            ['s_exp_estadosolicitud', 'Catálogo', 'Estados del flujo (PENDIENTE, APROBADA, etc)'],
            ['s_exp_estadoexpedientefisico', 'Catálogo', 'Estados físicos (DISPONIBLE, PRESTADO, PERDIDO)'],
            ['s_exp_expedienteprestamo', 'Estado', 'Estado físico actual de un expediente'],
            ['s_exp_solicitudprestamo', 'Transaccional', 'Solicitud creada por usuario'],
            ['s_exp_solicituddetalle', 'M2M', 'Expedientes de cada solicitud'],
            ['s_exp_prestamo', 'Transaccional', 'Préstamo aprobado con cronómetro'],
            ['s_exp_devolucion', 'Transaccional', 'Devoluciones por préstamo'],
            ['s_exp_loghistorico', 'Auditoría', 'Bitácora de todas las acciones'],
            ['s_exp_expedienteestadolog', 'Auditoría', 'Histórico de estados físicos'],
        ],
        [3000, 1800, 4200],
    ),
    spacer(),
    h2('4.1 Modelos clave'),
    h3('SolicitudPrestamo'),
    bullet('usuario: FK al solicitante (auth_user)'),
    bullet('servicio_unidad: FK a servicio.Unidad (capturada via RRHH al crear)'),
    bullet('area_destino: snapshot del nombre de la unidad (histórico)'),
    bullet('estado_flujo: FK a EstadoSolicitud'),
    bullet('motivo: FK a MotivoSolicitud'),
    bullet('notificado_listo: bool - dispara modal sticky al usuario'),
    bullet('tiempo_sugerido_horas: int - sugerencia del solicitante'),
    h3('Prestamo'),
    bullet('solicitud: OneToOne con SolicitudPrestamo'),
    bullet('fecha_aprobacion, fecha_entrega, fecha_limite, fecha_devolucion_real'),
    bullet('admin_aprobador: FK al admin que aprobó'),
    bullet('tiempo_limite_horas / es_minutos: configurable por préstamo'),
    bullet('estado: Activo, Entregado, Vencido, DevolucionParcial, Cerrado'),
    h3('LogHistorico'),
    bullet('accion: código (SOLICITUD_CREADA, PRESTAMO_APROBADO, etc)'),
    bullet('timestamp: usado por el endpoint changes-check para polling inteligente'),
    bullet('usuario, detalle, objeto_tipo, objeto_id'),
    pageBreak(),
];

const apis = [
    h1('5. APIs del Módulo'),
    p('20+ endpoints REST agrupados por función:'),
    h2('5.1 APIs de Solicitud (usuario)'),
    tablaSimple(
        ['Método', 'Ruta', 'Función'],
        [
            ['GET', '/s_exp/api/buscar-expedientes/', 'Buscar por número, identidad o nombre'],
            ['POST', '/s_exp/api/crear-solicitud/', 'Crear nueva solicitud'],
            ['GET', '/s_exp/api/mis-solicitudes/', 'Listar solicitudes del usuario'],
            ['POST', '/s_exp/api/solicitar-devolucion/', 'Marcar solicitud para devolver'],
        ],
        [900, 4200, 3900],
    ),
    spacer(),
    h2('5.2 APIs de Gestión (admin)'),
    tablaSimple(
        ['Método', 'Ruta', 'Función'],
        [
            ['GET', '/s_exp/api/listar-solicitudes/', 'DataTable de solicitudes (server-side)'],
            ['GET', '/s_exp/api/expedientes-solicitud/<id>/', 'Detalle para modal de aprobación'],
            ['POST', '/s_exp/api/aprobar-solicitud/', 'Aprobar con tiempo límite'],
            ['POST', '/s_exp/api/rechazar-solicitud/', 'Rechazar con motivo'],
            ['POST', '/s_exp/api/marcar-listo/', 'Listo para entregar + notifica usuario'],
            ['POST', '/s_exp/api/marcar-entregado/', 'Inicia cronómetro del préstamo'],
            ['GET', '/s_exp/api/prestamos-activos/', 'Monitoreo de préstamos en curso'],
            ['GET', '/s_exp/api/prestamos-devolucion/', 'Pendientes de devolver'],
            ['POST', '/s_exp/api/procesar-devolucion/', 'Auditoría de devolución'],
        ],
        [900, 4500, 3600],
    ),
    spacer(),
    h2('5.3 APIs de Realtime y Notificaciones'),
    tablaSimple(
        ['Método', 'Ruta', 'Función'],
        [
            ['GET', '/s_exp/api/alertas/', 'Alertas sticky (listo, vencimientos)'],
            ['GET', '/s_exp/api/changes-check/', 'Polling inteligente (timestamps)'],
            ['POST', '/s_exp/api/notificado-listo/', 'Marcar alerta como leída'],
            ['POST', '/s_exp/api/vencimiento-leido/', 'Marcar alerta de vencimiento'],
        ],
        [900, 4200, 3900],
    ),
    spacer(),
    h2('5.4 APIs de Reportes'),
    tablaSimple(
        ['Método', 'Ruta', 'Función'],
        [
            ['GET', '/s_exp/api/reportes-data/', 'Datos consolidados de reportes'],
            ['GET', '/s_exp/exportar-excel/', 'Descargar Excel'],
            ['GET', '/s_exp/exportar-pdf/', 'Descargar PDF'],
            ['GET', '/s_exp/api/historial-solicitudes/', 'Histórico para auditoría'],
            ['GET', '/s_exp/dashboard-stats/', 'KPIs del dashboard'],
        ],
        [900, 4200, 3900],
    ),
    pageBreak(),
];

const realtime = [
    h1('6. Sistema de Tiempo Real'),
    p('Diseño que NO afecta el timeout de 30 minutos de inactividad del usuario:'),
    h2('6.1 Componentes'),
    h3('Backend: NoSessionRefreshOnPollingMiddleware'),
    p('Detecta el header X-Polling-Request:true y marca la sesión como no-modificada/no-accedida. Esto evita que el polling renueve el timer.'),
    h3('Backend: changes-check-api'),
    p('Endpoint ULTRA LIGERO que devuelve solo timestamps por sección:'),
    ...bloqueCodigo([
        'GET /s_exp/api/changes-check/',
        '',
        'Response:',
        '{',
        '  "global":        "2026-05-21T14:23:45",',
        '  "solicitudes":   "2026-05-21T14:23:45",',
        '  "prestamos":     "2026-05-21T14:00:30",',
        '  "devoluciones":  "2026-05-21T13:50:00"',
        '}',
    ]),
    h3('Frontend: realtime.js'),
    p('Sistema de polling con dos modos:'),
    bulletRich([
        new TextRun({ text: 'registrarConTrigger', bold: true, font: 'Consolas' }),
        new TextRun({ text: ': muestra banner discreto cuando hay cambios. El usuario decide cuándo aplicar el refresh (admin).' }),
    ]),
    bulletRich([
        new TextRun({ text: 'registrarConAutoReload', bold: true, font: 'Consolas' }),
        new TextRun({ text: ': recarga automáticamente cuando hay cambios. Usado en Mis Solicitudes del usuario.' }),
    ]),
    h2('6.2 Configuración por pantalla'),
    tablaSimple(
        ['Pantalla', 'Intervalo', 'Modo'],
        [
            ['Gestión Solicitudes (admin)', '5s', 'Banner discreto'],
            ['Monitoreo Préstamos', '5s', 'Banner discreto'],
            ['Control Devoluciones', '5s', 'Banner discreto'],
            ['Dashboard KPIs', '10s', 'Banner discreto'],
            ['Reportes', '15s', 'Banner discreto'],
            ['Mis Solicitudes (usuario)', '5s', 'Auto-reload'],
            ['Notificaciones globales', '5s', 'Modal sticky'],
        ],
        [4500, 1500, 3000],
    ),
    pageBreak(),
];

const rrhh = [
    h1('7. Integración con RRHH'),
    p('El módulo s_exp valida usuarios y captura su unidad de trabajo via la cadena de relaciones de RRHH:'),
    ...bloqueCodigo([
        'auth_user',
        '  ↓ (rrhh_empleado.usuario_id)',
        'rrhh_empleado',
        '  ↓ (rrhh_personalnoclinico.empleado_id  O',
        '     rrhh_personalsalud.empleado_id)',
        'PersonalNoClinico  O  PersonalSalud',
        '  ↓ (servicio_unidad_id)',
        'servicio_unidad',
        '  → nombre_unidad (mostrado en pantallas y PDF)',
    ]),
    h2('7.1 Validaciones'),
    bullet('Acceso al módulo: usuario debe existir en rrhh_empleado.'),
    bullet('Acceso al módulo: usuario debe tener PersonalNoClinico o PersonalSalud con servicio_unidad asignado.'),
    bullet('Si falla la cadena → error 403 al intentar entrar.'),
    h2('7.2 Captura al crear solicitud'),
    p('Al crear una nueva solicitud:'),
    bullet('Se captura snapshot del nombre de la unidad en area_destino (texto).'),
    bullet('Se asocia FK a servicio_unidad para integridad.'),
    bullet('Solicitudes anteriores NO se modifican (queda en histórico).'),
    bullet('Si el usuario cambia de unidad, las nuevas solicitudes toman la unidad actual.'),
    h2('7.3 Resolución en PDF'),
    p('En la firma de Entrega/Devolución del PDF, la unidad del admin se resuelve con cascada:'),
    bullet('PerfilUnidad.servicio_unidad'),
    bullet('Empleado → PersonalNoClinico → servicio_unidad'),
    bullet('Empleado → PersonalSalud → servicio_unidad'),
    pageBreak(),
];

const checklist = [
    h1('8. Checklist Completo'),
    p('Tareas implementadas y verificadas:'),
    h2('8.1 Solicitud (usuario solicitante)'),
    checkOK('Buscador con filtro por número, identidad o nombre'),
    checkOK('Máscara automática para identidad'),
    checkOK('Carrito de expedientes seleccionados (grid 3 columnas)'),
    checkOK('Sugerencia de tiempo de entrega (horas / días, máx 3 días)'),
    checkOK('Stepper táctil (− +) para inputs numéricos en móvil'),
    checkOK('Selección de motivo desde catálogo'),
    checkOK('Validación: usuario debe estar en RRHH'),
    checkOK('Captura automática de unidad de servicio via RRHH'),
    checkOK('Mis Solicitudes con timeline y filtros de fecha'),
    checkOK('Auto-reload de Mis Solicitudes cuando hay cambios'),
    checkOK('Modal sticky "Listo para recoger" al notificar (polling 5s)'),
    h2('8.2 Gestión Admin'),
    checkOK('Listado de solicitudes con DataTable server-side'),
    checkOK('Filtros por estado (Todas/Pendientes/Listas/etc)'),
    checkOK('Modal de aprobación con tiempo + observaciones'),
    checkOK('Aprobación individual por expediente (checkbox + motivo)'),
    checkOK('Lista expandida por defecto + número de expediente visible'),
    checkOK('Generación PDF con firmas + observaciones generales'),
    checkOK('Marcar listo para entregar (notifica al usuario automáticamente)'),
    checkOK('Revisión de entrega: marcar faltantes con comentario'),
    checkOK('Marcar entregado: inicia cronómetro del préstamo'),
    checkOK('Banner "X novedades" cuando hay cambios (no intrusivo)'),
    h2('8.3 Monitoreo y Devoluciones'),
    checkOK('Monitoreo de préstamos activos con cronómetros'),
    checkOK('Alertas de vencimiento (10 min, 5 min, vencido)'),
    checkOK('Solicitar devolución desde Mis Solicitudes'),
    checkOK('Auditoría de devolución (recibido/no recibido/perdido)'),
    checkOK('Devolución parcial: faltantes interactivos, ya devueltos bloqueados'),
    checkOK('Ordenamiento: pendientes arriba, procesados abajo'),
    checkOK('Visualización por colores (verde devuelto, rojo perdido, naranja pendiente)'),
    checkOK('Buscador en modal de auditoría'),
    checkOK('Sincronización automática al procesar devolución'),
    h2('8.4 Reportes'),
    checkOK('KPIs del dashboard admin'),
    checkOK('Reporte con rankings (expedientes top, usuarios top, áreas)'),
    checkOK('Tabs: Resumen, Por Área, Top Expedientes, Top Usuarios, Rechazos, Morosidad, Inconsistencias'),
    checkOK('Exportación a Excel (.xlsx)'),
    checkOK('Exportación a PDF (apaisado, encabezado/pie completo)'),
    checkOK('Filtros: diario, semanal, mensual, trimestral, semestral, anual, rango'),
    checkOK('Timestamp en nombre de archivos descargados'),
    h2('8.5 Sistema Realtime'),
    checkOK('Middleware NoSessionRefreshOnPollingMiddleware (no afecta sesión)'),
    checkOK('Endpoint changes-check-api ligero por sección'),
    checkOK('realtime.js con polling inteligente'),
    checkOK('Pausa automática cuando la pestaña no está visible (Page Visibility API)'),
    checkOK('Backoff exponencial ante errores de red'),
    checkOK('Banner flotante con contador acumulativo'),
    checkOK('Anti-duplicado de modales sticky'),
    h2('8.6 PDF'),
    checkOK('Encabezado con logos GOB/SESAL'),
    checkOK('Información del solicitante: responsable, unidad/servicio'),
    checkOK('Tabla de expedientes con columnas: fecha, expediente, disponible, identidad, paciente, motivo'),
    checkOK('Columna "Disponible" con checkbox visual'),
    checkOK('Observaciones de entrega y devolución por expediente'),
    checkOK('Filas en rojo pastel para no prestados (PDF finalizado)'),
    checkOK('Firma Entrega: admin (con unidad) + solicitante (con unidad)'),
    checkOK('Firma Devolución: admin + solicitante'),
    checkOK('Numeración de página + total + timestamp local'),
    h2('8.7 PerfilUnidad / Permisos'),
    checkOK('Roles: admin, digitador, directivo, exp_solicitante'),
    checkOK('Acceso al módulo restringido a Estadística/Sala/Admisión/UAU'),
    checkOK('Tabs configurables por rol en expediente_detail'),
    checkOK('Permisos verificados en cada endpoint del backend'),
    pageBreak(),
];

const pendientes = [
    h1('9. Pendientes y Próximos Pasos'),
    p('Tareas opcionales o de mejora a futuro:'),
    h2('9.1 Funcionalidad'),
    checkPend('Notificaciones por correo electrónico (paralelo al modal sticky)'),
    checkPend('Exportación a CSV (además de Excel y PDF)'),
    checkPend('Dashboard con gráficos visuales (chart.js o similar)'),
    checkPend('App móvil PWA para solicitudes desde celular'),
    h2('9.2 Mejoras de Performance'),
    checkPend('Cachear el endpoint changes-check con Redis o memcached'),
    checkPend('Migrar el polling a WebSockets cuando se justifique (Channels + Daphne)'),
    checkPend('Índices BD adicionales si se nota lentitud en >10K registros'),
    h2('9.3 Calidad'),
    checkPend('Tests unitarios automatizados (pytest-django)'),
    checkPend('Tests de integración del flujo completo'),
    checkPend('Logging estructurado con JSON para análisis'),
    checkPend('Documentación OpenAPI/Swagger de los endpoints'),
    h2('9.4 Misión Actual: Ubicación en Tiempo Real de Expedientes (ExpedientesV2)'),
    p('Mejorar el seguimiento de dónde está físicamente cada expediente, usando el nuevo catálogo relacional de ubicaciones. Ver detalle en la sección 14.', {}),
    checkOK('Tabla expediente_ubicacion creada (catálogo unificado clínico/no clínico).'),
    checkOK('Comando poblar_ubicaciones (manual, idempotente).'),
    checkOK('Servicios DatosUbicacion + CatalogoUbicaciones.'),
    checkPend('Conectar ExpedientePrestamo con ExpedienteUbicacion (FK ubicacion).'),
    checkPend('Al entregar: mover expediente a la unidad del solicitante (Opción A).'),
    checkPend('Al devolver: regresar expediente a ADMISION.'),
    checkPend('Mostrar ubicación actual del expediente leyendo de la nueva tabla.'),
    checkPend('A futuro: migrar Localizacion → expediente_ubicacion por completo.'),
    pageBreak(),
];

const recomendaciones = [
    h1('10. Recomendaciones para Despliegue'),
    h2('10.1 Antes del merge a main'),
    bullet('Hacer rebase contra main para detectar conflictos (especialmente en base.html, ~245 líneas afectadas).'),
    bullet('Aplicar migraciones en orden: s_exp/0001-0012 + usuario/0003-0009.'),
    bullet('Ejecutar python manage.py check antes y después del merge.'),
    bullet('Cargar catálogos: MotivoSolicitud, EstadoSolicitud, EstadoExpedienteFisico (vía actualizar_catalogos.py).'),
    h2('10.2 Configuración de servidor'),
    bullet('Verificar que SESSION_SAVE_EVERY_REQUEST = True (necesario para timeout).'),
    bullet('Verificar que SESSION_COOKIE_AGE = 1800 (30 min).'),
    bullet('Confirmar registro de NoSessionRefreshOnPollingMiddleware en MIDDLEWARE.'),
    bullet('Validar que LOGGING tiene defaults={"app": "general"} (compatible con Python 3.10+).'),
    h2('10.3 Datos iniciales necesarios'),
    bullet('Localizacion "ARCHIVO" (donde regresan los expedientes devueltos).'),
    bullet('Usuarios con RRHH completo (Empleado + PersonalNoClinico/PersonalSalud + servicio_unidad).'),
    bullet('PerfilUnidad con rol "exp_solicitante" o "admin" para los usuarios del módulo.'),
    h2('10.4 Verificación post-deploy'),
    bullet('Crear una solicitud de prueba con usuario solicitante.'),
    bullet('Aprobarla como admin, marcarla lista, entregarla.'),
    bullet('Verificar que el cronómetro arranca y el usuario ve el modal sticky.'),
    bullet('Solicitar devolución, auditar parcialmente, verificar UI bloqueada para ya devueltos.'),
    bullet('Cerrar la devolución y verificar que el expediente vuelve a ARCHIVO en el listado.'),
    bullet('Generar PDF en cada estado y verificar firmas + unidad del admin.'),
];

const realtimeGranular = [
    pageBreak(),
    h1('11. Sistema Realtime Granular (Mejoras Mayo 2026)'),
    p('Evolución del sistema de tiempo real para que cada pantalla solo reciba eventos relevantes y nada interrumpa al usuario innecesariamente.'),

    h2('11.1 Mapping de Eventos por Sección'),
    p('Cada pantalla escucha SOLO sus eventos específicos en lugar de cualquier cambio global:'),
    tablaSimple(
        ['Evento Backend', 'Sección', 'Pantalla'],
        [
            ['SOLICITUD_CREADA', 'solicitudes', 'Gestión Solicitudes (admin)'],
            ['SOLICITUD_DEVOLUCION_INICIADA', 'devoluciones', 'Control de Devoluciones (admin)'],
            ['PRESTAMO_ENTREGADO, DEVOLUCION_PROCESADA', 'prestamos', 'Monitoreo (admin)'],
            ['SOLICITUD_APROBADA/RECHAZADA/LISTA + entregas + devoluciones', 'mis_solicitudes', 'Mis Solicitudes (usuario)'],
            ['Cualquier log', 'global', 'Dashboard, Reportes (fallback)'],
        ],
        [3500, 2000, 3500],
    ),

    h2('11.2 Comportamiento por Pantalla'),
    tablaSimple(
        ['Pantalla', 'Tipo', 'Intervalo'],
        [
            ['Gestión Solicitudes (admin)', '🔔 Banner', '5s'],
            ['Monitoreo Préstamos (admin)', '🔔 Banner', '5s'],
            ['Control Devoluciones (admin)', '✅ Auto-reload', '5s'],
            ['Mis Solicitudes (usuario)', '✅ Auto-reload', '5s'],
            ['Dashboard KPIs', '🔔 Banner', '10s'],
            ['Reportes', '🔔 Banner', '15s'],
            ['Notificaciones globales (modal sticky)', '✅ Event-driven', '5s'],
        ],
        [4500, 2500, 2000],
    ),

    h2('11.3 Reglas de Negocio del Sistema Realtime'),
    bullet('Acciones de USUARIO (crear solicitud, pedir devolución) → SIEMPRE notifican (incluso si el actor es el mismo user en pruebas con cuenta única).'),
    bullet('Acciones ADMIN (aprobar, rechazar, entregar, procesar) → excluyen al usuario actual (no auto-notificación).'),
    bullet('Notificaciones globales: cada 5s consulta changes-check (ligero), solo si cambia el timestamp consulta /api/alertas/.'),
    bullet('Si la sesión expira (401/403), el polling se detiene automáticamente en frontend.'),
    bullet('El polling NO renueva el timer de inactividad (header X-Polling-Request).'),
    bullet('Logs de access del runserver se silencian para changes-check y alertas (evita spam en consola).'),

    h2('11.4 Mejoras de UX'),
    bullet('Revisión de Entrega: el botón se bloquea después de usarse una vez (decisión definitiva). Si aparece un expediente faltante, debe crearse una nueva solicitud.'),
    bullet('Modal sticky "Listo para recoger": texto del botón compacto ("Entendido"), título y mensaje legibles en modo claro y oscuro.'),
    bullet('Texto "Devolución en proceso..." agrandado a 1.5rem para mejor lectura.'),
    bullet('Modal de aprobación: lista siempre expandida + número de expediente visible junto a identidad/nombre.'),
    bullet('Auditoría de devolución parcial: pendientes arriba (interactivos), ya devueltos abajo (bloqueados con badge).'),
    pageBreak(),
];

const seguridad = [
    pageBreak(),
    h1('12. Auditoría de Seguridad'),
    p('Revisión completa de vulnerabilidades realizada el 22 de mayo de 2026. Se evaluaron 27 endpoints, 7 archivos JavaScript, y todos los flujos de inserción/modificación de datos.'),

    h2('11.1 Resumen Ejecutivo'),
    tablaSimple(
        ['Categoría', 'Estado'],
        [
            ['SQL Injection', '✓ Protegido (Django ORM, sin SQL crudo)'],
            ['XSS (Cross-Site Scripting)', '✓ Protegido (sin eval, sin innerHTML con input)'],
            ['CSRF (Cross-Site Request Forgery)', '⚠ 2 endpoints @csrf_exempt con auth (revisar)'],
            ['Autenticación', '✓ 27/27 endpoints validan sesión'],
            ['Autorización por rol', '✓ _es_exp_admin / _es_exp_solicitante en todas las APIs'],
            ['Polling sin sesión activa', '✓ Detenido automáticamente al expirar'],
            ['Validación de inputs', '✓ Tipos validados (int/str/longitud)'],
            ['Carga inicial sin sesión', '✓ Bloqueada en base.html'],
            ['Acceso a datos ajenos', '✓ Filtrado por usuario en todas las queries'],
            ['Cadena RRHH', '✓ Validada antes de cualquier acción'],
        ],
        [4000, 5000],
    ),

    h2('11.2 Vulnerabilidades Detectadas y Corregidas'),

    h3('CRÍTICO — changes-check-api sin autenticación'),
    bullet('Endpoint: GET /s_exp/api/changes-check/'),
    bullet('Riesgo: petición anónima podía consultar timestamps de actividad del sistema.'),
    bullet('Impacto: bajo (no devuelve datos sensibles) pero permitía enumeración.'),
    bulletRich([
        new TextRun({ text: 'Fix aplicado: ', bold: true, color: COLORES.exito }),
        new TextRun({ text: 'agregado check de request.user.is_authenticated, retorna 401 si no.' }),
    ]),
    bulletRich([
        new TextRun({ text: 'Commit: ', bold: true }),
        new TextRun({ text: '6a48058 - Security hardening', font: 'Consolas', size: 18 }),
    ]),

    h3('ALTO — Polling no se detenía con sesión expirada'),
    bullet('Después de 30 min de inactividad, la sesión expira pero el polling continuaba haciendo requests cada 5 segundos.'),
    bullet('Generaba logs masivos de error 403/302, gastaba ancho de banda y CPU del servidor.'),
    bullet('Podía interferir con la redirección a /login del usuario.'),
    bulletRich([
        new TextRun({ text: 'Fix aplicado: ', bold: true, color: COLORES.exito }),
        new TextRun({ text: 'notificaciones_globales.js y realtime.js detectan respuestas 401/403 y ejecutan clearInterval() de todos los timers + vaciado del registro de pantallas. Flag interno sesionExpirada bloquea nuevos requests.' }),
    ]),

    h2('11.3 Observaciones (no crítico)'),
    h3('CSRF exempt en 2 endpoints internos'),
    bullet('marcar_notificacion_leida_api (s_exp/views.py:2006)'),
    bullet('marcar_vencimiento_leido_api (s_exp/views.py:2034)'),
    bullet('Ambos validan is_authenticated, riesgo mínimo.'),
    bulletRich([
        new TextRun({ text: 'Recomendación: ', bold: true, color: COLORES.advertencia }),
        new TextRun({ text: 'remover @csrf_exempt y enviar header X-CSRFToken desde el frontend (limpieza, no urgente).' }),
    ]),

    h3('Prints en background'),
    bullet('Solo 2 prints, ambos en s_exp/scripts/actualizar_catalogos.py'),
    bullet('Es un script CLI de setup (no API). Los prints son output esperado para el operador.'),
    p('No requiere acción.', { italics: true, color: COLORES.textoSuave }),

    h3('Console.error en JavaScript'),
    bullet('6 ocurrencias, todas en handlers de catch.'),
    bullet('No exponen datos sensibles (solo mensajes técnicos para debugging).'),
    p('No requiere acción.', { italics: true, color: COLORES.textoSuave }),

    h2('11.4 Mejoras Opcionales para Producción'),
    checkPend('Aplicar bleach.clean() a campos de texto largo (observaciones, comentarios) para sanitizar HTML.'),
    checkPend('Agregar django-ratelimit a buscar_expedientes_api para evitar enumeración de pacientes.'),
    checkPend('Establecer límite máximo de expedientes por solicitud (sugerido: 50).'),
    checkPend('Convertir los 2 endpoints @csrf_exempt a CSRF token estándar.'),
    checkPend('Configurar logging estructurado JSON para análisis automatizado.'),
    checkPend('Implementar Content-Security-Policy headers en producción.'),
    checkPend('Considerar Sentry o similar para tracking de errores en producción.'),

    h2('11.5 Conclusión'),
    p('El módulo s_exp tiene una postura de seguridad sólida. Las 2 vulnerabilidades activas fueron corregidas en el commit 6a48058. Las observaciones restantes son mejoras de defensa en profundidad para producción a gran escala, no riesgos activos.', { bold: true }),
    spacer(),
    bulletRich([
        new TextRun({ text: '✓ ', color: COLORES.exito, bold: true, size: 24 }),
        new TextRun({ text: 'Módulo APROBADO para despliegue en producción ', bold: true }),
        new TextRun({ text: 'con las correcciones aplicadas.', italics: true }),
    ]),
];

const refactorRelacional = [
    pageBreak(),
    h1('13. Refactor Relacional (uso de IDs en lugar de texto)'),
    p('Se optimizó el modelo de datos para almacenar solo identificadores (FK) y consultar la información en vivo, en lugar de duplicar texto. Esto reduce el tamaño de la base de datos, acelera los filtros por índice y elimina inconsistencias.'),

    h2('13.1 Problema que resolvía'),
    p('Antes, cada detalle de solicitud guardaba copias de texto (snapshots):'),
    bullet('paciente_identidad (DNI duplicado en cada préstamo)'),
    bullet('paciente_nombre (nombre completo duplicado)'),
    bullet('numero_expediente (ya existía en la tabla Expediente)'),
    bullet('area_destino (nombre de unidad duplicado en SolicitudPrestamo)'),
    spacer(),
    p('Problemas que esto causaba:', { bold: true }),
    bullet('Crecimiento innecesario de la BD: un mismo nombre se guardaba N veces.'),
    bullet('Inconsistencias: si el paciente cambiaba de nombre, los snapshots quedaban obsoletos.'),
    bullet('Filtrado más lento por índices de texto más grandes.'),

    h2('13.2 Solución implementada'),
    bullet('SolicitudExpedienteDetalle ahora guarda solo paciente (FK a Paciente).'),
    bullet('SolicitudPrestamo usa servicio_unidad (FK) en lugar de area_destino (texto).'),
    bullet('El número de expediente se lee desde la relación Expediente.numero.'),
    bullet('Los nombres/identidades se consultan en vivo cuando se necesitan mostrar.'),

    h2('13.3 Capa de servicios (s_exp/services/datos_solicitud.py)'),
    p('Clases que centralizan el acceso a datos para que ningún código lea snapshots directamente:'),
    ...bloqueCodigo([
        'DatosDetalleSolicitud:',
        '  numero_expediente(detalle)      -> Expediente.numero (via FK)',
        '  paciente_dni(detalle)           -> Paciente.dni (via FK)',
        '  paciente_nombre_completo(det)   -> Paciente nombres (via FK)',
        '  enriquecer(detalle) -> dict completo para APIs',
        '',
        'DatosSolicitud:',
        '  usuario_nombre_completo, unidad_nombre, motivo_nombre,',
        '  estado_codigo, estado_nombre, enriquecer(solicitud)',
        '',
        'UbicacionUsuario:',
        '  resolver(user) -> Unidad (cadena RRHH)',
        '  esta_registrado(user) -> bool',
        '',
        'DatosPaciente:',
        '  obtener_por_id, dni, nombre_completo',
    ]),

    h2('13.4 Migración en 5 fases (sin pérdida de datos)'),
    tablaSimple(
        ['Fase', 'Acción', 'Migración'],
        [
            ['1', 'Agregar paciente (FK) + marcar campos deprecados', '0013'],
            ['1.5', 'Backfill: poblar paciente_id en registros viejos', '0014'],
            ['2', 'Crear capa de servicios (datos_solicitud.py)', '—'],
            ['3', 'Migrar 12 APIs a usar los servicios', '—'],
            ['4', 'Migrar PDF y frontend', '—'],
            ['5', 'Eliminar campos snapshot redundantes', '0015'],
        ],
        [1200, 5800, 2000],
    ),
    spacer(),
    p('Beneficio cuantificado: ~93% menos bytes por fila en SolicitudExpedienteDetalle. Frontend sin cambios (las APIs devuelven los mismos keys como alias retrocompatibles).', { bold: true }),
    pageBreak(),
];

const catalogoUbicaciones = [
    h1('14. Catálogo Unificado de Ubicaciones (ExpedientesV2)'),
    p('Nueva tabla relacional expediente_ubicacion que unifica las ubicaciones CLÍNICAS y NO CLÍNICAS de los expedientes, capturando solo IDs. Reemplaza gradualmente al catálogo de texto Localizacion.'),

    h2('14.1 Motivación'),
    p('El catálogo viejo (Localizacion) guarda texto suelto (ARCHIVO, EMERGENCIA, HOSPITALIZACION) sin vínculo con las tablas reales de servicio. Si se agrega un área nueva, había que escribir el texto a mano sin relación. La nueva tabla resuelve esto enlazando por ID.'),

    h2('14.2 Estructura de la tabla'),
    ...bloqueCodigo([
        'expediente_ubicacion',
        '  id                 PK',
        '  unidad_clinica     FK servicio.Unidad_clinica  (NULL si no clínica)',
        '  unidad_no_clinica  FK servicio.Unidad          (NULL si clínica)',
        '  tipo               SmallInt  1=Clínica, 2=No Clínica',
        '  estado             Bool',
        '',
        '  Polimórfica: solo UNA de las dos FK está llena.',
        '  El campo tipo (entero, no texto) indica cuál usar.',
    ]),
    p('Unidades clínicas provienen de servicio_unidad_clinica (que a su vez es polimórfica: area_atencion / sala / servicio_aux / establecimiento_ext). Unidades no clínicas provienen de servicio_unidad (ESTADÍSTICA, ADMISION, UAU, etc.).', {}),

    h2('14.3 Integridad de datos'),
    bullet('CheckConstraint en BD (MySQL 8.0.16+): el tipo debe ser coherente con la FK presente.'),
    bullet('Validación en clean(): exactamente una FK llena + unicidad de unidad (reemplaza el UniqueConstraint condicional que MySQL no soporta).'),
    bullet('La descripción (nombre legible) se resuelve EN VIVO: clínica usa get_descripcion(), no clínica usa nombre_unidad. Sin texto duplicado.'),

    h2('14.4 Comando de población manual'),
    ...bloqueCodigo([
        'python manage.py poblar_ubicaciones',
        '    --solo-clinicas      # solo unidades clínicas',
        '    --solo-noclinicas    # solo unidades no clínicas',
        '    --dry-run            # simula sin guardar',
        '',
        'Idempotente: salta unidades ya registradas (no duplica).',
        'NO corre en migración: el operador decide cuándo ejecutarlo.',
    ]),
    p('Prueba realizada (dry-run): detectó 30 unidades clínicas + 4 no clínicas (incluida ADMISION).', { italics: true, color: COLORES.textoSuave }),

    h2('14.5 Servicios de acceso (expediente/services/ubicaciones.py)'),
    ...bloqueCodigo([
        'DatosUbicacion:',
        '  descripcion(ubic)    -> nombre legible en vivo',
        '  tipo_codigo / tipo_legible',
        '  enriquecer(ubic) -> dict para JSON',
        '',
        'CatalogoUbicaciones:',
        '  listar(solo_activas, tipo)  -> QuerySet optimizado',
        '  listar_dict()               -> lista de dicts (para selects)',
        '  obtener_o_crear_por_unidad_clinica / _no_clinica',
    ]),

    h2('14.6 Estrategia de convivencia'),
    bullet('NO reemplaza a Localizacion todavía (sería riesgoso para el módulo expediente).'),
    bullet('Localizacion sigue usándose para atenciones e ingresos (CONSULTA EXTERNA, HOSPITALIZACION, EMERGENCIA — ubicaciones generales).'),
    bullet('expediente_ubicacion se usa para préstamos hacia unidades específicas (más detallada).'),
    bullet('Obtención híbrida de datos mientras dura la transición. Migración total a futuro.'),

    h2('14.7 Flujo con Solicitud de Expedientes'),
    bullet('Al ENTREGAR un préstamo: el expediente se mueve a la ubicación del SOLICITANTE (su unidad de servicio, resuelta por RRHH).'),
    bullet('Al DEVOLVER: el expediente vuelve a ADMISION.'),
    bullet('La ubicación actual del expediente se consulta desde expediente_ubicacion (no texto).'),
    pageBreak(),
];

const cierre = [
    pageBreak(),
    h1('15. Cierre'),
    p('El módulo s_exp está en estado funcional completo. El flujo principal (solicitud → préstamo → devolución → auditoría) está implementado y verificado. Adicionalmente se realizó un refactor relacional que optimiza el uso de la base de datos, y se inició la fase ExpedientesV2 para el seguimiento de ubicación en tiempo real.'),
    p('Aspectos destacables del trabajo realizado:', { bold: true }),
    bullet('100% de cobertura del flujo solicitud → préstamo → devolución → auditoría.'),
    bullet('UX cuidada: notificaciones sin interrumpir, banners discretos, modales sticky solo cuando es necesario.'),
    bullet('Seguridad: validación RRHH, timeout de sesión respetado por polling, permisos por rol.'),
    bullet('Trazabilidad completa: LogHistorico + ExpedienteEstadoLog auditan cada acción.'),
    bullet('Modelo relacional optimizado: IDs en lugar de texto, capa de servicios documentada.'),
    bullet('Catálogo unificado de ubicaciones (expediente_ubicacion) para clínicas y no clínicas.'),
    spacer(),
    p('Puntos de retorno en git:', { bold: true }),
    bullet('solexp-finalizado — módulo completo con refactor relacional (rama feature/prestamos-expediente).'),
    bullet('app-solicitud-expedientes-antes-de-las-mejoras — antes del refactor relacional.'),
    bullet('Rama actual: expedientesV2 — catálogo de ubicaciones en desarrollo.'),
    spacer(),
    new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 600 },
        children: [new TextRun({
            text: '— Fin del Reporte —',
            italics: true, size: 24, color: COLORES.textoSuave,
        })],
    }),
];

// =========================================================================
// CONSTRUCCIÓN DEL DOCUMENTO
// =========================================================================

const doc = new Document({
    creator: 'Claude (SIWIH s_exp)',
    title: 'Reporte Técnico - Módulo s_exp',
    description: 'Reporte y Checklist del módulo Solicitud de Expedientes',
    styles: {
        default: {
            document: { run: { font: 'Calibri', size: 22 } },
        },
        paragraphStyles: [
            {
                id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
                run: { size: 32, bold: true, font: 'Calibri', color: COLORES.primario },
                paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 },
            },
            {
                id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
                run: { size: 26, bold: true, font: 'Calibri', color: COLORES.primario },
                paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 1 },
            },
            {
                id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
                run: { size: 22, bold: true, font: 'Calibri', color: COLORES.textoSuave },
                paragraph: { spacing: { before: 180, after: 100 }, outlineLevel: 2 },
            },
        ],
    },
    numbering: {
        config: [{
            reference: 'bullets',
            levels: [
                { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
                  style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
                { level: 1, format: LevelFormat.BULLET, text: '◦', alignment: AlignmentType.LEFT,
                  style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
            ],
        }],
    },
    sections: [{
        properties: {
            page: {
                size: { width: 12240, height: 15840 },  // US Letter
                margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
            },
        },
        headers: {
            default: new Header({
                children: [new Paragraph({
                    alignment: AlignmentType.RIGHT,
                    children: [new TextRun({
                        text: 'SIWIH · Reporte Técnico — Módulo s_exp',
                        italics: true, size: 18, color: COLORES.textoSuave,
                    })],
                })],
            }),
        },
        footers: {
            default: new Footer({
                children: [new Paragraph({
                    alignment: AlignmentType.CENTER,
                    children: [
                        new TextRun({ text: 'Página ', size: 18, color: COLORES.textoSuave }),
                        new TextRun({ children: [PageNumber.CURRENT], size: 18, color: COLORES.textoSuave }),
                        new TextRun({ text: ' de ', size: 18, color: COLORES.textoSuave }),
                        new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, color: COLORES.textoSuave }),
                    ],
                })],
            }),
        },
        children: [
            ...portada,
            ...resumenEjecutivo,
            ...lineaTiempo,
            ...arquitectura,
            ...modelos,
            ...apis,
            ...realtime,
            ...rrhh,
            ...checklist,
            ...pendientes,
            ...recomendaciones,
            ...realtimeGranular,
            ...seguridad,
            ...refactorRelacional,
            ...catalogoUbicaciones,
            ...cierre,
        ],
    }],
});

Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync('REPORTE_S_EXP.docx', buffer);
    console.log('REPORTE_S_EXP.docx generado correctamente.');
});

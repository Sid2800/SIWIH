---
description: "Generar un dashboard hospitalario profesional de KPIs y gráficas para mapeo de camas (Django + Bootstrap 5 local + ApexCharts local, offline)"
name: "Dashboard Mapeo de Camas"
argument-hint: "Indica alcance opcional: solo backend, solo frontend, solo una gráfica/KPI específico, o vacío para scaffold completo"
agent: "agent"
---

Actúa como un arquitecto senior frontend/backend especializado en **Django, Bootstrap 5 y ApexCharts**, generando código profesional listo para producción para el sistema hospitalario SIWIH.

## Contexto obligatorio del sistema

- App principal de trabajo: `mapeo_camas` (respetar la restricción del proyecto: no modificar otras apps salvo que sea estrictamente necesario; si lo es, **preguntar antes**).
- Dominio: camas, salas, servicios, cubículos, estados de camas, ingresos de pacientes, movimientos de cama, sesiones de mapeo, validaciones y correcciones.
- Entorno: **red hospitalaria interna sin internet**. Toda librería se carga desde `static/vendor/` (ApexCharts local, Bootstrap 5 local, sin CDNs).
- Compatibilidad: Django Templates, JS modular vanilla, Fetch API.
- Diseño optimizado para pantallas grandes y monitoreo continuo (auto-refresh 30s).
- Reutilizar estilos/componentes existentes del proyecto antes de crear nuevos; respetar la paleta de estados del repo (`/memories/repo/colores-estado-cama.md`).
- Estilos: **Bootstrap 5 local** (servido desde `mapeo_camas/static/mapeo_camas/vendor/bootstrap/`) + CSS global del proyecto. **No usar `border`** como recurso visual.
- Todo el `vendor/` (Bootstrap, ApexCharts) vive **dentro de la app `mapeo_camas`**, no en una carpeta global.
- Cada cambio relevante debe incluir comentario con la fecha del día.

## Objetivo

Entregar un **dashboard de KPIs hospitalarios en tiempo real** para `mapeo_camas`, con backend JSON, frontend modular y arquitectura escalable hacia WebSockets.

## KPIs requeridos (cards superiores)

1. Total camas
2. Camas ocupadas
3. Camas disponibles
4. Camas fuera de servicio
5. % ocupación
6. Altas del día
7. Traslados
8. Cambios detectados en mapeo
9. Camas validadas
10. Tiempo promedio de ocupación

## Gráficas requeridas (ApexCharts)

1. **Barras**: ocupación por servicio.
2. **Donut/Pie**: distribución global de camas por estado.
3. **Línea**: ocupación por hora (día actual).
4. **Heatmap**: saturación por sala.
5. **Tabla dinámica**: últimos movimientos de camas (paginada/scroll).

Indicadores visuales de estado: verde = disponible, rojo = ocupada, amarillo = pendiente, gris = fuera de servicio.

## Estructura de archivos a generar

```
mapeo_camas/
  views.py            # añadir DashboardView + endpoints JSON
  urls.py             # rutas /dashboard/ y /dashboard/api/*
  templates/mapeo_camas/dashboard/
    dashboard.html
    _kpi_cards.html
    _charts.html
    _tabla_movimientos.html
  static/mapeo_camas/
    css/dashboard/dashboard.css
    js/dashboard/
      dashboard.js          # bootstrap + auto-refresh + orquestador
      api.js                # wrapper Fetch (timeouts, errores, AbortController)
      kpis.js               # render de cards
      charts/
        ocupacion-servicio.js
        distribucion-camas.js
        ocupacion-hora.js
        saturacion-sala.js
      tabla-movimientos.js
    vendor/
      apexcharts/apexcharts.min.js
      bootstrap/{bootstrap.min.css,bootstrap.bundle.min.js}
```

> Vendor **siempre local dentro de `mapeo_camas/static/mapeo_camas/vendor/`**. Si ya existen copias en otra ruta del proyecto, preguntar antes de duplicar o mover.

## Backend (Django)

- Vista principal `DashboardMapeoCamasView` (TemplateView) protegida con el patrón de permisos del proyecto: **GET de visualización → `UnidadRolRequiredMixin`** (regla obligatoria del repo).
- Endpoints JSON read-only (`JsonResponse`) bajo `/mapeo_camas/dashboard/api/`:
  - `kpis/`
  - `ocupacion-servicio/`
  - `distribucion-camas/`
  - `ocupacion-hora/`
  - `saturacion-sala/`
  - `ultimos-movimientos/?limit=N`
- Cada endpoint:
  - Usa `select_related`/`values`/`annotate` para evitar N+1.
  - Devuelve estructura `{ "ok": true, "ts": "...", "data": {...} }`.
  - Maneja errores con try/except y status HTTP correcto.
  - Considera caching corto (`cache_page(15)`) cuando aplique.
- Respetar modelos existentes (consultar antes de crear nuevos). No inventar campos: si falta data, dejar `# TODO(<fecha>):` y avisar.

## Frontend

- `dashboard.js` orquesta: registra módulos, dispara `refreshAll()`, programa `setInterval(30_000)`, pausa cuando la pestaña está oculta (`document.visibilitychange`).
- `api.js`: `fetchJson(url, {signal})` con manejo unificado de errores y estados de carga.
- Cada gráfica vive en su módulo con `init(elId)` + `update(data)` para permitir reemplazo fácil por WebSocket.
- Estados de loading/empty/error visibles en cada card y chart.
- Accesibilidad: roles ARIA en cards, `aria-live="polite"` en KPIs.
- Responsive con grid Bootstrap (`row`/`col-xl-3 col-md-6`), sin `border`.

## Optimización futura WebSocket

- Centralizar el contrato de datos en `api.js` para que el día de mañana se reemplace `fetchJson` por una capa `subscribe(topic, cb)` sin tocar los módulos de chart.
- Documentar en comentario al inicio de `dashboard.js` el punto de inyección.

## Entregables esperados en la respuesta

1. Plan corto de archivos a crear/modificar.
2. Código completo de cada archivo listado, en bloques separados con su ruta.
3. Snippet de URL include en `SIWI/urls.py` **solo como sugerencia** (no editar fuera de `mapeo_camas` sin confirmar).
4. Ejemplo de respuesta JSON de cada endpoint.
5. Checklist final: permisos aplicados, vendor local verificado, auto-refresh activo, sin dependencias de internet, sin `border`, comentarios con fecha.

## Restricciones duras

- No tocar apps fuera de `mapeo_camas` sin preguntar.
- No usar CDNs ni recursos remotos.
- No introducir librerías nuevas pesadas sin justificar.
- No mezclar reglas de permisos (GET → mixin, POST → `verificar_permisos_usuario()`).
- No agregar docstrings/typing/comentarios a código que no se modifica.

Si algún dato del modelo no existe o es ambiguo, **detente y pregunta** antes de inventar esquemas.

# s_exp: tiempo real completo, avisos, devoluciones y reportes — diseño

Fecha: 2026-11-23 · Rama base: `claude/modulo-equipos-repos-a204f1` (b46717ee)

## Por qué

El navegador consumía mucha RAM y el servidor recibía consultas cada 5 s por
pantalla. Ya se pasó de polling a WebSocket, pero:

- el socket **no da los mismos avisos** que daba el polling (pantallas que se
  quedan quietas sin error visible);
- varias pantallas solo muestran un banner "hay cambios" y esperan un clic;
  el usuario quiere que **se actualicen solas, como WhatsApp**;
- quiere **avisos** cuando a alguien le toca actuar: al personal cuando puede
  recoger expedientes, al admin cuando llega una solicitud;
- Devoluciones y Reportes siguen sin tope y con N+1.

Regla del usuario: **la funcionalidad queda tal cual, cambia el código, sin
pérdida de datos.**

## Metas

1. Paridad socket = polling en qué pantallas se enteran de qué.
2. Las pantallas se actualizan solas al llegar un aviso, sin perder lo que el
   usuario tiene abierto o a medio marcar.
3. Avisos en pantalla en PC, móvil y tablet; del sistema operativo cuando el
   navegador lo permita (https).
4. Devoluciones y Reportes sin N+1, con techo y contador.
5. Corregir el cálculo de inconsistencias y hacer atómico `procesar_devolucion_api`.

## No metas

- Web Push (avisos con el navegador cerrado / móvil en segundo plano). Exige
  https y servidor de push; proyecto aparte tras pasar a https.
- Cambiar nginx/https (vive en el servidor, no en el repo).
- Mandar datos de pacientes o expedientes por el socket.

## Anti-metas (fallaría aunque "funcione")

- Que una recarga automática borre lo que un admin está marcando en un modal.
- Que un usuario normal reciba avisos del ritmo de trabajo del archivo.
- Que un aviso del sistema muestre nombre de paciente o número de expediente.

## Enfoques considerados

Para la actualización automática:

- **A (elegido por el usuario).** Al llegar el aviso la pantalla vuelve a pedir
  su lista a su API y se redibuja; si hay un modal SweetAlert abierto o una
  fila expandida, espera a que se cierre. Listas ya ligeras → poco coste.
- B. El aviso trae el id y se repinta solo esa fila: más fino, lógica propia
  por pantalla, más riesgo de desincronizar.
- C. El socket trae los datos: descartado, sería una segunda puerta a datos
  sin los permisos de las APIs.

Para Devoluciones: **B (elegido)** — mostrar toda la cola con techo de
seguridad 200 y "Mostrando X de N", en lugar de paginar a 10 (una cola de
trabajo no debe esconder pendientes).

## Diseño

### 1. Servidor: paridad del socket (`s_exp/signals.py`, `s_exp/consumers.py`)

- Acciones sin sección propia (`EXPEDIENTES_RECUPERADOS`,
  `PRESTAMO_PENDIENTE_ENTREGADO`, `PRESTAMO_PENDIENTE_CANCELADO`,
  `REVISION_ENTREGA` y cualquiera futura) se emiten con sección `global` a un
  grupo **solo de administradores** (`admin_global`). El cliente ya despacha
  los manejadores `global` con cualquier mensaje.
- Cada evento lleva el `actor_id` (id de quien hizo la acción). El consumer
  **no reenvía** al propio actor los avisos de `prestamos` y `global`, igual
  que el `exclude(usuario=user)` del polling. El `actor_id` no se manda al
  navegador.
- `EXPEDIENTES_RECUPERADOS` toca varias solicitudes de varios dueños: la vista
  de recuperación avisa por `on_commit` a cada dueño en su grupo personal
  (`mis_solicitudes`). Es la única excepción a "todo por señal", porque el log
  solo apunta a una solicitud.

### 2. Cliente: auto-actualización (`realtime.js`)

- `registrarConTrigger` deja de mostrar banner: recarga sola. La firma no
  cambia, así las pantallas no se tocan.
- Antes de recargar consulta `ocupado()`: modal SweetAlert visible
  (`Swal.isVisible()`) o fila expandida de DataTables (`tr.shown`). Si está
  ocupado, deja la recarga pendiente y la ejecuta al quedar libre (comprobación
  local cada 1 s solo mientras hay pendiente; sin red).
- Varios avisos seguidos se agrupan (300 ms) en una sola recarga.
- El polling de respaldo se mantiene igual que hoy.

### 3. Avisos (`avisos.js` nuevo + `notificaciones_globales.js`)

- El socket ya trae `accion`. Tabla en el cliente acción → aviso:
  - admin: `SOLICITUD_CREADA` "Nueva solicitud de expedientes";
    `SOLICITUD_DEVOLUCION_INICIADA` "Un usuario inició una devolución".
  - personal: `SOLICITUD_LISTA` "Sus expedientes están listos para recoger";
    `SOLICITUD_RECHAZADA` "Su solicitud fue rechazada"; recuperación por
    Admisión; vencimiento (vía alertas, ver abajo).
- Pestaña visible → toast en pantalla (toastr, ya cargado). Pestaña oculta y
  contexto seguro (https/localhost) con permiso → notificación del sistema que
  al tocarla enfoca la pestaña y lleva a la pantalla correspondiente. Con http
  solo toast (temporal, hasta pasar a https). El permiso se pide con un botón
  discreto, nunca al cargar.
- Los modales sticky existentes (listo, recuperación, vencido) siguen igual.
- **Cola de alertas:** al cerrar un modal se vuelve a consultar `/api/alertas/`
  para mostrar la siguiente (antes dependía del ciclo de 5 s).
- **Alertas por tiempo** (10 min, 5 min, vencido): `/api/alertas/` devuelve
  `proximo_chequeo_seg`, el tiempo hasta el siguiente umbral de algún préstamo
  activo; el cliente programa un único `setTimeout`. Sin préstamos activos, no
  hay temporizador.

### 4. Devoluciones (`views/devoluciones.py`)

- `Prestamo` con `select_related` y `Prefetch('solicitud__detalles',
  queryset=aprobados con select_related, to_attr=...)`; conteos en memoria.
- Techo 200; respuesta añade `total` y `mostrando`; `data` igual que hoy.
- `procesar_devolucion_api` dentro de `transaction.atomic()` con
  `select_for_update` sobre el préstamo; misma lógica.
- Plantilla: "Mostrando X de N" cuando se corta.

### 5. Reportes (`views/reportes.py`, `reportes.js`)

- Rechazos: `select_related('prestamo')`. Inconsistencias: prefetch de
  detalles. Morosidad ya es una consulta.
- **Inconsistencias corregido:** total = detalles aprobados; devueltos =
  detalles aprobados con `devuelto=True` (estado real), no la suma de
  `cantidad_recibida`, que es acumulada.
- Las tres listas con techo 200 y total; el front muestra "Mostrando X de N".
- Escapar HTML de los campos de texto en `reportes.js`.
- Totales y agregados sin cambios.

## Restricciones

- Pruebas con `--settings=SIWI.test_settings`; Python del sistema.
- Editar archivos con herramientas que no metan BOM.
- Commits a nombre del usuario, en español, sin co-autor.

## Decisiones del implementador (marcadas como suyas)

- Nombre del grupo `admin_global`, techo 200, agrupación 300 ms, chequeo 1 s.
- Texto exacto de los avisos.

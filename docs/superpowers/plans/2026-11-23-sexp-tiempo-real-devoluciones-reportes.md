# s_exp tiempo real, avisos, devoluciones y reportes — plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el socket avise lo mismo que el polling, las pantallas se actualicen solas sin perder lo abierto, haya avisos en pantalla/sistema, y Devoluciones/Reportes queden sin N+1 y con datos correctos.

**Architecture:** Servidor: la señal de `LogHistorico` reparte avisos por grupos; se añade `admin_global`, `actor_id` filtrado en el consumer y aviso personal por recuperación. Cliente: `realtime.js` recarga en lugar de banner, con guarda de "ocupado"; `avisos.js` traduce `accion` a toast / Notification.

**Tech Stack:** Django 5, Channels 4, jQuery, DataTables, SweetAlert2, toastr.

**Spec:** `docs/superpowers/specs/2026-11-23-sexp-tiempo-real-devoluciones-reportes-design.md`

## Global Constraints

- Pruebas: `python manage.py test s_exp --settings=SIWI.test_settings`.
- Nada de datos de pacientes/expedientes por el socket ni en notificaciones del sistema.
- Formas JSON existentes se conservan; solo se añaden claves.
- Techo de filas: 200. Agrupación de avisos: 300 ms. Chequeo de "ocupado": 1 s.
- Archivos sin BOM; commits en español a nombre del usuario, sin co-autor.

## Review Focus

- Admin con modal de auditoría abierto cuando llega otra devolución → la lista no se recarga hasta cerrar el modal (Task 5, prueba manual en navegador).
- Usuario normal conectado cuando otro admin entrega un pendiente → no recibe nada (Task 1, `test_usuario_normal_no_entra_a_admin_global`).
- Admin que entrega un préstamo → no se auto-avisa en `prestamos`/`global` (Task 1, `test_el_actor_no_recibe_su_propio_aviso`).
- Devolución en dos tandas → inconsistencias muestra faltantes reales (Task 3, `test_inconsistencias_no_suma_acumulados`).
- Fallo a mitad de `procesar_devolucion_api` → nada queda a medias (Task 2, `test_procesar_devolucion_es_atomico`).

---

### Task 1: Paridad del socket en servidor

**Files:** Modify `s_exp/signals.py`, `s_exp/consumers.py`, `s_exp/views/recuperacion.py`; Test `s_exp/tests.py`

**Interfaces:**
- Produces: `grupo_de_seccion('admin_global')`; evento de grupo `{'type':'cambio','seccion','ts','accion','actor_id'}`; `SECCIONES_SIN_AUTOAVISO = ('prestamos', 'global')` en `consumers.py`; `avisar_usuarios(usuario_ids: Iterable[int], accion: str) -> None` en `signals.py` (programa `on_commit`, sección `mis_solicitudes`).

- [ ] Tests: `test_accion_sin_seccion_va_a_admin_global` (acción `REVISION_ENTREGA` → `_emitir` llamado con `'global'` y grupo admin, usando mock de `_emitir`); `test_usuario_normal_no_entra_a_admin_global` (consumer de usuario sin permiso: `self.grupos` sin `admin_global`); `test_el_actor_no_recibe_su_propio_aviso` (`CambiosConsumer.cambio` con `actor_id == user_id` y sección `prestamos` no envía; con `solicitudes` sí envía); `test_recuperacion_avisa_a_cada_dueno` (`avisar_usuarios([a,b], 'EXPEDIENTES_RECUPERADOS')` dentro de `captureOnCommitCallbacks(execute=True)` → dos `_emitir` personales).
- [ ] Ejecutar: fallan.
- [ ] Implementar: en `avisar_cambio`, acciones sin mapeo → sección `global` hacia `admin_global`; `_emitir(..., actor_id)`; el consumer une admins a `admin_global` y en `cambio()` descarta si `seccion in SECCIONES_SIN_AUTOAVISO and actor_id == self.user_id`. En `recuperacion.py`, tras `_registrar_log`, `avisar_usuarios(dueños de solicitudes_tocadas, 'EXPEDIENTES_RECUPERADOS')`.
- [ ] Ejecutar: pasan todas.
- [ ] Commit `fix(s_exp): el socket avisa lo mismo que avisaba el polling`.

### Task 2: Devoluciones sin N+1, con techo y atómica

**Files:** Modify `s_exp/views/devoluciones.py`, `s_exp/templates/s_exp/control_devoluciones.html`; Test `s_exp/tests.py`

**Interfaces:** Produces respuesta `{"data": [...igual...], "total": int, "mostrando": int}`; `LIMITE_DEVOLUCIONES = 200`.

- [ ] Tests (fixture: admin con ficha RRHH, 3 préstamos en `SOL_EN_DEVOLUCION` con 2 detalles aprobados cada uno): `test_devoluciones_consultas_constantes` (`assertNumQueries` igual con 3 y con 6 préstamos); `test_devoluciones_forma_y_total` (claves de cada fila iguales a las de hoy, `total == 3`); `test_procesar_devolucion_es_atomico` (parchear `Devolucion.objects.create` para lanzar → detalle sigue `devuelto=False`).
- [ ] Ejecutar: fallan.
- [ ] Implementar con `Prefetch('solicitud__detalles', queryset=aprobados.select_related(...), to_attr='detalles_aprobados')`, conteos en memoria; `procesar_devolucion_api` en `transaction.atomic()` + `select_for_update()` del préstamo. Plantilla muestra "Mostrando X de N" si `mostrando < total`.
- [ ] Ejecutar: pasan.
- [ ] Commit `perf(s_exp): devoluciones sin N+1, con techo, y auditoría atómica`.

### Task 3: Reportes sin N+1 e inconsistencias correctas

**Files:** Modify `s_exp/views/reportes.py`, `core/static/core/scripts/s_exp/reportes.js`, `s_exp/templates/s_exp/reportes.html`; Test `s_exp/tests.py`

**Interfaces:** Produces claves nuevas `rechazos_total`, `morosidad_total`, `inconsistencias_total`.

- [ ] Tests: `test_inconsistencias_no_suma_acumulados` (préstamo `DevolucionParcial`, 3 aprobados, 2 `devuelto=True`, dos `Devolucion` con `cantidad_recibida` 1 y 2 → `devueltos == 2`, `faltantes == 1`); `test_reportes_consultas_constantes` (mismo número de consultas con 2 y 5 rechazos/parciales).
- [ ] Ejecutar: fallan.
- [ ] Implementar: `select_related('prestamo')` en rechazos; inconsistencias con `annotate(total=Count(detalles aprobados), devueltos=Count(detalles aprobados y devueltos))`; techo 200 con total. `reportes.js`: función `escaparHtml(s)` aplicada a textos; "Mostrando X de N" bajo cada tabla cortada.
- [ ] Ejecutar: pasan.
- [ ] Commit `fix(s_exp): reportes sin N+1 y faltantes calculados sobre el estado real`.

### Task 4: Próximo chequeo de alertas por tiempo

**Files:** Modify `s_exp/views/alertas.py`; Test `s_exp/tests.py`

**Interfaces:** Produces `"proximo_chequeo_seg": int | null` en `/api/alertas/`.

- [ ] Tests: préstamo `Entregado` con límite en 30 min → `proximo_chequeo_seg` ≈ 1200 (umbral de 10 min; tolerancia ±5); sin préstamos → `null`; vencido → `300`.
- [ ] Ejecutar: fallan.
- [ ] Implementar: mínimo, sobre préstamos activos del usuario, de segundos hasta (límite − 10 min), (límite − 5 min), límite, y 300 si hay vencidos; ignorar los ≤ 0.
- [ ] Ejecutar: pasan. Commit `feat(s_exp): alertas dicen cuándo toca el siguiente aviso por tiempo`.

### Task 5: Auto-actualización en `realtime.js`

**Files:** Modify `core/static/core/scripts/s_exp/realtime.js`

**Interfaces:** Produces `RealtimeSExp.ocupado(): boolean`; `RealtimeSExp.onMensaje(fn(datos))` para suscriptores del socket (lo usa Task 6). `registrarConTrigger` conserva firma.

- [ ] Implementar: `alCambiar` de `registrarConTrigger` → `_recargarCuandoLibre(nombre, fn)`: agrupa 300 ms; si `ocupado()` (`window.Swal && Swal.isVisible()` o existe `tr.shown`) reintenta cada 1 s; luego ejecuta `fn`. Rama de polling igual. Sin banner.
- [ ] Verificar en navegador (Task 7).
- [ ] Commit `feat(s_exp): las pantallas se actualizan solas sin pisar lo que está abierto`.

### Task 6: Avisos en pantalla y del sistema

**Files:** Create `core/static/core/scripts/s_exp/avisos.js`; Modify `core/templates/core/bases/base_recursos.html`, `core/static/core/scripts/s_exp/notificaciones_globales.js`

**Interfaces:** Consumes `RealtimeSExp.onMensaje`, `proximo_chequeo_seg`. Produces `AvisosSExp.mostrar({titulo, mensaje, url})`.

- [ ] Implementar `avisos.js`: tabla acción→{titulo, mensaje, url} (textos del spec §3); pestaña visible → `toastr.info`; oculta + `isSecureContext` + permiso → `new Notification` (o `registration.showNotification` si hay SW), clic → `window.focus()` y `location = url`. Botón "Activar avisos" solo si `isSecureContext && Notification.permission === 'default'`.
- [ ] `notificaciones_globales.js`: tras cerrar cada modal sticky, `verificarAlertasGlobales()`; con `proximo_chequeo_seg` programar un único `setTimeout`.
- [ ] Commit `feat(s_exp): avisos en pantalla y del navegador`.

### Task 7: Verificación

- [ ] Suite completa pasando.
- [ ] `runserver` con Daphne/ASGI; en el navegador `RealtimeSExp.socket()` → `conectado: true`.
- [ ] Dos sesiones (admin y usuario): crear solicitud → toast en admin y lista se actualiza sola; marcar lista → toast al usuario; modal de auditoría abierto + nueva devolución → no se recarga hasta cerrar.

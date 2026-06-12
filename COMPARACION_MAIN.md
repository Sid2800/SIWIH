# Informe del módulo `s_exp` (Préstamo de Expedientes) — rama `expedientesV2` vs `main`

> Este documento tiene dos partes:
> 1. La **comparación inicial** del módulo (creación, dada de alta en el sistema).
> 2. Una **ACTUALIZACIÓN** al final con el refactor relacional, correcciones y la
>    **guía de instalación en equipo nuevo**. Para lo más reciente, ir a la
>    sección "🔄 ACTUALIZACIÓN" más abajo.

## 📊 Resumen Numérico (comparación inicial)

| Concepto | Valor |
|----------|-------|
| Archivos NUEVOS | 50 |
| Archivos MODIFICADOS | 12 |
| Archivos ELIMINADOS de main | 0 |
| Líneas agregadas en módulo s_exp | **5,978** |
| Líneas agregadas en frontend (CSS + JS s_exp) | **5,781** |
| Líneas agregadas en archivos modificados | **+410 / -204** |

---

## 📂 Archivos NUEVOS (50)

### Módulo `s_exp/` completo
```
s_exp/__init__.py
s_exp/admin.py                       (53 líneas)
s_exp/apps.py                        (7 líneas)
s_exp/models.py                      (547 líneas) → 10 modelos nuevos
s_exp/urls.py                        (67 líneas)
s_exp/views.py                       (2976 líneas) → APIs + lógica completa
s_exp/tests.py                       (3 líneas)
s_exp/services/__init__.py
s_exp/services/pdf_solicitud_service.py  (554 líneas)
s_exp/scripts/actualizar_catalogos.py    (68 líneas)
s_exp/migrations/0001-0012             (12 migraciones)
```

### Templates `s_exp/` (8 archivos)
```
s_exp/templates/s_exp/
  ├── buscador_expedientes.html
  ├── control_devoluciones.html
  ├── dashboard_admin.html
  ├── gestion_solicitudes.html
  ├── historial_solicitudes.html
  ├── monitoreo_prestamos.html
  ├── reportes.html
  └── seguimiento_usuario.html
```

### Frontend JS `core/static/core/scripts/s_exp/` (7 archivos)
```
buscador_carrito.js          (557 líneas) → carrito de solicitud
dashboard.js                 (38 líneas)  → KPIs admin
notificaciones_globales.js   (159 líneas) → alertas listo-para-recoger
prestamos.js                 (234 líneas) → monitoreo activo
realtime.js                  (445 líneas) → sistema de polling
reportes.js                  (219 líneas) → vista reportes
seguimiento.js               (365 líneas) → mis solicitudes
solicitudes.js               (966 líneas) → gestión admin
```

### CSS
```
core/static/core/css/s_exp.css   (2798 líneas) → todo el styling del módulo
```

### Documentación
```
RRHH_USER_LOCATION_IMPLEMENTATION.md   → guía de integración RRHH
COMPARACION_MAIN.md                    → este documento
s_exp_datos_v2.sql                     → seed data
requirements.txt                       (23 líneas)
```

### Migraciones extra
```
usuario/migrations/0003-0009 (varias)  → cambios en PerfilUnidad.rol
```

---

## ✏️ Archivos MODIFICADOS (12)

| Archivo | Líneas +/- | ¿Riesgo de conflicto? |
|---------|-----------|----------------------|
| `.gitignore` | +17 -0 | 🟢 Bajo - solo agrega ignores |
| `SIWI/settings.py` | +19 -1 | 🟡 Medio - middleware nuevo + LOGGING |
| `SIWI/urls.py` | +1 -0 | 🟢 Bajo - 1 línea (include s_exp) |
| `core/constants/permisos.py` | +15 -2 | 🟡 Medio - nuevos grupos permisos |
| `core/middleware.py` | +39 -0 | 🟢 Bajo - clase nueva |
| `core/services/usuario_service.py` | +2 -0 | 🟢 Bajo - tabs nuevas |
| `core/static/core/css/style.css` | +66 -0 | 🟢 Bajo - clases nuevas |
| `core/static/core/scripts/features/expediente.js` | +100 -0 | 🟢 Bajo - solo agregado |
| `core/templates/core/base.html` | +245 -196 | 🔴 **Alto** - rewrite parcial |
| `expediente/templates/expediente/expediente_detail.html` | +37 -3 | 🟡 Medio - nuevo tab |
| `expediente/views.py` | +13 -1 | 🟢 Bajo - 1 método agregado |
| `usuario/templatetags/permisos_unidad.py` | +39 -1 | 🟡 Medio - helpers nuevos |

---

## 🔍 Análisis de Impacto Mutuo

### 🟢 Sin riesgo de conflicto
Estos archivos solo **agregan** cosas, no modifican código existente:
- `core/middleware.py` → nueva clase `NoSessionRefreshOnPollingMiddleware`
- `core/services/usuario_service.py` → 2 líneas para tabs
- `core/static/core/css/style.css` → clases nuevas al final
- `expediente/views.py` → endpoint `historial_ubicaciones_api` (sin usar)
- `core/static/core/scripts/features/expediente.js` → tab "Historial ubicaciones"

### 🟡 Riesgo medio
**`SIWI/settings.py`** — toca:
- `MIDDLEWARE` (agrega `NoSessionRefreshOnPollingMiddleware` al final)
- `LOGGING` (agrega `defaults={'app':'general'}` al formatter)
- Si main hace cambios al middleware o logging → conflicto resolvible

**`core/constants/permisos.py`** — agrega constantes nuevas
- Si main agrega otras constantes → conflicto fácil de resolver

**`usuario/templatetags/permisos_unidad.py`** — agrega helpers nuevos
- Si main toca el archivo → conflicto medio

### 🔴 Alto riesgo de conflicto
**`core/templates/core/base.html`**
- 245 líneas agregadas + 196 eliminadas
- Es el template más usado del sistema
- Si main toca el menú lateral, header o footer → conflicto importante
- **Recomendación:** revisar a mano antes de merge

---

## 🆕 ¿Hay tablas nuevas en BD?

**Catálogos** (poblados automáticamente por migraciones / comandos):

| Tabla | Filas | PK | Poblado por |
|-------|------|----|-------------|
| `s_exp_motivosolicitud` | 16 | id | **manual** (`s_exp_datos_v2.sql`) |
| `s_exp_estadosolicitud` | 8 | id | migración 0020 |
| `s_exp_estadoexpedientefisico` | 5 | id | migración 0020 |
| `s_exp_estadoprestamo` | 6 | id | migración 0020 |
| `s_exp_estadodevolucion` | 3 | id | migración 0020 |
| `s_exp_tipoaccionlog` | 8 | id | migración 0020 |
| `s_exp_tipoobjetolog` | 3 | id | migración 0021 |
| `expediente_ubicacion` | ~35 | id | migr. `expediente/0009` + signals (alta/baja) |

**Transaccionales** (crecen con el uso):

| Tabla | Uso |
|-------|-----|
| `s_exp_expedienteprestamo` | Estado físico + ubicación (FK) actual del expediente |
| `s_exp_solicitudprestamo` | Solicitudes de préstamo |
| `s_exp_solicituddetalle` | Detalles (M2M intermedio) |
| `s_exp_prestamo` | Préstamos aprobados |
| `s_exp_devolucion` | Devoluciones |
| `s_exp_loghistorico` | Auditoría completa |
| `s_exp_expedienteestadolog` | Histórico de estados físicos |

**Columna nueva en tabla existente:** `expediente_expediente.ubicacion_id`
(FK a `expediente_ubicacion`, transición híbrida; convive con `localizacion_id`).

**❌ No hay tablas para eliminar.**

---

## ✅ Verificación

```bash
python manage.py check
# System check identified no issues (0 silenced).

DJANGO_SETTINGS_MODULE=SIWI.settings python -c "import django; django.setup();
from s_exp import views, urls, models, admin; print('OK')"
# Views, urls, models, admin OK
```

---

---

# 🔄 ACTUALIZACIÓN — Refactor relacional y correcciones (rama `expedientesV2`)

> Estado de fusión con `main`: **`main` es ancestro directo** de `expedientesV2`
> (135 commits adelante, **0 divergentes**). El merge es **fast-forward → SIN
> conflictos**. Verificado: en `base.html` **se conservan las 82 URLs de main**
> y se agregan 31 de s_exp (no se perdió ni reordenó nada de otros módulos).

## 1) Arquitectura: `views.py` → paquete `s_exp/views/`
El antiguo `views.py` (~3100 líneas) se dividió por dominio. `__init__.py`
re-exporta todo, así `urls.py` no cambia:
`comunes, dashboard, solicitudes, prestamos, devoluciones, buscador, alertas,
reportes, historial`.

## 2) Capa de servicios `s_exp/services/`
`datos_solicitud, permisos, formato, log_service, reporte_export_service,
pdf_solicitud_service`. Las vistas quedan delgadas; el acceso a datos y la
generación de PDF/Excel vive aquí.

## 3) Más relacional (menos texto, más IDs)
- Snapshots de texto → **FK**: `SolicitudExpedienteDetalle.paciente`,
  `SolicitudPrestamo.servicio_unidad` (se eliminaron columnas de texto duplicado).
- **Catálogos de estados/acciones con PK ENTERA `id`** (antes el `codigo` texto
  era la PK). `codigo` queda como columna única. Aplica a: `EstadoSolicitud`,
  `EstadoExpedienteFisico`, `EstadoPrestamo`, `EstadoDevolucion`, `TipoAccionLog`.
  Las FK ahora guardan un entero pequeño, no texto repetido.
  - Helpers cacheados en el modelo: `Modelo.id_de('CODIGO')`,
    `Modelo.codigo_de(id)`, `Modelo.obtener('CODIGO')` (0 queries tras la 1ª).
  - En consultas: `filter(estado__codigo='Entregado')`.
- `LogHistorico.objeto_tipo`: texto → **FK** al catálogo nuevo `TipoObjetoLog`.
- `ExpedientePrestamo.ubicacion_fisica` (texto) **eliminado**; la ubicación es
  100% relacional vía FK `ubicacion` a `expediente_ubicacion`.

## 4) Ubicaciones unificadas (`expediente_ubicacion`)
- Catálogo único de ubicaciones clínicas (tipo=1) y no clínicas (tipo=2),
  por **ID** (no texto).
- **Nueva columna `expediente_expediente.ubicacion`** (FK por id). Transición
  híbrida: convive con `localizacion_id` (legacy) y a futuro lo reemplaza.
- Flujo de préstamo: al **entregar** → ubicación = unidad del solicitante;
  al **devolver** → ADMISION. Se actualiza tanto en `ExpedientePrestamo` como
  en `Expediente`.
- **Sincronización automática (signals, en ambos sentidos):**
  - Alta/reactivación de una `Unidad_clinica`/`Unidad` activa → crea/reactiva su
    fila en `expediente_ubicacion`.
  - Baja (estado=0) de la unidad → **desactiva** su fila (no la borra: la FK es
    PROTECT por estar referenciada). Todo por id, así que si la unidad cambia,
    la relación se mantiene correcta sin conflictos.
- **Carga inicial por migración** (`expediente/0009_poblar_ubicaciones`): al
  hacer `migrate` se crea una fila por cada unidad activa existente en ese
  momento. Después, los signals lo mantienen al día.

## 5) UX / correcciones
- Menú "Préstamos Exp." gateado por el filtro `es_no_clinico` (derivado de RRHH
  `rrhh_personalnoclinico`), no por nombres escritos a mano.
- Devoluciones (admin): banner "Actualizar" igual que Gestión de Solicitudes.
- Notificaciones globales: cola secuencial (un modal sticky a la vez).
- Horas en formato 24h, consistente con el resto del sistema (BD en UTC).
- PDF de solicitud: cuadro de firma más alto para nombres de unidad largos.

## 6) Comandos de management (reutilizables, idempotentes)
- `python manage.py poblar_catalogos` — estados/acciones de s_exp.
- `python manage.py poblar_ubicaciones` — pobla `expediente_ubicacion` desde
  las unidades de `servicio`.
- `python manage.py limpiar_transaccional [--dry-run] [--noinput]` — borra datos
  transaccionales de prueba conservando catálogos.

## 7) Migraciones (consolidadas y limpias)
- `s_exp/`: **`0001_initial`** (esquema completo, catálogos con **id PK desde el
  inicio**) + **`0002_datos_iniciales`** (siembra TODOS los catálogos:
  estados, acciones, tipos de objeto **y los 16 motivos**). Se eliminaron las
  21 migraciones incrementales anteriores (que creaban catálogos con `codigo`
  como PK y luego los convertían) — ya no hay churn.
- `expediente/`: **`0008_expediente_ubicacion`** (agrega columna + backfill a
  ADMISION) + **`0009_poblar_ubicaciones`** (siembra `expediente_ubicacion`
  desde las unidades activas de `servicio`).
- Resultado: un `migrate` en limpio deja la BD **lista** (esquema + catálogos +
  motivos). Solo falta `poblar_ubicaciones` (depende de las unidades de servicio).
- **Ya NO se usan scripts SQL** (`s_exp_datos*.sql` eliminados).

> ⚠️ **`venv/` quedó trackeado** (~7,761 archivos). No debería ir a `main`.
> Antes de fusionar conviene: `git rm -r --cached venv && echo "venv/" >> .gitignore`.

---

# 🚀 Instalación en un equipo nuevo

### Requisitos previos
- Python 3.12, MySQL 8.0.16+ (soporta `CHECK` constraints), Git.
- Acceso a un **dump de la base de datos** del hospital (contiene pacientes,
  expedientes, `servicio` (unidades), `rrhh`, usuarios). El módulo s_exp NO crea
  esos datos base — los consume.

### Pasos

```bash
# 1) Clonar el repositorio
git clone <URL_DEL_REPO> SIWIH
cd SIWIH

# 2) Entorno virtual + dependencias
python -m venv venv
venv\Scripts\activate            # Windows  (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt

# 3) Configurar variables de entorno (.env o variables del sistema)
#    SECRET_KEY, credenciales de la BD MySQL, DEBUG, etc.
#    (ver SIWI/settings.py: usa os.getenv para SECRET_KEY/DEBUG/BD)

# 4) Restaurar el dump de la BD base (servicio, rrhh, paciente, expediente...)
mysql -u <user> -p <nombre_bd> < dump_base.sql

# 5) Aplicar migraciones (crea el esquema s_exp + puebla catálogos de estados)
python manage.py migrate
```

### Datos OBLIGATORIOS

| Dato | Cómo | Estado |
|------|------|--------|
| Estados (solicitud, físico, préstamo, devolución), acciones, tipos de objeto | **Automático** en `migrate` (migr. `s_exp/0002_datos_iniciales`) | ✅ ya queda |
| **Motivos de solicitud** (16 del hospital) | **Automático** en `migrate` (migr. `s_exp/0002_datos_iniciales`) | ✅ ya queda |
| **Catálogo de ubicaciones** `expediente_ubicacion` | **Automático** en `migrate` (migr. `expediente/0009_poblar_ubicaciones`), siempre que el dump base con las unidades de `servicio` ya esté restaurado. Luego los signals lo mantienen | ✅ ya queda |
| Unidad **ADMISION** en `servicio_unidad` | debe existir en el dump base (la usan devoluciones y el backfill de `expediente.ubicacion`) | ✅ dump |

> ⚠️ **Orden importante:** restaurar el dump base (paso 4) **antes** del `migrate`
> (paso 5), porque `0009_poblar_ubicaciones` lee las unidades de `servicio`. Si
> migraste antes de tener las unidades, basta con:
> `python manage.py poblar_ubicaciones` (idempotente).

```bash
# (opcional, idempotente) re-sincronizar catálogos/ubicaciones si hizo falta:
python manage.py poblar_catalogos
python manage.py poblar_ubicaciones

# 9) Crear superusuario (si la BD no trae uno)
python manage.py createsuperuser
```

### Vincular usuarios al módulo (importante)
El acceso a s_exp se basa en la **cadena RRHH**:
`auth_user → rrhh_empleado (usuario_id) → rrhh_personalnoclinico (servicio_unidad)`.
Al crear un usuario, **el empleado debe quedar enlazado a la cuenta**
(`rrhh_empleado.usuario`); de lo contrario no verá "Préstamos Exp." ni podrá
entrar al módulo.

### Verificación final
```bash
python manage.py check                       # sin issues
python manage.py makemigrations --check --dry-run   # "No changes detected"
python manage.py runserver
# Login con un usuario NO clínico (Estadística/Admisión/UAU) →
# debe ver "Préstamos Exp." y poder hacer el flujo completo:
# solicitar → aprobar → entregar → devolver.
```

---

**Última actualización:** 2026-06-05
**Rama actual:** `expedientesV2`
**Relación con main:** fast-forward (135 commits adelante, 0 divergentes, sin conflictos)
**Commits adelante de main:** `git rev-list --count main..HEAD`

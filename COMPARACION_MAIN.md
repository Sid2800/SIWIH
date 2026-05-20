# Comparación: `feature/prestamos-expediente` vs `origin/main`

## 📊 Resumen Numérico

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

Sí — **10 tablas nuevas** del módulo `s_exp` (todas en uso):

| Tabla | Filas esperadas | Uso |
|-------|----------------|-----|
| `s_exp_motivosolicitud` | ~15 | Catálogo de motivos |
| `s_exp_estadosolicitud` | ~9 | Catálogo de estados solicitud |
| `s_exp_estadoexpedientefisico` | ~5 | Catálogo de estados físicos |
| `s_exp_expedienteprestamo` | grow | Estado físico actual del expediente |
| `s_exp_solicitudprestamo` | grow | Solicitudes de préstamo |
| `s_exp_solicituddetalle` | grow | Detalles (M2M intermedio) |
| `s_exp_prestamo` | grow | Préstamos aprobados |
| `s_exp_devolucion` | grow | Devoluciones |
| `s_exp_loghistorico` | grow | Auditoría completa |
| `s_exp_expedienteestadolog` | grow | Histórico de estados físicos |

**❌ No hay tablas para eliminar.** Todas referenciadas con 5-130 usos cada una.

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

## 📋 Recomendaciones para Merge

1. **Antes del merge**, hacer rebase contra main para detectar conflictos:
   ```bash
   git rebase origin/main
   ```

2. **Conflicto esperado en `base.html`** → revisar a mano (245 líneas afectadas)

3. **Migraciones**: aplicar en orden las de `s_exp/0001-0012` y las de `usuario/0003-0009`

4. **Verificar después del merge**:
   - `python manage.py check`
   - `python manage.py migrate`
   - Login + acceso al menú "Préstamos Exp."
   - Crear solicitud + aprobar + entregar + devolver (flujo completo)

---

**Fecha de comparación:** 2026-05-20
**Rama actual:** `feature/prestamos-expediente`
**Commits adelante de main:** verificar con `git log --oneline origin/main..HEAD | wc -l`

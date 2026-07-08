# Guía de instalación — SIWIH (Windows)

Pasos para dejar el sistema funcionando en un **equipo nuevo**: desde los
prerrequisitos hasta arrancar el programa. Pensado para Windows (hay notas para
Linux/Mac donde cambia el comando).

---

## 1. Prerrequisitos (instalar una sola vez)

| Software | Versión | Dónde |
|----------|---------|-------|
| **Python** | 3.12 | https://www.python.org/downloads/ — marca **"Add python.exe to PATH"** |
| **Git** | cualquiera reciente | https://git-scm.com/download/win |
| **MySQL** | 8.0.16+ | servidor MySQL (soporta `CHECK` constraints) |
| **ODBC Driver SQL Server** | 17 o 18 | *solo si se usa la BD `bitlesp`/SQL Server* (por `pyodbc`) |

> Necesitas además el **dump de la base de datos** del hospital (contiene
> `servicio`, `rrhh`, `paciente`, `expediente`, usuarios…). El módulo s_exp NO
> crea esos datos base: los **consume**.

---

## 2. Clonar el repositorio

```bat
cd C:\Users\TuUsuario\Documents
git clone https://github.com/Sid2800/SIWIH.git SIWIH
cd SIWIH
git checkout main
```

---

## 3. Entorno virtual (venv)

```bat
python -m venv venv
venv\Scripts\activate
```
- **Linux/Mac:** `source venv/bin/activate`
- Si en **PowerShell** falla la activación por permisos:
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y reintenta
  `venv\Scripts\Activate.ps1`.
- El prompt debe mostrar `(venv)`. Hay que **activarlo en cada terminal nueva**.

---

## 4. Instalar dependencias (requirements)

```bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Incluye: Django 5.2, mysqlclient, reportlab, openpyxl, pillow, pyodbc,
python-dotenv, gunicorn, etc.

> Si falla **mysqlclient**: usa Python 64-bit (instala el wheel solo).
> Si falla **pyodbc**: instala el ODBC Driver de SQL Server (paso 1).

---

## 5. Variables de entorno (`.env`)

El `.env` **no viene en el repo** (está en `.gitignore`). Créalo en la raíz
(`SIWIH\.env`) con tus credenciales:

```env
SECRET_KEY=pon-una-clave-larga-y-secreta
DEBUG=0
ENVIRONMENT=local

# Base de datos principal (MySQL) — IMPRESCINDIBLE
DB_DEFAULT_NAME=nombre_bd
DB_DEFAULT_USER=usuario
DB_DEFAULT_PASSWORD=contraseña
DB_DEFAULT_HOST=127.0.0.1
DB_DEFAULT_PORT=3306

# BD adicionales (rellenar solo si se usan esos módulos)
DB_CENSO_NAME=
DB_CENSO_USER=
DB_CENSO_PASSWORD=
DB_CENSO_HOST=
DB_CENSO_PORT=3306

DB_SALMI_NAME=
DB_SALMI_USER=
DB_SALMI_PASSWORD=
DB_SALMI_HOST=
DB_SALMI_PORT=3306

DB_BITLESP_NAME=
DB_BITLESP_USER=
DB_BITLESP_PASSWORD=
DB_BITLESP_HOST=
DB_BITLESP_PORT=1433

# Servidor de imágenes
IMAGE_SERVER_URL=
IMAGE_SERVER_USER=
IMAGE_SERVER_PASSWORD=
```

- **Mínimo para arrancar:** `SECRET_KEY` + el bloque `DB_DEFAULT_*`.
- **`DEBUG=0`** en producción (deja `1` solo para desarrollo local).
- Si tu host/IP no está en `ALLOWED_HOSTS` (en `SIWI/settings.py`), agrégalo.

---

## 6. Restaurar el dump base (ANTES de migrar)

```bat
mysql -u usuario -p nombre_bd < dump_base.sql
```

> **Orden importante:** el dump va **antes** del `migrate`, porque la migración
> `expediente/0009_poblar_ubicaciones` lee las unidades de `servicio` para
> poblar `expediente_ubicacion`.

---

## 7. Migraciones (crea esquema + SIEMBRA catálogos)

```bat
python manage.py migrate
```

Esto deja listo **automáticamente, sin scripts SQL**:
- Esquema de todas las apps.
- Catálogos de s_exp: estados (solicitud/físico/préstamo/devolución), tipos de
  acción y de objeto, y los **16 motivos** (migración `s_exp/0002_datos_iniciales`).
- `expediente_ubicacion` poblado desde las unidades de servicio (migración
  `expediente/0009`).

---

## 8. Datos obligatorios (verificación / re-sync, idempotente)

Si migraste sin el dump, o por seguridad:

```bat
python manage.py poblar_catalogos      # estados/motivos de s_exp
python manage.py poblar_ubicaciones    # expediente_ubicacion desde servicio
```

| Dato | Cómo queda |
|------|-----------|
| Estados / motivos / tipos | Automático en `migrate` (`s_exp/0002`) |
| `expediente_ubicacion` | Automático en `migrate` (`expediente/0009`) + signals |
| Unidad **ADMISION** en `servicio_unidad` | Debe venir en el dump base |

---

## 9. Superusuario (si el dump no trae uno)

```bat
python manage.py createsuperuser
```

---

## 10. Arrancar el programa

```bat
python manage.py runserver
```

Abre **http://127.0.0.1:8000/** e inicia sesión.

- **Producción** (con Gunicorn, en Linux): `gunicorn SIWI.wsgi:application`.

---

## 11. Funcionamiento del aplicativo (resumen)

SIWIH es un sistema hospitalario modular (Django). Apps principales:

- **paciente / expediente / ingreso / atencion** — gestión clínica del paciente.
- **imagenologia / referencia / clinico** — estudios, referencias, datos clínicos.
- **servicio** — catálogo de unidades (clínicas y no clínicas), camas.
- **mapeo_camas** — mapa y dashboard de ocupación de camas.
- **rrhh / usuario** — empleados y permisos por unidad (`PerfilUnidad`).
- **s_exp (Préstamo de Expedientes)** — solicitar, aprobar, entregar, devolver y
  reportar préstamos de expedientes físicos.

### Acceso por permisos
El acceso a cada módulo depende de la **unidad** y **rol** del usuario:
- Para **s_exp ("Préstamos Exp.")**: el usuario debe ser de **unidad NO clínica**
  y su **empleado debe estar vinculado a la cuenta** (`rrhh_empleado.usuario`).
  Sin ese vínculo no verá el menú ni podrá entrar al módulo.

### Flujo de un préstamo (s_exp)
1. **Solicitar** (usuario no clínico) → 2. **Aprobar/organizar** (admin) →
3. **Listo para recoger** → 4. **Entregar** (el expediente se mueve a la unidad
del solicitante) → 5. **Devolver** (regresa a ADMISION). Todo queda en el
historial y la bitácora (`LogHistorico`).

---

## 12. Verificación final

```bat
python manage.py check
python manage.py makemigrations --check --dry-run    # idealmente "No changes detected"
```

Luego inicia sesión con un usuario **no clínico** (Estadística/Admisión/UAU) y
prueba el flujo completo de s_exp: solicitar → aprobar → entregar → devolver.

---

## Problemas comunes

| Síntoma | Causa / solución |
|---------|------------------|
| No aparece "Préstamos Exp." | El empleado no está vinculado a la cuenta (`rrhh_empleado.usuario`) o no es unidad no clínica. |
| Error `ALLOWED_HOSTS` | Agrega tu IP/host en `SIWI/settings.py`. |
| `mysqlclient`/`pyodbc` no instala | Ver notas del paso 4. |
| `expediente_ubicacion` vacío | Corre `python manage.py poblar_ubicaciones` (requiere unidades de `servicio`). |
| El venv "no se reconoce" | Actívalo: `venv\Scripts\activate`. |

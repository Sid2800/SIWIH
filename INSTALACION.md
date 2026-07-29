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

Incluye: Django 5.2, mysqlclient, reportlab, openpyxl, Pillow, pyodbc,
python-dotenv, requests, qrcode y gunicorn, entre otras dependencias.

> Si falla **mysqlclient**: usa Python 64-bit (instala el wheel solo).
> Si falla **pyodbc**: instala el ODBC Driver de SQL Server (paso 1).

---

## 5. Variables de entorno (`.env`)

El `.env` **no viene en el repo** (está en `.gitignore`). Créalo en la raíz
(`SIWIH\.env`) con tus credenciales:

```env
SECRET_KEY=pon-una-clave-larga-y-secreta
DEBUG=0
ENVIRONMENT=development
ALLOWED_HOSTS=localhost,127.0.0.1

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
IMAGE_SERVER_URL=http://127.0.0.1:8001
IMAGE_SERVER_USER=
IMAGE_SERVER_PASSWORD=

# URL pública usada al generar los QR de equipos
EQUIPOS_QR_BASE_URL=
```

- **Mínimo para arrancar:** `SECRET_KEY` + el bloque `DB_DEFAULT_*`.
- **`DEBUG=0`** en producción (deja `1` solo para desarrollo local).
- Usa `ENVIRONMENT=development` en desarrollo. En producción utiliza un valor
  distinto, por ejemplo `production`, para que Django emplee `STATIC_ROOT`.
- Agrega a `ALLOWED_HOSTS` los nombres o IP desde los que se accederá a SIWIH,
  separados por comas. No es necesario modificar `SIWI/settings.py`.
- `IMAGE_SERVER_URL`, `IMAGE_SERVER_USER` e `IMAGE_SERVER_PASSWORD` son
  obligatorios para consultar y cargar fotografías de equipos.
- En producción, `EQUIPOS_QR_BASE_URL` debe contener la dirección estable de
  SIWIH, por ejemplo `https://siwih.hospital.local`. En desarrollo puede quedar
  vacío y el sistema utilizará la dirección de la solicitud actual.

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
- **equipos** — inventario, ubicación, responsables, fotografías, QR y proceso
  administrativo de baja de equipos.
- **s_exp (Préstamo de Expedientes)** — solicitar, aprobar, entregar, devolver y
  reportar préstamos de expedientes físicos.

### Imágenes de equipos

Las fotografías no se guardan en la base principal de SIWIH. El módulo
`equipos` envía y consulta las imágenes mediante la API de SIWIH Images,
utilizando las credenciales `IMAGE_SERVER_*`. La base principal conserva el
equipo y SIWIH Images relaciona cada fotografía mediante el `dispositivo_id`.

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
python manage.py migrate --plan                       # idealmente sin operaciones
python manage.py showmigrations equipos
python manage.py test equipos --settings=SIWI.test_settings
```

Para validar Equipos, inicia sesión y prueba:

1. Abrir `/equipos/`.
2. Registrar un equipo con fotografía general.
3. Consultarlo en el listado y abrir su detalle.
4. Editar sus datos y agregar fotografías adicionales.
5. Generar y abrir su QR.

Para validar s_exp, inicia sesión con un usuario **no clínico**
(Estadística/Admisión/UAU) y prueba solicitar → aprobar → entregar → devolver.

---

## Problemas comunes

| Síntoma | Causa / solución |
|---------|------------------|
| No aparece "Préstamos Exp." | El empleado no está vinculado a la cuenta (`rrhh_empleado.usuario`) o no es unidad no clínica. |
| Error `ALLOWED_HOSTS` | Agrega la IP o el nombre del servidor a `ALLOWED_HOSTS` en `.env` y reinicia SIWIH. |
| `mysqlclient`/`pyodbc` no instala | Ver notas del paso 4. |
| `expediente_ubicacion` vacío | Corre `python manage.py poblar_ubicaciones` (requiere unidades de `servicio`). |
| Equipos indica que el servidor de imágenes no está disponible | Verifica `IMAGE_SERVER_URL`, las credenciales, que SIWIH Images esté activo y que exista conectividad entre ambos servidores. |
| El venv "no se reconoce" | Actívalo: `venv\Scripts\activate`. |

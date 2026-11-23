"""Ajustes para correr las pruebas.

Las pruebas no pueden usar SIWI.settings tal cual. Ese archivo declara cinco
bases de datos, y el ejecutor de Django intenta crear una base de pruebas por
cada alias antes de correr nada. Dos de esos alias apuntan a servidores que no
son de este proyecto -SALMI y BIT_LESP, el segundo ademas por un motor mssql
que exige su propio controlador- asi que el ejecutor se cae antes de llegar a
la primera prueba.

Aqui se deja solo 'default'. Ninguna prueba del modulo consulta esas otras
bases; son integraciones de lectura con sistemas externos del hospital.

Uso:
    python manage.py test s_exp --settings=SIWI.test_settings
"""

from .settings import *  # noqa: F401,F403

# Solo la base propia. Las demas son sistemas externos que las pruebas no
# tocan y que no tienen por que estar levantados para correrlas.
DATABASES = {'default': DATABASES['default']}  # noqa: F405

# Sin enrutador, porque el que hay reparte entre los alias que se acaban de
# quitar y mandaria consultas a bases que ya no existen.
DATABASE_ROUTERS = []

# La capa en memoria basta y no necesita Redis levantado. Las pruebas corren
# en un proceso, que es justo el caso en el que este backend es correcto.
CHANNEL_LAYERS = {
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
}

# El hash rapido ahorra varios segundos por usuario creado. No afecta a lo
# que se esta comprobando.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

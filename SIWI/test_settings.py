"""Ajustes para correr las pruebas.

Las bases reales (MySQL y BIT_LESP en mssql) se sustituyen por SQLite en
memoria: el ejecutor crea una base de pruebas por alias y no puede
depender de servidores externos del hospital.

Uso:
    python manage.py test s_exp equipos --settings=SIWI.test_settings
"""

from .settings import *

SECRET_KEY = SECRET_KEY or "siwih-test-secret-key"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
    "censo2025": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
    "salmi": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
    "BIT_LESP": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# La capa en memoria basta y no necesita Redis levantado. Las pruebas corren
# en un proceso, que es justo el caso en el que este backend es correcto.
CHANNEL_LAYERS = {
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
}

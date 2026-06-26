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

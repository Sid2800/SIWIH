import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE","SIWI.settings")
import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User

u = User.objects.get(username="ffffffffffffffffff")
client = Client(HTTP_HOST='127.0.0.1')
client.force_login(u)

resp = client.get('/mapeo-camas/', follow=False)
print('GET /mapeo-camas/ status=', resp.status_code)
print('Location=', resp.get('Location'))

resp_follow = client.get('/mapeo-camas/', follow=True)
print('follow final status=', resp_follow.status_code)
print('redirect_chain=', resp_follow.redirect_chain)
print('final path=', getattr(resp_follow, 'request', {}).get('PATH_INFO'))

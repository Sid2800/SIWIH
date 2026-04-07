import sys
from django.test import RequestFactory
from paciente.views import dispensacion_view

rf = RequestFactory()
request = rf.get('/dispensaciones-paciente/?id_paciente=1')  # Get some patient
response = dispensacion_view(request)
print("Status Code:", response.status_code)
print("Response Content:", response.content)

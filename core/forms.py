from django import forms
from django.contrib.auth.forms import AuthenticationForm

from servicio.models import Zona  # Importa tu modelo Zona

class CustomLoginForm(AuthenticationForm):
    zona = forms.ModelChoiceField(
        queryset=Zona.objects.filter(estado=1), 
        required=True, 
        empty_label=None,
        initial=Zona.objects.get(codigo=1),
        to_field_name="codigo"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "class": "input-field",
            "placeholder": "Usuario"  # Agregar placeholder
        })
        self.fields["password"].widget.attrs.update({
            "class": "input-field",
            "placeholder": "Contraseña"  # Agregar placeholder
        })
        self.fields["zona"].widget.attrs.update({
            "class": "input-field"
        })

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from servicio.models import Zona  # Importa tu modelo Zona

class CustomLoginForm(AuthenticationForm):
    zona = forms.ModelChoiceField(
        queryset=Zona.objects.filter(estado=1), 
        required=True, 
        empty_label=None,
        # Se resuelve al construir el formulario, no al importar el modulo.
        # Tal como estaba -una llamada suelta en el cuerpo de la clase- la
        # consulta salia en el import: rompia con la base vacia (un despliegue
        # nuevo, o las pruebas, que empiezan sin catalogos) y ademas congelaba
        # la zona al arrancar el proceso, asi que cambiarla en base no se veia
        # hasta reiniciar. filter().first() en vez de get() porque la ausencia
        # de la zona 1 no debe tumbar la pantalla de login.
        initial=lambda: Zona.objects.filter(codigo=1).first(),
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

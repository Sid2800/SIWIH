
from django import forms
from expediente import models

class ExpedienteCreateForm(forms.ModelForm):

    class Meta:
        model = models.Expediente    
        fields = ["numero","localizacion","estado"]
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


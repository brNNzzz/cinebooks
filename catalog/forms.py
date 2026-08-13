from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Avaliacao


class RegistroForm(UserCreationForm):
    email = forms.EmailField(required=False, label="e-mail")

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]


class AvaliacaoForm(forms.ModelForm):
    class Meta:
        model = Avaliacao
        fields = ["nota", "comentario"]
        widgets = {
            "nota": forms.Select(
                choices=[(n, f"{n} estrela{'s' if n > 1 else ''}") for n in range(1, 6)],
                attrs={"class": "form-select"},
            ),
            "comentario": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "O que você achou? (opcional)"}
            ),
        }
        labels = {"nota": "Sua nota", "comentario": "Comentário"}

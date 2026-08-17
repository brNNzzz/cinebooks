from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .i18n import IDIOMA_PADRAO, traduzir
from .models import Avaliacao


class RegistroForm(UserCreationForm):
    email = forms.EmailField(required=False, label="e-mail")

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def __init__(self, *args, idioma=IDIOMA_PADRAO, **kwargs):
        """Recebe o idioma atual do site (veja _idioma_atual em views.py) e
        traduz o rótulo do campo "e-mail" — os outros campos (usuário,
        senha) vêm prontos do próprio Django, e já são traduzidos
        automaticamente pelo IdiomaDjangoMiddleware (veja catalog/
        middleware.py), sem precisar repetir a tradução aqui."""
        super().__init__(*args, **kwargs)
        self.fields["email"].label = traduzir("registrar_campo_email", idioma)


class AvaliacaoForm(forms.ModelForm):
    class Meta:
        model = Avaliacao
        fields = ["nota", "comentario"]
        widgets = {
            "nota": forms.Select(attrs={"class": "form-select"}),
            "comentario": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, idioma=IDIOMA_PADRAO, **kwargs):
        """As opções da nota (ex: "3 estrelas"), os rótulos e o placeholder
        do comentário são montados aqui (em vez de fixos na Meta) porque
        precisam mudar de idioma — e a Meta é definida uma única vez, quando
        o Django sobe, então não tem como saber o idioma de cada visitante."""
        super().__init__(*args, **kwargs)
        estrela = traduzir("avaliacao_estrela_singular", idioma)
        estrelas = traduzir("avaliacao_estrela_plural", idioma)
        self.fields["nota"].widget.choices = [
            (n, f"{n} {estrela if n == 1 else estrelas}") for n in range(1, 6)
        ]
        self.fields["nota"].label = traduzir("avaliacao_label_nota", idioma)
        self.fields["comentario"].label = traduzir("avaliacao_label_comentario", idioma)
        self.fields["comentario"].widget.attrs["placeholder"] = traduzir(
            "avaliacao_placeholder_comentario", idioma
        )

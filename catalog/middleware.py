"""Liga o idioma escolhido no site (guardado na sessão, ver catalog/i18n.py)
com o sistema de tradução NATIVO do Django (gettext).

Nosso texto próprio (menus, botões, rótulos das páginas) é traduzido pelo
dicionário em catalog/i18n.py, através da tag `{% t "chave" %}`. Mas
algumas partes da página vêm prontas de dentro do próprio Django — por
exemplo, os rótulos e mensagens de erro do formulário de criar conta
(`UserCreationForm`, usado em `RegistroForm`), que tem validações como
"This password is too common" ou "This field is required." Essas strings
já vêm traduzidas profissionalmente para dezenas de idiomas dentro do
próprio Django (não precisamos escrever nem manter nada) — só precisamos
"ativar" o idioma certo em cada request, o que esse middleware faz.
"""

from django.utils import translation

from .i18n import IDIOMA_PADRAO, IDIOMAS

# Mapa do nosso código de idioma (usado na sessão, ex: "zh") pro código de
# localização que o Django usa internamente (ex: "zh-hans").
IDIOMA_PARA_LOCALE_DJANGO = {
    "pt": "pt-br",
    "en": "en",
    "zh": "zh-hans",
    "hi": "hi",
    "es": "es",
    "fr": "fr",
    "ar": "ar",
    "bn": "bn",
    "ru": "ru",
    "ur": "ur",
    "id": "id",
}


class IdiomaDjangoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        codigo = request.session.get("idioma", IDIOMA_PADRAO)
        if codigo not in IDIOMAS:
            codigo = IDIOMA_PADRAO
        locale = IDIOMA_PARA_LOCALE_DJANGO.get(codigo, "pt-br")
        translation.activate(locale)
        request.LANGUAGE_CODE = translation.get_language()
        try:
            response = self.get_response(request)
        finally:
            translation.deactivate()
        return response

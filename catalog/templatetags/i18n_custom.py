"""Tag de template `{% t "chave" %}` que devolve o texto traduzido de acordo
com o idioma escolhido pela pessoa (veja catalog/i18n.py e
catalog/context_processors.py)."""

from django import template

from catalog.i18n import IDIOMA_PADRAO, traduzir

register = template.Library()


@register.simple_tag(takes_context=True)
def t(context, chave):
    idioma = context.get("IDIOMA_ATUAL", IDIOMA_PADRAO)
    return traduzir(chave, idioma)

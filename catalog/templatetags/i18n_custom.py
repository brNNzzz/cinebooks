"""Tag de template `{% t "chave" %}` que devolve o texto traduzido de acordo
com o idioma escolhido pela pessoa (veja catalog/i18n.py e
catalog/context_processors.py). Também tem o filtro `traduzir_genero`, pra
traduzir nomes de gênero (Ação, Drama...) — ver catalog/generos_i18n.py."""

from django import template

from catalog.generos_i18n import traduzir_genero as _traduzir_genero
from catalog.i18n import IDIOMA_PADRAO, traduzir

register = template.Library()


@register.simple_tag(takes_context=True)
def t(context, chave):
    idioma = context.get("IDIOMA_ATUAL", IDIOMA_PADRAO)
    return traduzir(chave, idioma)


@register.filter
def traduzir_genero(nome, idioma_atual):
    return _traduzir_genero(nome, idioma_atual)

from .i18n import IDIOMA_PADRAO, IDIOMAS


def idioma(request):
    """Deixa disponível em TODOS os templates: o código do idioma atual, a
    lista de idiomas disponíveis (pra montar o seletor de bandeiras) e os
    dados (nome/bandeira/direção) do idioma atual."""
    codigo = request.session.get("idioma", IDIOMA_PADRAO)
    if codigo not in IDIOMAS:
        codigo = IDIOMA_PADRAO
    return {
        "IDIOMA_ATUAL": codigo,
        "IDIOMAS": IDIOMAS,
        "IDIOMA_INFO": IDIOMAS[codigo],
    }

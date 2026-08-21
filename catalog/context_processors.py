from .i18n import IDIOMA_PADRAO, IDIOMAS


def estante(request):
    """Deixa disponível em TODOS os templates o total de títulos na
    watchlist ("Estante · N", mostrado na navegação em todas as páginas) —
    0 pra quem não está logado. Feito como context processor (em vez de
    calcular dentro de cada view) porque a navegação aparece em TODA
    página do site, não só nas que já calculavam esse número."""
    if not request.user.is_authenticated:
        return {"ESTANTE_TOTAL": 0}
    from .models import QueroVer

    return {"ESTANTE_TOTAL": QueroVer.objects.filter(usuario=request.user).count()}


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

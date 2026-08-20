"""
Motor de recomendações personalizadas — a fileira "Recomendados pra você"
que aparece na home pra quem está logado.

IDEIA GERAL: cada usuário deixa 3 tipos de "pista" espalhadas pelo site
sobre do que ele gosta — as notas que dá (Avaliacao), os títulos que guarda
pra ver depois (QueroVer) e o que ele procura na busca (Busca). Juntamos
essas pistas num placar de "gêneros favoritos", "diretores/criadores/
autores favoritos" e "épocas favoritas" (a década de lançamento) — e aí
damos nota pra cada título do catálogo que a pessoa AINDA NÃO avaliou nem
colocou na watchlist, de acordo com o quanto ele bate com esse placar. Os
títulos com maior nota viram a fileira de recomendados.

Pesos usados (constantes PESO_* logo abaixo): uma nota alta (4 ou 5
estrelas) conta mais do que só ter colocado na watchlist, que por sua vez
conta mais do que uma busca (a pessoa pode ter buscado só por curiosidade,
sem necessariamente gostar do que achou). Uma nota BAIXA (1 ou 2 estrelas)
conta CONTRA aquele gênero/diretor/década — não faz sentido recomendar mais
coisa parecida com algo que a pessoa não gostou.

Sem NENHUMA pista (usuário novo, que nunca avaliou, nunca usou a watchlist e
nunca buscou nada), `recomendar_para_usuario` devolve uma lista vazia — a
home simplesmente não mostra a fileira nesse caso, em vez de "recomendar"
qualquer coisa aleatória sem sentido nenhum (esse é o chamado "problema do
início frio"/cold start, comum em qualquer sistema de recomendação).
"""

from collections import Counter

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import Avaliacao, Busca, Filme, Livro, QueroVer, Serie

TIPOS_RECOMENDACAO = (("filme", Filme), ("serie", Serie), ("livro", Livro))

# Quantas buscas recentes do usuário entram na conta — só as mais recentes,
# pra recomendação acompanhar o gosto ATUAL da pessoa, não uma pesquisa
# feita há meses que já nem faz mais sentido pra ela.
LIMITE_BUSCAS_CONSIDERADAS = 30

# Quantos títulos do catálogo cada termo buscado pode "apontar" — sem esse
# limite, um termo bem genérico (tipo "o") poderia inflar o placar com
# meio catálogo de uma vez só.
LIMITE_TITULOS_POR_BUSCA = 5

# Quanto cada avaliação/item da watchlist/busca "vota" nos gêneros, na
# pessoa (diretor/criador/autor) e na década do título relacionado.
PESO_POR_NOTA = {5: 3, 4: 2, 3: 0, 2: -1, 1: -2}
PESO_WATCHLIST = 2
PESO_BUSCA = 1

# Quanto cada tipo de "batida" (gênero em comum, mesma pessoa, mesma década)
# vale na pontuação final de um título candidato. Pessoa pesa mais que
# gênero sozinho: gostar do MESMO diretor/autor é um sinal mais forte do que
# só compartilhar um gênero (que costuma ser bem amplo, tipo "Drama").
PESO_GENERO = 3
PESO_PESSOA = 4
PESO_DECADA = 1

# Quantos títulos aparecem na fileira "Recomendados pra você" da home.
LIMITE_RECOMENDACOES = 12


def _decada(item):
    return (item.ano_lancamento // 10) * 10


def _pessoa_do_item(item, tipo):
    """Nome de quem 'assina' o título: diretor (filme), criador (série) ou
    autor (livro). Fica em branco se não tiver sido preenchido ainda (ex:
    título importado rápido pela busca, que só completa isso na primeira
    visita à página de detalhe) — nesse caso simplesmente não soma nem
    conta ponto nenhum de pessoa pra esse item."""
    if tipo == "filme":
        return (item.diretor or "").strip()
    if tipo == "serie":
        return (item.criador or "").strip()
    return (item.autor or "").strip()


def _somar_sinais_do_item(item, tipo, peso, sinais_genero, sinais_pessoa, sinais_decada):
    if not peso:
        return
    for genero in item.generos.all():
        sinais_genero[genero.id] += peso
    pessoa = _pessoa_do_item(item, tipo)
    if pessoa:
        sinais_pessoa[pessoa] += peso
    sinais_decada[_decada(item)] += peso


def _coletar_sinais(usuario):
    """Devolve (sinais_genero, sinais_pessoa, sinais_decada, vistos):
    os 3 primeiros são Counter (peso acumulado por gênero/pessoa/década,
    somando avaliações + watchlist + buscas) e `vistos` é o conjunto de
    (tipo, pk) que a pessoa já avaliou ou colocou na watchlist — usado
    depois pra NUNCA recomendar de volta algo que ela já viu."""
    mapa_content_types = {
        ContentType.objects.get_for_model(model).id: tipo for tipo, model in TIPOS_RECOMENDACAO
    }

    sinais_genero = Counter()
    sinais_pessoa = Counter()
    sinais_decada = Counter()
    vistos = set()

    avaliacoes = Avaliacao.objects.filter(usuario=usuario).select_related("content_type")
    for avaliacao in avaliacoes:
        tipo = mapa_content_types.get(avaliacao.content_type_id)
        if not tipo:
            continue
        vistos.add((tipo, avaliacao.object_id))
        item = avaliacao.titulo_avaliado
        if not item:
            continue
        peso = PESO_POR_NOTA.get(avaliacao.nota, 0)
        _somar_sinais_do_item(item, tipo, peso, sinais_genero, sinais_pessoa, sinais_decada)

    itens_watchlist = QueroVer.objects.filter(usuario=usuario).select_related("content_type")
    for item_watchlist in itens_watchlist:
        tipo = mapa_content_types.get(item_watchlist.content_type_id)
        if not tipo:
            continue
        vistos.add((tipo, item_watchlist.object_id))
        item = item_watchlist.titulo_lista
        if not item:
            continue
        _somar_sinais_do_item(item, tipo, PESO_WATCHLIST, sinais_genero, sinais_pessoa, sinais_decada)

    # Buscas: usa o TERMO buscado pra achar títulos do catálogo com nome
    # parecido (mesma lógica simples de "contém o texto" da busca de
    # verdade, ver views.busca) e soma um voto fraco nos gêneros/pessoa/
    # década desses títulos — sinal mais fraco que avaliação/watchlist,
    # porque a pessoa só PROCUROU, não necessariamente gostou do que achou.
    termos = list(
        Busca.objects.filter(usuario=usuario)
        .order_by("-criado_em")
        .values_list("termo", flat=True)[:LIMITE_BUSCAS_CONSIDERADAS]
    )
    for termo in termos:
        termo = (termo or "").strip()
        if not termo:
            continue
        for tipo, model in TIPOS_RECOMENDACAO:
            correspondentes = model.objects.filter(titulo__icontains=termo)[:LIMITE_TITULOS_POR_BUSCA]
            for item in correspondentes:
                _somar_sinais_do_item(item, tipo, PESO_BUSCA, sinais_genero, sinais_pessoa, sinais_decada)

    return sinais_genero, sinais_pessoa, sinais_decada, vistos


def _pontuar_candidato(item, tipo, sinais_genero, sinais_pessoa, sinais_decada):
    pontos = 0
    for genero in item.generos.all():
        pontos += sinais_genero.get(genero.id, 0) * PESO_GENERO
    pessoa = _pessoa_do_item(item, tipo)
    if pessoa:
        pontos += sinais_pessoa.get(pessoa, 0) * PESO_PESSOA
    pontos += sinais_decada.get(_decada(item), 0) * PESO_DECADA
    return pontos


def recomendar_para_usuario(usuario, limite=LIMITE_RECOMENDACOES):
    """Monta a lista de títulos recomendados pra esse usuário, do mais pro
    menos recomendado (cada item já vem com `.tipo` preenchido, do mesmo
    jeito que `views._destaques_do_ano` faz — pronto pra passar direto pra
    `views._aplicar_exibicao` e pro template `_card.html`).

    Devolve uma lista vazia se a pessoa não deixou nenhuma pista ainda (ver
    módulo acima) OU se, mesmo tendo pistas, nada no catálogo bateu com
    elas (catálogo pequeno demais, gosto muito específico etc.) — nos dois
    casos a home some com a fileira em vez de mostrar algo forçado."""
    sinais_genero, sinais_pessoa, sinais_decada, vistos = _coletar_sinais(usuario)
    if not sinais_genero and not sinais_pessoa and not sinais_decada:
        return []

    ano_atual = timezone.now().year
    candidatos = []
    for tipo, model in TIPOS_RECOMENDACAO:
        queryset = model.objects.filter(ano_lancamento__lte=ano_atual).prefetch_related("generos")
        for item in queryset:
            if (tipo, item.pk) in vistos:
                continue
            pontos = _pontuar_candidato(item, tipo, sinais_genero, sinais_pessoa, sinais_decada)
            if pontos <= 0:
                continue
            item.tipo = tipo
            item.pontuacao_recomendacao = pontos
            candidatos.append(item)

    # Em caso de empate na pontuação, prioriza quem tem melhor nota do
    # público (a que vem do IMDb/Open Library, não a da nossa comunidade) —
    # sem isso, o empate ficaria na ordem "por acaso" que o banco devolveu.
    candidatos.sort(key=lambda i: (i.pontuacao_recomendacao, i.nota_publico or 0), reverse=True)
    return candidatos[:limite]

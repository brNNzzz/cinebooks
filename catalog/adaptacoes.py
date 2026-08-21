"""
Detecção AUTOMÁTICA de vínculos "livro → adaptação em filme/série" (aba
"Adaptações", ver `views.adaptacoes`, e o card "Do livro à tela" na página
de detalhe).

Como funciona: comparamos o título de cada Livro com o título de cada
Filme/Série do catálogo, usando `difflib.SequenceMatcher` (biblioteca
padrão do Python, sem dependência nova) sobre uma versão NORMALIZADA dos
dois títulos (sem acento, minúsculo, sem pontuação, sem palavras genéricas
tipo "o"/"a"/"the" no início) — assim "O Senhor dos Anéis" bate com
"O Senhor dos Anéis: A Sociedade do Anel" mesmo com capitalização/pontuação
diferentes, mas "Duna" não bate com "Duna Cinzenta" (títulos parecidos mas
de obras diferentes) por estar abaixo do limiar de semelhança.

Isso é DE PROPÓSITO só título contra título — sem usar autor/diretor, ano,
ou qualquer outro campo como sinal extra: o autor de um livro quase nunca é
a mesma pessoa que dirige o filme baseado nele, e o ano da adaptação pode
vir décadas depois do livro, então esses campos não ajudam a decidir se é
uma adaptação de verdade e só adicionariam ruído.

`LIMIAR_SIMILARIDADE` foi escolhido pra ser rigoroso (poucos falsos
positivos) às custas de perder alguma adaptação com nome bem diferente do
livro (ex: um filme que troca completamente o título na adaptação) — nesse
caso o vínculo simplesmente não é criado, o que é preferível a linkar dois
títulos que não têm nada a ver."""

import re
import unicodedata
from difflib import SequenceMatcher

from django.contrib.contenttypes.models import ContentType

from .models import Adaptacao, Filme, Livro, Serie

# Abaixo desse valor (escala 0 a 1 do SequenceMatcher.ratio()), os títulos
# são considerados "parecidos demais pra ser coincidência, mas não iguais o
# bastante pra ter certeza" — não cria vínculo nenhum nesse caso.
LIMIAR_SIMILARIDADE = 0.84

# Palavras iniciais genéricas demais pra pesar na comparação (artigos, em
# português/inglês/espanhol/francês — os idiomas mais comuns dos títulos
# cadastrados) — sem isso, "O Hobbit" x "A Hobbit" (tradução diferente do
# mesmo artigo) pesaria mais diferença do que devia.
_ARTIGOS = {"o", "a", "os", "as", "um", "uma", "the", "a", "an", "le", "la", "les", "el", "los", "las"}


def _normalizar(titulo):
    """"O Senhor dos Anéis: A Sociedade do Anel" → "senhor dos aneis
    sociedade do anel" — minúsculo, sem acento, sem pontuação, sem artigo
    inicial."""
    if not titulo:
        return ""
    sem_acento = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    sem_pontuacao = re.sub(r"[^a-z0-9\s]", " ", sem_acento.lower())
    palavras = [p for p in sem_pontuacao.split() if p]
    if palavras and palavras[0] in _ARTIGOS:
        palavras = palavras[1:]
    return " ".join(palavras)


def _similaridade(titulo_a, titulo_b):
    a, b = _normalizar(titulo_a), _normalizar(titulo_b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _melhor_correspondencia(titulo_alvo, candidatos):
    """Devolve (candidato, pontuação) do candidato mais parecido com
    `titulo_alvo`, ou (None, 0.0) se nenhum passar do limiar. `candidatos` é
    um queryset/lista de objetos com `.titulo`."""
    melhor, melhor_pontuacao = None, 0.0
    for candidato in candidatos:
        pontuacao = _similaridade(titulo_alvo, candidato.titulo)
        if pontuacao > melhor_pontuacao:
            melhor, melhor_pontuacao = candidato, pontuacao
    if melhor and melhor_pontuacao >= LIMIAR_SIMILARIDADE:
        return melhor, melhor_pontuacao
    return None, 0.0


def _criar_vinculo(livro, item_adaptacao, pontuacao):
    content_type = ContentType.objects.get_for_model(item_adaptacao)
    Adaptacao.objects.get_or_create(
        livro=livro,
        content_type=content_type,
        object_id=item_adaptacao.pk,
        defaults={"pontuacao_similaridade": pontuacao},
    )


def detectar_adaptacoes_para_livro(livro):
    """Compara `livro` contra TODOS os filmes e séries já cadastrados, e cria
    um vínculo `Adaptacao` pra cada correspondência que passar do limiar
    (pode achar mais de uma — ex: um livro que virou filme E série, ou uma
    trilogia de livros que virou uma trilogia de filmes, cada um linkando
    com o volume mais parecido). Chamado automaticamente quando um livro
    novo é importado (ver `views._criar_livro_rapido`/
    `_criar_livro_do_openlibrary`)."""
    encontrados = []
    for model in (Filme, Serie):
        for item in model.objects.all():
            pontuacao = _similaridade(livro.titulo, item.titulo)
            if pontuacao >= LIMIAR_SIMILARIDADE:
                _criar_vinculo(livro, item, pontuacao)
                encontrados.append(item)
    return encontrados


def detectar_adaptacoes_para_filme_serie(item):
    """O inverso de `detectar_adaptacoes_para_livro`: compara um filme/série
    recém-importado contra TODOS os livros já cadastrados. Chamado
    automaticamente quando um filme/série novo é importado (ver
    `views._criar_filme_rapido`/`_criar_serie_rapida`/`_criar_filme_do_tmdb`/
    `_criar_serie_do_tmdb`) — cobre o caso comum de o livro já estar no
    catálogo antes da adaptação ser adicionada."""
    encontrados = []
    for livro in Livro.objects.all():
        pontuacao = _similaridade(livro.titulo, item.titulo)
        if pontuacao >= LIMIAR_SIMILARIDADE:
            _criar_vinculo(livro, item, pontuacao)
            encontrados.append(livro)
    return encontrados


def detectar_todas_adaptacoes():
    """Varredura completa do catálogo inteiro — cada livro contra cada
    filme/série. Usado pelo comando `python manage.py detectar_adaptacoes`,
    útil pra achar vínculos entre títulos que já estavam cadastrados ANTES
    dessa funcionalidade existir (os pontos de chamada automática em
    views.py só cobrem título NOVO entrando no catálogo dali pra frente)."""
    total = 0
    for livro in Livro.objects.all():
        total += len(detectar_adaptacoes_para_livro(livro))
    return total

"""
Busca de filmes, séries e livros em APIs externas, para importar direto pro
catálogo sem precisar digitar os dados manualmente.

- Filmes e séries: TMDB (themoviedb.org) — precisa da variável de ambiente
  TMDB_API_KEY configurada (veja o README).
- Livros: Open Library (openlibrary.org) — gratuito, sem chave nenhuma.

Qualquer erro de rede/API aqui é tratado (devolve lista vazia ou dados
parciais) para nunca travar a página de importação.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
OMDB_BASE_URL = "https://www.omdbapi.com/"
TIMEOUT_SEGUNDOS = 6

# Lista oficial de gêneros do TMDB (fixa, praticamente nunca muda) — usamos
# esse mapa pronto pra não precisar de uma chamada extra à API só pra
# descobrir o nome de cada gênero.
GENEROS_FILME_TMDB = {
    28: "Ação", 12: "Aventura", 16: "Animação", 35: "Comédia", 80: "Crime",
    99: "Documentário", 18: "Drama", 10751: "Família", 14: "Fantasia",
    36: "História", 27: "Terror", 10402: "Música", 9648: "Mistério",
    10749: "Romance", 878: "Ficção Científica", 10770: "Cinema TV",
    53: "Suspense", 10752: "Guerra", 37: "Faroeste",
}
GENEROS_SERIE_TMDB = {
    10759: "Ação e Aventura", 16: "Animação", 35: "Comédia", 80: "Crime",
    99: "Documentário", 18: "Drama", 10751: "Família", 10762: "Infantil",
    9648: "Mistério", 10763: "Notícia", 10764: "Reality", 10765: "Ficção Científica",
    10766: "Novela", 10767: "Talk Show", 10768: "Guerra e Política", 37: "Faroeste",
}


def tmdb_configurado():
    return bool(getattr(settings, "TMDB_API_KEY", ""))


def _tmdb_get(caminho, parametros_extra=None):
    chave = getattr(settings, "TMDB_API_KEY", "")
    parametros = {"language": "pt-BR"}
    cabecalhos = {}
    if chave.startswith("eyJ"):  # token v4 (JWT)
        cabecalhos["Authorization"] = f"Bearer {chave}"
    else:  # chave v3 (string curta)
        parametros["api_key"] = chave
    if parametros_extra:
        parametros.update(parametros_extra)

    resposta = requests.get(
        f"{TMDB_BASE_URL}{caminho}", params=parametros, headers=cabecalhos, timeout=TIMEOUT_SEGUNDOS
    )
    resposta.raise_for_status()
    return resposta.json()


def buscar_filmes_series(tipo_tmdb, query):
    """tipo_tmdb é 'movie' ou 'tv'. Devolve uma lista resumida de resultados —
    já com tudo que dá pra cadastrar um item completo, numa ÚNICA chamada à
    API (sem precisar buscar detalhes um por um depois, o que deixaria a
    busca lenta)."""
    if not tmdb_configurado() or not query:
        return []
    mapa_generos = GENEROS_FILME_TMDB if tipo_tmdb == "movie" else GENEROS_SERIE_TMDB
    try:
        dados = _tmdb_get(f"/search/{tipo_tmdb}", {"query": query})
        resultados = []
        for item in (dados.get("results") or [])[:10]:
            titulo = item.get("title") or item.get("name") or ""
            data = item.get("release_date") or item.get("first_air_date") or ""
            poster_path = item.get("poster_path")
            resultados.append(
                {
                    "id": item["id"],
                    "titulo": titulo,
                    "ano": data[:4] if data else "",
                    "poster_url": f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else "",
                    "resumo": (item.get("overview") or "")[:180],
                    "sinopse": item.get("overview") or "",
                    "generos": [
                        mapa_generos[g_id] for g_id in item.get("genre_ids") or [] if g_id in mapa_generos
                    ],
                }
            )
        return resultados
    except (requests.RequestException, ValueError, KeyError) as erro:
        logger.warning("Falha ao buscar %r no TMDB: %s", query, erro)
        return []


MAX_ELENCO = 8  # quantos atores/atrizes principais trazer por título


def _extrair_elenco(dados):
    pessoas = []
    for ator in (dados.get("credits", {}).get("cast") or [])[:MAX_ELENCO]:
        foto_path = ator.get("profile_path")
        pessoas.append(
            {
                "nome": ator.get("name", ""),
                "foto_url": f"{TMDB_IMAGE_BASE_URL}{foto_path}" if foto_path else "",
            }
        )
    return [p for p in pessoas if p["nome"]]


def detalhes_filme(tmdb_id):
    """Devolve um dict com os dados completos do filme (inclusive elenco),
    ou None se a busca falhar."""
    try:
        dados = _tmdb_get(f"/movie/{tmdb_id}", {"append_to_response": "credits"})
    except (requests.RequestException, ValueError) as erro:
        logger.warning("Falha ao buscar detalhes do filme %r no TMDB: %s", tmdb_id, erro)
        return None

    diretor = ""
    for pessoa in dados.get("credits", {}).get("crew") or []:
        if pessoa.get("job") == "Director":
            diretor = pessoa.get("name", "")
            break
    poster_path = dados.get("poster_path")
    ano = (dados.get("release_date") or "")[:4]
    return {
        "titulo": dados.get("title") or "",
        "ano_lancamento": int(ano) if ano else None,
        "sinopse": dados.get("overview") or "",
        "diretor": diretor,
        "duracao_minutos": dados.get("runtime") or None,
        "poster_url": f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else "",
        "generos": [g["name"].title() for g in dados.get("genres") or []],
        "elenco": _extrair_elenco(dados),
    }


def detalhes_serie(tmdb_id):
    """Devolve um dict com os dados completos da série (inclusive elenco),
    ou None se a busca falhar."""
    try:
        dados = _tmdb_get(f"/tv/{tmdb_id}", {"append_to_response": "credits"})
    except (requests.RequestException, ValueError) as erro:
        logger.warning("Falha ao buscar detalhes da série %r no TMDB: %s", tmdb_id, erro)
        return None

    criadores = dados.get("created_by") or []
    poster_path = dados.get("poster_path")
    ano = (dados.get("first_air_date") or "")[:4]
    return {
        "titulo": dados.get("name") or "",
        "ano_lancamento": int(ano) if ano else None,
        "sinopse": dados.get("overview") or "",
        "criador": ", ".join(c.get("name", "") for c in criadores),
        "numero_temporadas": dados.get("number_of_seasons") or None,
        "poster_url": f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else "",
        "generos": [g["name"].title() for g in dados.get("genres") or []],
        "elenco": _extrair_elenco(dados),
    }


def omdb_configurado():
    return bool(getattr(settings, "OMDB_API_KEY", ""))


def buscar_notas_omdb(titulo, ano):
    """Busca no OMDb (omdbapi.com) a nota do público (IMDb) e a nota da
    crítica (Metacritic) de um filme ou série, pelo título + ano. Devolve um
    dict {"nota_publico": float|None, "nota_critica": float|None} — nunca
    lança erro, só devolve tudo None se algo falhar ou não tiver a chave
    configurada."""
    vazio = {"nota_publico": None, "nota_critica": None}
    chave = getattr(settings, "OMDB_API_KEY", "")
    if not chave or not titulo:
        return vazio
    try:
        resposta = requests.get(
            OMDB_BASE_URL,
            params={"apikey": chave, "t": titulo, "y": ano or ""},
            timeout=TIMEOUT_SEGUNDOS,
        )
        resposta.raise_for_status()
        dados = resposta.json()
        if dados.get("Response") != "True":
            return vazio

        nota_publico = None
        nota_imdb = dados.get("imdbRating")
        if nota_imdb and nota_imdb != "N/A":
            try:
                nota_publico = float(nota_imdb)
            except ValueError:
                nota_publico = None

        nota_critica = None
        for avaliacao in dados.get("Ratings") or []:
            if avaliacao.get("Source") == "Metacritic":
                valor = (avaliacao.get("Value") or "").split("/")[0]
                try:
                    # Metacritic é de 0 a 100 — convertemos pra escala de 0 a 10,
                    # igual às outras notas do site, pra ficar fácil de comparar.
                    nota_critica = round(float(valor) / 10, 1)
                except ValueError:
                    nota_critica = None
                break

        return {"nota_publico": nota_publico, "nota_critica": nota_critica}
    except (requests.RequestException, ValueError) as erro:
        logger.warning("Falha ao buscar notas de %r no OMDb: %s", titulo, erro)
        return vazio


def buscar_livros(query):
    if not query:
        return []
    try:
        resposta = requests.get(
            "https://openlibrary.org/search.json",
            params={
                "q": query,
                "limit": 10,
                "fields": "key,title,first_publish_year,author_name,author_key,cover_i,"
                "publisher,number_of_pages_median",
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        resposta.raise_for_status()
        resultados = []
        for doc in resposta.json().get("docs") or []:
            cover_id = doc.get("cover_i")
            author_key = (doc.get("author_key") or [""])[0]
            resultados.append(
                {
                    "id": doc.get("key", "").replace("/works/", ""),
                    "titulo": doc.get("title", ""),
                    "ano": doc.get("first_publish_year") or "",
                    "autor": (doc.get("author_name") or [""])[0],
                    # Foto do autor: o Open Library monta a URL a partir do
                    # ID do autor, sem precisar de outra chamada à API.
                    "autor_foto_url": f"https://covers.openlibrary.org/a/olid/{author_key}-M.jpg"
                    if author_key
                    else "",
                    "editora": (doc.get("publisher") or [""])[0][:150],
                    "numero_paginas": doc.get("number_of_pages_median"),
                    "poster_url": f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                    if cover_id
                    else "",
                }
            )
        return resultados
    except (requests.RequestException, ValueError) as erro:
        logger.warning("Falha ao buscar %r no Open Library: %s", query, erro)
        return []


def sinopse_livro(olid):
    """Busca só a sinopse (descrição) do livro, que fica num endpoint separado."""
    try:
        resposta = requests.get(
            f"https://openlibrary.org/works/{olid}.json", timeout=TIMEOUT_SEGUNDOS
        )
        resposta.raise_for_status()
        descricao = resposta.json().get("description") or ""
        if isinstance(descricao, dict):
            descricao = descricao.get("value", "")
        return descricao
    except (requests.RequestException, ValueError) as erro:
        logger.warning("Falha ao buscar sinopse do livro %r no Open Library: %s", olid, erro)
        return ""


def nota_publico_livro(olid):
    """Busca a média de avaliações do público do Open Library para um livro
    (0 a 5 lá, convertemos pra 0 a 10 pra ficar na mesma escala das outras
    notas do site). Devolve None se o livro ainda não tiver avaliações, ou se
    a busca falhar."""
    try:
        resposta = requests.get(
            f"https://openlibrary.org/works/{olid}/ratings.json", timeout=TIMEOUT_SEGUNDOS
        )
        resposta.raise_for_status()
        media = (resposta.json().get("summary") or {}).get("average")
        return round(media * 2, 1) if media else None
    except (requests.RequestException, ValueError) as erro:
        logger.warning("Falha ao buscar nota do livro %r no Open Library: %s", olid, erro)
        return None

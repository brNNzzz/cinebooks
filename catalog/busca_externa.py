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
TIMEOUT_SEGUNDOS = 6


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
    """tipo_tmdb é 'movie' ou 'tv'. Devolve uma lista resumida de resultados."""
    if not tmdb_configurado() or not query:
        return []
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
                }
            )
        return resultados
    except (requests.RequestException, ValueError, KeyError) as erro:
        logger.warning("Falha ao buscar %r no TMDB: %s", query, erro)
        return []


def detalhes_filme(tmdb_id):
    """Devolve um dict com os dados do filme, ou None se a busca falhar."""
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
    }


def detalhes_serie(tmdb_id):
    """Devolve um dict com os dados da série, ou None se a busca falhar."""
    try:
        dados = _tmdb_get(f"/tv/{tmdb_id}")
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
    }


def buscar_livros(query):
    if not query:
        return []
    try:
        resposta = requests.get(
            "https://openlibrary.org/search.json",
            params={
                "q": query,
                "limit": 10,
                "fields": "key,title,first_publish_year,author_name,cover_i,publisher,"
                "number_of_pages_median",
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        resposta.raise_for_status()
        resultados = []
        for doc in resposta.json().get("docs") or []:
            cover_id = doc.get("cover_i")
            resultados.append(
                {
                    "id": doc.get("key", "").replace("/works/", ""),
                    "titulo": doc.get("title", ""),
                    "ano": doc.get("first_publish_year") or "",
                    "autor": (doc.get("author_name") or [""])[0],
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

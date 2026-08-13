"""
Busca automática de capas/pôsteres reais para os títulos cadastrados.

- Filmes e séries: usa a API do TMDB (themoviedb.org), gratuita, mas exige
  uma chave configurada na variável de ambiente TMDB_API_KEY (veja o README
  para criar a sua). Sem essa chave, a busca simplesmente não acontece.
- Livros: usa a API do Open Library (openlibrary.org), gratuita e sem
  necessidade de nenhuma chave.

Em qualquer erro (sem internet, título não encontrado, chave inválida...) as
funções aqui devolvem None em vez de travar o cadastro — o site continua
funcionando normalmente e usa a imagem padrão no lugar da capa.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
TIMEOUT_SEGUNDOS = 6


def _buscar_no_tmdb(tipo, titulo, ano=None):
    """tipo é 'movie' (filme) ou 'tv' (série).

    O TMDB oferece dois formatos de chave, e aceitamos os dois:
    - "API Key (v3 auth)": string curta, vai como parâmetro `api_key` na URL.
    - "API Read Access Token (v4 auth)": token longo (formato JWT, começa com
      "eyJ"), vai no cabeçalho Authorization como Bearer token.
    """
    chave = getattr(settings, "TMDB_API_KEY", "")
    if not chave:
        return None

    parametros = {"query": titulo, "language": "pt-BR"}
    if ano:
        parametros["year" if tipo == "movie" else "first_air_date_year"] = ano

    cabecalhos = {}
    if chave.startswith("eyJ"):  # token v4 (JWT)
        cabecalhos["Authorization"] = f"Bearer {chave}"
    else:  # chave v3 (string curta)
        parametros["api_key"] = chave

    try:
        resposta = requests.get(
            f"{TMDB_BASE_URL}/search/{tipo}",
            params=parametros,
            headers=cabecalhos,
            timeout=TIMEOUT_SEGUNDOS,
        )
        resposta.raise_for_status()
        resultados = resposta.json().get("results") or []
        if not resultados:
            return None
        poster_path = resultados[0].get("poster_path")
        return f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None
    except (requests.RequestException, ValueError) as erro:
        logger.warning("Falha ao buscar capa no TMDB para %r: %s", titulo, erro)
        return None


def buscar_poster_filme(titulo, ano=None):
    return _buscar_no_tmdb("movie", titulo, ano)


def buscar_poster_serie(titulo, ano=None):
    return _buscar_no_tmdb("tv", titulo, ano)


def buscar_capa_livro(titulo, autor=None):
    query = titulo if not autor else f"{titulo} {autor}"
    try:
        resposta = requests.get(
            "https://openlibrary.org/search.json",
            params={"q": query, "limit": 1},
            timeout=TIMEOUT_SEGUNDOS,
        )
        resposta.raise_for_status()
        docs = resposta.json().get("docs") or []
        if not docs:
            return None
        cover_id = docs[0].get("cover_i")
        return f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None
    except (requests.RequestException, ValueError) as erro:
        logger.warning("Falha ao buscar capa no Open Library para %r: %s", titulo, erro)
        return None

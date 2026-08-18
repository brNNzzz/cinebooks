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
from datetime import date

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
OMDB_BASE_URL = "https://www.omdbapi.com/"
TIMEOUT_SEGUNDOS = 6
IDIOMA_TMDB_PADRAO = "pt-BR"

# Lista oficial de gêneros do TMDB em português (fixa, praticamente nunca
# muda) — usada como padrão/reserva, pra não precisar de uma chamada extra à
# API só pra descobrir o nome de cada gênero quando o idioma pedido é o
# português. Para os outros idiomas, ver _mapa_generos() logo abaixo.
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

# Cache em memória dos nomes de gênero por idioma, pra não ter que buscar de
# novo a cada busca (a lista de gêneros do TMDB praticamente nunca muda).
# Reseta quando o processo do site reinicia — sem problema, é só um pedido a
# mais nesse caso.
_CACHE_GENEROS = {}


def tmdb_configurado():
    return bool(getattr(settings, "TMDB_API_KEY", ""))


def _parse_data(data_str):
    """Converte uma data no formato do TMDB ("AAAA-MM-DD") num `date` do
    Python. Devolve None se vier vazia ou num formato inesperado — mais
    seguro que deixar um erro estourar por causa de um dado malformado que
    vier de uma API externa (fora do nosso controle)."""
    if not data_str:
        return None
    try:
        return date.fromisoformat(data_str)
    except ValueError:
        return None


def _tmdb_get(caminho, parametros_extra=None, idioma=IDIOMA_TMDB_PADRAO):
    chave = getattr(settings, "TMDB_API_KEY", "")
    parametros = {"language": idioma or IDIOMA_TMDB_PADRAO}
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


def _mapa_generos(tipo_tmdb, idioma):
    """Nome de cada gênero (id -> nome) no idioma pedido. Em português, usa
    o mapa fixo (sem gastar chamada de API). Nos outros idiomas, busca uma
    vez no TMDB e guarda em cache pro resto da vida do processo."""
    mapa_padrao = GENEROS_FILME_TMDB if tipo_tmdb == "movie" else GENEROS_SERIE_TMDB
    if not idioma or idioma == IDIOMA_TMDB_PADRAO:
        return mapa_padrao

    chave_cache = (tipo_tmdb, idioma)
    if chave_cache in _CACHE_GENEROS:
        return _CACHE_GENEROS[chave_cache]

    try:
        dados = _tmdb_get(f"/genre/{tipo_tmdb}/list", idioma=idioma)
        mapa = {g["id"]: g["name"] for g in dados.get("genres") or []}
        if mapa:
            _CACHE_GENEROS[chave_cache] = mapa
            return mapa
    except (requests.RequestException, ValueError, KeyError) as erro:
        logger.warning("Falha ao buscar gêneros (%s/%s) no TMDB: %s", tipo_tmdb, idioma, erro)
    return mapa_padrao


def _resumo_de_item_tmdb(item, mapa_generos):
    """Converte um item "cru" da API do TMDB (como vem tanto na busca por
    texto quanto nas listas de populares/mais bem avaliados) num dict
    resumido — já com tudo que dá pra cadastrar um item completo numa
    ÚNICA chamada à API, sem precisar buscar detalhes um por um depois
    (o que seria lento pra buscar/importar vários títulos de uma vez)."""
    titulo = item.get("title") or item.get("name") or ""
    data = item.get("release_date") or item.get("first_air_date") or ""
    poster_path = item.get("poster_path")
    return {
        "id": item["id"],
        "titulo": titulo,
        "ano": data[:4] if data else "",
        "data_lancamento": _parse_data(data),
        "poster_url": f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else "",
        "resumo": (item.get("overview") or "")[:180],
        "sinopse": item.get("overview") or "",
        "generos": [mapa_generos[g_id] for g_id in item.get("genre_ids") or [] if g_id in mapa_generos],
    }


def buscar_filmes_series(tipo_tmdb, query, idioma=IDIOMA_TMDB_PADRAO):
    """tipo_tmdb é 'movie' ou 'tv'. Devolve uma lista resumida de resultados —
    já com tudo que dá pra cadastrar um item completo, numa ÚNICA chamada à
    API (sem precisar buscar detalhes um por um depois, o que deixaria a
    busca lenta). O parâmetro `idioma` (ex: "en-US") faz o TMDB devolver
    título/sinopse já traduzidos — usado pra que buscas de títulos NOVOS
    apareçam no idioma que a pessoa escolheu no site."""
    if not tmdb_configurado() or not query:
        return []
    mapa_generos = _mapa_generos(tipo_tmdb, idioma)
    try:
        dados = _tmdb_get(f"/search/{tipo_tmdb}", {"query": query}, idioma=idioma)
        return [_resumo_de_item_tmdb(item, mapa_generos) for item in (dados.get("results") or [])[:10]]
    except (requests.RequestException, ValueError, KeyError) as erro:
        logger.warning("Falha ao buscar %r no TMDB: %s", query, erro)
        return []


def _listar_tmdb(caminho, tipo_tmdb, idioma=IDIOMA_TMDB_PADRAO, paginas=1):
    """Busca uma ou mais páginas de uma LISTA pronta do TMDB (ex:
    "/movie/popular", "/tv/top_rated" — 20 resultados por página) e devolve
    tudo já no mesmo formato resumido de `buscar_filmes_series`. Usada pelo
    comando `popular_catalogo` pra pré-popular o catálogo com títulos
    conhecidos, sem precisar de uma busca por texto pra cada um.

    Diferente da busca por texto (só 1 chamada, no máximo 10 resultados),
    aqui cada PÁGINA é uma chamada separada — por isso o parâmetro
    `paginas` existe: pedir só o necessário, nunca mais que isso."""
    if not tmdb_configurado():
        return []
    mapa_generos = _mapa_generos(tipo_tmdb, idioma)
    resultados = []
    for pagina in range(1, paginas + 1):
        try:
            dados = _tmdb_get(caminho, {"page": pagina}, idioma=idioma)
        except (requests.RequestException, ValueError, KeyError) as erro:
            logger.warning("Falha ao listar %r (página %s) no TMDB: %s", caminho, pagina, erro)
            break
        itens = dados.get("results") or []
        if not itens:
            break
        resultados.extend(_resumo_de_item_tmdb(item, mapa_generos) for item in itens)
        if pagina >= (dados.get("total_pages") or 1):
            break  # já pegamos todas as páginas que existem, não adianta pedir mais
    return resultados


def filmes_populares(idioma=IDIOMA_TMDB_PADRAO, paginas=1):
    """Os filmes mais populares no TMDB agora (o mesmo critério da home page
    deles) — bom pra pré-popular o catálogo com títulos que as pessoas
    realmente conhecem/estão assistindo."""
    return _listar_tmdb("/movie/popular", "movie", idioma=idioma, paginas=paginas)


def filmes_bem_avaliados(idioma=IDIOMA_TMDB_PADRAO, paginas=1):
    """Os filmes mais bem avaliados de todos os tempos no TMDB — usado
    JUNTO com `filmes_populares` (não no lugar), pra misturar sucessos do
    momento com clássicos consagrados."""
    return _listar_tmdb("/movie/top_rated", "movie", idioma=idioma, paginas=paginas)


def series_populares(idioma=IDIOMA_TMDB_PADRAO, paginas=1):
    return _listar_tmdb("/tv/popular", "tv", idioma=idioma, paginas=paginas)


def series_bem_avaliadas(idioma=IDIOMA_TMDB_PADRAO, paginas=1):
    return _listar_tmdb("/tv/top_rated", "tv", idioma=idioma, paginas=paginas)


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


# Região usada pra ler os provedores de streaming/aluguel/compra — o TMDB
# devolve isso já separado por país (chave "BR", "US", etc.), porque a
# disponibilidade muda de região pra região. Como o projeto é em português
# e hospedado no Brasil, fixamos "BR"; não é o mesmo campo que o idioma da
# página (dá pra estar navegando o site em inglês e ainda ver os serviços
# disponíveis no Brasil).
REGIAO_ONDE_ASSISTIR = "BR"


def _extrair_provedores(lista_bruta):
    """Converte a lista bruta de provedores do TMDB (each: provider_name,
    logo_path...) num formato mais simples pro template usar."""
    provedores = []
    for provedor in lista_bruta or []:
        logo_path = provedor.get("logo_path")
        provedores.append(
            {
                "nome": provedor.get("provider_name", ""),
                "logo_url": f"{TMDB_IMAGE_BASE_URL}{logo_path}" if logo_path else "",
            }
        )
    return [p for p in provedores if p["nome"]]


def _extrair_onde_assistir(dados):
    """Lê o bloco "watch/providers" (vindo de append_to_response na mesma
    chamada de detalhes, sem gastar requisição extra) e devolve um dict com
    link + as 3 categorias (streaming por assinatura, aluguel, compra) pra
    região do Brasil. Devolve um dict vazio se o título não tiver nenhuma
    dessas informações (comum pra títulos muito novos ou pouco conhecidos)
    — o template simplesmente não mostra a seção nesse caso.

    Fonte dos dados: JustWatch (via TMDB)."""
    resultados = ((dados.get("watch/providers") or {}).get("results") or {}).get(
        REGIAO_ONDE_ASSISTIR
    ) or {}
    onde_assistir = {
        "link": resultados.get("link", ""),
        "streaming": _extrair_provedores(resultados.get("flatrate")),
        "aluguel": _extrair_provedores(resultados.get("rent")),
        "compra": _extrair_provedores(resultados.get("buy")),
    }
    if not (onde_assistir["streaming"] or onde_assistir["aluguel"] or onde_assistir["compra"]):
        return {}
    return onde_assistir


def _extrair_trailer_youtube(dados, idioma=IDIOMA_TMDB_PADRAO):
    """Lê o bloco "videos" (vindo de graça na mesma chamada de detalhes, via
    append_to_response) e devolve a URL de um trailer no YouTube pra esse
    título, ou "" se não achar nenhum.

    Só usamos vídeo hospedado no PRÓPRIO YouTube (`site == "YouTube"`) — o
    TMDB às vezes também lista vídeos do Vimeo, que a gente ignora aqui pra
    manter as coisas simples (sempre abre no YouTube, como foi pedido).

    Ordem de preferência (a lista do TMDB não vem sempre no mesmo formato,
    então escolhemos o "melhor" vídeo disponível) — tenta achar um DUBLADO
    no idioma pedido primeiro, e só cai pro que tiver disponível se não
    achar (cada vídeo do TMDB carrega o próprio idioma em `iso_639_1`, ex:
    "pt", "en"):
    1. Trailer oficial NESSE idioma.
    2. Qualquer trailer NESSE idioma (não necessariamente marcado oficial).
    3. Trailer oficial em qualquer idioma (geralmente o original/inglês).
    4. Qualquer trailer, de qualquer idioma.
    5. Teaser (nessa mesma ordem de preferência), só se não achar trailer.

    Sobre direitos autorais: isso NÃO baixa nem hospeda o vídeo em lugar
    nenhum — é só um link pra abrir direto no YouTube (o próprio site do
    YouTube, na aba do navegador da pessoa), o mesmo que compartilhar
    qualquer link de vídeo. Sem problema legal nisso: quem decide se um
    vídeo pode ser visto assim é o YouTube/quem publicou, não quem linka
    pra ele."""
    idioma_curto = (idioma or IDIOMA_TMDB_PADRAO).split("-")[0]
    videos = (dados.get("videos") or {}).get("results") or []
    candidatos_youtube = [v for v in videos if v.get("site") == "YouTube" and v.get("key")]

    def _primeiro(tipo, so_oficial=False, so_no_idioma=False):
        for video in candidatos_youtube:
            if video.get("type") != tipo:
                continue
            if so_oficial and not video.get("official"):
                continue
            if so_no_idioma and video.get("iso_639_1") != idioma_curto:
                continue
            return video
        return None

    escolhido = (
        _primeiro("Trailer", so_oficial=True, so_no_idioma=True)
        or _primeiro("Trailer", so_no_idioma=True)
        or _primeiro("Trailer", so_oficial=True)
        or _primeiro("Trailer")
        or _primeiro("Teaser", so_oficial=True, so_no_idioma=True)
        or _primeiro("Teaser", so_no_idioma=True)
        or _primeiro("Teaser", so_oficial=True)
        or _primeiro("Teaser")
    )
    if not escolhido:
        return ""
    return f"https://www.youtube.com/watch?v={escolhido['key']}"


def detalhes_filme(tmdb_id, idioma=IDIOMA_TMDB_PADRAO):
    """Devolve um dict com os dados completos do filme (inclusive elenco),
    ou None se a busca falhar."""
    try:
        dados = _tmdb_get(
            f"/movie/{tmdb_id}",
            {
                "append_to_response": "credits,external_ids,watch/providers,videos",
                # Amplia a busca de vídeos além do idioma da página: o TMDB,
                # por padrão, só devolve vídeo (trailer) que bate exatamente
                # com o idioma pedido — e a maioria dos trailers cadastrados
                # lá é em inglês ou sem idioma marcado, então sem isso a
                # gente perderia trailer pra quase todo título navegado em
                # português. "null" pega os vídeos sem idioma marcado.
                "include_video_language": f"{(idioma or IDIOMA_TMDB_PADRAO).split('-')[0]},en,null",
            },
            idioma=idioma,
        )
    except (requests.RequestException, ValueError) as erro:
        logger.warning("Falha ao buscar detalhes do filme %r no TMDB: %s", tmdb_id, erro)
        return None

    diretor = ""
    for pessoa in dados.get("credits", {}).get("crew") or []:
        if pessoa.get("job") == "Director":
            diretor = pessoa.get("name", "")
            break
    poster_path = dados.get("poster_path")
    data_lancamento_str = dados.get("release_date") or ""
    ano = data_lancamento_str[:4]
    return {
        "titulo": dados.get("title") or "",
        "ano_lancamento": int(ano) if ano else None,
        "data_lancamento": _parse_data(data_lancamento_str),
        "sinopse": dados.get("overview") or "",
        "diretor": diretor,
        "duracao_minutos": dados.get("runtime") or None,
        "poster_url": f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else "",
        "generos": [g["name"].title() for g in dados.get("genres") or []],
        "elenco": _extrair_elenco(dados),
        # ID do IMDb (ex: "tt1160419") — vem de graça nessa mesma chamada
        # (append_to_response=external_ids), sem gastar requisição extra.
        # Usado depois pra buscar as notas no OMDb de forma exata (por ID em
        # vez de por texto do título, que falha quando o título está
        # traduzido pro idioma do site).
        "imdb_id": (dados.get("external_ids") or {}).get("imdb_id") or "",
        # Onde assistir (streaming/aluguel/compra) — também vem de graça
        # nessa mesma chamada (append_to_response=watch/providers).
        "onde_assistir": _extrair_onde_assistir(dados),
        # Trailer no YouTube — idem, vem de graça (append_to_response=videos).
        "trailer_youtube_url": _extrair_trailer_youtube(dados, idioma=idioma),
    }


def detalhes_serie(tmdb_id, idioma=IDIOMA_TMDB_PADRAO):
    """Devolve um dict com os dados completos da série (inclusive elenco),
    ou None se a busca falhar."""
    try:
        dados = _tmdb_get(
            f"/tv/{tmdb_id}",
            {
                "append_to_response": "credits,external_ids,watch/providers,videos",
                "include_video_language": f"{(idioma or IDIOMA_TMDB_PADRAO).split('-')[0]},en,null",
            },
            idioma=idioma,
        )
    except (requests.RequestException, ValueError) as erro:
        logger.warning("Falha ao buscar detalhes da série %r no TMDB: %s", tmdb_id, erro)
        return None

    criadores = dados.get("created_by") or []
    poster_path = dados.get("poster_path")
    data_lancamento_str = dados.get("first_air_date") or ""
    ano = data_lancamento_str[:4]
    return {
        "titulo": dados.get("name") or "",
        "ano_lancamento": int(ano) if ano else None,
        "data_lancamento": _parse_data(data_lancamento_str),
        "sinopse": dados.get("overview") or "",
        "criador": ", ".join(c.get("name", "") for c in criadores),
        "numero_temporadas": dados.get("number_of_seasons") or None,
        "poster_url": f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else "",
        "generos": [g["name"].title() for g in dados.get("genres") or []],
        "elenco": _extrair_elenco(dados),
        "imdb_id": (dados.get("external_ids") or {}).get("imdb_id") or "",
        "onde_assistir": _extrair_onde_assistir(dados),
        "trailer_youtube_url": _extrair_trailer_youtube(dados, idioma=idioma),
    }


def omdb_configurado():
    return bool(getattr(settings, "OMDB_API_KEY", ""))


def buscar_notas_omdb(titulo, ano, imdb_id=""):
    """Busca no OMDb (omdbapi.com) a nota do público (IMDb), a nota da
    crítica (Metacritic), a % do Rotten Tomatoes e uma sinopse mais longa
    ("plot=full", bem mais detalhada que o resumo padrão) de um filme ou
    série. Devolve um dict {"nota_publico": float|None, "nota_critica":
    float|None, "nota_rotten_tomatoes": int|None, "sinopse_omdb": str} —
    nunca lança erro, só devolve tudo vazio se algo falhar ou não tiver a
    chave configurada.

    Sempre que tivermos o `imdb_id` (ex: "tt1160419", que vem de graça junto
    com os detalhes do TMDB), buscamos por ELE em vez de por título+ano —
    é uma busca exata, então funciona mesmo com o título traduzido pro
    idioma do site (o OMDb é uma base majoritariamente em inglês, então
    buscar por texto o título em português/espanhol/etc. costuma falhar e
    devolver nada, nem nota do público nem da crítica).

    IMPORTANTE sobre `sinopse_omdb`: o OMDb só devolve texto em INGLÊS, não
    tem opção de idioma. Por isso quem usa esse retorno (ver
    `_garantir_notas_omdb` em views.py) só aplica esse texto em títulos cujo
    conteúdo original já é em inglês, ou guarda como uma tradução pronta pro
    inglês — nunca substitui a sinopse de um título cadastrado em outro
    idioma, senão a página ficaria com um parágrafo em inglês no meio do
    site em português (o mesmo cuidado que já existe no cache de tradução,
    ver `_buscar_traducao_agora`)."""
    vazio = {
        "nota_publico": None,
        "nota_critica": None,
        "nota_rotten_tomatoes": None,
        "sinopse_omdb": "",
    }
    chave = getattr(settings, "OMDB_API_KEY", "")
    if not chave or (not titulo and not imdb_id):
        return vazio
    try:
        if imdb_id:
            parametros = {"apikey": chave, "i": imdb_id, "plot": "full"}
        else:
            parametros = {"apikey": chave, "t": titulo, "y": ano or "", "plot": "full"}
        resposta = requests.get(OMDB_BASE_URL, params=parametros, timeout=TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
        dados = resposta.json()
        if dados.get("Response") != "True":
            # Se buscamos por ID e falhou (raro, mas pode acontecer com dado
            # inconsistente), tenta de novo por título+ano como reserva.
            if imdb_id and titulo:
                return buscar_notas_omdb(titulo, ano)
            return vazio

        nota_publico = None
        nota_imdb = dados.get("imdbRating")
        if nota_imdb and nota_imdb != "N/A":
            try:
                nota_publico = float(nota_imdb)
            except ValueError:
                nota_publico = None

        nota_critica = None
        nota_rotten_tomatoes = None
        for avaliacao in dados.get("Ratings") or []:
            fonte = avaliacao.get("Source")
            valor_bruto = avaliacao.get("Value") or ""
            if fonte == "Metacritic":
                valor = valor_bruto.split("/")[0]
                try:
                    # Metacritic é de 0 a 100 — convertemos pra escala de 0 a 10,
                    # igual às outras notas do site, pra ficar fácil de comparar.
                    nota_critica = round(float(valor) / 10, 1)
                except ValueError:
                    nota_critica = None
            elif fonte == "Rotten Tomatoes":
                valor = valor_bruto.replace("%", "").strip()
                try:
                    nota_rotten_tomatoes = int(float(valor))
                except ValueError:
                    nota_rotten_tomatoes = None

        plot_bruto = dados.get("Plot") or ""
        sinopse_omdb = plot_bruto if plot_bruto != "N/A" else ""

        return {
            "nota_publico": nota_publico,
            "nota_critica": nota_critica,
            "nota_rotten_tomatoes": nota_rotten_tomatoes,
            "sinopse_omdb": sinopse_omdb,
        }
    except (requests.RequestException, ValueError) as erro:
        logger.warning("Falha ao buscar notas de %r no OMDb: %s", titulo or imdb_id, erro)
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

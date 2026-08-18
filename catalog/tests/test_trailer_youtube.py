"""
Testes do trailer no YouTube (botão "Assistir trailer" na página de
detalhe de filme/série).

De onde vem: o TMDB tem um bloco "videos" (append_to_response, mesma
chamada que já buscava elenco/onde assistir — sem requisição extra) com
todos os vídeos cadastrados pra aquele título (trailers, teasers,
bastidores...), cada um apontando pro YouTube (ou Vimeo, que ignoramos —
ver `busca_externa._extrair_trailer_youtube`) e marcado com o PRÓPRIO
idioma (`iso_639_1`, ex: "pt", "en"). Escolhemos o melhor candidato
priorizando um trailer NESSE idioma (dublado/legendado) antes de cair pro
que tiver disponível, e guardamos só a URL final do YouTube.

Sobre a preocupação de "problema legal": isso NUNCA baixa nem hospeda o
vídeo — é só um link que abre direto no YouTube, igual compartilhar
qualquer link. Quem decide se aquele vídeo pode ser aberto assim é o
YouTube/quem publicou o trailer, não o nosso site.

- `busca_externa._extrair_trailer_youtube` → escolhe o melhor vídeo entre
  os candidatos brutos do TMDB, priorizando o idioma pedido.
- `detalhes_filme`/`detalhes_serie` → conferem que "trailer_youtube_url"
  sai preenchido e que o `include_video_language` amplia a busca além do
  idioma da página (a maioria dos trailers no TMDB está em inglês).
- `_completar_filme`/`_completar_serie` → conferem que o campo é salvo,
  seguindo o padrão "só preenche se ainda tava vazio" (igual imdb_id,
  poster_url — diferente de onde_assistir, que sempre atualiza). Esse é o
  trailer no idioma ORIGINAL do cadastro.
- `views._trailer_no_idioma`/`_buscar_traducao_agora` → o trailer que
  aparece pra quem está navegando num idioma DIFERENTE do original —
  reaproveita o mesmo cache/mecanismo já usado pra título/sinopse
  traduzidos (ver test_traducao_tmdb.py).
"""

from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from catalog import busca_externa, views
from catalog.tests.fabricas import criar_filme, criar_serie


def _video(key="abc123", tipo="Trailer", site="YouTube", official=True, idioma="en"):
    return {"key": key, "type": tipo, "site": site, "official": official, "iso_639_1": idioma}


class ExtrairTrailerYoutubeTest(SimpleTestCase):
    def test_prefere_trailer_oficial(self):
        dados = {
            "videos": {
                "results": [
                    _video(key="nao-oficial", official=False),
                    _video(key="oficial", official=True),
                ]
            }
        }
        url = busca_externa._extrair_trailer_youtube(dados)
        self.assertEqual(url, "https://www.youtube.com/watch?v=oficial")

    def test_sem_trailer_oficial_usa_qualquer_trailer(self):
        dados = {"videos": {"results": [_video(key="qualquer", official=False)]}}
        url = busca_externa._extrair_trailer_youtube(dados)
        self.assertEqual(url, "https://www.youtube.com/watch?v=qualquer")

    def test_sem_trailer_nenhum_cai_pro_teaser(self):
        dados = {"videos": {"results": [_video(key="teaser1", tipo="Teaser", official=False)]}}
        url = busca_externa._extrair_trailer_youtube(dados)
        self.assertEqual(url, "https://www.youtube.com/watch?v=teaser1")

    def test_ignora_video_do_vimeo(self):
        dados = {"videos": {"results": [_video(key="vimeo1", site="Vimeo")]}}
        url = busca_externa._extrair_trailer_youtube(dados)
        self.assertEqual(url, "")

    def test_sem_nenhum_video_devolve_vazio(self):
        self.assertEqual(busca_externa._extrair_trailer_youtube({}), "")
        self.assertEqual(busca_externa._extrair_trailer_youtube({"videos": {"results": []}}), "")

    def test_ignora_outros_tipos_tipo_bastidores(self):
        dados = {"videos": {"results": [_video(key="bts", tipo="Behind the Scenes")]}}
        url = busca_externa._extrair_trailer_youtube(dados)
        self.assertEqual(url, "")

    def test_prefere_trailer_dublado_no_idioma_pedido_mesmo_sem_ser_oficial(self):
        dados = {
            "videos": {
                "results": [
                    _video(key="oficial-ingles", official=True, idioma="en"),
                    _video(key="dublado-pt", official=False, idioma="pt"),
                ]
            }
        }
        url = busca_externa._extrair_trailer_youtube(dados, idioma="pt-BR")
        self.assertEqual(url, "https://www.youtube.com/watch?v=dublado-pt")

    def test_prefere_oficial_dublado_sobre_nao_oficial_dublado(self):
        dados = {
            "videos": {
                "results": [
                    _video(key="dublado-nao-oficial", official=False, idioma="pt"),
                    _video(key="dublado-oficial", official=True, idioma="pt"),
                ]
            }
        }
        url = busca_externa._extrair_trailer_youtube(dados, idioma="pt-BR")
        self.assertEqual(url, "https://www.youtube.com/watch?v=dublado-oficial")

    def test_sem_trailer_no_idioma_pedido_cai_pro_original(self):
        dados = {"videos": {"results": [_video(key="so-ingles", official=True, idioma="en")]}}
        url = busca_externa._extrair_trailer_youtube(dados, idioma="fr-FR")
        self.assertEqual(url, "https://www.youtube.com/watch?v=so-ingles")

    def test_idioma_composto_e_comparado_so_pela_parte_curta(self):
        # "pt-BR" (idioma da página) deve bater com um vídeo marcado "pt"
        # (o TMDB usa só o código curto de idioma pros vídeos, sem região).
        dados = {"videos": {"results": [_video(key="dublado", official=True, idioma="pt")]}}
        url = busca_externa._extrair_trailer_youtube(dados, idioma="pt-BR")
        self.assertEqual(url, "https://www.youtube.com/watch?v=dublado")


class DetalhesFilmeSerieIncluiTrailerTest(SimpleTestCase):
    def test_detalhes_filme_pede_videos_e_include_video_language(self):
        with patch("catalog.busca_externa._tmdb_get", return_value={"title": "X", "credits": {}}) as mock_get:
            busca_externa.detalhes_filme("123", idioma="pt-BR")

        parametros = mock_get.call_args[0][1]
        self.assertIn("videos", parametros["append_to_response"])
        self.assertIn("pt", parametros["include_video_language"])
        self.assertIn("en", parametros["include_video_language"])
        self.assertIn("null", parametros["include_video_language"])

    def test_detalhes_filme_devolve_trailer_youtube_url(self):
        dados_tmdb = {"title": "X", "credits": {}, "videos": {"results": [_video(key="xyz")]}}
        with patch("catalog.busca_externa._tmdb_get", return_value=dados_tmdb):
            info = busca_externa.detalhes_filme("123")
        self.assertEqual(info["trailer_youtube_url"], "https://www.youtube.com/watch?v=xyz")

    def test_detalhes_serie_pede_videos_e_include_video_language(self):
        with patch("catalog.busca_externa._tmdb_get", return_value={"name": "X", "credits": {}}) as mock_get:
            busca_externa.detalhes_serie("456", idioma="en-US")

        parametros = mock_get.call_args[0][1]
        self.assertIn("videos", parametros["append_to_response"])
        self.assertIn("en", parametros["include_video_language"])

    def test_detalhes_serie_devolve_trailer_youtube_url(self):
        dados_tmdb = {"name": "X", "credits": {}, "videos": {"results": [_video(key="uvw")]}}
        with patch("catalog.busca_externa._tmdb_get", return_value=dados_tmdb):
            info = busca_externa.detalhes_serie("456")
        self.assertEqual(info["trailer_youtube_url"], "https://www.youtube.com/watch?v=uvw")


class CompletarFilmeSerieSalvaTrailerTest(TestCase):
    def _info_base_filme(self, **extra):
        base = {
            "sinopse": "", "diretor": "", "duracao_minutos": None, "poster_url": "",
            "imdb_id": "", "data_lancamento": None, "onde_assistir": {},
            "trailer_youtube_url": "",
        }
        base.update(extra)
        return base

    def _info_base_serie(self, **extra):
        base = {
            "sinopse": "", "criador": "", "numero_temporadas": None, "poster_url": "",
            "imdb_id": "", "data_lancamento": None, "onde_assistir": {},
            "trailer_youtube_url": "",
        }
        base.update(extra)
        return base

    def test_completar_filme_salva_trailer_encontrado(self):
        filme = criar_filme(id_externo="123", dados_completos=False)
        info = self._info_base_filme(trailer_youtube_url="https://www.youtube.com/watch?v=abc")
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=info):
            with patch("catalog.views.busca_externa.omdb_configurado", return_value=False):
                views._completar_filme(filme)

        filme.refresh_from_db()
        self.assertEqual(filme.trailer_youtube_url, "https://www.youtube.com/watch?v=abc")

    def test_completar_serie_salva_trailer_encontrado(self):
        serie = criar_serie(id_externo="456", dados_completos=False)
        info = self._info_base_serie(trailer_youtube_url="https://www.youtube.com/watch?v=def")
        with patch("catalog.views.busca_externa.detalhes_serie", return_value=info):
            with patch("catalog.views.busca_externa.omdb_configurado", return_value=False):
                views._completar_serie(serie)

        serie.refresh_from_db()
        self.assertEqual(serie.trailer_youtube_url, "https://www.youtube.com/watch?v=def")

    def test_nao_sobrescreve_trailer_ja_salvo(self):
        # Diferente de onde_assistir (sempre atualiza), o trailer só é
        # preenchido se ainda estava vazio — não fica "desatualizando" o
        # que já tinha sido encontrado antes.
        filme = criar_filme(
            id_externo="123",
            dados_completos=False,
            trailer_youtube_url="https://www.youtube.com/watch?v=original",
        )
        info = self._info_base_filme(trailer_youtube_url="https://www.youtube.com/watch?v=novo")
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=info):
            with patch("catalog.views.busca_externa.omdb_configurado", return_value=False):
                views._completar_filme(filme)

        filme.refresh_from_db()
        self.assertEqual(filme.trailer_youtube_url, "https://www.youtube.com/watch?v=original")

    def test_sem_trailer_encontrado_fica_em_branco_sem_erro(self):
        filme = criar_filme(id_externo="123", dados_completos=False)
        info = self._info_base_filme(trailer_youtube_url="")
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=info):
            with patch("catalog.views.busca_externa.omdb_configurado", return_value=False):
                views._completar_filme(filme)

        filme.refresh_from_db()
        self.assertEqual(filme.trailer_youtube_url, "")


class TrailerNoIdiomaTest(TestCase):
    """`views._trailer_no_idioma` — o trailer que aparece de verdade na
    página, dependendo do idioma em que a pessoa está navegando o site
    (não necessariamente o mesmo do trailer "original" salvo no cadastro).
    """

    def setUp(self):
        self.filme = criar_filme(
            idioma_tmdb_conteudo="en-US",
            trailer_youtube_url="https://www.youtube.com/watch?v=original-en",
            id_externo="99999",
        )

    def test_mesmo_idioma_do_cadastro_usa_o_trailer_original_direto(self):
        with patch("catalog.views.busca_externa.detalhes_filme") as mock_busca:
            url = views._trailer_no_idioma(self.filme, "filme", "en-US")
            mock_busca.assert_not_called()
        self.assertEqual(url, "https://www.youtube.com/watch?v=original-en")

    def test_usa_trailer_cacheado_pro_idioma_pedido_sem_buscar_de_novo(self):
        self.filme.traducoes = {
            "pt-BR": {"titulo": "X", "sinopse": "Y", "trailer_youtube_url": "https://www.youtube.com/watch?v=dublado-pt", "v": 2}
        }
        self.filme.save()
        with patch("catalog.views.busca_externa.detalhes_filme") as mock_busca:
            url = views._trailer_no_idioma(self.filme, "filme", "pt-BR")
            mock_busca.assert_not_called()
        self.assertEqual(url, "https://www.youtube.com/watch?v=dublado-pt")

    def test_cache_sem_trailer_pra_esse_idioma_cai_pro_original(self):
        # Entrada de cache existe (título/sinopse já traduzidos), mas sem
        # trailer nesse idioma (TMDB não tinha um dublado) — cai pro
        # trailer original, não fica sem nenhum.
        self.filme.traducoes = {"pt-BR": {"titulo": "X", "sinopse": "Y", "v": 2}}
        self.filme.save()
        url = views._trailer_no_idioma(self.filme, "filme", "pt-BR")
        self.assertEqual(url, "https://www.youtube.com/watch?v=original-en")

    def test_sem_cache_nenhum_tambem_cai_pro_original_sem_buscar(self):
        # Diferente de _texto_no_idioma, essa função NÃO dispara busca
        # própria — só lê o que já tiver em cache (ver docstring da função).
        with patch("catalog.views.busca_externa.detalhes_filme") as mock_busca:
            url = views._trailer_no_idioma(self.filme, "filme", "pt-BR")
            mock_busca.assert_not_called()
        self.assertEqual(url, "https://www.youtube.com/watch?v=original-en")


class BuscarTraducaoAgoraCacheiaTrailerTest(TestCase):
    """`_buscar_traducao_agora` (já usada pra cachear título/sinopse
    traduzidos) agora também cacheia o trailer nesse idioma, já que vem de
    graça na mesma resposta do TMDB — usado por `_texto_no_idioma` (chamada
    pela view `detalhe`) e reaproveitado depois por `_trailer_no_idioma`."""

    def setUp(self):
        self.filme = criar_filme(idioma_tmdb_conteudo="en-US", id_externo="12345")

    def test_guarda_o_trailer_do_idioma_pedido_no_cache(self):
        resposta_simulada = {
            "titulo": "Título PT",
            "sinopse": "Sinopse em português.",
            "trailer_youtube_url": "https://www.youtube.com/watch?v=dublado-pt",
        }
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=resposta_simulada):
            views._texto_no_idioma(self.filme, "filme", "pt-BR")

        self.filme.refresh_from_db()
        self.assertEqual(
            self.filme.traducoes["pt-BR"]["trailer_youtube_url"],
            "https://www.youtube.com/watch?v=dublado-pt",
        )

    def test_sem_trailer_nesse_idioma_guarda_vazio_no_cache(self):
        resposta_simulada = {"titulo": "Título PT", "sinopse": "Sinopse.", "trailer_youtube_url": ""}
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=resposta_simulada):
            views._texto_no_idioma(self.filme, "filme", "pt-BR")

        self.filme.refresh_from_db()
        self.assertEqual(self.filme.traducoes["pt-BR"]["trailer_youtube_url"], "")

    def test_texto_no_idioma_seguido_de_trailer_no_idioma_usa_o_trailer_certo(self):
        # Fluxo real da view `detalhe`: chama _texto_no_idioma primeiro
        # (popula o cache), depois _trailer_no_idioma (lê o cache já
        # preenchido) — confere que os dois juntos dão o resultado certo,
        # numa ÚNICA chamada à API.
        resposta_simulada = {
            "titulo": "Título PT",
            "sinopse": "Sinopse em português.",
            "trailer_youtube_url": "https://www.youtube.com/watch?v=dublado-pt",
        }
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=resposta_simulada) as mock_busca:
            views._texto_no_idioma(self.filme, "filme", "pt-BR")
            self.filme.refresh_from_db()
            url = views._trailer_no_idioma(self.filme, "filme", "pt-BR")
            self.assertEqual(mock_busca.call_count, 1)  # só UMA chamada à API

        self.assertEqual(url, "https://www.youtube.com/watch?v=dublado-pt")

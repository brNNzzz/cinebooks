"""
Testes do trailer no YouTube (botão "Assistir trailer" na página de
detalhe de filme/série).

De onde vem: o TMDB tem um bloco "videos" (append_to_response, mesma
chamada que já buscava elenco/onde assistir — sem requisição extra) com
todos os vídeos cadastrados pra aquele título (trailers, teasers,
bastidores...), cada um apontando pro YouTube (ou Vimeo, que ignoramos —
ver `busca_externa._extrair_trailer_youtube`). Escolhemos o melhor
candidato (trailer oficial > qualquer trailer > teaser) e guardamos só a
URL final do YouTube.

Sobre a preocupação de "problema legal": isso NUNCA baixa nem hospeda o
vídeo — é só um link que abre direto no YouTube, igual compartilhar
qualquer link. Quem decide se aquele vídeo pode ser aberto assim é o
YouTube/quem publicou o trailer, não o nosso site.

- `busca_externa._extrair_trailer_youtube` → escolhe o melhor vídeo entre
  os candidatos brutos do TMDB.
- `detalhes_filme`/`detalhes_serie` → conferem que "trailer_youtube_url"
  sai preenchido e que o `include_video_language` amplia a busca além do
  idioma da página (a maioria dos trailers no TMDB está em inglês).
- `_completar_filme`/`_completar_serie` → conferem que o campo é salvo,
  seguindo o padrão "só preenche se ainda tava vazio" (igual imdb_id,
  poster_url — diferente de onde_assistir, que sempre atualiza).
"""

from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from catalog import busca_externa, views
from catalog.tests.fabricas import criar_filme, criar_serie


def _video(key="abc123", tipo="Trailer", site="YouTube", official=True):
    return {"key": key, "type": tipo, "site": site, "official": official}


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

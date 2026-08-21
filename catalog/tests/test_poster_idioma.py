"""
Testes do pôster "local" — quando a pessoa troca o idioma do site, a capa
do filme/série também troca pra uma versão com o título escrito naquela
língua, se o TMDB tiver uma (é assim que o próprio site do TMDB troca de
capa ao trocar de idioma: cada mercado costuma ter uma arte própria, em
vez de só reaproveitar a mesma imagem original).

De onde vem: o TMDB tem um bloco "images" (append_to_response, mesma
chamada que já buscava elenco/onde assistir/trailer — sem requisição
extra) com TODOS os pôsteres cadastrados pra aquele título, cada um
marcado com o idioma do texto nele (`iso_639_1`, ex: "pt", "en", ou
None pra pôster "sem texto"/textless). Pedimos explicitamente o idioma da
página (`include_image_language`) e escolhemos o primeiro pôster marcado
nesse idioma.

REGRA DE FALLBACK (pedida explicitamente): se não existir NENHUM pôster
nesse idioma específico, mantém o pôster ORIGINAL de lançamento
(`item.poster_url`) — nunca cai pra um pôster genérico/textless nem fica
sem imagem.

- `busca_externa._extrair_poster_no_idioma` → escolhe o pôster certo entre
  os candidatos brutos do TMDB, pro idioma pedido.
- `detalhes_filme`/`detalhes_serie` → conferem que "poster_no_idioma" sai
  preenchido e que `include_image_language` é passado certinho.
- `views._poster_no_idioma`/`_buscar_traducao_agora` → o pôster que
  aparece de verdade pra quem está navegando num idioma diferente do
  original — reaproveita o mesmo cache/mecanismo já usado pra
  título/sinopse/trailer traduzidos (ver test_traducao_tmdb.py e
  test_trailer_youtube.py). Livro nunca troca de capa por idioma (Open
  Library não tem esse conceito).
"""

from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from catalog import busca_externa, views
from catalog.tests.fabricas import criar_filme, criar_livro, criar_serie


def _poster(caminho="/poster-pt.jpg", idioma="pt"):
    return {"file_path": caminho, "iso_639_1": idioma}


class ExtrairPosterNoIdiomaTest(SimpleTestCase):
    def test_acha_poster_no_idioma_pedido(self):
        dados = {"images": {"posters": [_poster(idioma="en"), _poster("/poster-pt.jpg", idioma="pt")]}}
        url = busca_externa._extrair_poster_no_idioma(dados, idioma="pt-BR")
        self.assertEqual(url, f"{busca_externa.TMDB_IMAGE_BASE_URL}/poster-pt.jpg")

    def test_sem_poster_nesse_idioma_devolve_vazio(self):
        dados = {"images": {"posters": [_poster(idioma="en")]}}
        url = busca_externa._extrair_poster_no_idioma(dados, idioma="pt-BR")
        self.assertEqual(url, "")

    def test_sem_nenhum_poster_devolve_vazio(self):
        self.assertEqual(busca_externa._extrair_poster_no_idioma({}, idioma="pt-BR"), "")
        self.assertEqual(
            busca_externa._extrair_poster_no_idioma({"images": {"posters": []}}, idioma="pt-BR"), ""
        )

    def test_ignora_poster_sem_file_path(self):
        dados = {"images": {"posters": [{"file_path": "", "iso_639_1": "pt"}]}}
        self.assertEqual(busca_externa._extrair_poster_no_idioma(dados, idioma="pt-BR"), "")

    def test_idioma_composto_e_comparado_so_pela_parte_curta(self):
        dados = {"images": {"posters": [_poster("/poster-pt.jpg", idioma="pt")]}}
        url = busca_externa._extrair_poster_no_idioma(dados, idioma="pt-BR")
        self.assertEqual(url, f"{busca_externa.TMDB_IMAGE_BASE_URL}/poster-pt.jpg")

    def test_pega_o_primeiro_poster_que_bater_com_o_idioma(self):
        # O TMDB já devolve os pôsteres ordenados por relevância (nota da
        # comunidade) — a gente só pega o primeiro que bater com o idioma.
        dados = {
            "images": {
                "posters": [
                    _poster("/melhor-pt.jpg", idioma="pt"),
                    _poster("/outro-pt.jpg", idioma="pt"),
                ]
            }
        }
        url = busca_externa._extrair_poster_no_idioma(dados, idioma="pt-BR")
        self.assertEqual(url, f"{busca_externa.TMDB_IMAGE_BASE_URL}/melhor-pt.jpg")


class DetalhesFilmeSerieIncluiPosterNoIdiomaTest(SimpleTestCase):
    def test_detalhes_filme_pede_images_e_include_image_language(self):
        with patch("catalog.busca_externa._tmdb_get", return_value={"title": "X", "credits": {}}) as mock_get:
            busca_externa.detalhes_filme("123", idioma="pt-BR")

        parametros = mock_get.call_args[0][1]
        self.assertIn("images", parametros["append_to_response"])
        self.assertIn("pt", parametros["include_image_language"])
        self.assertIn("null", parametros["include_image_language"])

    def test_detalhes_filme_devolve_poster_no_idioma(self):
        dados_tmdb = {
            "title": "X", "credits": {},
            "images": {"posters": [_poster("/capa-pt.jpg", idioma="pt")]},
        }
        with patch("catalog.busca_externa._tmdb_get", return_value=dados_tmdb):
            info = busca_externa.detalhes_filme("123", idioma="pt-BR")
        self.assertEqual(info["poster_no_idioma"], f"{busca_externa.TMDB_IMAGE_BASE_URL}/capa-pt.jpg")

    def test_detalhes_serie_pede_images_e_include_image_language(self):
        with patch("catalog.busca_externa._tmdb_get", return_value={"name": "X", "credits": {}}) as mock_get:
            busca_externa.detalhes_serie("456", idioma="en-US")

        parametros = mock_get.call_args[0][1]
        self.assertIn("images", parametros["append_to_response"])
        self.assertIn("en", parametros["include_image_language"])

    def test_detalhes_serie_devolve_poster_no_idioma(self):
        dados_tmdb = {
            "name": "X", "credits": {},
            "images": {"posters": [_poster("/capa-en.jpg", idioma="en")]},
        }
        with patch("catalog.busca_externa._tmdb_get", return_value=dados_tmdb):
            info = busca_externa.detalhes_serie("456", idioma="en-US")
        self.assertEqual(info["poster_no_idioma"], f"{busca_externa.TMDB_IMAGE_BASE_URL}/capa-en.jpg")


class PosterNoIdiomaTest(TestCase):
    """`views._poster_no_idioma` — o pôster que aparece de verdade na
    página, dependendo do idioma em que a pessoa está navegando o site."""

    def setUp(self):
        self.filme = criar_filme(
            idioma_tmdb_conteudo="en-US",
            poster_url="https://exemplo.com/original-en.jpg",
            id_externo="99999",
        )

    def test_mesmo_idioma_do_cadastro_usa_o_poster_original_direto(self):
        with patch("catalog.views.busca_externa.detalhes_filme") as mock_busca:
            url = views._poster_no_idioma(self.filme, "filme", "en-US")
            mock_busca.assert_not_called()
        self.assertEqual(url, "https://exemplo.com/original-en.jpg")

    def test_usa_poster_cacheado_pro_idioma_pedido_sem_buscar_de_novo(self):
        self.filme.traducoes = {
            "pt-BR": {
                "titulo": "X", "sinopse": "Y",
                "poster_url": "https://exemplo.com/capa-pt.jpg", "v": 2,
            }
        }
        self.filme.save()
        with patch("catalog.views.busca_externa.detalhes_filme") as mock_busca:
            url = views._poster_no_idioma(self.filme, "filme", "pt-BR")
            mock_busca.assert_not_called()
        self.assertEqual(url, "https://exemplo.com/capa-pt.jpg")

    def test_cache_sem_poster_pra_esse_idioma_mantem_o_original_de_lancamento(self):
        # Regra pedida explicitamente: sem um pôster próprio pra esse
        # idioma, mantém a capa ORIGINAL de lançamento — não fica sem
        # imagem nem usa algo genérico.
        self.filme.traducoes = {"pt-BR": {"titulo": "X", "sinopse": "Y", "v": 2}}
        self.filme.save()
        url = views._poster_no_idioma(self.filme, "filme", "pt-BR")
        self.assertEqual(url, "https://exemplo.com/original-en.jpg")

    def test_sem_cache_nenhum_tambem_mantem_original_sem_buscar(self):
        with patch("catalog.views.busca_externa.detalhes_filme") as mock_busca:
            url = views._poster_no_idioma(self.filme, "filme", "pt-BR")
            mock_busca.assert_not_called()
        self.assertEqual(url, "https://exemplo.com/original-en.jpg")

    def test_livro_nunca_troca_de_capa_por_idioma(self):
        livro = criar_livro(poster_url="https://exemplo.com/capa-livro.jpg")
        livro.traducoes = {"pt-BR": {"poster_url": "https://exemplo.com/deveria-ser-ignorado.jpg"}}
        livro.save()
        url = views._poster_no_idioma(livro, "livro", "pt-BR")
        self.assertEqual(url, "https://exemplo.com/capa-livro.jpg")


class BuscarTraducaoAgoraCacheiaPosterTest(TestCase):
    """`_buscar_traducao_agora` (já usada pra cachear título/sinopse/trailer
    traduzidos) agora também cacheia o pôster "local" desse idioma, já que
    vem de graça na mesma resposta do TMDB."""

    def setUp(self):
        self.filme = criar_filme(idioma_tmdb_conteudo="en-US", id_externo="12345")

    def test_guarda_o_poster_do_idioma_pedido_no_cache(self):
        resposta_simulada = {
            "titulo": "Título PT",
            "sinopse": "Sinopse em português.",
            "poster_no_idioma": "https://exemplo.com/capa-pt.jpg",
        }
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=resposta_simulada):
            views._texto_no_idioma(self.filme, "filme", "pt-BR")

        self.filme.refresh_from_db()
        self.assertEqual(self.filme.traducoes["pt-BR"]["poster_url"], "https://exemplo.com/capa-pt.jpg")

    def test_sem_poster_nesse_idioma_guarda_vazio_no_cache(self):
        resposta_simulada = {"titulo": "Título PT", "sinopse": "Sinopse.", "poster_no_idioma": ""}
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=resposta_simulada):
            views._texto_no_idioma(self.filme, "filme", "pt-BR")

        self.filme.refresh_from_db()
        self.assertEqual(self.filme.traducoes["pt-BR"]["poster_url"], "")

    def test_texto_no_idioma_seguido_de_poster_no_idioma_usa_o_poster_certo(self):
        # Fluxo real da view `detalhe`: _texto_no_idioma primeiro (popula o
        # cache), depois _poster_no_idioma (lê o cache já preenchido) —
        # confere que os dois juntos dão o resultado certo, numa ÚNICA
        # chamada à API.
        resposta_simulada = {
            "titulo": "Título PT",
            "sinopse": "Sinopse em português.",
            "poster_no_idioma": "https://exemplo.com/capa-pt.jpg",
        }
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=resposta_simulada) as mock_busca:
            views._texto_no_idioma(self.filme, "filme", "pt-BR")
            self.filme.refresh_from_db()
            url = views._poster_no_idioma(self.filme, "filme", "pt-BR")
            self.assertEqual(mock_busca.call_count, 1)  # só UMA chamada à API

        self.assertEqual(url, "https://exemplo.com/capa-pt.jpg")


class CacheAntigoSemPosterEReprocessadoTest(TestCase):
    """Regressão: entradas cacheadas ANTES do pôster por idioma existir
    (formato "v": 2, sem a chave "poster_url") ficavam presas pra sempre no
    pôster de fallback — `_texto_no_idioma`/`_traduzir_varios` só disparam
    busca nova quando NÃO existe cache pra aquele idioma, não quando existe
    mas está incompleto. A correção bumped a versão do cache pra 3; o
    comando `limpar_cache_traducoes` (rodado a cada deploy) descarta essas
    entradas "v": 2 antigas, forçando uma busca nova que já inclui o
    pôster."""

    def setUp(self):
        self.filme = criar_filme(
            idioma_tmdb_conteudo="en-US",
            poster_url="https://exemplo.com/original-en.jpg",
            id_externo="12345",
        )

    def test_limpeza_descarta_entrada_v2_sem_poster_e_proxima_visita_busca_de_novo(self):
        # Entrada "v": 2 pré-pôster — tem título/sinopse, mas nunca teve a
        # chance de guardar "poster_url" (a chave nem existe).
        self.filme.traducoes = {"zh-CN": {"titulo": "标题", "sinopse": "Sinopse.", "v": 2}}
        self.filme.save()

        call_command("limpar_cache_traducoes")
        self.filme.refresh_from_db()
        self.assertEqual(self.filme.traducoes, {})

        # Próxima visita nesse idioma: sem cache nenhum agora, então busca
        # de novo — e dessa vez o TMDB tem uma capa própria pra esse
        # idioma, que finalmente é cacheada e exibida.
        resposta_simulada = {
            "titulo": "标题",
            "sinopse": "Sinopse.",
            "poster_no_idioma": "https://exemplo.com/capa-zh.jpg",
        }
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=resposta_simulada):
            views._texto_no_idioma(self.filme, "filme", "zh-CN")
            self.filme.refresh_from_db()
            url = views._poster_no_idioma(self.filme, "filme", "zh-CN")

        self.assertEqual(url, "https://exemplo.com/capa-zh.jpg")
        self.assertEqual(self.filme.traducoes["zh-CN"]["v"], 3)

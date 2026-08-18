"""
Testes de que título/sinopse/pôster traduzidos (ver `views._aplicar_
exibicao`, `_texto_no_idioma`, `_poster_no_idioma`) aparecem de verdade nas
páginas que mostram VÁRIOS cards de uma vez — home ("recentes"), listagem
(`/filme/`, `/serie/`, `/livro/`) e busca — não só na página de detalhe de
um único título e no carrossel de destaque do topo da home.

CONTEXTO REAL que motivou esses testes: a troca de idioma já funcionava na
página de detalhe e no carrossel de destaque, mas os cards das outras
páginas (fileiras "recentes" da home, aba de listagem por tipo, resultados
de busca) continuavam mostrando sempre o título/capa ORIGINAL, mesmo com o
site em outro idioma — porque esses lugares nunca chamavam a função de
tradução, só usavam `item.titulo`/`item.poster_url` direto.

Usamos `unittest.mock.patch` pra simular a resposta do TMDB sem depender de
rede/chave de API de verdade — mesma abordagem de test_traducao_tmdb.py e
test_poster_idioma.py.
"""

from unittest.mock import patch

from django.test import Client, TestCase

from catalog.tests.fabricas import criar_filme, criar_serie


def _resposta_tmdb(titulo="Título PT", poster="/capa-pt.jpg"):
    return {
        "titulo": titulo,
        "sinopse": "Sinopse em português.",
        "trailer_youtube_url": "",
        "poster_no_idioma": f"https://image.tmdb.org/t/p/w500{poster}" if poster else "",
    }


class HomeMostraExibicaoTraduzidaTest(TestCase):
    def setUp(self):
        self.client = Client()
        # ano_lancamento fixo no passado — sempre entra na fileira
        # "recentes" (filtro é <= ano atual), sem depender da data de hoje.
        self.filme = criar_filme(
            titulo="Original EN",
            ano=2020,
            idioma_tmdb_conteudo="en-US",
            id_externo="123",
            poster_url="https://exemplo.com/original.jpg",
        )

    def test_fileira_recentes_mostra_titulo_e_capa_no_idioma_do_site(self):
        self.client.get("/idioma/pt/")
        with patch(
            "catalog.views.busca_externa.detalhes_filme",
            return_value=_resposta_tmdb(titulo="Título PT", poster="/capa-pt.jpg"),
        ):
            resposta = self.client.get("/")

        self.assertContains(resposta, "Título PT")
        self.assertContains(resposta, "https://image.tmdb.org/t/p/w500/capa-pt.jpg")
        self.assertNotContains(resposta, "Original EN")

    def test_sem_tradução_disponível_mantem_titulo_e_capa_originais(self):
        self.client.get("/idioma/pt/")
        with patch(
            "catalog.views.busca_externa.detalhes_filme",
            return_value=_resposta_tmdb(titulo="Original EN", poster=""),
        ):
            resposta = self.client.get("/")

        self.assertContains(resposta, "Original EN")
        self.assertContains(resposta, "https://exemplo.com/original.jpg")


class ListaMostraExibicaoTraduzidaTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.serie = criar_serie(
            titulo="Original EN",
            ano=2021,
            idioma_tmdb_conteudo="en-US",
            id_externo="456",
            poster_url="https://exemplo.com/original-serie.jpg",
        )

    def test_aba_de_listagem_mostra_titulo_e_capa_no_idioma_do_site(self):
        self.client.get("/idioma/pt/")
        with patch(
            "catalog.views.busca_externa.detalhes_serie",
            return_value=_resposta_tmdb(titulo="Série em Português", poster="/capa-serie-pt.jpg"),
        ):
            resposta = self.client.get("/serie/")

        self.assertContains(resposta, "Série em Português")
        self.assertContains(resposta, "https://image.tmdb.org/t/p/w500/capa-serie-pt.jpg")

    def test_no_idioma_original_do_cadastro_nao_chama_a_api(self):
        self.client.get("/idioma/en/")
        with patch("catalog.views.busca_externa.detalhes_serie") as mock_busca:
            resposta = self.client.get("/serie/")
            mock_busca.assert_not_called()
        self.assertContains(resposta, "Original EN")


class BuscaMostraExibicaoTraduzidaTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.filme = criar_filme(
            titulo="Bâtards",
            ano=2019,
            idioma_tmdb_conteudo="en-US",
            id_externo="789",
            poster_url="https://exemplo.com/original-busca.jpg",
        )

    def test_resultado_de_busca_ja_existente_mostra_traducao(self):
        self.client.get("/idioma/pt/")
        with patch(
            "catalog.views.busca_externa.detalhes_filme",
            return_value=_resposta_tmdb(titulo="Bastardos", poster="/capa-busca-pt.jpg"),
        ):
            with patch("catalog.views.busca_externa.buscar_filmes_series", return_value=[]):
                with patch("catalog.views.busca_externa.buscar_livros", return_value=[]):
                    resposta = self.client.get("/busca/?q=Bâtards")

        self.assertContains(resposta, "Bastardos")
        self.assertContains(resposta, "https://image.tmdb.org/t/p/w500/capa-busca-pt.jpg")

"""
Testes do comando `popular_catalogo` (catalog/management/commands/
popular_catalogo.py) e das funções de listagem do TMDB que ele usa
(catalog/busca_externa.py: filmes_populares, filmes_bem_avaliados,
series_populares, series_bem_avaliadas).

CONTEXTO: esse comando existe pra pré-popular o catálogo com uma leva de
títulos populares/bem avaliados do TMDB, respondendo ao pedido "queria usar
um banco tipo o do IMDb, com todos os filmes aparecendo, mas sem ocupar
espaço no Render". Importar o dump oficial do IMDb (mais de 1 GB só de
texto, milhões de linhas) não cabe no plano gratuito — a solução foi
importar só uma quantidade configurável de títulos POPULARES (usando o
mesmo "modo rápido" já usado pela busca pública, sem gastar chamada extra
de API por título), de forma idempotente (não duplica em execuções
seguintes), pra poder ficar direto no build.sh.
"""

from unittest.mock import patch

import requests
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from catalog import busca_externa
from catalog.models import Filme, Serie


def _item_tmdb(id_, titulo, data="2024-05-01"):
    """Simula um item "cru" como vem numa lista do TMDB (/movie/popular,
    /tv/top_rated etc.) — mesmo formato usado em qualquer endpoint de
    listagem/busca deles. Usado nos testes de `ListarTmdbTest`, que mockam
    a chamada de rede EM SI (`_tmdb_get`) — o formato de entrada precisa
    ser o formato bruto da API."""
    return {
        "id": id_,
        "title": titulo,
        "release_date": data,
        "overview": f"Sinopse de {titulo}.",
        "poster_path": "/poster.jpg",
        "genre_ids": [],
    }


def _resultado_resumido(id_, titulo, ano="2024"):
    """Simula um resultado JÁ PROCESSADO, no formato que `filmes_populares`/
    `filmes_bem_avaliados`/`series_populares`/`series_bem_avaliadas`
    devolvem de verdade (ver `busca_externa._resumo_de_item_tmdb`) — usado
    nos testes de `PopularCatalogoCommandTest`, que mockam essas funções
    DIRETO (uma camada acima de `_tmdb_get`), então precisam do formato de
    SAÍDA delas, não do formato bruto da API."""
    return {
        "id": id_,
        "titulo": titulo,
        "ano": ano,
        "data_lancamento": None,
        "poster_url": "https://exemplo.test/poster.jpg",
        "resumo": f"Sinopse de {titulo}.",
        "sinopse": f"Sinopse de {titulo}.",
        "generos": [],
    }


class ListarTmdbTest(SimpleTestCase):
    """Testa `_listar_tmdb` e as 4 funções que a usam (filmes_populares,
    filmes_bem_avaliados, series_populares, series_bem_avaliadas) — todas
    "puras" no sentido de não tocar no banco, só simulam a resposta da API
    via mock, por isso SimpleTestCase (mais rápido que TestCase)."""

    def test_sem_tmdb_api_key_devolve_lista_vazia(self):
        with patch("catalog.busca_externa.tmdb_configurado", return_value=False):
            self.assertEqual(busca_externa.filmes_populares(), [])
            self.assertEqual(busca_externa.series_bem_avaliadas(), [])

    def test_uma_pagina_devolve_os_resultados_dela(self):
        resposta_simulada = {
            "results": [_item_tmdb(1, "Filme Um"), _item_tmdb(2, "Filme Dois")],
            "total_pages": 1,
        }
        with patch("catalog.busca_externa.tmdb_configurado", return_value=True), patch(
            "catalog.busca_externa._tmdb_get", return_value=resposta_simulada
        ):
            resultados = busca_externa.filmes_populares(paginas=1)

        self.assertEqual(len(resultados), 2)
        self.assertEqual(resultados[0]["titulo"], "Filme Um")
        self.assertEqual(resultados[0]["ano"], "2024")

    def test_pede_varias_paginas_quando_solicitado(self):
        # Cada página do TMDB é uma chamada separada — pedindo 2 páginas,
        # a função tem que chamar a API duas vezes e juntar os resultados.
        pagina1 = {"results": [_item_tmdb(1, "Filme Um")], "total_pages": 3}
        pagina2 = {"results": [_item_tmdb(2, "Filme Dois")], "total_pages": 3}
        with patch("catalog.busca_externa.tmdb_configurado", return_value=True), patch(
            "catalog.busca_externa._tmdb_get", side_effect=[pagina1, pagina2]
        ) as mock_get:
            resultados = busca_externa.filmes_bem_avaliados(paginas=2)

        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual({r["titulo"] for r in resultados}, {"Filme Um", "Filme Dois"})

    def test_para_de_pedir_paginas_quando_acaba_o_total_disponivel(self):
        # Se o TMDB diz que só existe 1 página no total, não faz sentido
        # pedir a página 2 mesmo que o comando tenha solicitado mais.
        unica_pagina = {"results": [_item_tmdb(1, "Único Filme")], "total_pages": 1}
        with patch("catalog.busca_externa.tmdb_configurado", return_value=True), patch(
            "catalog.busca_externa._tmdb_get", return_value=unica_pagina
        ) as mock_get:
            busca_externa.series_populares(paginas=5)

        mock_get.assert_called_once()

    def test_falha_numa_pagina_nao_derruba_o_que_ja_foi_buscado(self):
        # Se a segunda página falhar (rede/API fora do ar), o que já foi
        # buscado na primeira não pode ser jogado fora.
        pagina1 = {"results": [_item_tmdb(1, "Filme Um")], "total_pages": 3}
        with patch("catalog.busca_externa.tmdb_configurado", return_value=True), patch(
            "catalog.busca_externa._tmdb_get",
            side_effect=[pagina1, requests.RequestException("Falha de rede")],
        ):
            resultados = busca_externa.filmes_populares(paginas=2)

        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["titulo"], "Filme Um")


class PopularCatalogoCommandTest(TestCase):
    """Testa o comando de ponta a ponta (contra o banco de teste de
    verdade), mockando só a "borda" com o TMDB — as funções de
    busca_externa que o comando chama."""

    def test_sem_tmdb_api_key_nao_importa_nada_e_nao_quebra(self):
        with patch("catalog.busca_externa.tmdb_configurado", return_value=False):
            call_command("popular_catalogo")  # não deve levantar exceção
        self.assertEqual(Filme.objects.count(), 0)
        self.assertEqual(Serie.objects.count(), 0)

    def test_importa_filmes_e_series_respeitando_a_quantidade_pedida(self):
        filmes_simulados = [_resultado_resumido(i, f"Filme {i}") for i in range(1, 11)]
        series_simuladas = [_resultado_resumido(100 + i, f"Série {i}") for i in range(1, 11)]

        with patch("catalog.busca_externa.tmdb_configurado", return_value=True), patch(
            "catalog.management.commands.popular_catalogo.busca_externa.filmes_populares",
            return_value=filmes_simulados,
        ), patch(
            "catalog.management.commands.popular_catalogo.busca_externa.filmes_bem_avaliados",
            return_value=[],
        ), patch(
            "catalog.management.commands.popular_catalogo.busca_externa.series_populares",
            return_value=series_simuladas,
        ), patch(
            "catalog.management.commands.popular_catalogo.busca_externa.series_bem_avaliadas",
            return_value=[],
        ):
            call_command("popular_catalogo", "--quantidade", "10")

        # --quantidade 10, com a fatia padrão de 65% pra filme: 6-7 filmes
        # e o restante de série (a quantidade exata de candidatos
        # disponíveis pra cada um também limita, já que só simulamos 10
        # de cada categoria acima).
        self.assertGreater(Filme.objects.count(), 0)
        self.assertGreater(Serie.objects.count(), 0)
        self.assertEqual(Filme.objects.count() + Serie.objects.count(), 10)

    def test_e_idempotente_rodar_duas_vezes_nao_duplica(self):
        filmes_simulados = [_resultado_resumido(i, f"Filme {i}") for i in range(1, 6)]

        with patch("catalog.busca_externa.tmdb_configurado", return_value=True), patch(
            "catalog.management.commands.popular_catalogo.busca_externa.filmes_populares",
            return_value=filmes_simulados,
        ), patch(
            "catalog.management.commands.popular_catalogo.busca_externa.filmes_bem_avaliados",
            return_value=[],
        ), patch(
            "catalog.management.commands.popular_catalogo.busca_externa.series_populares",
            return_value=[],
        ), patch(
            "catalog.management.commands.popular_catalogo.busca_externa.series_bem_avaliadas",
            return_value=[],
        ):
            call_command("popular_catalogo", "--quantidade", "5")
            total_apos_primeira_vez = Filme.objects.count()

            call_command("popular_catalogo", "--quantidade", "5")
            total_apos_segunda_vez = Filme.objects.count()

        # --quantidade 5, com a fatia de 65% pra filme, dá alvo_filmes=3
        # (round(5*0.65)) — o importante aqui não é o número exato, é que a
        # SEGUNDA execução não crie duplicata nenhuma da primeira.
        self.assertEqual(total_apos_primeira_vez, 3)
        self.assertEqual(total_apos_segunda_vez, 3)  # não duplicou

    def test_titulo_repetido_entre_populares_e_bem_avaliados_nao_conta_duas_vezes(self):
        # É comum o MESMO filme aparecer tanto na lista de populares quanto
        # na de bem avaliados — não pode ser importado/contado duas vezes.
        filme_em_comum = _resultado_resumido(1, "Filme Aclamado")

        with patch("catalog.busca_externa.tmdb_configurado", return_value=True), patch(
            "catalog.management.commands.popular_catalogo.busca_externa.filmes_populares",
            return_value=[filme_em_comum],
        ), patch(
            "catalog.management.commands.popular_catalogo.busca_externa.filmes_bem_avaliados",
            return_value=[filme_em_comum],
        ), patch(
            "catalog.management.commands.popular_catalogo.busca_externa.series_populares",
            return_value=[],
        ), patch(
            "catalog.management.commands.popular_catalogo.busca_externa.series_bem_avaliadas",
            return_value=[],
        ):
            call_command("popular_catalogo", "--quantidade", "10")

        self.assertEqual(Filme.objects.count(), 1)

    def test_quantidade_zero_nao_importa_nada(self):
        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            call_command("popular_catalogo", "--quantidade", "0")
        self.assertEqual(Filme.objects.count(), 0)
        self.assertEqual(Serie.objects.count(), 0)

"""
Testes de "onde assistir" (streaming por assinatura, aluguel, compra).

De onde vem: o TMDB tem um bloco de dados chamado "watch/providers" —
pedido junto com o resto dos detalhes do filme/série (mesma chamada que já
buscava elenco/sinopse, via `append_to_response`, então não gasta requisição
extra) — que devolve, por PAÍS, quais serviços de streaming têm aquele
título disponível. A fonte de verdade por trás disso é a JustWatch (por
isso a atribuição obrigatória no template, ver `templates/catalog/
detalhe.html`); fixamos a região "BR" porque o site é em português e
hospedado pensando no público brasileiro.

- `busca_externa._extrair_onde_assistir` → parsing do bloco bruto do TMDB.
- `busca_externa.detalhes_filme`/`detalhes_serie` → conferem que o campo
  novo ("onde_assistir") sai preenchido no dict final.
- `views._completar_filme`/`_completar_serie` → conferem que o campo é
  salvo no banco durante a "completada" automática de dados.
- `atualizar_onde_assistir` (comando de manutenção) → conferem que ele
  RE-busca (não só a primeira vez) pra pegar mudanças de catálogo dos
  serviços de streaming.
"""

from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from catalog import busca_externa, views
from catalog.tests.fabricas import criar_filme, criar_serie


def _bloco_watch_providers_tmdb(regiao="BR", **categorias):
    """Simula o formato bruto que o TMDB devolve dentro de
    `dados["watch/providers"]["results"]`."""
    return {"watch/providers": {"results": {regiao: categorias}}}


class ExtrairOndeAssistirTest(SimpleTestCase):
    def test_extrai_streaming_aluguel_e_compra(self):
        dados = _bloco_watch_providers_tmdb(
            link="https://www.themoviedb.org/movie/1/watch",
            flatrate=[{"provider_name": "Netflix", "logo_path": "/netflix.jpg"}],
            rent=[{"provider_name": "Google Play Filmes", "logo_path": "/gplay.jpg"}],
            buy=[{"provider_name": "Apple TV", "logo_path": "/appletv.jpg"}],
        )
        resultado = busca_externa._extrair_onde_assistir(dados)

        self.assertEqual(resultado["link"], "https://www.themoviedb.org/movie/1/watch")
        self.assertEqual(resultado["streaming"], [{"nome": "Netflix", "logo_url": f"{busca_externa.TMDB_IMAGE_BASE_URL}/netflix.jpg"}])
        self.assertEqual(resultado["aluguel"][0]["nome"], "Google Play Filmes")
        self.assertEqual(resultado["compra"][0]["nome"], "Apple TV")

    def test_usa_a_regiao_br_e_ignora_outras_regioes(self):
        dados = _bloco_watch_providers_tmdb(
            regiao="US",
            flatrate=[{"provider_name": "Hulu", "logo_path": "/hulu.jpg"}],
        )
        resultado = busca_externa._extrair_onde_assistir(dados)
        self.assertEqual(resultado, {})  # não tem bloco "BR" nesse exemplo

    def test_sem_nenhum_provedor_devolve_dict_vazio(self):
        dados = {"watch/providers": {"results": {"BR": {}}}}
        resultado = busca_externa._extrair_onde_assistir(dados)
        self.assertEqual(resultado, {})

    def test_sem_o_bloco_watch_providers_nao_da_erro(self):
        resultado = busca_externa._extrair_onde_assistir({})
        self.assertEqual(resultado, {})

    def test_provedor_sem_nome_e_descartado(self):
        dados = _bloco_watch_providers_tmdb(flatrate=[{"provider_name": "", "logo_path": "/x.jpg"}])
        resultado = busca_externa._extrair_onde_assistir(dados)
        self.assertEqual(resultado, {})


class DetalhesFilmeSerieIncluiOndeAssistirTest(SimpleTestCase):
    """Confere que `detalhes_filme`/`detalhes_serie` pedem o bloco certo ao
    TMDB (append_to_response) e devolvem "onde_assistir" no dict final."""

    def test_detalhes_filme_pede_watch_providers_no_append_to_response(self):
        with patch("catalog.busca_externa._tmdb_get", return_value={"title": "X", "credits": {}}) as mock_get:
            busca_externa.detalhes_filme("123")

        parametros = mock_get.call_args[0][1]
        self.assertIn("watch/providers", parametros["append_to_response"])

    def test_detalhes_filme_devolve_onde_assistir_preenchido(self):
        dados_tmdb = {"title": "X", "credits": {}}
        dados_tmdb.update(_bloco_watch_providers_tmdb(flatrate=[{"provider_name": "Netflix", "logo_path": "/n.jpg"}]))
        with patch("catalog.busca_externa._tmdb_get", return_value=dados_tmdb):
            info = busca_externa.detalhes_filme("123")

        self.assertEqual(info["onde_assistir"]["streaming"][0]["nome"], "Netflix")

    def test_detalhes_serie_pede_watch_providers_no_append_to_response(self):
        with patch("catalog.busca_externa._tmdb_get", return_value={"name": "X", "credits": {}}) as mock_get:
            busca_externa.detalhes_serie("456")

        self.assertIn("watch/providers", mock_get.call_args[0][1]["append_to_response"])

    def test_detalhes_serie_devolve_onde_assistir_preenchido(self):
        dados_tmdb = {"name": "X", "credits": {}}
        dados_tmdb.update(_bloco_watch_providers_tmdb(rent=[{"provider_name": "Google Play", "logo_path": "/g.jpg"}]))
        with patch("catalog.busca_externa._tmdb_get", return_value=dados_tmdb):
            info = busca_externa.detalhes_serie("456")

        self.assertEqual(info["onde_assistir"]["aluguel"][0]["nome"], "Google Play")


class CompletarFilmeSerieSalvaOndeAssistirTest(TestCase):
    def test_completar_filme_salva_onde_assistir(self):
        filme = criar_filme(id_externo="123", dados_completos=False)
        info_simulada = {
            "sinopse": "", "diretor": "", "duracao_minutos": None, "poster_url": "",
            "imdb_id": "", "data_lancamento": None,
            "onde_assistir": {"link": "", "streaming": [{"nome": "Netflix", "logo_url": ""}], "aluguel": [], "compra": []},
        }
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=info_simulada):
            with patch("catalog.views.busca_externa.omdb_configurado", return_value=False):
                views._completar_filme(filme)

        filme.refresh_from_db()
        self.assertEqual(filme.onde_assistir["streaming"][0]["nome"], "Netflix")

    def test_completar_serie_salva_onde_assistir(self):
        serie = criar_serie(id_externo="456", dados_completos=False)
        info_simulada = {
            "sinopse": "", "criador": "", "numero_temporadas": None, "poster_url": "",
            "imdb_id": "", "data_lancamento": None,
            "onde_assistir": {"link": "", "streaming": [], "aluguel": [{"nome": "Apple TV", "logo_url": ""}], "compra": []},
        }
        with patch("catalog.views.busca_externa.detalhes_serie", return_value=info_simulada):
            with patch("catalog.views.busca_externa.omdb_configurado", return_value=False):
                views._completar_serie(serie)

        serie.refresh_from_db()
        self.assertEqual(serie.onde_assistir["aluguel"][0]["nome"], "Apple TV")

    def test_titulo_sem_nenhum_provedor_fica_com_dict_vazio_sem_erro(self):
        filme = criar_filme(id_externo="789", dados_completos=False)
        info_simulada = {
            "sinopse": "", "diretor": "", "duracao_minutos": None, "poster_url": "",
            "imdb_id": "", "data_lancamento": None, "onde_assistir": {},
        }
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=info_simulada):
            with patch("catalog.views.busca_externa.omdb_configurado", return_value=False):
                views._completar_filme(filme)

        filme.refresh_from_db()
        self.assertEqual(filme.onde_assistir, {})


class AtualizarOndeAssistirCommandTest(TestCase):
    """O comando de manutenção que RE-busca essa informação (diferente dos
    outros comandos de completar dados, que só rodam uma vez — ver
    docstring de `atualizar_onde_assistir.py` sobre por quê)."""

    def test_sem_tmdb_api_key_nao_faz_nada(self):
        filme = criar_filme(id_externo="123")
        with patch("catalog.busca_externa.tmdb_configurado", return_value=False):
            call_command("atualizar_onde_assistir")
        filme.refresh_from_db()
        self.assertEqual(filme.onde_assistir, {})

    def test_atualiza_filme_com_id_externo(self):
        filme = criar_filme(id_externo="123", onde_assistir={})
        info_simulada = {"onde_assistir": {"link": "", "streaming": [{"nome": "Netflix", "logo_url": ""}], "aluguel": [], "compra": []}}
        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch("catalog.management.commands.atualizar_onde_assistir.busca_externa.detalhes_filme", return_value=info_simulada):
                with patch("catalog.management.commands.atualizar_onde_assistir.busca_externa.detalhes_serie", return_value={"onde_assistir": {}}):
                    call_command("atualizar_onde_assistir")

        filme.refresh_from_db()
        self.assertEqual(filme.onde_assistir["streaming"][0]["nome"], "Netflix")

    def test_ignora_titulos_sem_id_externo(self):
        criar_filme(id_externo="")  # nunca foi encontrado no TMDB ainda
        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch("catalog.management.commands.atualizar_onde_assistir.busca_externa.detalhes_filme") as mock_detalhes:
                with patch("catalog.management.commands.atualizar_onde_assistir.busca_externa.detalhes_serie", return_value={"onde_assistir": {}}):
                    call_command("atualizar_onde_assistir")
        mock_detalhes.assert_not_called()

    def test_re_busca_mesmo_quem_ja_tinha_onde_assistir_preenchido(self):
        # Diferente dos outros comandos "completar dados" (só uma vez): esse
        # busca de novo mesmo pra quem já tinha informação — pra pegar
        # mudança de catálogo de streaming.
        filme = criar_filme(id_externo="123", onde_assistir={"link": "", "streaming": [{"nome": "Netflix", "logo_url": ""}], "aluguel": [], "compra": []})
        info_nova = {"onde_assistir": {"link": "", "streaming": [{"nome": "Prime Video", "logo_url": ""}], "aluguel": [], "compra": []}}
        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch("catalog.management.commands.atualizar_onde_assistir.busca_externa.detalhes_filme", return_value=info_nova):
                with patch("catalog.management.commands.atualizar_onde_assistir.busca_externa.detalhes_serie", return_value={"onde_assistir": {}}):
                    call_command("atualizar_onde_assistir")

        filme.refresh_from_db()
        self.assertEqual(filme.onde_assistir["streaming"][0]["nome"], "Prime Video")

    def test_falha_temporaria_nao_apaga_o_que_ja_tinha(self):
        onde_assistir_atual = {"link": "", "streaming": [{"nome": "Netflix", "logo_url": ""}], "aluguel": [], "compra": []}
        filme = criar_filme(id_externo="123", onde_assistir=onde_assistir_atual)
        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch("catalog.management.commands.atualizar_onde_assistir.busca_externa.detalhes_filme", return_value=None):
                with patch("catalog.management.commands.atualizar_onde_assistir.busca_externa.detalhes_serie", return_value={"onde_assistir": {}}):
                    call_command("atualizar_onde_assistir")

        filme.refresh_from_db()
        self.assertEqual(filme.onde_assistir, onde_assistir_atual)

"""
Testes da sinopse mais detalhada vinda do OMDb (`plot=full`).

CONTEXTO: a sinopse que o TMDB devolve (`overview`) costuma ser bem curta —
praticamente um resumo de uma frase. O OMDb (omdbapi.com), que o site já
usa pra buscar as notas do público/crítica, também tem um campo "Plot" bem
mais completo quando pedimos com o parâmetro `plot=full` — e como é a MESMA
chamada que já buscava as notas, não gasta nenhuma requisição extra.

O detalhe importante: o OMDb só devolve texto em INGLÊS (não tem opção de
idioma, ao contrário do TMDB). Por isso a lógica em
`views._guardar_sinopse_detalhada_omdb` trata isso com cuidado — ver os
comentários da própria função e o `test_traducao_tmdb.py` (que já cobre o
mesmo tipo de cuidado, só que pro caso inverso: sinopse aparecendo na
língua errada por causa de uma tradução incompleta do TMDB).

- `busca_externa.py`  → testamos que `buscar_notas_omdb` pede `plot=full` e
  extrai o campo "Plot" certinho (inclusive o caso "N/A", que o OMDb usa
  pra "não tem essa informação").
- `views.py`          → testamos `_guardar_sinopse_detalhada_omdb` isolada
  (decide ONDE aplicar o texto em inglês) e sua integração dentro de
  `_garantir_notas_omdb` (a função chamada de verdade toda vez que a página
  de detalhe é aberta pela primeira vez).
"""

from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from catalog import busca_externa, views
from catalog.tests.fabricas import criar_filme


@override_settings(OMDB_API_KEY="chave-fake")
class BuscarNotasOmdbPlotTest(SimpleTestCase):
    """Cobre só a parte de rede/parsing do OMDb — não toca no banco.

    Usa uma OMDB_API_KEY falsa (via `override_settings`) porque, sem
    nenhuma chave configurada, `buscar_notas_omdb` nem chega a chamar a
    rede — devolve tudo vazio de cara (ver `test_sem_chave_configurada_...`
    logo abaixo, que testa exatamente esse outro caminho, SEM a chave)."""

    def _resposta_base(self, **extra):
        base = {
            "Response": "True",
            "imdbRating": "8.1",
            "Ratings": [],
        }
        base.update(extra)
        return base

    def test_pede_plot_full_buscando_por_imdb_id(self):
        with patch("catalog.busca_externa.requests.get") as mock_get:
            mock_get.return_value.json.return_value = self._resposta_base(Plot="Um resumo bem completo.")
            mock_get.return_value.raise_for_status.return_value = None
            busca_externa.buscar_notas_omdb("Um Filme", 2020, imdb_id="tt1234567")

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["plot"], "full")

    def test_pede_plot_full_buscando_por_titulo(self):
        with patch("catalog.busca_externa.requests.get") as mock_get:
            mock_get.return_value.json.return_value = self._resposta_base(Plot="Outro resumo completo.")
            mock_get.return_value.raise_for_status.return_value = None
            busca_externa.buscar_notas_omdb("Um Filme", 2020)

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["plot"], "full")

    def test_extrai_o_campo_plot_pro_dict_de_retorno(self):
        with patch("catalog.busca_externa.requests.get") as mock_get:
            mock_get.return_value.json.return_value = self._resposta_base(
                Plot="Depois que o pai morre, o protagonista descobre um segredo de família."
            )
            mock_get.return_value.raise_for_status.return_value = None
            resultado = busca_externa.buscar_notas_omdb("Um Filme", 2020, imdb_id="tt1234567")

        self.assertEqual(
            resultado["sinopse_omdb"],
            "Depois que o pai morre, o protagonista descobre um segredo de família.",
        )

    def test_plot_n_a_vira_string_vazia(self):
        # O OMDb usa o texto literal "N/A" quando não tem essa informação —
        # não pode vazar isso pra sinopse mostrada no site.
        with patch("catalog.busca_externa.requests.get") as mock_get:
            mock_get.return_value.json.return_value = self._resposta_base(Plot="N/A")
            mock_get.return_value.raise_for_status.return_value = None
            resultado = busca_externa.buscar_notas_omdb("Um Filme", 2020, imdb_id="tt1234567")

        self.assertEqual(resultado["sinopse_omdb"], "")

    @override_settings(OMDB_API_KEY="")
    def test_sem_chave_configurada_devolve_sinopse_vazia_tambem(self):
        resultado = busca_externa.buscar_notas_omdb("Um Filme", 2020)
        self.assertEqual(resultado["sinopse_omdb"], "")

    def test_falha_de_rede_devolve_sinopse_vazia_sem_lancar_erro(self):
        with patch(
            "catalog.busca_externa.requests.get",
            side_effect=busca_externa.requests.RequestException("timeout"),
        ):
            resultado = busca_externa.buscar_notas_omdb("Um Filme", 2020, imdb_id="tt1234567")
        self.assertEqual(resultado["sinopse_omdb"], "")


class GuardarSinopseDetalhadaOmdbTest(TestCase):
    """Cobre a decisão de ONDE aplicar o texto em inglês vindo do OMDb —
    a parte mais delicada da funcionalidade (ver docstring do módulo)."""

    def test_titulo_nativo_em_ingles_aplica_direto_na_sinopse_se_for_maior(self):
        filme = criar_filme(
            sinopse="Short plot.",
            idioma_tmdb_conteudo="en-US",
        )
        views._guardar_sinopse_detalhada_omdb(filme, "A much longer and more detailed plot summary.")
        filme.refresh_from_db()
        self.assertEqual(filme.sinopse, "A much longer and more detailed plot summary.")

    def test_titulo_nativo_em_ingles_nao_aplica_se_a_sinopse_atual_ja_for_maior(self):
        sinopse_longa = "A" * 500
        filme = criar_filme(sinopse=sinopse_longa, idioma_tmdb_conteudo="en-US")
        views._guardar_sinopse_detalhada_omdb(filme, "Curta.")
        filme.refresh_from_db()
        self.assertEqual(filme.sinopse, sinopse_longa)

    def test_titulo_nativo_em_portugues_nao_mexe_na_sinopse_original(self):
        # Esse é o caso mais comum do site (idioma padrão pt-BR) — a
        # sinopse original NUNCA pode ser sobrescrita por texto em inglês.
        filme = criar_filme(
            sinopse="Um resumo curto em português.",
            idioma_tmdb_conteudo="pt-BR",
        )
        views._guardar_sinopse_detalhada_omdb(filme, "A much longer plot, but in English.")
        filme.refresh_from_db()
        self.assertEqual(filme.sinopse, "Um resumo curto em português.")

    def test_titulo_nativo_em_portugues_guarda_como_traducao_pronta_pro_ingles(self):
        filme = criar_filme(sinopse="Resumo em português.", idioma_tmdb_conteudo="pt-BR")
        views._guardar_sinopse_detalhada_omdb(filme, "A detailed English plot summary.")
        filme.refresh_from_db()
        self.assertEqual(filme.traducoes["en-US"]["sinopse"], "A detailed English plot summary.")
        self.assertEqual(filme.traducoes["en-US"]["v"], 3)
        # A sinopse original continua intacta.
        self.assertEqual(filme.sinopse, "Resumo em português.")

    def test_nao_sobrescreve_traducao_en_us_ja_existente_se_a_nova_for_menor(self):
        filme = criar_filme(idioma_tmdb_conteudo="pt-BR")
        filme.traducoes = {"en-US": {"titulo": "X", "sinopse": "A" * 300, "v": 2}}
        filme.save()

        views._guardar_sinopse_detalhada_omdb(filme, "curto")

        filme.refresh_from_db()
        self.assertEqual(filme.traducoes["en-US"]["sinopse"], "A" * 300)

    def test_sinopse_omdb_vazia_nao_faz_nada(self):
        filme = criar_filme(sinopse="Original.", idioma_tmdb_conteudo="pt-BR")
        views._guardar_sinopse_detalhada_omdb(filme, "")
        filme.refresh_from_db()
        self.assertEqual(filme.sinopse, "Original.")
        self.assertEqual(filme.traducoes, {})


class GarantirNotasOmdbAplicaSinopseTest(TestCase):
    """Integração: `_garantir_notas_omdb` (chamada de verdade na página de
    detalhe) já aplica a sinopse detalhada junto com as notas, numa única
    passada."""

    def test_aplica_sinopse_detalhada_junto_com_as_notas(self):
        filme = criar_filme(
            sinopse="Curto.",
            idioma_tmdb_conteudo="en-US",
            imdb_id="tt7654321",
        )
        notas_simuladas = {
            "nota_publico": 7.5,
            "nota_critica": None,
            "nota_rotten_tomatoes": None,
            "sinopse_omdb": "A much more detailed plot, straight from OMDb.",
        }
        with patch("catalog.views.busca_externa.buscar_notas_omdb", return_value=notas_simuladas):
            with patch("catalog.views.busca_externa.omdb_configurado", return_value=True):
                views._garantir_notas_omdb(filme, tipo="filme")

        filme.refresh_from_db()
        self.assertEqual(filme.sinopse, "A much more detailed plot, straight from OMDb.")
        self.assertEqual(filme.nota_publico, 7.5)

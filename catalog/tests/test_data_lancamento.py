"""
Testes da precisão de DIA no "já foi lançado?" (campo `data_lancamento` e a
função `views._titulo_ja_lancado`).

CONTEXTO: a regra "só avalia quem já lançou" (ver test_detalhe_e_avaliacoes.py)
começou comparando só o ANO (`ano_lancamento <= ano_atual`). Isso resolveu o
caso óbvio (ex: "Avatar 5", cadastrado com ano bem no futuro), mas deixava
passar um caso mais sutil, relatado pelo grupo com o exemplo do filme
"Doomsday": um título pode ter `ano_lancamento` IGUAL ao ano atual e mesmo
assim ainda não ter sido lançado de verdade (ex: previsto pra dezembro,
visto em agosto). A correção adiciona um campo `data_lancamento` (dia exato,
quando a API souber informar) e usa ele — com precisão de DIA — sempre que
disponível, caindo pro ano só quando não tivermos essa data (livros, ou
títulos cadastrados antes desse campo existir).

Este arquivo testa as PEÇAS que dão suporte a essa regra:
  - `busca_externa._parse_data`: converte a string de data do TMDB pra um
    `date` do Python, sem quebrar com dado malformado.
  - `busca_externa.detalhes_filme` / `detalhes_serie` / `buscar_filmes_series`:
    passam a devolver `data_lancamento` junto com os outros campos.
  - `views._completar_filme` / `_completar_serie`: preenchem
    `data_lancamento` pra títulos que já estão no catálogo mas ainda não
    tinham essa data (cadastrados antes desse campo existir, ou importados
    "rápido" pela busca).
  - o comando `buscar_datas_lancamento`: faz esse mesmo preenchimento em
    lote, pra rodar no build.sh a cada deploy.

A regra em si (bloquear/permitir avaliação) já é testada de ponta a ponta
em test_detalhe_e_avaliacoes.py (AvaliarTituloComDataFuturaNoMesmoAnoTest) —
não repetimos esses testes de view aqui, só as peças de mais baixo nível.
"""

import datetime
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from catalog import busca_externa, views
from catalog.tests.fabricas import criar_filme, criar_serie


class ParseDataTest(SimpleTestCase):
    """`_parse_data` é uma função "pura" (sem banco de dados, sem rede) —
    por isso usamos SimpleTestCase em vez de TestCase, um pouco mais rápido
    (não cria/destrói transação de banco pra cada teste)."""

    def test_data_valida_vira_um_date(self):
        resultado = busca_externa._parse_data("2026-12-25")
        self.assertEqual(resultado, datetime.date(2026, 12, 25))

    def test_string_vazia_devolve_none(self):
        self.assertIsNone(busca_externa._parse_data(""))

    def test_none_devolve_none(self):
        self.assertIsNone(busca_externa._parse_data(None))

    def test_data_malformada_devolve_none_em_vez_de_quebrar(self):
        # A API externa está fora do nosso controle — um formato inesperado
        # (ex: só o ano, ou uma string qualquer) não pode derrubar o site,
        # só devolver "não sabemos a data exata".
        self.assertIsNone(busca_externa._parse_data("2026"))
        self.assertIsNone(busca_externa._parse_data("data inválida"))


class DetalhesIncluemDataLancamentoTest(SimpleTestCase):
    """Confere que as três funções de busca_externa que trazem dados de
    filme/série do TMDB passam a incluir `data_lancamento` (data completa),
    e não só `ano`/`ano_lancamento` (só o ano) como antes. Simulamos a
    resposta da API mockando `_tmdb_get` (a função que faz a chamada de
    rede em si) — assim não depende de internet nem de TMDB_API_KEY."""

    def test_detalhes_filme_inclui_data_lancamento(self):
        resposta_simulada = {
            "title": "Doomsday",
            "release_date": "2026-12-31",
            "overview": "",
            "credits": {},
            "external_ids": {},
        }
        with patch("catalog.busca_externa._tmdb_get", return_value=resposta_simulada):
            info = busca_externa.detalhes_filme("123")

        self.assertEqual(info["ano_lancamento"], 2026)
        self.assertEqual(info["data_lancamento"], datetime.date(2026, 12, 31))

    def test_detalhes_filme_sem_release_date_deixa_data_lancamento_none(self):
        # Acontece na prática: alguns títulos (ex: ainda sem data confirmada)
        # vêm do TMDB com "release_date": "" — não pode quebrar.
        resposta_simulada = {"title": "Sem Data Ainda", "release_date": "", "credits": {}, "external_ids": {}}
        with patch("catalog.busca_externa._tmdb_get", return_value=resposta_simulada):
            info = busca_externa.detalhes_filme("456")

        self.assertIsNone(info["ano_lancamento"])
        self.assertIsNone(info["data_lancamento"])

    def test_detalhes_serie_inclui_data_lancamento(self):
        resposta_simulada = {
            "name": "Série Teste",
            "first_air_date": "2027-03-10",
            "overview": "",
            "created_by": [],
            "credits": {},
            "external_ids": {},
        }
        with patch("catalog.busca_externa._tmdb_get", return_value=resposta_simulada):
            info = busca_externa.detalhes_serie("789")

        self.assertEqual(info["ano_lancamento"], 2027)
        self.assertEqual(info["data_lancamento"], datetime.date(2027, 3, 10))

    def test_buscar_filmes_series_inclui_data_lancamento_em_cada_resultado(self):
        # Essa é a busca usada na tela de importação/busca pública — só ELA
        # que decide o que entra no catálogo quando alguém importa "rápido"
        # (sem abrir os detalhes completos), então também precisa trazer a
        # data exata, não só o ano.
        resposta_simulada = {
            "results": [
                {
                    "id": 1,
                    "title": "Doomsday",
                    "release_date": "2026-12-31",
                    "overview": "",
                    "genre_ids": [],
                }
            ]
        }
        with patch("catalog.busca_externa.tmdb_configurado", return_value=True), patch(
            "catalog.busca_externa._tmdb_get", return_value=resposta_simulada
        ):
            resultados = busca_externa.buscar_filmes_series("movie", "doomsday")

        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["ano"], "2026")
        self.assertEqual(resultados[0]["data_lancamento"], datetime.date(2026, 12, 31))


class CompletarPreencheDataLancamentoTest(TestCase):
    """`_completar_filme`/`_completar_serie` rodam na primeira visita à
    página de um título que ainda não tem `dados_completos=True` (ver
    catalog/views.py). Testamos aqui que, além do que já preenchiam antes
    (elenco, sinopse maior...), agora também preenchem `data_lancamento`
    quando o título ainda não tinha essa data."""

    def test_completar_filme_preenche_data_lancamento_que_estava_faltando(self):
        filme = criar_filme(
            titulo="Filme Sem Data Exata Ainda",
            ano=2026,
            data_lancamento=None,
            id_externo="111",
            dados_completos=False,
        )
        info_simulada = {
            "titulo": "Filme Sem Data Exata Ainda",
            "ano_lancamento": 2026,
            "data_lancamento": datetime.date(2026, 12, 31),
            "sinopse": "",
            "diretor": "",
            "duracao_minutos": None,
            "poster_url": "",
            "generos": [],
            "elenco": [],
            "imdb_id": "",
        }
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=info_simulada), patch(
            "catalog.views._garantir_notas_omdb"
        ):
            views._completar_filme(filme)

        filme.refresh_from_db()
        self.assertEqual(filme.data_lancamento, datetime.date(2026, 12, 31))

    def test_completar_filme_nao_sobrescreve_data_lancamento_ja_preenchida(self):
        # Se o filme já tinha uma data (ex: preenchida na criação), o
        # "completar" não deve trocar por outra — mesma lógica cautelosa já
        # usada pros outros campos aqui (diretor, duração, pôster...).
        data_original = datetime.date(2026, 6, 1)
        filme = criar_filme(
            titulo="Filme Com Data Já Preenchida",
            ano=2026,
            data_lancamento=data_original,
            id_externo="222",
            dados_completos=False,
        )
        info_simulada = {
            "titulo": "Filme Com Data Já Preenchida",
            "ano_lancamento": 2026,
            "data_lancamento": datetime.date(2026, 12, 31),  # diferente, não devia "ganhar"
            "sinopse": "",
            "diretor": "",
            "duracao_minutos": None,
            "poster_url": "",
            "generos": [],
            "elenco": [],
            "imdb_id": "",
        }
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=info_simulada), patch(
            "catalog.views._garantir_notas_omdb"
        ):
            views._completar_filme(filme)

        filme.refresh_from_db()
        self.assertEqual(filme.data_lancamento, data_original)

    def test_completar_serie_preenche_data_lancamento_que_estava_faltando(self):
        serie = criar_serie(
            titulo="Série Sem Data Exata Ainda",
            ano=2027,
            data_lancamento=None,
            id_externo="333",
            dados_completos=False,
        )
        info_simulada = {
            "titulo": "Série Sem Data Exata Ainda",
            "ano_lancamento": 2027,
            "data_lancamento": datetime.date(2027, 3, 10),
            "sinopse": "",
            "criador": "",
            "numero_temporadas": None,
            "poster_url": "",
            "generos": [],
            "elenco": [],
            "imdb_id": "",
        }
        with patch("catalog.views.busca_externa.detalhes_serie", return_value=info_simulada), patch(
            "catalog.views._garantir_notas_omdb"
        ):
            views._completar_serie(serie)

        serie.refresh_from_db()
        self.assertEqual(serie.data_lancamento, datetime.date(2027, 3, 10))


class BuscarDatasLancamentoCommandTest(TestCase):
    """Testa o comando de backfill (`python manage.py buscar_datas_lancamento`),
    que existe pra preencher `data_lancamento` de títulos cadastrados ANTES
    desse campo existir — sem esse comando, esses títulos ficariam pra
    sempre só com a comparação por ano (menos precisa), mesmo já tendo
    `id_externo` (ou seja, mesmo já sendo possível buscar a data certa)."""

    def test_sem_tmdb_api_key_nao_faz_nada_e_nao_quebra(self):
        # Ambiente de teste normalmente não tem TMDB_API_KEY configurada —
        # o comando precisa avisar e sair de forma tranquila, sem tentar
        # nenhuma chamada de rede (o que, sem chave, falharia de qualquer
        # jeito e poluiria a saída do build.sh no Render).
        with patch("catalog.busca_externa.tmdb_configurado", return_value=False):
            call_command("buscar_datas_lancamento")  # não deve levantar exceção

    def test_preenche_apenas_titulos_com_id_externo_e_sem_data(self):
        com_id_sem_data = criar_filme(
            titulo="Tem ID, Sem Data", ano=2026, id_externo="999", data_lancamento=None
        )
        sem_id = criar_filme(titulo="Sem ID Externo", ano=2026, id_externo="", data_lancamento=None)
        ja_tem_data = criar_filme(
            titulo="Já Tem Data",
            ano=2026,
            id_externo="888",
            data_lancamento=datetime.date(2026, 1, 1),
        )

        info_simulada = {"data_lancamento": datetime.date(2026, 12, 31)}
        with patch("catalog.busca_externa.tmdb_configurado", return_value=True), patch(
            "catalog.management.commands.buscar_datas_lancamento.busca_externa.detalhes_filme",
            return_value=info_simulada,
        ) as mock_detalhes:
            call_command("buscar_datas_lancamento")

        com_id_sem_data.refresh_from_db()
        sem_id.refresh_from_db()
        ja_tem_data.refresh_from_db()

        # Só o título com id_externo E sem data ainda é que gera chamada à
        # API e recebe a data nova.
        self.assertEqual(com_id_sem_data.data_lancamento, datetime.date(2026, 12, 31))
        # Sem id_externo, não tem como buscar — continua sem data, sem erro.
        self.assertIsNone(sem_id.data_lancamento)
        # Já tinha data — não mexe (evita chamada de API desnecessária).
        self.assertEqual(ja_tem_data.data_lancamento, datetime.date(2026, 1, 1))
        mock_detalhes.assert_called_once_with("999", idioma="pt-BR")

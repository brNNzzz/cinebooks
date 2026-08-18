"""
Testes do comando `rebuscar_sem_correspondencia`.

CONTEXTO REAL que motivou esse comando: ao testar o site publicado, alguns
títulos antigos (cadastrados via `seed_data`, antes da TMDB_API_KEY estar
configurada no Render) nunca tinham conseguido achar correspondência no
TMDB — a primeira (e única) tentativa de busca por texto falhou, e
`_completar_filme`/`_completar_serie` marcam `dados_completos=True` mesmo
sem achar nada, pra não ficar tentando de novo a cada visita (ver
comentário em `catalog/views.py`). Isso deixava esses títulos travados PRA
SEMPRE sem elenco, onde assistir ou trailer, mesmo depois da chave da API
estar certinha — só um comando que reseta e tenta de novo resolve.

Esses testes mockam `_completar_filme`/`_completar_serie` diretamente (já
testados a fundo em outros arquivos — ver test_onde_assistir.py,
test_trailer_youtube.py) pra isolar só a responsabilidade desse comando:
achar os títulos travados, resetar `dados_completos`, chamar de novo, e
contar o resultado.
"""

from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from catalog.tests.fabricas import criar_filme, criar_serie


class RebuscarSemCorrespondenciaTest(TestCase):
    def test_sem_tmdb_api_key_nao_faz_nada(self):
        filme = criar_filme(dados_completos=True, id_externo="")
        with patch("catalog.busca_externa.tmdb_configurado", return_value=False):
            call_command("rebuscar_sem_correspondencia")
        filme.refresh_from_db()
        self.assertTrue(filme.dados_completos)
        self.assertEqual(filme.id_externo, "")

    def test_ignora_titulos_que_ja_tem_id_externo(self):
        filme = criar_filme(dados_completos=True, id_externo="123")
        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch("catalog.management.commands.rebuscar_sem_correspondencia._completar_filme") as mock_completar:
                call_command("rebuscar_sem_correspondencia")
        mock_completar.assert_not_called()
        filme.refresh_from_db()
        self.assertEqual(filme.id_externo, "123")

    def test_ignora_titulos_que_ainda_nao_foram_completados(self):
        # dados_completos=False significa que a visita normal à página já
        # vai tentar completar sozinha — não é "travado", é só ainda não
        # visitado, então esse comando não precisa mexer.
        filme = criar_filme(dados_completos=False, id_externo="")
        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch("catalog.management.commands.rebuscar_sem_correspondencia._completar_filme") as mock_completar:
                call_command("rebuscar_sem_correspondencia")
        mock_completar.assert_not_called()

    def test_titulo_travado_e_resetado_e_completado_de_novo(self):
        filme = criar_filme(dados_completos=True, id_externo="")

        def completar_com_sucesso(item):
            item.id_externo = "999"
            item.dados_completos = True
            item.save()

        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch(
                "catalog.management.commands.rebuscar_sem_correspondencia._completar_filme",
                side_effect=completar_com_sucesso,
            ) as mock_completar:
                call_command("rebuscar_sem_correspondencia")

        mock_completar.assert_called_once()
        filme.refresh_from_db()
        self.assertEqual(filme.id_externo, "999")
        self.assertTrue(filme.dados_completos)

    def test_titulo_que_continua_sem_correspondencia_nao_da_erro(self):
        filme = criar_filme(dados_completos=True, id_externo="")

        def completar_sem_achar(item):
            item.dados_completos = True
            item.save()

        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch(
                "catalog.management.commands.rebuscar_sem_correspondencia._completar_filme",
                side_effect=completar_sem_achar,
            ):
                call_command("rebuscar_sem_correspondencia")  # não deve lançar exceção

        filme.refresh_from_db()
        self.assertEqual(filme.id_externo, "")
        self.assertTrue(filme.dados_completos)

    def test_funciona_tambem_pra_series(self):
        serie = criar_serie(dados_completos=True, id_externo="")

        def completar_com_sucesso(item):
            item.id_externo = "777"
            item.dados_completos = True
            item.save()

        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch(
                "catalog.management.commands.rebuscar_sem_correspondencia._completar_serie",
                side_effect=completar_com_sucesso,
            ) as mock_completar:
                call_command("rebuscar_sem_correspondencia")

        mock_completar.assert_called_once()
        serie.refresh_from_db()
        self.assertEqual(serie.id_externo, "777")

    def test_e_seguro_rodar_duas_vezes_seguidas(self):
        # Depois de encontrado com sucesso, o título sai do filtro "travado"
        # — rodar de novo não deve chamar _completar_filme outra vez.
        filme = criar_filme(dados_completos=True, id_externo="")

        def completar_com_sucesso(item):
            item.id_externo = "999"
            item.dados_completos = True
            item.save()

        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch(
                "catalog.management.commands.rebuscar_sem_correspondencia._completar_filme",
                side_effect=completar_com_sucesso,
            ) as mock_completar:
                call_command("rebuscar_sem_correspondencia")
                call_command("rebuscar_sem_correspondencia")

        self.assertEqual(mock_completar.call_count, 1)
        filme.refresh_from_db()
        self.assertEqual(filme.id_externo, "999")

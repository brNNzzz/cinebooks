"""
Testes do comando `completar_dados_pendentes`.

CONTEXTO REAL que motivou esse comando: mesmo depois de `rebuscar_sem_
correspondencia` (que só resolve o caso "achou dados_completos=True e
id_externo vazio"), títulos de exemplo do `seed_data` como "A Origem" e
"Matrix" continuavam SEM elenco/onde assistir/trailer mesmo sendo
visitados várias vezes — ou seja, ficavam com `dados_completos=False` pra
sempre, nunca chegando nem a ficar "travados". A suspeita é que a thread
em segundo plano disparada por `detalhe()` (ver `catalog.views.
_completar_em_segundo_plano`) não está sobrevivendo até o fim no ambiente
de produção (Render, plano gratuito, processo pode reiniciar a qualquer
momento). Esse comando resolve isso completando os pendentes de forma
síncrona, direto no `build.sh` — sem depender de nenhuma visita real nem
de uma thread em segundo plano terminando por conta própria.

Assim como em test_rebuscar_sem_correspondencia.py, mockamos
`_garantir_dados_completos` diretamente (já testada a fundo via
_completar_filme/_completar_serie em outros arquivos) pra isolar só a
responsabilidade desse comando: achar os pendentes, chamar a função de
sempre pra cada um, respeitar o limite por execução e contar o
resultado.
"""

from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from catalog.tests.fabricas import criar_filme, criar_livro, criar_serie


class CompletarDadosPendentesTest(TestCase):
    def test_sem_tmdb_api_key_nao_faz_nada(self):
        filme = criar_filme(dados_completos=False)
        with patch("catalog.busca_externa.tmdb_configurado", return_value=False):
            with patch(
                "catalog.management.commands.completar_dados_pendentes._garantir_dados_completos"
            ) as mock_garantir:
                call_command("completar_dados_pendentes")
        mock_garantir.assert_not_called()
        filme.refresh_from_db()
        self.assertFalse(filme.dados_completos)

    def test_ignora_titulos_que_ja_estao_completos(self):
        filme = criar_filme(dados_completos=True, id_externo="123")
        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch(
                "catalog.management.commands.completar_dados_pendentes._garantir_dados_completos"
            ) as mock_garantir:
                call_command("completar_dados_pendentes")
        mock_garantir.assert_not_called()
        filme.refresh_from_db()
        self.assertEqual(filme.id_externo, "123")

    def test_completa_filme_pendente_com_sucesso(self):
        filme = criar_filme(dados_completos=False)

        def completar_com_sucesso(item, tipo):
            item.id_externo = "999"
            item.dados_completos = True
            item.save()

        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch(
                "catalog.management.commands.completar_dados_pendentes._garantir_dados_completos",
                side_effect=completar_com_sucesso,
            ) as mock_garantir:
                call_command("completar_dados_pendentes")

        mock_garantir.assert_called_once()
        filme.refresh_from_db()
        self.assertEqual(filme.id_externo, "999")
        self.assertTrue(filme.dados_completos)

    def test_falha_temporaria_nao_da_erro_e_tenta_de_novo_depois(self):
        # Se a função de completar não conseguir dessa vez (ex: API fora do
        # ar), o item continua com dados_completos=False — sem exceção — e
        # entra de novo no próximo deploy, exatamente como uma visita normal.
        filme = criar_filme(dados_completos=False)

        def nao_completa_agora(item, tipo):
            pass  # simula falha temporária: não muda nada

        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch(
                "catalog.management.commands.completar_dados_pendentes._garantir_dados_completos",
                side_effect=nao_completa_agora,
            ):
                call_command("completar_dados_pendentes")  # não deve lançar exceção

        filme.refresh_from_db()
        self.assertFalse(filme.dados_completos)

    def test_funciona_pra_serie_e_livro_tambem(self):
        serie = criar_serie(dados_completos=False)
        livro = criar_livro(dados_completos=False)

        def completar_com_sucesso(item, tipo):
            item.id_externo = "555"
            item.dados_completos = True
            item.save()

        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch(
                "catalog.management.commands.completar_dados_pendentes._garantir_dados_completos",
                side_effect=completar_com_sucesso,
            ) as mock_garantir:
                call_command("completar_dados_pendentes")

        self.assertEqual(mock_garantir.call_count, 2)
        serie.refresh_from_db()
        livro.refresh_from_db()
        self.assertTrue(serie.dados_completos)
        self.assertTrue(livro.dados_completos)

    def test_respeita_o_limite_por_tipo(self):
        for i in range(5):
            criar_filme(titulo=f"Filme {i}", dados_completos=False)

        def completar_com_sucesso(item, tipo):
            item.dados_completos = True
            item.save()

        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch(
                "catalog.management.commands.completar_dados_pendentes._garantir_dados_completos",
                side_effect=completar_com_sucesso,
            ) as mock_garantir:
                call_command("completar_dados_pendentes", limite=2)

        self.assertEqual(mock_garantir.call_count, 2)

    def test_e_seguro_rodar_varias_vezes_ate_esgotar_os_pendentes(self):
        for i in range(3):
            criar_filme(titulo=f"Filme {i}", dados_completos=False)

        def completar_com_sucesso(item, tipo):
            item.dados_completos = True
            item.save()

        with patch("catalog.busca_externa.tmdb_configurado", return_value=True):
            with patch(
                "catalog.management.commands.completar_dados_pendentes._garantir_dados_completos",
                side_effect=completar_com_sucesso,
            ) as mock_garantir:
                call_command("completar_dados_pendentes", limite=2)
                call_command("completar_dados_pendentes", limite=2)

        # 2 na primeira rodada + 1 restante na segunda = 3 no total, sem
        # nenhum título sendo processado duas vezes.
        self.assertEqual(mock_garantir.call_count, 3)

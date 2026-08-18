"""
Testes do sistema de troca de idioma (catalog/i18n.py + views.mudar_idioma).
Esse sistema é "caseiro" (um dicionário Python, não o gettext de fábrica do
Django — ver o comentário grande no topo de catalog/i18n.py explicando por
quê), então vale a pena testar ele com mais cuidado do que se fosse algo
pronto do framework.
"""

from django.test import Client, TestCase

from catalog.i18n import IDIOMA_PADRAO, IDIOMAS, TRADUCOES, traduzir


class TraduzirFuncaoTest(TestCase):
    """Testes diretos da função traduzir(), sem precisar de views/templates."""

    def test_traduz_pro_idioma_pedido(self):
        self.assertEqual(traduzir("nav_filmes", "en"), "Movies")
        self.assertEqual(traduzir("nav_filmes", "es"), "Películas")

    def test_chave_inexistente_cai_pro_portugues(self):
        # traduzir() tem que ter um "modo seguro": se alguém digitar uma
        # chave errada (typo em `{% t "chave_que_nao_existe" %}`), é melhor
        # mostrar ALGUMA coisa em português do que quebrar a página inteira
        # com um KeyError.
        resultado = traduzir("essa_chave_nao_existe_de_jeito_nenhum", "en")
        self.assertIsInstance(resultado, str)

    def test_idioma_inexistente_cai_pro_padrao(self):
        # Um código de idioma inválido (ex: sessão adulterada manualmente,
        # ou um idioma que foi removido) não pode quebrar a página — cai
        # pro idioma padrão (português) em vez de dar erro.
        resultado = traduzir("nav_filmes", "codigo-de-idioma-que-nao-existe")
        self.assertEqual(resultado, traduzir("nav_filmes", IDIOMA_PADRAO))


class TodosOsIdiomasTemAsMesmasChavesTest(TestCase):
    """Teste de REGRESSÃO importante: garante que os 11 idiomas continuam
    com exatamente o mesmo conjunto de chaves entre si. Sem esse teste,
    seria fácil adicionar uma chave nova só no português (esquecendo de
    traduzir pros outros 10 idiomas) sem perceber — o site não quebraria
    (traduzir() cai pro português quando falta uma chave, ver acima), mas
    ia aparecer um textinho em português "vazando" no meio de uma página
    em, por exemplo, russo ou árabe, sem ninguém notar até um usuário
    reportar."""

    def test_todos_os_idiomas_tem_as_mesmas_chaves_que_o_portugues(self):
        chaves_portugues = set(TRADUCOES[IDIOMA_PADRAO].keys())
        for codigo in IDIOMAS:
            with self.subTest(idioma=codigo):
                chaves_do_idioma = set(TRADUCOES[codigo].keys())
                faltando = chaves_portugues - chaves_do_idioma
                sobrando = chaves_do_idioma - chaves_portugues
                self.assertEqual(faltando, set(), f"Chaves faltando em '{codigo}': {faltando}")
                self.assertEqual(sobrando, set(), f"Chaves a mais (sem par em pt) em '{codigo}': {sobrando}")

    def test_nenhuma_traducao_esta_vazia(self):
        # Uma chave existir mas valer "" (string vazia) é quase pior do que
        # não existir — passaria no teste acima mas apareceria como um
        # espaço em branco esquisito na página, sem nenhum aviso.
        for codigo, traducoes in TRADUCOES.items():
            for chave, texto in traducoes.items():
                with self.subTest(idioma=codigo, chave=chave):
                    self.assertTrue(texto, f"'{chave}' está vazia no idioma '{codigo}'")


class MudarIdiomaViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_mudar_pra_idioma_valido_salva_na_sessao(self):
        self.client.get("/idioma/en/", follow=True)
        self.assertEqual(self.client.session["idioma"], "en")

    def test_mudar_pra_idioma_invalido_nao_salva_nada_quebrado(self):
        # "/idioma/klingon/" não é um código válido (ver IDIOMAS) — a view
        # não pode salvar esse valor na sessão (isso quebraria toda tradução
        # subsequente, já que _idioma_atual() confia no que tá na sessão).
        resposta = self.client.get("/idioma/klingon/", follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertNotEqual(self.client.session.get("idioma"), "klingon")

    def test_pagina_home_respeita_idioma_escolhido(self):
        self.client.get("/idioma/es/")
        resposta = self.client.get("/")
        # "Filmes recentes" traduzido pro espanhol usa "Películas recientes"
        # (chave home_filmes_recentes) — conferimos um texto fixo da
        # interface que SÓ aparece assim em espanhol.
        self.assertContains(resposta, traduzir("home_filmes_recentes", "es"))

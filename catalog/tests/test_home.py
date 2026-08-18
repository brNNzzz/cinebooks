"""
Testes da página inicial (views.home) — em especial a correção de um bug
relatado pelo grupo: um título cadastrado com ano de lançamento no FUTURO
(ex: uma continuação anunciada tipo "Avatar 5", que só lança daqui a vários
anos) aparecia nas fileiras "Filmes/Séries/Livros recentes" da home, porque
essas fileiras mostram os 4 títulos de MAIOR ano_lancamento — e um ano no
futuro sempre "ganha" de qualquer ano que já passou de verdade, mesmo o
título ainda nem tendo sido lançado.

A correção (ver views.home) restringe essas 3 fileiras a
`ano_lancamento__lte=ano_atual` — só entra quem já lançou, ou lança até o
fim do ano civil atual. O carrossel de destaque do topo (_destaques_do_ano)
já tinha essa mesma proteção desde antes (ver o teste
DestaquesDoAnoNaoMostraTituloFuturoTest mais abaixo, que confirma que ela
continua funcionando).
"""

import datetime

from django.test import Client, TestCase
from django.utils import timezone

from catalog.tests.fabricas import criar_filme, criar_livro, criar_serie


class HomeRecentesNaoMostraTituloFuturoTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.ano_atual = timezone.now().year

    def test_filme_com_ano_no_futuro_nao_aparece_em_filmes_recentes(self):
        # Reproduz exatamente o caso relatado: um filme "anunciado" com ano
        # de lançamento muito à frente do ano atual.
        futuro = criar_filme(titulo="Avatar 5", ano=self.ano_atual + 8)
        ja_lancado = criar_filme(titulo="Filme Já Lançado", ano=self.ano_atual)

        resposta = self.client.get("/")

        self.assertNotIn(futuro, list(resposta.context["filmes"]))
        self.assertIn(ja_lancado, list(resposta.context["filmes"]))
        self.assertNotContains(resposta, "Avatar 5")

    def test_serie_com_ano_no_futuro_nao_aparece_em_series_recentes(self):
        # Mesma regra vale pros 3 tipos — não é só filme que pode ter uma
        # data de lançamento anunciada/futura cadastrada.
        futura = criar_serie(titulo="Série Anunciada", ano=self.ano_atual + 3)
        resposta = self.client.get("/")
        self.assertNotIn(futura, list(resposta.context["series"]))

    def test_livro_com_ano_no_futuro_nao_aparece_em_livros_recentes(self):
        futuro = criar_livro(titulo="Livro Anunciado", ano=self.ano_atual + 2)
        resposta = self.client.get("/")
        self.assertNotIn(futuro, list(resposta.context["livros"]))

    def test_titulo_lancado_no_proprio_ano_atual_continua_aparecendo(self):
        # Importante não exagerar na correção: um título lançado ESSE ano
        # (ano_lancamento == ano_atual) não é "futuro", é um lançamento
        # normal de 2026 (ou o ano que for) — tem que continuar aparecendo.
        deste_ano = criar_filme(titulo="Lançamento Deste Ano", ano=self.ano_atual)
        resposta = self.client.get("/")
        self.assertIn(deste_ano, list(resposta.context["filmes"]))

    def test_home_abre_normalmente_mesmo_so_com_titulos_futuros_cadastrados(self):
        # Catálogo só com títulos futuros (ex: projeto recém-instalado,
        # alguém só importou anúncios de continuação) — a home não pode
        # quebrar, só mostrar a fileira vazia.
        criar_filme(titulo="Só Existe Como Anúncio", ano=self.ano_atual + 5)
        resposta = self.client.get("/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(list(resposta.context["filmes"]), [])

    def test_titulo_deste_ano_ainda_nao_lancado_continua_aparecendo_na_home(self):
        # Importante não confundir as duas regras: a home continua
        # decidindo quem APARECE só pelo ANO (`ano_lancamento`), mesmo que
        # a regra de AVALIAÇÃO (ver test_detalhe_e_avaliacoes.py,
        # AvaliarTituloComDataFuturaNoMesmoAnoTest) use a data exata. Um
        # título como "Doomsday" — deste ano, mas com `data_lancamento` só
        # pra daqui a alguns meses — precisa continuar navegável/visível
        # normalmente; só a avaliação é que fica bloqueada até ele sair.
        data_futura = datetime.date(self.ano_atual, 12, 31)
        doomsday = criar_filme(titulo="Doomsday", ano=self.ano_atual, data_lancamento=data_futura)
        resposta = self.client.get("/")
        self.assertIn(doomsday, list(resposta.context["filmes"]))
        self.assertContains(resposta, "Doomsday")


class DestaquesDoAnoNaoMostraTituloFuturoTest(TestCase):
    """O carrossel de destaque do topo (_destaques_do_ano) já tinha essa
    proteção antes da correção acima — esse teste é só pra confirmar que
    continua funcionando, e não quebrou nada ao mexer no resto de home()."""

    def test_titulo_futuro_nao_entra_no_carrossel_de_destaque(self):
        ano_atual = timezone.now().year
        criar_filme(titulo="Avatar 5", ano=ano_atual + 8, nota_publico=9.5)
        lancado = criar_filme(titulo="Filme Deste Ano", ano=ano_atual, nota_publico=7.0)

        resposta = Client().get("/")
        itens_do_carrossel = resposta.context["destaques_do_ano"]["itens"]
        titulos = [item.titulo for item in itens_do_carrossel]

        self.assertNotIn("Avatar 5", titulos)
        self.assertIn("Filme Deste Ano", titulos)

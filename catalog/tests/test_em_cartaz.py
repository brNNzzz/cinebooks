"""
Testes do botão "Comprar ingresso" na página de filme — pedido
explicitamente: link automático pro ingresso.com (busca pelo título, sem
cadastro manual por filme) que só aparece quando o filme está "em cartaz"
(decidido automaticamente pela data de lançamento, sem campo manual novo).
"""

import datetime
from urllib.parse import quote_plus

from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog import views
from catalog.tests.fabricas import criar_filme, criar_serie


class LinkIngressoTest(SimpleTestCase):
    def test_monta_url_de_busca_com_titulo_codificado(self):
        url = views._link_ingresso_com("A Jornada do Herói Perdido: Parte 2")
        self.assertEqual(
            url,
            "https://www.ingresso.com/busca/resultado?q=" + quote_plus("A Jornada do Herói Perdido: Parte 2"),
        )


class FilmeEmCartazTest(TestCase):
    def test_filme_lancado_ha_poucos_dias_esta_em_cartaz(self):
        filme = criar_filme(data_lancamento=timezone.localdate() - datetime.timedelta(days=5))
        self.assertTrue(views._filme_em_cartaz(filme))

    def test_filme_lancado_ha_muito_tempo_nao_esta_mais_em_cartaz(self):
        filme = criar_filme(
            data_lancamento=timezone.localdate() - datetime.timedelta(days=views.DIAS_EM_CARTAZ + 10)
        )
        self.assertFalse(views._filme_em_cartaz(filme))

    def test_filme_que_ainda_nao_lancou_nao_esta_em_cartaz(self):
        filme = criar_filme(data_lancamento=timezone.localdate() + datetime.timedelta(days=3))
        self.assertFalse(views._filme_em_cartaz(filme))

    def test_filme_lancado_hoje_esta_em_cartaz(self):
        filme = criar_filme(data_lancamento=timezone.localdate())
        self.assertTrue(views._filme_em_cartaz(filme))

    def test_sem_data_de_lancamento_exata_nao_arrisca_mostrar_botao(self):
        filme = criar_filme(data_lancamento=None)
        self.assertFalse(views._filme_em_cartaz(filme))


class DetalheFilmeMostraBotaoDeIngressoTest(TestCase):
    def test_filme_em_cartaz_mostra_botao_com_link_pro_ingresso_com(self):
        filme = criar_filme(
            titulo="Filme Em Cartaz Agora",
            data_lancamento=timezone.localdate() - datetime.timedelta(days=2),
        )
        resposta = Client().get(reverse("detalhe", args=["filme", filme.pk]))
        self.assertContains(resposta, "ingresso.com/busca/resultado?q=")
        self.assertContains(resposta, quote_plus("Filme Em Cartaz Agora"))

    def test_filme_fora_de_cartaz_nao_mostra_botao(self):
        filme = criar_filme(
            data_lancamento=timezone.localdate() - datetime.timedelta(days=365),
        )
        resposta = Client().get(reverse("detalhe", args=["filme", filme.pk]))
        self.assertNotContains(resposta, "ingresso.com")

    def test_serie_nunca_mostra_botao_de_ingresso(self):
        # Série não vai ao cinema — o botão é exclusivo de Filme.
        serie = criar_serie()
        resposta = Client().get(reverse("detalhe", args=["serie", serie.pk]))
        self.assertNotContains(resposta, "ingresso.com")

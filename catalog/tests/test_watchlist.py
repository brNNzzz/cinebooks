"""
Testes da watchlist ("+ Quero ver depois" / "Remover da lista") — a
funcionalidade nova pedida: um único botão que ALTERNA (adiciona se não
tá na lista, remove se já tá), na página de detalhe, e uma seção separada
na página de perfil listando tudo que foi adicionado.

Rota testada: POST /<tipo>/<pk>/watchlist/ → views.alternar_watchlist
"""

from django.test import Client, TestCase

from catalog.models import QueroVer
from catalog.tests.fabricas import criar_filme, criar_serie, criar_usuario


class AlternarWatchlistTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.filme = criar_filme(titulo="Duna", ano=2021, dados_completos=True)
        self.usuario = criar_usuario()
        self.client.login(username=self.usuario.username, password="senha-forte-123")

    def test_precisa_estar_logado(self):
        self.client.logout()
        resposta = self.client.post(f"/filme/{self.filme.pk}/watchlist/")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/conta/entrar/", resposta.url)
        self.assertEqual(QueroVer.objects.count(), 0)

    def test_primeiro_clique_adiciona_na_lista(self):
        resposta = self.client.post(f"/filme/{self.filme.pk}/watchlist/")
        self.assertRedirects(resposta, f"/filme/{self.filme.pk}/")
        self.assertTrue(
            QueroVer.objects.filter(usuario=self.usuario, object_id=self.filme.pk).exists()
        )

    def test_segundo_clique_remove_da_lista(self):
        # É o MESMO botão/URL pras duas ações — o "alternar" do nome da
        # view é isso: primeiro POST adiciona, segundo POST no mesmo título
        # remove, sem precisar de duas rotas diferentes.
        self.client.post(f"/filme/{self.filme.pk}/watchlist/")  # adiciona
        self.client.post(f"/filme/{self.filme.pk}/watchlist/")  # remove
        self.assertFalse(
            QueroVer.objects.filter(usuario=self.usuario, object_id=self.filme.pk).exists()
        )

    def test_nao_serve_pra_metodo_get(self):
        # @require_POST — adicionar/remover é uma mudança de estado, não
        # pode acontecer só visitando uma URL.
        resposta = self.client.get(f"/filme/{self.filme.pk}/watchlist/")
        self.assertEqual(resposta.status_code, 405)

    def test_tipo_invalido_da_404(self):
        resposta = self.client.post(f"/documentario/{self.filme.pk}/watchlist/")
        self.assertEqual(resposta.status_code, 404)

    def test_titulo_inexistente_da_404(self):
        resposta = self.client.post("/filme/99999/watchlist/")
        self.assertEqual(resposta.status_code, 404)

    def test_pagina_de_detalhe_mostra_botao_certo_conforme_o_estado(self):
        # Antes de adicionar: botão de ADICIONAR.
        resposta = self.client.get(f"/filme/{self.filme.pk}/")
        self.assertFalse(resposta.context["na_watchlist"])

        # Depois de adicionar: botão de REMOVER (na_watchlist muda pra True).
        self.client.post(f"/filme/{self.filme.pk}/watchlist/")
        resposta = self.client.get(f"/filme/{self.filme.pk}/")
        self.assertTrue(resposta.context["na_watchlist"])

    def test_dois_usuarios_diferentes_tem_watchlists_independentes(self):
        outro_usuario = criar_usuario("outra_pessoa")
        self.client.post(f"/filme/{self.filme.pk}/watchlist/")  # usuario adiciona

        self.client.logout()
        self.client.login(username="outra_pessoa", password="senha-forte-123")
        resposta = self.client.get(f"/filme/{self.filme.pk}/")
        # outro_usuario não adicionou nada — não pode aparecer como "na
        # lista dele" só porque outra pessoa adicionou o mesmo filme.
        self.assertFalse(resposta.context["na_watchlist"])
        self.assertTrue(QueroVer.objects.filter(usuario=self.usuario).exists())
        self.assertFalse(QueroVer.objects.filter(usuario=outro_usuario).exists())


class WatchlistNoPerfilTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.usuario = criar_usuario()
        self.client.login(username=self.usuario.username, password="senha-forte-123")

    def test_perfil_sem_nada_na_watchlist_mostra_mensagem_vazia(self):
        resposta = self.client.get("/perfil/")
        self.assertEqual(resposta.context["total_watchlist"], 0)
        self.assertEqual(resposta.context["watchlist_filmes"], [])
        self.assertContains(resposta, "Você ainda não adicionou nenhum título à sua lista.")

    def test_titulos_adicionados_aparecem_no_perfil_agrupados_por_tipo(self):
        filme = criar_filme(titulo="Duna", ano=2021, dados_completos=True)
        serie = criar_serie(titulo="Round 6", ano=2021, dados_completos=True)
        QueroVer.objects.create(usuario=self.usuario, titulo_lista=filme)
        QueroVer.objects.create(usuario=self.usuario, titulo_lista=serie)

        resposta = self.client.get("/perfil/")
        self.assertEqual(len(resposta.context["watchlist_filmes"]), 1)
        self.assertEqual(len(resposta.context["watchlist_series"]), 1)
        self.assertEqual(len(resposta.context["watchlist_livros"]), 0)
        self.assertContains(resposta, "Duna")
        self.assertContains(resposta, "Round 6")

    def test_perfil_so_mostra_a_watchlist_do_proprio_usuario(self):
        outro_usuario = criar_usuario("outra_pessoa")
        filme_do_outro = criar_filme(titulo="Filme da Outra Pessoa", dados_completos=True)
        QueroVer.objects.create(usuario=outro_usuario, titulo_lista=filme_do_outro)

        resposta = self.client.get("/perfil/")
        self.assertEqual(resposta.context["watchlist_filmes"], [])
        self.assertNotContains(resposta, "Filme da Outra Pessoa")

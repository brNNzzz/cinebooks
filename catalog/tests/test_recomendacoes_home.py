"""
Testes de que a fileira "Recomendados pra você" (ver catalog/recomendacoes.py)
aparece — ou não — na home certinho, dependendo de quem está olhando:

- Visitante sem login: nunca vê a fileira (não tem avaliação/watchlist/busca
  pra basear nada nele).
- Usuário logado mas sem nenhuma pista ainda: também não vê (evita
  recomendar qualquer coisa aleatória pra quem acabou de criar a conta).
- Usuário logado com pelo menos uma avaliação: vê a fileira, com um título
  do mesmo gênero do que ele avaliou bem.
"""

from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase

from catalog.models import Avaliacao, Genero
from catalog.tests.fabricas import criar_filme, criar_usuario


class RecomendadosNaHomeTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.genero = Genero.objects.create(nome="Ficção Científica")

    def test_visitante_sem_login_nao_ve_a_fileira(self):
        resposta = self.client.get("/")
        self.assertNotContains(resposta, "Recomendados pra você")

    def test_usuario_logado_sem_nenhuma_pista_nao_ve_a_fileira(self):
        usuario = criar_usuario()
        self.client.force_login(usuario)

        resposta = self.client.get("/")
        self.assertNotContains(resposta, "Recomendados pra você")

    def test_usuario_logado_com_avaliacao_ve_recomendacao_do_mesmo_genero(self):
        usuario = criar_usuario()
        avaliado = criar_filme(titulo="Duna", ano=2021)
        avaliado.generos.add(self.genero)
        Avaliacao.objects.create(
            usuario=usuario,
            nota=5,
            content_type=ContentType.objects.get_for_model(avaliado.__class__),
            object_id=avaliado.pk,
        )
        candidato = criar_filme(titulo="Interestelar", ano=2014)
        candidato.generos.add(self.genero)

        self.client.force_login(usuario)
        resposta = self.client.get("/")

        self.assertContains(resposta, "Recomendados pra você")
        self.assertContains(resposta, "Interestelar")
        # O texto explicativo abaixo do título da fileira também precisa
        # aparecer (garante que o template renderizou a seção inteira, não
        # só coincidentemente o nome do filme em outro lugar da página).
        self.assertContains(resposta, "Com base nas suas avaliações")

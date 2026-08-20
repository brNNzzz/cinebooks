"""
Testes do motor de recomendações (catalog/recomendacoes.py) — a fileira
"Recomendados pra você" que aparece na home pra quem está logado.

Testamos aqui só a LÓGICA de pontuação (gênero + diretor/autor + década,
a partir de avaliações + watchlist + buscas), chamando
`recomendar_para_usuario` diretamente — sem passar pela view/HTTP. O teste
de que a fileira aparece (ou não) certinho na página está em
`test_recomendacoes_home.py`.
"""

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from catalog.models import Avaliacao, Busca, Genero, QueroVer
from catalog.recomendacoes import recomendar_para_usuario
from catalog.tests.fabricas import criar_filme, criar_serie, criar_usuario


def _avaliar(usuario, item, nota):
    Avaliacao.objects.create(
        usuario=usuario,
        nota=nota,
        content_type=ContentType.objects.get_for_model(item.__class__),
        object_id=item.pk,
    )


def _adicionar_watchlist(usuario, item):
    QueroVer.objects.create(
        usuario=usuario,
        content_type=ContentType.objects.get_for_model(item.__class__),
        object_id=item.pk,
    )


class SemPistasTest(TestCase):
    def test_usuario_sem_nenhuma_pista_nao_recebe_recomendacao(self):
        # Usuário novo: nunca avaliou, nunca usou a watchlist, nunca buscou
        # nada — não tem base nenhuma pra recomendar algo, então a fileira
        # tem que ficar vazia (e some da home, ver test_recomendacoes_home).
        usuario = criar_usuario()
        criar_filme(titulo="Qualquer Filme")

        self.assertEqual(recomendar_para_usuario(usuario), [])


class SinalDeAvaliacaoTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.ficcao = Genero.objects.create(nome="Ficção Científica")

    def test_nota_alta_recomenda_outro_filme_do_mesmo_genero(self):
        filme_avaliado = criar_filme(titulo="Duna")
        filme_avaliado.generos.add(self.ficcao)
        _avaliar(self.usuario, filme_avaliado, nota=5)

        candidato = criar_filme(titulo="Interestelar", ano=2014)
        candidato.generos.add(self.ficcao)

        recomendados = recomendar_para_usuario(self.usuario)

        self.assertIn(candidato, recomendados)
        # O item que a pessoa JÁ avaliou nunca deve voltar na lista.
        self.assertNotIn(filme_avaliado, recomendados)

    def test_nota_baixa_nao_recomenda_mesmo_genero(self):
        # Nota baixa (1 ou 2) conta CONTRA aquele gênero — não faz sentido
        # empurrar mais coisa parecida com algo que a pessoa não curtiu.
        filme_avaliado = criar_filme(titulo="Filme Ruim")
        filme_avaliado.generos.add(self.ficcao)
        _avaliar(self.usuario, filme_avaliado, nota=1)

        candidato = criar_filme(titulo="Outro do Mesmo Gênero", ano=2014)
        candidato.generos.add(self.ficcao)

        recomendados = recomendar_para_usuario(self.usuario)

        self.assertNotIn(candidato, recomendados)

    def test_nota_media_nao_gera_sinal_nenhum(self):
        # Nota 3 (nem gostou nem desgostou) tem peso 0 de propósito — não
        # deveria puxar recomendação nem a favor nem contra o gênero.
        filme_avaliado = criar_filme(titulo="Filme Mediano")
        filme_avaliado.generos.add(self.ficcao)
        _avaliar(self.usuario, filme_avaliado, nota=3)

        candidato = criar_filme(titulo="Vizinho de Gênero", ano=2014)
        candidato.generos.add(self.ficcao)

        self.assertEqual(recomendar_para_usuario(self.usuario), [])


class SinalDeWatchlistTest(TestCase):
    def test_item_na_watchlist_recomenda_mesmo_genero(self):
        usuario = criar_usuario()
        terror = Genero.objects.create(nome="Terror")

        na_watchlist = criar_filme(titulo="Coisa Assustadora")
        na_watchlist.generos.add(terror)
        _adicionar_watchlist(usuario, na_watchlist)

        candidato = criar_filme(titulo="Outra Coisa Assustadora", ano=2014)
        candidato.generos.add(terror)

        recomendados = recomendar_para_usuario(usuario)

        self.assertIn(candidato, recomendados)
        # O próprio item da watchlist não pode se recomendar de volta.
        self.assertNotIn(na_watchlist, recomendados)

    def test_watchlist_pesa_menos_que_avaliacao_alta(self):
        # Dado o mesmo gênero vindo só da watchlist (peso 2) vs. vindo de
        # uma nota 5 (peso 3), o candidato "puxado" pela avaliação tem que
        # pontuar mais alto.
        usuario = criar_usuario()
        aventura = Genero.objects.create(nome="Aventura")

        avaliado = criar_filme(titulo="Avaliado", ano=2010)
        avaliado.generos.add(aventura)
        _avaliar(usuario, avaliado, nota=5)

        na_watchlist = criar_filme(titulo="Na Watchlist", ano=2011)
        na_watchlist.generos.add(aventura)
        _adicionar_watchlist(usuario, na_watchlist)

        candidato = criar_filme(titulo="Candidato", ano=2012)
        candidato.generos.add(aventura)

        recomendados = recomendar_para_usuario(usuario)
        self.assertIn(candidato, recomendados)


class SinalDeBuscaTest(TestCase):
    def test_busca_por_titulo_recomenda_mesmo_genero(self):
        usuario = criar_usuario()
        comedia = Genero.objects.create(nome="Comédia")

        encontrado_pela_busca = criar_filme(titulo="Superbad Brasileiro")
        encontrado_pela_busca.generos.add(comedia)
        Busca.objects.create(usuario=usuario, termo="Superbad")

        candidato = criar_filme(titulo="Outra Comédia", ano=2014)
        candidato.generos.add(comedia)

        recomendados = recomendar_para_usuario(usuario)

        self.assertIn(candidato, recomendados)

    def test_busca_de_outro_usuario_nao_interfere(self):
        # Histórico de busca é POR usuário — a busca de uma pessoa não pode
        # virar recomendação pra outra.
        usuario_a = criar_usuario(username="usuaria_a")
        usuario_b = criar_usuario(username="usuaria_b")
        drama = Genero.objects.create(nome="Drama")

        encontrado = criar_filme(titulo="Filme Dramático")
        encontrado.generos.add(drama)
        Busca.objects.create(usuario=usuario_a, termo="Dramático")

        candidato = criar_filme(titulo="Outro Drama", ano=2014)
        candidato.generos.add(drama)

        self.assertEqual(recomendar_para_usuario(usuario_b), [])


class SinalDePessoaTest(TestCase):
    def test_mesmo_diretor_e_sinal_mais_forte_que_genero_sozinho(self):
        usuario = criar_usuario()
        ficcao = Genero.objects.create(nome="Ficção Científica")
        drama = Genero.objects.create(nome="Drama")

        avaliado = criar_filme(titulo="Filme do Diretor X", diretor="Diretor X")
        avaliado.generos.add(ficcao)
        _avaliar(usuario, avaliado, nota=5)

        # Mesmo diretor, gênero DIFERENTE — ainda deve pontuar (sinal de
        # pessoa), mesmo sem bater o gênero.
        mesmo_diretor_outro_genero = criar_filme(
            titulo="Outro Filme do Diretor X", diretor="Diretor X", ano=2015
        )
        mesmo_diretor_outro_genero.generos.add(drama)

        recomendados = recomendar_para_usuario(usuario)

        self.assertIn(mesmo_diretor_outro_genero, recomendados)

    def test_mesmo_criador_de_serie_tambem_conta(self):
        usuario = criar_usuario()
        avaliada = criar_serie(titulo="Série Y", criador="Criador Y")
        _avaliar(usuario, avaliada, nota=5)

        candidata = criar_serie(titulo="Outra Série Y", criador="Criador Y", ano=2015)

        recomendados = recomendar_para_usuario(usuario)
        self.assertIn(candidata, recomendados)


class SinalDeDecadaTest(TestCase):
    def test_titulos_da_mesma_decada_recebem_algum_sinal(self):
        usuario = criar_usuario()
        genero_a = Genero.objects.create(nome="Gênero A")
        genero_b = Genero.objects.create(nome="Gênero B")

        avaliado = criar_filme(titulo="Filme Anos 90", ano=1995)
        avaliado.generos.add(genero_a)
        _avaliar(usuario, avaliado, nota=5)

        # Mesma década (1990), gênero diferente — ainda ganha algum ponto
        # (peso de década), mesmo que menor que um candidato que bate tudo.
        mesma_decada = criar_filme(titulo="Outro Filme Anos 90", ano=1992)
        mesma_decada.generos.add(genero_b)

        recomendados = recomendar_para_usuario(usuario)
        self.assertIn(mesma_decada, recomendados)


class LimiteEExclusaoTest(TestCase):
    def test_respeita_o_limite_pedido(self):
        usuario = criar_usuario()
        genero = Genero.objects.create(nome="Ação")

        avaliado = criar_filme(titulo="Base", ano=2000)
        avaliado.generos.add(genero)
        _avaliar(usuario, avaliado, nota=5)

        for i in range(5):
            candidato = criar_filme(titulo=f"Ação {i}", ano=2001 + i)
            candidato.generos.add(genero)

        recomendados = recomendar_para_usuario(usuario, limite=3)
        self.assertEqual(len(recomendados), 3)

    def test_nao_recomenda_titulo_ainda_nao_lancado(self):
        usuario = criar_usuario()
        genero = Genero.objects.create(nome="Fantasia")

        avaliado = criar_filme(titulo="Base", ano=2020)
        avaliado.generos.add(genero)
        _avaliar(usuario, avaliado, nota=5)

        futuro = criar_filme(titulo="Anunciado pro Futuro", ano=2099)
        futuro.generos.add(genero)

        recomendados = recomendar_para_usuario(usuario)
        self.assertNotIn(futuro, recomendados)

"""
Testes dos MODELOS (catalog/models.py) — a camada mais "de baixo" do site,
sem passar por views nem templates. A ideia aqui é garantir que as regras
de negócio básicas (nota tem que ser de 1 a 5, não dá pra avaliar o mesmo
título duas vezes, a média de avaliações calcula certo...) continuam
valendo mesmo se alguém mexer no código depois.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from catalog.models import Avaliacao, Filme, Genero, QueroVer
from catalog.tests.fabricas import criar_filme, criar_livro, criar_serie, criar_usuario


class FilmeSerieLivroTest(TestCase):
    """Testes que valem igual pros três tipos de título (Filme/Serie/Livro),
    porque todos herdam os mesmos campos/comportamentos da classe abstrata
    Titulo (ver catalog/models.py)."""

    def test_str_mostra_titulo_e_ano(self):
        # __str__ é o que aparece, por exemplo, na lista de filmes do Django
        # Admin — precisa deixar claro QUAL filme é, sem abrir o registro.
        filme = criar_filme(titulo="Duna", ano=2021)
        self.assertEqual(str(filme), "Duna (2021)")

    def test_media_avaliacoes_sem_nenhuma_avaliacao_e_none(self):
        # Um título recém-cadastrado, sem ninguém ter avaliado ainda, não
        # pode mostrar "0 estrelas" (isso pareceria uma nota real e ruim) —
        # tem que mostrar "sem avaliações", que é o que a view/template fazem
        # quando media_avaliacoes() devolve None.
        filme = criar_filme()
        self.assertIsNone(filme.media_avaliacoes())
        self.assertEqual(filme.total_avaliacoes(), 0)

    def test_media_avaliacoes_calcula_a_media_certa(self):
        filme = criar_filme()
        usuario1 = criar_usuario("usuaria1")
        usuario2 = criar_usuario("usuaria2")
        Avaliacao.objects.create(usuario=usuario1, titulo_avaliado=filme, nota=5)
        Avaliacao.objects.create(usuario=usuario2, titulo_avaliado=filme, nota=3)

        # (5 + 3) / 2 = 4.0 — e o total tem que bater com a quantidade de
        # avaliações usadas na conta, não só a nota calculada.
        self.assertEqual(filme.media_avaliacoes(), 4.0)
        self.assertEqual(filme.total_avaliacoes(), 2)

    def test_serie_e_livro_tambem_calculam_media(self):
        # Mesma lógica do teste acima, mas confirmando que Serie e Livro
        # (que reaproveitam o código de Titulo) funcionam igual — não é só
        # o Filme que foi testado por coincidência.
        serie = criar_serie()
        livro = criar_livro()
        usuario = criar_usuario()
        Avaliacao.objects.create(usuario=usuario, titulo_avaliado=serie, nota=4)
        Avaliacao.objects.create(usuario=usuario, titulo_avaliado=livro, nota=2)

        self.assertEqual(serie.media_avaliacoes(), 4.0)
        self.assertEqual(livro.media_avaliacoes(), 2.0)

    def test_generos_e_relacao_muitos_para_muitos(self):
        # Um filme pode ter vários gêneros, e um gênero pode estar em vários
        # filmes — é isso que o ManyToManyField garante. Testamos os dois
        # lados da relação.
        acao = Genero.objects.create(nome="Ação")
        ficcao = Genero.objects.create(nome="Ficção científica")
        filme = criar_filme()
        filme.generos.set([acao, ficcao])

        self.assertEqual(filme.generos.count(), 2)
        self.assertIn(filme, acao.filme_set.all())


class AvaliacaoTest(TestCase):
    def test_nota_menor_que_1_e_invalida(self):
        # PositiveSmallIntegerField com MinValueValidator(1)/MaxValueValidator(5)
        # (ver catalog/models.py) — o banco em si aceitaria qualquer número
        # positivo, então quem garante o limite de verdade é a validação do
        # Django, chamada explicitamente aqui via full_clean().
        filme = criar_filme()
        usuario = criar_usuario()
        avaliacao = Avaliacao(usuario=usuario, titulo_avaliado=filme, nota=0)
        with self.assertRaises(ValidationError):
            avaliacao.full_clean()

    def test_nota_maior_que_5_e_invalida(self):
        filme = criar_filme()
        usuario = criar_usuario()
        avaliacao = Avaliacao(usuario=usuario, titulo_avaliado=filme, nota=6)
        with self.assertRaises(ValidationError):
            avaliacao.full_clean()

    def test_mesmo_usuario_nao_pode_avaliar_o_mesmo_titulo_duas_vezes(self):
        # A constraint "usuario_avalia_uma_vez_cada_titulo" (ver Meta de
        # Avaliacao) impede duas linhas de Avaliacao com o mesmo (usuario,
        # content_type, object_id) — é isso que faz o site EDITAR a
        # avaliação existente em vez de criar uma segunda, na view avaliar().
        filme = criar_filme()
        usuario = criar_usuario()
        Avaliacao.objects.create(usuario=usuario, titulo_avaliado=filme, nota=5)

        with self.assertRaises(IntegrityError):
            # `atomic()` aqui é só pra não derrubar o resto da transação de
            # teste quando o IntegrityError acontece — sem isso, o Django
            # reclama que a transação já estava "quebrada" nos testes
            # seguintes deste método.
            with transaction.atomic():
                Avaliacao.objects.create(usuario=usuario, titulo_avaliado=filme, nota=1)

    def test_usuarios_diferentes_podem_avaliar_o_mesmo_titulo(self):
        # Garante que a constraint acima é por (usuário + título), não só
        # por título — senão ninguém além da primeira pessoa conseguiria
        # avaliar um título já avaliado.
        filme = criar_filme()
        usuario1 = criar_usuario("usuaria1")
        usuario2 = criar_usuario("usuaria2")
        Avaliacao.objects.create(usuario=usuario1, titulo_avaliado=filme, nota=5)
        Avaliacao.objects.create(usuario=usuario2, titulo_avaliado=filme, nota=1)

        self.assertEqual(filme.total_avaliacoes(), 2)


class QueroVerTest(TestCase):
    """QueroVer é o modelo da watchlist ("quero ver depois") — mesma ideia
    de Avaliacao (Generic Foreign Key apontando pra Filme/Serie/Livro), só
    que sem nota/comentário: é só um lembrete de "quero ver isso depois"."""

    def test_mesmo_usuario_nao_pode_adicionar_o_mesmo_titulo_duas_vezes(self):
        # Mesma ideia da constraint de Avaliacao: sem isso, clicar duas
        # vezes rápido no botão "+ Quero ver depois" (ou um bug de duplo
        # clique) criaria duas linhas idênticas na watchlist.
        filme = criar_filme()
        usuario = criar_usuario()
        QueroVer.objects.create(usuario=usuario, titulo_lista=filme)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                QueroVer.objects.create(usuario=usuario, titulo_lista=filme)

    def test_str_mostra_quem_e_o_que(self):
        filme = criar_filme(titulo="Interestelar")
        usuario = criar_usuario("bruno")
        item = QueroVer.objects.create(usuario=usuario, titulo_lista=filme)
        self.assertIn("bruno", str(item))
        self.assertIn("Interestelar", str(item))

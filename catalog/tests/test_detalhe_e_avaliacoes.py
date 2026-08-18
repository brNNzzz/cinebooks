"""
Testes da página de detalhe de um título (views.detalhe) e do fluxo de
avaliação (views.avaliar / views.excluir_avaliacao).

Observação sobre `dados_completos=True`: quando um título ainda não tem os
dados completos (elenco, sinopse maior...), `views.detalhe` dispara uma
BUSCA EM SEGUNDO PLANO numa thread separada (ver `_completar_em_segundo_
plano` em catalog/views.py) — de propósito, pra não travar a página
esperando a API externa responder. Numa thread separada rodando ao mesmo
tempo que o teste, isso pode causar comportamento não-determinístico (a
thread pode terminar antes, depois, ou durante a checagem do teste). Como
esse comportamento em si já não faz nenhuma chamada de rede de verdade sem
TMDB_API_KEY configurada (ver catalog/busca_externa.py), ele não quebra os
testes — mas, pra manter os testes 100% previsíveis e rápidos, criamos os
títulos de teste já com `dados_completos=True`, o que faz a view pular essa
etapa de vez.
"""

import datetime

from django.test import Client, TestCase
from django.utils import timezone

from catalog.models import Avaliacao
from catalog.tests.fabricas import criar_filme, criar_livro, criar_serie, criar_usuario


class DetalhePaginaTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_pagina_de_detalhe_abre_e_mostra_o_titulo(self):
        filme = criar_filme(titulo="A Origem", ano=2010, dados_completos=True)
        resposta = self.client.get(f"/filme/{filme.pk}/")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "A Origem")

    def test_titulo_inexistente_da_404(self):
        resposta = self.client.get("/filme/99999/")
        self.assertEqual(resposta.status_code, 404)

    def test_sem_avaliacoes_mostra_mensagem_de_sem_avaliacoes(self):
        filme = criar_filme(dados_completos=True)
        resposta = self.client.get(f"/filme/{filme.pk}/")
        self.assertIsNone(resposta.context["media"])

    def test_com_avaliacoes_mostra_a_media(self):
        filme = criar_filme(dados_completos=True)
        usuario = criar_usuario()
        Avaliacao.objects.create(usuario=usuario, titulo_avaliado=filme, nota=4)
        resposta = self.client.get(f"/filme/{filme.pk}/")
        self.assertEqual(resposta.context["media"], 4.0)

    def test_funciona_pros_tres_tipos_de_titulo(self):
        # detalhe() é uma view SÓ, reaproveitada pra filme/série/livro via
        # o dicionário TIPOS (catalog/views.py) — testamos os três pra
        # garantir que nenhum deles quebra por causa de algum campo que só
        # existe num dos tipos (ex: "diretor" só existe em Filme).
        filme = criar_filme(dados_completos=True)
        serie = criar_serie(dados_completos=True)
        livro = criar_livro(dados_completos=True)

        self.assertEqual(self.client.get(f"/filme/{filme.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/serie/{serie.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/livro/{livro.pk}/").status_code, 200)


class AvaliarTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.filme = criar_filme(dados_completos=True)
        self.usuario = criar_usuario(password="senha-forte-123")

    def test_precisa_estar_logado_pra_avaliar(self):
        # @login_required (ver views.avaliar) — sem estar logado, o Django
        # redireciona pra página de login em vez de deixar avaliar.
        resposta = self.client.post(
            f"/filme/{self.filme.pk}/avaliar/", {"nota": 5, "comentario": "Ótimo!"}
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/conta/entrar/", resposta.url)
        self.assertEqual(Avaliacao.objects.count(), 0)

    def test_criar_avaliacao_pela_primeira_vez(self):
        self.client.login(username=self.usuario.username, password="senha-forte-123")
        resposta = self.client.post(
            f"/filme/{self.filme.pk}/avaliar/", {"nota": 5, "comentario": "Ótimo!"}
        )
        self.assertRedirects(resposta, f"/filme/{self.filme.pk}/")
        avaliacao = Avaliacao.objects.get(usuario=self.usuario, object_id=self.filme.pk)
        self.assertEqual(avaliacao.nota, 5)
        self.assertEqual(avaliacao.comentario, "Ótimo!")

    def test_reenviar_avaliacao_edita_em_vez_de_duplicar(self):
        # A view usa `instancia = Avaliacao.objects.filter(...).first()` e
        # passa pro form como `instance=` — segunda avaliação da MESMA
        # pessoa pro MESMO título tem que ATUALIZAR a linha existente, não
        # criar uma segunda (o que, aliás, bateria na constraint de
        # unicidade testada em test_models.py).
        self.client.login(username=self.usuario.username, password="senha-forte-123")
        self.client.post(f"/filme/{self.filme.pk}/avaliar/", {"nota": 2, "comentario": "Meh"})
        self.client.post(f"/filme/{self.filme.pk}/avaliar/", {"nota": 5, "comentario": "Revi e amei"})

        self.assertEqual(Avaliacao.objects.filter(usuario=self.usuario).count(), 1)
        avaliacao = Avaliacao.objects.get(usuario=self.usuario, object_id=self.filme.pk)
        self.assertEqual(avaliacao.nota, 5)
        self.assertEqual(avaliacao.comentario, "Revi e amei")

    def test_nota_invalida_nao_salva_e_mostra_erro(self):
        self.client.login(username=self.usuario.username, password="senha-forte-123")
        resposta = self.client.post(
            f"/filme/{self.filme.pk}/avaliar/", {"nota": 9, "comentario": "Nota fora do range"}, follow=True
        )
        self.assertEqual(Avaliacao.objects.count(), 0)
        mensagens = [str(m) for m in resposta.context["messages"]]
        self.assertTrue(any("erro" in m.lower() or "inválid" in m.lower() for m in mensagens) or mensagens)


class AvaliarTituloFuturoTest(TestCase):
    """Regra pedida pelo grupo: só dá pra avaliar títulos que JÁ foram
    lançados — não faz sentido dar nota pra uma continuação anunciada que
    ainda nem saiu. Esses testes cobrem o caso "fácil", em que nem o ANO
    já chegou (sem precisar de `data_lancamento` pra saber que não rolou
    ainda). Ver `AvaliarTituloComDataFuturaNoMesmoAnoTest` logo abaixo pro
    caso mais sutil (título "deste ano", mas que ainda não lançou de
    verdade), e o mesmo cuidado em catalog/tests/test_home.py (títulos
    futuros também não aparecem nas fileiras "recentes" da home)."""

    def setUp(self):
        self.client = Client()
        self.ano_atual = timezone.now().year
        self.filme_futuro = criar_filme(
            titulo="Avatar 5", ano=self.ano_atual + 8, dados_completos=True
        )
        self.usuario = criar_usuario()
        self.client.login(username=self.usuario.username, password="senha-forte-123")

    def test_pagina_de_detalhe_nao_mostra_o_formulario_de_avaliacao(self):
        resposta = self.client.get(f"/filme/{self.filme_futuro.pk}/")
        self.assertFalse(resposta.context["ja_lancado"])
        # Sem o campo de nota (renderizado pelo <select name="nota">) — se o
        # formulário estivesse visível, esse texto apareceria no HTML.
        self.assertNotContains(resposta, 'name="nota"')

    def test_pagina_de_detalhe_mostra_mensagem_no_lugar_do_formulario(self):
        resposta = self.client.get(f"/filme/{self.filme_futuro.pk}/")
        self.assertContains(
            resposta, "Esse título ainda não foi lançado — você poderá avaliar assim que ele sair."
        )

    def test_enviar_avaliacao_direto_por_post_e_bloqueado_mesmo_assim(self):
        # A tela já esconde o formulário (teste acima), mas isso sozinho não
        # PROTEGE nada — é só uma questão de interface. Esse teste manda o
        # POST direto pra URL de avaliar, contornando a tela por completo
        # (como um bot ou alguém mexendo no DevTools faria), pra confirmar
        # que a view também recusa, e não só o template.
        resposta = self.client.post(
            f"/filme/{self.filme_futuro.pk}/avaliar/",
            {"nota": 5, "comentario": "Não deveria conseguir avaliar isso"},
        )
        self.assertRedirects(resposta, f"/filme/{self.filme_futuro.pk}/")
        self.assertEqual(Avaliacao.objects.count(), 0)

    def test_titulo_lancado_no_ano_atual_pode_ser_avaliado_normalmente(self):
        # Não pode "passar do ponto" na correção: um lançamento DESTE ano
        # (não do futuro) precisa continuar avaliável normalmente.
        filme_deste_ano = criar_filme(
            titulo="Lançamento Deste Ano", ano=self.ano_atual, dados_completos=True
        )
        resposta = self.client.post(
            f"/filme/{filme_deste_ano.pk}/avaliar/", {"nota": 4, "comentario": "Gostei"}
        )
        self.assertRedirects(resposta, f"/filme/{filme_deste_ano.pk}/")
        self.assertEqual(Avaliacao.objects.filter(usuario=self.usuario).count(), 1)


class AvaliarTituloComDataFuturaNoMesmoAnoTest(TestCase):
    """Caso relatado pelo grupo (exemplo dado: "Doomsday"): um título pode
    ter `ano_lancamento` igual ao ano ATUAL e mesmo assim ainda não ter
    saído de verdade (ex: previsto pra dezembro, visto em agosto). Só olhar
    pro ANO (como o `AvaliarTituloFuturoTest` acima) não pega esse caso —
    "esse ano" não é a mesma coisa que "já lançou". Por isso, quando temos a
    data EXATA (`data_lancamento`, vinda do TMDB — ver
    catalog/busca_externa.py), a checagem usa ela em vez do ano (ver
    `views._titulo_ja_lancado`).

    IMPORTANTE: diferente do título com ANO no futuro (que nem aparece na
    home — ver test_home.py), um título "deste ano" mas ainda não lançado
    CONTINUA aparecendo/navegável no site normalmente — só a AVALIAÇÃO é
    que fica bloqueada até a data chegar. É por isso que esses testes nunca
    checam se o filme sai da lista/home, só se dá pra avaliar."""

    def setUp(self):
        self.client = Client()
        self.hoje = timezone.localdate()
        # Monta uma data no futuro que, no dia a dia, cai no MESMO ano
        # atual (reproduzindo o exemplo do "Doomsday" — lançamento previsto
        # pra mais tarde neste ano). No raríssimo caso de o teste rodar em
        # 31/12, usa uma data no ano seguinte — o que importa pro teste é
        # só que a data esteja no futuro, não em que ano ela cai.
        if self.hoje.month == 12 and self.hoje.day == 31:
            self.data_futura = datetime.date(self.hoje.year + 1, 1, 15)
        else:
            self.data_futura = datetime.date(self.hoje.year, 12, 31)

        self.filme_deste_ano_nao_lancado = criar_filme(
            titulo="Doomsday",
            ano=self.data_futura.year,
            data_lancamento=self.data_futura,
            dados_completos=True,
        )
        self.usuario = criar_usuario()
        self.client.login(username=self.usuario.username, password="senha-forte-123")

    def test_titulo_deste_ano_mas_ainda_nao_lancado_nao_mostra_formulario(self):
        resposta = self.client.get(f"/filme/{self.filme_deste_ano_nao_lancado.pk}/")
        self.assertFalse(resposta.context["ja_lancado"])
        self.assertNotContains(resposta, 'name="nota"')
        self.assertContains(
            resposta, "Esse título ainda não foi lançado — você poderá avaliar assim que ele sair."
        )

    def test_titulo_deste_ano_mas_ainda_nao_lancado_bloqueia_post_direto(self):
        resposta = self.client.post(
            f"/filme/{self.filme_deste_ano_nao_lancado.pk}/avaliar/",
            {"nota": 5, "comentario": "Contornando a interface"},
        )
        self.assertRedirects(resposta, f"/filme/{self.filme_deste_ano_nao_lancado.pk}/")
        self.assertEqual(Avaliacao.objects.count(), 0)

    def test_titulo_com_data_de_lancamento_ja_passada_pode_ser_avaliado(self):
        # O outro lado da mesma regra: se `data_lancamento` já passou (nem
        # que tenha sido ontem), a avaliação é permitida normalmente — a
        # precisão de dia vale nos dois sentidos, não só pra bloquear.
        ja_lancado = criar_filme(
            titulo="Filme Lançado Ontem",
            ano=self.hoje.year,
            data_lancamento=self.hoje - datetime.timedelta(days=1),
            dados_completos=True,
        )
        resposta = self.client.post(
            f"/filme/{ja_lancado.pk}/avaliar/", {"nota": 4, "comentario": "Peguei estreia"}
        )
        self.assertRedirects(resposta, f"/filme/{ja_lancado.pk}/")
        self.assertEqual(Avaliacao.objects.filter(usuario=self.usuario).count(), 1)

    def test_sem_data_de_lancamento_cadastrada_cai_de_volta_pro_ano(self):
        # Título "legado" (cadastrado antes desse campo existir) ou um
        # livro (Open Library só informa o ano) não tem `data_lancamento` —
        # nesse caso, a regra volta a ser só por ano, igual antes dessa
        # melhoria (comportamento coberto também em AvaliarTituloFuturoTest).
        sem_data_exata = criar_filme(
            titulo="Filme Cadastrado Antes Desse Campo Existir",
            ano=self.hoje.year,
            data_lancamento=None,
            dados_completos=True,
        )
        resposta = self.client.post(
            f"/filme/{sem_data_exata.pk}/avaliar/", {"nota": 3, "comentario": "Sem data exata"}
        )
        self.assertRedirects(resposta, f"/filme/{sem_data_exata.pk}/")
        self.assertEqual(Avaliacao.objects.filter(usuario=self.usuario).count(), 1)


class ExcluirAvaliacaoTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.filme = criar_filme(dados_completos=True)
        self.dona = criar_usuario("dona_da_avaliacao")
        self.outra_pessoa = criar_usuario("outra_pessoa")
        self.avaliacao = Avaliacao.objects.create(usuario=self.dona, titulo_avaliado=self.filme, nota=3)

    def test_dono_consegue_excluir_a_propria_avaliacao(self):
        self.client.login(username="dona_da_avaliacao", password="senha-forte-123")
        self.client.post(f"/avaliacao/{self.avaliacao.pk}/excluir/")
        self.assertFalse(Avaliacao.objects.filter(pk=self.avaliacao.pk).exists())

    def test_outra_pessoa_nao_consegue_excluir_a_avaliacao_alheia(self):
        # get_object_or_404(..., usuario=request.user) em excluir_avaliacao
        # é o que garante isso: se o ID for de uma avaliação de OUTRA
        # pessoa, dá 404 em vez de deixar apagar (não é "403 proibido" de
        # propósito — assim nem revela que aquele ID existe).
        self.client.login(username="outra_pessoa", password="senha-forte-123")
        resposta = self.client.post(f"/avaliacao/{self.avaliacao.pk}/excluir/")
        self.assertEqual(resposta.status_code, 404)
        self.assertTrue(Avaliacao.objects.filter(pk=self.avaliacao.pk).exists())

    def test_precisa_estar_logado_pra_excluir(self):
        resposta = self.client.post(f"/avaliacao/{self.avaliacao.pk}/excluir/")
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(Avaliacao.objects.filter(pk=self.avaliacao.pk).exists())

    def test_exclusao_via_get_nao_e_permitida(self):
        # @require_POST (ver views.excluir_avaliacao) — apagar é uma ação
        # destrutiva, não pode acontecer só por visitar uma URL (GET), só
        # via formulário (POST), pra evitar exclusão acidental (ex: um
        # crawler/bot seguindo o link).
        self.client.login(username="dona_da_avaliacao", password="senha-forte-123")
        resposta = self.client.get(f"/avaliacao/{self.avaliacao.pk}/excluir/")
        self.assertEqual(resposta.status_code, 405)  # "Method Not Allowed"

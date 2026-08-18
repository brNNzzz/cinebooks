"""
Testes da página de listagem (views.lista, templates/catalog/lista.html):
busca por texto, filtro de gênero/ano/nota mínima, e a paginação. Essa é a
página que mais mudou na "polida de experiência" pedida — antes ela
carregava TODOS os títulos de uma vez numa lista só, sem filtro de ano nem
de nota, e sem paginação nenhuma.
"""

from django.test import Client, TestCase

from catalog.models import Avaliacao, Genero
from catalog.tests.fabricas import criar_filme, criar_usuario


class ListaBuscaEFiltrosTest(TestCase):
    def setUp(self):
        # Client() novo em cada teste (padrão do Django TestCase) — evita
        # que sessão/login de um teste vaze pro próximo.
        self.client = Client()
        self.acao = Genero.objects.create(nome="Ação")
        self.drama = Genero.objects.create(nome="Drama")

    def test_pagina_lista_abre_normalmente(self):
        criar_filme(titulo="Duna", ano=2021)
        resposta = self.client.get("/filme/")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Duna")

    def test_tipo_invalido_na_url_da_404(self):
        # "/documentario/" não é um dos 3 tipos conhecidos (filme/serie/
        # livro) — TIPOS.get() em views.py devolve None e a view levanta
        # Http404 de propósito, em vez de deixar o Django quebrar feio.
        resposta = self.client.get("/documentario/")
        self.assertEqual(resposta.status_code, 404)

    def test_busca_por_titulo_encontra_so_o_que_bate(self):
        criar_filme(titulo="Duna", ano=2021)
        criar_filme(titulo="Vingadores", ano=2019)

        resposta = self.client.get("/filme/?q=duna")  # minúsculo de propósito
        self.assertContains(resposta, "Duna")
        self.assertNotContains(resposta, "Vingadores")

    def test_busca_por_titulo_e_case_insensitive(self):
        # icontains (usado em views.lista) já ignora maiúsc./minúsc.
        # sozinho — esse teste é só pra garantir que continua assim.
        criar_filme(titulo="Duna", ano=2021)
        resposta = self.client.get("/filme/?q=DUNA")
        self.assertContains(resposta, "Duna")

    def test_filtro_de_genero(self):
        acao1 = criar_filme(titulo="Filme de Ação", ano=2020)
        acao1.generos.add(self.acao)
        drama1 = criar_filme(titulo="Filme de Drama", ano=2020)
        drama1.generos.add(self.drama)

        resposta = self.client.get(f"/filme/?genero={self.acao.pk}")
        self.assertContains(resposta, "Filme de Ação")
        self.assertNotContains(resposta, "Filme de Drama")

    def test_filtro_de_genero_nao_duplica_titulo_com_varios_generos(self):
        # O filtro de gênero faz um JOIN (ManyToMany) — sem o .distinct()
        # em views.lista, um filme com 2 gêneros que batem no filtro (nesse
        # caso não bate, mas o titulo tem os dois gêneros cadastrados)
        # apareceria REPETIDO na página. Aqui garantimos que aparece só uma
        # vez mesmo tendo 2 gêneros.
        filme = criar_filme(titulo="Filme com Dois Gêneros", ano=2020)
        filme.generos.set([self.acao, self.drama])

        resposta = self.client.get(f"/filme/?genero={self.acao.pk}")
        itens = list(resposta.context["itens"])
        self.assertEqual(len(itens), 1)

    def test_filtro_de_ano(self):
        criar_filme(titulo="Filme de 2020", ano=2020)
        criar_filme(titulo="Filme de 2021", ano=2021)

        resposta = self.client.get("/filme/?ano=2020")
        self.assertContains(resposta, "Filme de 2020")
        self.assertNotContains(resposta, "Filme de 2021")

    def test_filtro_de_nota_minima(self):
        bem_avaliado = criar_filme(titulo="Filme Bem Avaliado", ano=2020)
        mal_avaliado = criar_filme(titulo="Filme Mal Avaliado", ano=2020)
        usuario = criar_usuario()
        Avaliacao.objects.create(usuario=usuario, titulo_avaliado=bem_avaliado, nota=5)
        Avaliacao.objects.create(usuario=usuario, titulo_avaliado=mal_avaliado, nota=2)

        resposta = self.client.get("/filme/?nota_minima=4")
        self.assertContains(resposta, "Filme Bem Avaliado")
        self.assertNotContains(resposta, "Filme Mal Avaliado")

    def test_filtro_de_nota_minima_invalido_nao_quebra_a_pagina(self):
        # Alguém pode chegar em "?nota_minima=abc" editando a URL na mão —
        # a view precisa ignorar esse valor (em vez de tentar float("abc")
        # e devolver erro 500 pra quem tá navegando).
        criar_filme(titulo="Qualquer Filme", ano=2020)
        resposta = self.client.get("/filme/?nota_minima=abc")
        self.assertEqual(resposta.status_code, 200)

    def test_filtros_combinados(self):
        # Gênero + ano + nota mínima ao mesmo tempo — o pedido original era
        # "filtro avançado (gênero + ano + nota mínima)", então testamos os
        # três juntos, não só cada um isolado.
        alvo = criar_filme(titulo="Filme Certo", ano=2020)
        alvo.generos.add(self.acao)
        usuario = criar_usuario()
        Avaliacao.objects.create(usuario=usuario, titulo_avaliado=alvo, nota=5)

        # Mesmo gênero e nota, mas ano diferente — não pode aparecer.
        errado_ano = criar_filme(titulo="Filme Ano Errado", ano=2019)
        errado_ano.generos.add(self.acao)
        Avaliacao.objects.create(usuario=usuario, titulo_avaliado=errado_ano, nota=5)

        resposta = self.client.get(f"/filme/?genero={self.acao.pk}&ano=2020&nota_minima=4")
        self.assertContains(resposta, "Filme Certo")
        self.assertNotContains(resposta, "Filme Ano Errado")


class ListaPaginacaoTest(TestCase):
    def setUp(self):
        self.client = Client()
        # ITENS_POR_PAGINA é 12 (ver views.py) — criamos 15 pra garantir
        # que sobra pra uma segunda página (15 = 12 + 3).
        for i in range(15):
            criar_filme(titulo=f"Filme Número {i:02d}", ano=2000 + i)

    def test_primeira_pagina_mostra_so_o_limite_por_pagina(self):
        resposta = self.client.get("/filme/")
        self.assertEqual(len(resposta.context["itens"]), 12)
        self.assertEqual(resposta.context["itens"].paginator.num_pages, 2)

    def test_segunda_pagina_mostra_o_restante(self):
        resposta = self.client.get("/filme/?pagina=2")
        self.assertEqual(len(resposta.context["itens"]), 3)

    def test_pagina_fora_do_intervalo_cai_na_ultima_em_vez_de_quebrar(self):
        # Paginator.get_page() (diferente de .page()) já lida sozinho com
        # números fora do intervalo — esse teste é só pra confirmar que a
        # view está mesmo usando get_page() e não um .page() que levantaria
        # EmptyPage e derrubaria a página com erro 500.
        resposta = self.client.get("/filme/?pagina=999")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["itens"].number, 2)  # última página existente

    def test_pagina_nao_numerica_cai_na_primeira_em_vez_de_quebrar(self):
        resposta = self.client.get("/filme/?pagina=abc")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["itens"].number, 1)

    def test_trocar_de_pagina_mantem_o_filtro_ativo(self):
        # query_sem_pagina (montado em views.lista e usado nos links
        # "anterior"/"próxima" de lista.html) precisa preservar os outros
        # parâmetros da URL (busca, gênero...) — senão, ao clicar em
        # "próxima página" com uma busca ativa, a pessoa perderia o filtro
        # sem querer.
        resposta = self.client.get("/filme/?q=Filme&pagina=1")
        self.assertIn("q=Filme", resposta.context["query_sem_pagina"])
        self.assertNotIn("pagina", resposta.context["query_sem_pagina"])

    def test_ordem_e_sempre_a_mesma_entre_paginas(self):
        # Bug real que apareceu ao implementar a paginação: como
        # views._com_media() faz um annotate() com Avg/Count, o Django, em
        # certas condições, deixa de aplicar a ordenação padrão do modelo
        # sozinho — o que faria a ORDEM dos títulos mudar a cada consulta,
        # duplicando ou pulando títulos ao trocar de página. Por isso
        # views.lista() força `.order_by("-ano_lancamento", "titulo")`
        # explicitamente antes de paginar. Este teste pega os títulos das
        # duas páginas e garante que juntos formam o total certo, SEM
        # repetir nenhum.
        pagina1 = self.client.get("/filme/?pagina=1").context["itens"]
        pagina2 = self.client.get("/filme/?pagina=2").context["itens"]

        titulos_pagina1 = {item.titulo for item in pagina1}
        titulos_pagina2 = {item.titulo for item in pagina2}

        self.assertEqual(len(titulos_pagina1), 12)
        self.assertEqual(len(titulos_pagina2), 3)
        # As duas páginas juntas não podem ter nenhum título em comum.
        self.assertEqual(titulos_pagina1 & titulos_pagina2, set())

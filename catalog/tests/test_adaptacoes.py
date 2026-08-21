"""
Testes da funcionalidade "Adaptações" (livro → filme/série) pedida
explicitamente pelo usuário: vínculo detectado por um ALGORITMO automático
(nunca cadastro manual), numa aba separada do catálogo comum.

- `catalog/adaptacoes.py` (`_normalizar`, `_similaridade`,
  `detectar_adaptacoes_para_livro`/`_para_filme_serie`) → a detecção em si.
- `catalog.models.Adaptacao` → o vínculo salvo (Generic FK pro lado
  filme/série, FK normal pro lado livro).
- `views.adaptacoes` → a página/aba separada que lista os pares.
- Pontos de chamada automática (`views._criar_*`) já são cobertos
  indiretamente pelos testes de importação existentes; aqui testamos a
  função de detecção isolada, que é o que eles chamam.
"""

from django.contrib.contenttypes.models import ContentType
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from catalog import adaptacoes as matching
from catalog.models import Adaptacao
from catalog.tests.fabricas import criar_filme, criar_livro, criar_serie, criar_usuario


class NormalizarESimilaridadeTest(SimpleTestCase):
    def test_normaliza_acento_pontuacao_maiuscula(self):
        self.assertEqual(matching._normalizar("O Senhor dos Anéis!"), "senhor dos aneis")

    def test_titulos_iguais_tem_similaridade_maxima(self):
        self.assertEqual(matching._similaridade("Duna", "Duna"), 1.0)

    def test_titulo_e_subtitulo_tem_similaridade_alta(self):
        # "O Senhor dos Anéis" (livro) x "O Senhor dos Anéis: A Sociedade do
        # Anel" (filme) — mesma obra, título do filme só tem um subtítulo
        # a mais. Não exige limiar aqui, só confere que fica bem alto.
        pontuacao = matching._similaridade("O Senhor dos Anéis", "O Senhor dos Anéis: A Sociedade do Anel")
        self.assertGreater(pontuacao, 0.6)

    def test_titulos_parecidos_mas_diferentes_ficam_abaixo_do_limiar(self):
        # "Duna" x "Duna Cinzenta" são títulos parecidos, mas obras
        # diferentes — não deveria passar do limiar de detecção.
        pontuacao = matching._similaridade("Duna", "Duna Cinzenta")
        self.assertLess(pontuacao, matching.LIMIAR_SIMILARIDADE)

    def test_titulo_vazio_nunca_bate(self):
        self.assertEqual(matching._similaridade("", "Duna"), 0.0)
        self.assertEqual(matching._similaridade("Duna", ""), 0.0)


class DetectarAdaptacoesTest(TestCase):
    """`detectar_adaptacoes_para_livro`/`_para_filme_serie` — a detecção
    automática em si, chamada pelos pontos de importação (ver
    `views._criar_filme_rapido` e companhia)."""

    def test_titulo_identico_cria_vinculo(self):
        livro = criar_livro(titulo="A Jornada do Herói Perdido")
        filme = criar_filme(titulo="A Jornada do Herói Perdido")

        encontrados = matching.detectar_adaptacoes_para_livro(livro)

        self.assertEqual(encontrados, [filme])
        self.assertTrue(
            Adaptacao.objects.filter(
                livro=livro,
                content_type=ContentType.objects.get_for_model(filme),
                object_id=filme.pk,
            ).exists()
        )

    def test_titulo_diferente_nao_cria_vinculo(self):
        livro = criar_livro(titulo="Um Livro Qualquer")
        criar_filme(titulo="Outro Filme Sem Nada A Ver")

        encontrados = matching.detectar_adaptacoes_para_livro(livro)

        self.assertEqual(encontrados, [])
        self.assertEqual(Adaptacao.objects.count(), 0)

    def test_funciona_tambem_pro_lado_filme_serie(self):
        # O inverso: filme/série novo entrando no catálogo, livro já
        # existia antes — usado quando o filme é importado DEPOIS do livro
        # (ver views._criar_filme_do_tmdb e companhia).
        livro = criar_livro(titulo="Crônicas do Vento Leste")
        serie = criar_serie(titulo="Crônicas do Vento Leste")

        encontrados = matching.detectar_adaptacoes_para_filme_serie(serie)

        self.assertEqual(encontrados, [livro])
        self.assertTrue(
            Adaptacao.objects.filter(
                livro=livro,
                content_type=ContentType.objects.get_for_model(serie),
                object_id=serie.pk,
            ).exists()
        )

    def test_encontra_vinculo_com_filme_e_serie_ao_mesmo_tempo(self):
        # Um livro que virou filme E série — os dois vínculos devem ser
        # criados, não só o primeiro achado.
        livro = criar_livro(titulo="Trilogia das Estrelas Frias")
        filme = criar_filme(titulo="Trilogia das Estrelas Frias")
        serie = criar_serie(titulo="Trilogia das Estrelas Frias")

        encontrados = matching.detectar_adaptacoes_para_livro(livro)

        self.assertCountEqual(encontrados, [filme, serie])
        self.assertEqual(Adaptacao.objects.filter(livro=livro).count(), 2)

    def test_e_idempotente_nao_duplica_ao_rodar_de_novo(self):
        livro = criar_livro(titulo="Idempotência no Fim do Mundo")
        criar_filme(titulo="Idempotência no Fim do Mundo")

        matching.detectar_adaptacoes_para_livro(livro)
        matching.detectar_adaptacoes_para_livro(livro)

        self.assertEqual(Adaptacao.objects.filter(livro=livro).count(), 1)

    def test_detectar_todas_adaptacoes_varre_o_catalogo_inteiro(self):
        livro_a = criar_livro(titulo="Livro Alfa Único")
        criar_filme(titulo="Livro Alfa Único")
        livro_b = criar_livro(titulo="Livro Beta Único")
        criar_serie(titulo="Livro Beta Único")
        criar_livro(titulo="Livro Gama Sem Adaptação Nenhuma")

        total = matching.detectar_todas_adaptacoes()

        self.assertEqual(total, 2)
        self.assertTrue(Adaptacao.objects.filter(livro=livro_a).exists())
        self.assertTrue(Adaptacao.objects.filter(livro=livro_b).exists())


class AdaptacaoModelTest(TestCase):
    def test_str(self):
        livro = criar_livro(titulo="Livro X")
        filme = criar_filme(titulo="Livro X")
        vinculo = Adaptacao.objects.create(
            livro=livro,
            content_type=ContentType.objects.get_for_model(filme),
            object_id=filme.pk,
        )
        self.assertIn("Livro X", str(vinculo))

    def test_constraint_impede_vinculo_duplicado(self):
        from django.db import IntegrityError, transaction

        livro = criar_livro(titulo="Livro Único")
        filme = criar_filme(titulo="Livro Único")
        content_type = ContentType.objects.get_for_model(filme)
        Adaptacao.objects.create(livro=livro, content_type=content_type, object_id=filme.pk)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Adaptacao.objects.create(livro=livro, content_type=content_type, object_id=filme.pk)


class PaginaAdaptacoesTest(TestCase):
    """A view `adaptacoes` — aba SEPARADA do catálogo, pedida explicitamente
    ("em uma aba separada")."""

    def test_pagina_lista_os_pares_detectados(self):
        livro = criar_livro(titulo="Par Visível")
        filme = criar_filme(titulo="Par Visível")
        matching.detectar_adaptacoes_para_livro(livro)

        resposta = Client().get(reverse("adaptacoes"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Par Visível")

    def test_pagina_vazia_nao_quebra(self):
        resposta = Client().get(reverse("adaptacoes"))
        self.assertEqual(resposta.status_code, 200)

    def test_link_de_adaptacoes_aparece_na_navegacao(self):
        resposta = Client().get(reverse("home"))
        self.assertContains(resposta, reverse("adaptacoes"))


class DetalheMostraCardDeAdaptacaoTest(TestCase):
    """O card "Do livro à tela"/"Adaptações deste livro" na página de
    detalhe — dos dois lados (livro e filme/série)."""

    def setUp(self):
        self.livro = criar_livro(titulo="Vínculo Visível No Detalhe")
        self.filme = criar_filme(titulo="Vínculo Visível No Detalhe")
        matching.detectar_adaptacoes_para_livro(self.livro)

    def test_lado_do_livro_mostra_a_adaptacao(self):
        resposta = Client().get(reverse("detalhe", args=["livro", self.livro.pk]))
        self.assertContains(resposta, self.filme.titulo)

    def test_lado_do_filme_mostra_o_livro(self):
        resposta = Client().get(reverse("detalhe", args=["filme", self.filme.pk]))
        self.assertContains(resposta, self.livro.titulo)

    def test_titulo_sem_adaptacao_nenhuma_nao_mostra_o_card(self):
        outro_livro = criar_livro(titulo="Livro Completamente Sozinho")
        resposta = Client().get(reverse("detalhe", args=["livro", outro_livro.pk]))
        self.assertNotContains(resposta, "nc-card-lateral--adaptacao")

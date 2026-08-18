"""
Testes dos formulários (catalog/forms.py) — em especial a parte que muda de
acordo com o idioma escolhido no site. AvaliacaoForm e RegistroForm recebem
um parâmetro `idioma` no `__init__` porque os rótulos/opções não podem ser
fixados na classe (`Meta`) — eles são montados só na hora de criar o
formulário, usando `traduzir()` (ver catalog/i18n.py). Esses testes
garantem que essa tradução dinâmica realmente acontece.
"""

from django.test import TestCase

from catalog.forms import AvaliacaoForm, RegistroForm


class AvaliacaoFormTest(TestCase):
    def test_rotulos_em_portugues_por_padrao(self):
        form = AvaliacaoForm()
        self.assertEqual(form.fields["nota"].label, "Sua nota")
        self.assertEqual(form.fields["comentario"].label, "Comentário")

    def test_rotulos_mudam_pro_idioma_pedido(self):
        # Mesma classe, mesmos campos — só o idioma passado no __init__
        # muda. Isso é o que faz o formulário de avaliação aparecer em
        # inglês quando o site está em inglês, por exemplo.
        form = AvaliacaoForm(idioma="en")
        self.assertEqual(form.fields["nota"].label, "Your rating")
        self.assertEqual(form.fields["comentario"].label, "Comment")

    def test_opcoes_de_nota_tem_singular_e_plural_certos(self):
        # "1 estrela" (singular) mas "2 estrelas", "3 estrelas"... (plural)
        # — testamos os dois casos pra garantir que a escolha entre singular
        # e plural (feita em forms.py: `estrela if n == 1 else estrelas`)
        # está certa nas duas pontas.
        form = AvaliacaoForm()
        opcoes = dict(form.fields["nota"].widget.choices)
        self.assertEqual(opcoes[1], "1 estrela")
        self.assertEqual(opcoes[2], "2 estrelas")
        self.assertEqual(opcoes[5], "5 estrelas")

    def test_formulario_valido_com_nota_e_comentario_vazio(self):
        # comentário é opcional (blank=True no modelo) — só a nota é
        # obrigatória pra avaliação valer.
        form = AvaliacaoForm(data={"nota": 4, "comentario": ""})
        self.assertTrue(form.is_valid())

    def test_formulario_invalido_sem_nota(self):
        form = AvaliacaoForm(data={"comentario": "Gostei bastante"})
        self.assertFalse(form.is_valid())


class RegistroFormTest(TestCase):
    def test_rotulo_do_email_em_portugues_por_padrao(self):
        form = RegistroForm()
        self.assertEqual(form.fields["email"].label, "e-mail")

    def test_rotulo_do_email_muda_pro_idioma_pedido(self):
        form = RegistroForm(idioma="es")
        self.assertEqual(form.fields["email"].label, "correo electrónico")

    def test_email_e_opcional(self):
        # required=False no campo (ver forms.py) — a conta pode ser criada
        # sem e-mail, já que o site não manda nenhum e-mail de verificação.
        self.assertFalse(RegistroForm().fields["email"].required)

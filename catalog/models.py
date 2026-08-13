"""
Modelos de dados do catálogo (CineBooks).

Estrutura pensada para ficar fácil de explicar no trabalho:

- Genero: tabela simples de gêneros (Ação, Drama, Fantasia, etc.)
- Titulo: classe ABSTRATA com os campos que Filme, Serie e Livro têm em comum
  (não vira tabela no banco, só evita repetir código nas três classes filhas)
- Filme, Serie, Livro: herdam de Titulo e adicionam seus campos específicos
- Avaliacao: nota + comentário que um usuário dá para um filme, série OU livro.
  Para não precisar de 3 tabelas de avaliação (uma pra cada tipo), usamos o
  recurso de "Generic Foreign Key" do Django, que permite uma avaliação
  apontar para qualquer um dos três modelos acima.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse


class Genero(models.Model):
    nome = models.CharField("nome", max_length=50, unique=True)

    class Meta:
        verbose_name = "gênero"
        verbose_name_plural = "gêneros"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Titulo(models.Model):
    """Campos comuns a Filme, Serie e Livro. Não gera tabela própria."""

    titulo = models.CharField("título", max_length=200)
    sinopse = models.TextField("sinopse", blank=True)
    ano_lancamento = models.PositiveIntegerField("ano de lançamento")
    poster_url = models.URLField(
        "URL do pôster/capa",
        blank=True,
        help_text="Link de uma imagem (opcional). Se deixar em branco, usamos uma imagem padrão.",
    )
    generos = models.ManyToManyField(Genero, verbose_name="gêneros", blank=True)
    criado_em = models.DateTimeField("adicionado em", auto_now_add=True)

    # Ligação genérica com Avaliacao (não cria coluna no banco, é só um atalho
    # para conseguirmos fazer `filme.avaliacoes.all()`)
    avaliacoes = GenericRelation(
        "Avaliacao",
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="%(class)s",
    )

    class Meta:
        abstract = True
        ordering = ["-ano_lancamento", "titulo"]

    def __str__(self):
        return f"{self.titulo} ({self.ano_lancamento})"

    def media_avaliacoes(self):
        agregada = self.avaliacoes.aggregate(media=models.Avg("nota"))["media"]
        return round(agregada, 1) if agregada else None

    def total_avaliacoes(self):
        return self.avaliacoes.count()


class Filme(Titulo):
    diretor = models.CharField("diretor(a)", max_length=150, blank=True)
    duracao_minutos = models.PositiveIntegerField("duração (minutos)", null=True, blank=True)

    class Meta(Titulo.Meta):
        verbose_name = "filme"
        verbose_name_plural = "filmes"

    def get_absolute_url(self):
        return reverse("filme_detalhe", args=[self.pk])


class Serie(Titulo):
    criador = models.CharField("criador(a)", max_length=150, blank=True)
    numero_temporadas = models.PositiveIntegerField("número de temporadas", null=True, blank=True)

    class Meta(Titulo.Meta):
        verbose_name = "série"
        verbose_name_plural = "séries"

    def get_absolute_url(self):
        return reverse("serie_detalhe", args=[self.pk])


class Livro(Titulo):
    autor = models.CharField("autor(a)", max_length=150, blank=True)
    editora = models.CharField("editora", max_length=150, blank=True)
    numero_paginas = models.PositiveIntegerField("número de páginas", null=True, blank=True)

    class Meta(Titulo.Meta):
        verbose_name = "livro"
        verbose_name_plural = "livros"

    def get_absolute_url(self):
        return reverse("livro_detalhe", args=[self.pk])


class Avaliacao(models.Model):
    """Nota (1 a 5) + comentário de um usuário para um Filme, Série ou Livro."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="usuário", on_delete=models.CASCADE
    )
    nota = models.PositiveSmallIntegerField(
        "nota", validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comentario = models.TextField("comentário", blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    # As duas linhas abaixo, juntas, formam a "Generic Foreign Key":
    # content_type diz QUAL tabela (Filme, Serie ou Livro) e object_id diz
    # QUAL registro daquela tabela.
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    titulo_avaliado = GenericForeignKey("content_type", "object_id")

    class Meta:
        verbose_name = "avaliação"
        verbose_name_plural = "avaliações"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "content_type", "object_id"],
                name="usuario_avalia_uma_vez_cada_titulo",
            )
        ]

    def __str__(self):
        return f"{self.usuario} → {self.titulo_avaliado} ({self.nota}/5)"

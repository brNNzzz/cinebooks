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


class Pessoa(models.Model):
    """Um ator/atriz (elenco de filmes/séries) ou autor(a) de livro. Uma
    tabela só, reaproveitada pelos três tipos de título, pra não repetir
    nome/foto de quem aparece em mais de uma obra."""

    nome = models.CharField("nome", max_length=150, unique=True)
    foto_url = models.URLField("URL da foto", blank=True)

    class Meta:
        verbose_name = "pessoa"
        verbose_name_plural = "pessoas"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Titulo(models.Model):
    """Campos comuns a Filme, Serie e Livro. Não gera tabela própria."""

    titulo = models.CharField("título", max_length=200)
    sinopse = models.TextField("sinopse", blank=True)
    ano_lancamento = models.PositiveIntegerField("ano de lançamento")
    # Data EXATA de lançamento (dia/mês/ano), quando a API externa souber
    # informar — o TMDB devolve isso pra filme/série (campo "release_date"/
    # "first_air_date"), mas o Open Library só sabe o ano dos livros, então
    # fica None nesse caso. Guardado à parte de `ano_lancamento` (que
    # continua existindo e sendo usado pra ordenar/filtrar o catálogo) só
    # pra decidir com precisão se um título JÁ saiu ou não — necessário
    # porque um título pode ter `ano_lancamento` igual ao ano atual mas
    # ainda não ter sido lançado de verdade (ex: um filme anunciado pra
    # dezembro, visto em agosto do mesmo ano: aparece no catálogo, mas
    # ninguém deveria conseguir avaliar antes de existir de verdade). Ver
    # `views._titulo_ja_lancado`.
    data_lancamento = models.DateField("data de lançamento", null=True, blank=True)
    poster_url = models.URLField(
        "URL do pôster/capa",
        blank=True,
        help_text="Link de uma imagem (opcional). Se deixar em branco, usamos uma imagem padrão.",
    )
    generos = models.ManyToManyField(Genero, verbose_name="gêneros", blank=True)
    criado_em = models.DateTimeField("adicionado em", auto_now_add=True)

    # Notas vindas da internet (não são as avaliações dos usuários do site,
    # que continuam só em Avaliacao — isso aqui é só pra exibir "o que a
    # internet acha" ao lado da nota da nossa comunidade).
    # nota_publico: nota do público em geral (IMDb pra filme/série, média de
    # avaliações do Open Library pra livro), numa escala de 0 a 10.
    nota_publico = models.FloatField("nota do público (internet)", null=True, blank=True)
    # nota_critica: nota da crítica especializada (Metacritic, via OMDb).
    # Só existe pra filme/série — livro não tem um "Metacritic" equivalente.
    nota_critica = models.FloatField("nota da crítica (internet)", null=True, blank=True)
    # nota_rotten_tomatoes: % de aprovação no Rotten Tomatoes (via OMDb).
    # Também só existe pra filme/série.
    nota_rotten_tomatoes = models.IntegerField("nota Rotten Tomatoes (%)", null=True, blank=True)
    # True depois que já tentamos buscar as notas no OMDb pelo menos uma vez
    # (independente do resultado). Precisa ser um campo separado, e não só
    # "os 3 campos de nota estão vazios?", porque nem todo título tem as 3
    # notas no OMDb — é normal um filme ter nota do público e não ter
    # Rotten Tomatoes, por exemplo. Sem esse campo, um título que já achou
    # ALGUMA nota nunca tentaria buscar a que ainda falta.
    notas_omdb_verificadas = models.BooleanField("notas do OMDb já verificadas", default=False)

    # ID do título no IMDb (ex: "tt1234567"), obtido via TMDB. Usado pra
    # buscar as notas no OMDb por ID em vez de por texto — muito mais
    # confiável, já que buscar por título+ano falha sempre que o título
    # está traduzido (ex: "Duna" não bate com "Dune" no OMDb).
    imdb_id = models.CharField("ID no IMDb", max_length=20, blank=True)

    # Em que idioma (código do TMDB, tipo "pt-BR" ou "en-US") esse título
    # foi cadastrado — ou seja, em que idioma estão o título e a sinopse
    # hoje. Guardado no momento da criação e usado pra TODAS as buscas de
    # complemento depois (elenco, sinopse maior, imdb_id...), mesmo que a
    # pessoa que visitar a página esteja navegando em outro idioma. Sem
    # isso, um filme cadastrado em português podia acabar com a sinopse
    # trocada pra inglês só porque alguém navegando em inglês abriu a
    # página dele — título e sinopse ficavam em idiomas diferentes.
    idioma_tmdb_conteudo = models.CharField(
        "idioma do conteúdo cadastrado", max_length=10, blank=True, default="pt-BR"
    )

    # Cache de título/sinopse traduzidos, um por idioma do site (ex:
    # {"en-US": {"titulo": "...", "sinopse": "..."}}). É só um "extra" pra
    # EXIBIÇÃO: quando alguém navega no site num idioma diferente do
    # `idioma_tmdb_conteudo`, mostramos a tradução daqui (se já tiver sido
    # buscada) em vez do texto original. Os campos `titulo`/`sinopse` lá em
    # cima NUNCA são sobrescritos por isso — continuam sempre no idioma
    # original, pra não repetir o bug de misturar idiomas dentro do mesmo
    # registro.
    traducoes = models.JSONField("traduções para exibição", default=dict, blank=True)

    # Onde assistir (streaming por assinatura, aluguel, compra), pra região
    # do Brasil — vem do TMDB (que por sua vez usa a JustWatch como fonte),
    # buscado junto com o resto dos dados complementares (ver
    # `views._completar_filme`/`_completar_serie`). Formato:
    # {"link": "...", "streaming": [{"nome": "...", "logo_url": "..."}, ...],
    # "aluguel": [...], "compra": [...]} — ou {} se não achou nada ainda, ou
    # se o título não tem essa informação disponível. Só existe pra
    # filme/série; livro herda o campo (por causa da classe abstrata) mas
    # nunca é preenchido.
    onde_assistir = models.JSONField("onde assistir", default=dict, blank=True)

    # Link direto pro trailer no YouTube (ex: "https://www.youtube.com/
    # watch?v=..."), quando o TMDB tiver um cadastrado — busca o vídeo
    # OFICIAL mais adequado (ver `busca_externa._extrair_trailer_youtube`).
    # Fica em branco se não achar nenhum. Só existe pra filme/série; livro
    # herda o campo (classe abstrata) mas nunca é preenchido.
    trailer_youtube_url = models.URLField("trailer no YouTube", blank=True)

    # Guarda o ID do título na API externa (TMDB para filme/série, Open
    # Library para livro). Usado depois pra completar os dados (elenco,
    # sinopse maior) sem precisar buscar o título de novo pelo nome.
    id_externo = models.CharField("ID na API externa", max_length=50, blank=True)
    # Fica True depois que já buscamos os dados completos (elenco, sinopse
    # detalhada) desse título pelo menos uma vez. Enquanto for False, a
    # página de detalhe tenta completar automaticamente na próxima visita.
    dados_completos = models.BooleanField("dados completos", default=False)

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
    elenco = models.ManyToManyField(Pessoa, verbose_name="elenco", blank=True, related_name="filmes")

    class Meta(Titulo.Meta):
        verbose_name = "filme"
        verbose_name_plural = "filmes"

    def get_absolute_url(self):
        return reverse("filme_detalhe", args=[self.pk])

    def save(self, *args, **kwargs):
        # Se ninguém preencheu uma capa manualmente, tenta buscar uma real
        # automaticamente (ver catalog/capas.py). Se falhar, não tem problema:
        # o site usa uma imagem padrão no lugar.
        if not self.poster_url:
            from .capas import buscar_poster_filme

            encontrado = buscar_poster_filme(self.titulo, self.ano_lancamento)
            if encontrado:
                self.poster_url = encontrado
        super().save(*args, **kwargs)


class Serie(Titulo):
    criador = models.CharField("criador(a)", max_length=150, blank=True)
    numero_temporadas = models.PositiveIntegerField("número de temporadas", null=True, blank=True)
    elenco = models.ManyToManyField(Pessoa, verbose_name="elenco", blank=True, related_name="series")

    class Meta(Titulo.Meta):
        verbose_name = "série"
        verbose_name_plural = "séries"

    def get_absolute_url(self):
        return reverse("serie_detalhe", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.poster_url:
            from .capas import buscar_poster_serie

            encontrado = buscar_poster_serie(self.titulo, self.ano_lancamento)
            if encontrado:
                self.poster_url = encontrado
        super().save(*args, **kwargs)


class Livro(Titulo):
    autor = models.CharField("autor(a)", max_length=150, blank=True)
    editora = models.CharField("editora", max_length=150, blank=True)
    numero_paginas = models.PositiveIntegerField("número de páginas", null=True, blank=True)
    # Além do nome em texto (campo "autor" acima, usado pra busca/filtro),
    # guardamos um link pra Pessoa quando tivermos a foto de quem escreveu.
    autor_pessoa = models.ForeignKey(
        Pessoa,
        verbose_name="autor(a) (com foto)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="livros",
    )

    class Meta(Titulo.Meta):
        verbose_name = "livro"
        verbose_name_plural = "livros"

    def get_absolute_url(self):
        return reverse("livro_detalhe", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.poster_url:
            from .capas import buscar_capa_livro

            encontrada = buscar_capa_livro(self.titulo, self.autor)
            if encontrada:
                self.poster_url = encontrada
        super().save(*args, **kwargs)


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


class Busca(models.Model):
    """Histórico de termos que um usuário LOGADO já buscou no site — um dos
    3 sinais usados pra montar a fileira "Recomendados pra você" na home
    (ver `catalog/recomendacoes.py`), junto com as avaliações e a watchlist.
    Ajuda a captar interesse mesmo antes da pessoa avaliar ou guardar algo:
    se ela vive buscando "Star Wars", "Duna", "Interestelar"..., isso já diz
    bastante sobre o gosto dela, mesmo sem nenhuma nota dada ainda.

    Buscas de quem NÃO está logado não são salvas (não tem em qual usuário
    guardar, e não faria sentido misturar com o histórico de outra pessoa
    no mesmo navegador)."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        on_delete=models.CASCADE,
        related_name="buscas",
    )
    termo = models.CharField("termo buscado", max_length=200)
    criado_em = models.DateTimeField("buscado em", auto_now_add=True)

    class Meta:
        verbose_name = "busca"
        verbose_name_plural = "buscas"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.usuario} buscou: {self.termo!r}"


class QueroVer(models.Model):
    """"Watchlist": um usuário marca um Filme, Série ou Livro que ainda não
    viu/leu mas quer ver depois — separado das avaliações de propósito, já
    que Avaliacao é pra quem JÁ assistiu/leu e quer dar nota/comentário.

    Mesma técnica de "Generic Foreign Key" usada em Avaliacao (ver
    comentário lá em cima): content_type + object_id juntos apontam pra
    QUALQUER um dos três modelos (Filme, Serie ou Livro), sem precisar de
    uma tabela de watchlist separada pra cada tipo."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="usuário", on_delete=models.CASCADE
    )
    criado_em = models.DateTimeField("adicionado em", auto_now_add=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    titulo_lista = GenericForeignKey("content_type", "object_id")

    class Meta:
        verbose_name = "item da watchlist"
        verbose_name_plural = "itens da watchlist"
        ordering = ["-criado_em"]
        constraints = [
            # Mesmo título não pode ser adicionado duas vezes pelo mesmo
            # usuário — o botão "quero ver depois" vira "remover da lista"
            # assim que o item já está lá (ver views.alternar_watchlist).
            models.UniqueConstraint(
                fields=["usuario", "content_type", "object_id"],
                name="usuario_adiciona_um_titulo_uma_vez_na_watchlist",
            )
        ]

    def __str__(self):
        return f"{self.usuario} quer ver: {self.titulo_lista}"


class Adaptacao(models.Model):
    """Vínculo entre um Livro e a adaptação dele em Filme OU Série — a aba
    "Adaptações" do site (separada do catálogo comum, ver `views.adaptacoes`)
    e o card "Do livro à tela" na página de detalhe (ver
    `templates/catalog/detalhe.html`).

    Esses vínculos NUNCA são cadastrados manualmente: são detectados por um
    algoritmo automático (`catalog/adaptacoes.py`, função
    `detectar_adaptacoes_para`) que compara o título do livro com o título
    de cada filme/série do catálogo (normalizando acentos/pontuação/
    maiúsculas) e cria o registro quando a semelhança passa de um limiar —
    ver `LIMIAR_SIMILARIDADE` lá. É chamado automaticamente sempre que um
    título novo entra no catálogo (livro OU filme/série, não importa qual
    lado chegou primeiro — ver os pontos de chamada em `views.py`, nas
    funções `_criar_*`), e também dá pra rodar num catálogo já existente
    inteiro com `python manage.py detectar_adaptacoes`.

    Mesma técnica de "Generic Foreign Key" de Avaliacao/QueroVer pro lado
    filme/série (que pode ser um OU outro modelo) — o lado do livro é uma FK
    normal, já que esse lado é sempre um Livro."""

    livro = models.ForeignKey(
        Livro, verbose_name="livro", on_delete=models.CASCADE, related_name="adaptacoes"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    adaptacao = GenericForeignKey("content_type", "object_id")

    # Guardado só pra transparência/depuração (ex: no admin, dá pra ver o
    # quão "forte" foi a semelhança que gerou esse vínculo) — não é exibido
    # pro usuário final, já que "72% parecido" sem mais contexto não diz
    # muita coisa útil pra quem só quer saber "isso é uma adaptação desse
    # livro ou não é".
    pontuacao_similaridade = models.FloatField("pontuação de similaridade do título", default=0.0)
    criado_em = models.DateTimeField("detectado em", auto_now_add=True)

    class Meta:
        verbose_name = "adaptação"
        verbose_name_plural = "adaptações"
        ordering = ["livro__titulo"]
        constraints = [
            models.UniqueConstraint(
                fields=["livro", "content_type", "object_id"],
                name="livro_nao_repete_a_mesma_adaptacao",
            )
        ]

    def __str__(self):
        return f"{self.livro} → {self.adaptacao}"

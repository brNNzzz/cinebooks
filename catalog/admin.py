from django.contrib import admin

from .models import Avaliacao, Filme, Genero, Livro, Pessoa, Serie


@admin.register(Genero)
class GeneroAdmin(admin.ModelAdmin):
    search_fields = ["nome"]


@admin.register(Pessoa)
class PessoaAdmin(admin.ModelAdmin):
    list_display = ["nome", "foto_url"]
    search_fields = ["nome"]


@admin.register(Filme)
class FilmeAdmin(admin.ModelAdmin):
    list_display = [
        "titulo", "ano_lancamento", "diretor", "duracao_minutos",
        "nota_publico", "nota_critica", "dados_completos",
    ]
    list_filter = ["generos", "ano_lancamento", "dados_completos"]
    search_fields = ["titulo", "diretor"]
    filter_horizontal = ["generos", "elenco"]


@admin.register(Serie)
class SerieAdmin(admin.ModelAdmin):
    list_display = [
        "titulo", "ano_lancamento", "criador", "numero_temporadas",
        "nota_publico", "nota_critica", "dados_completos",
    ]
    list_filter = ["generos", "ano_lancamento", "dados_completos"]
    search_fields = ["titulo", "criador"]
    filter_horizontal = ["generos", "elenco"]


@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    list_display = ["titulo", "ano_lancamento", "autor", "editora", "nota_publico", "dados_completos"]
    list_filter = ["generos", "ano_lancamento", "dados_completos"]
    search_fields = ["titulo", "autor"]
    filter_horizontal = ["generos"]
    autocomplete_fields = ["autor_pessoa"]


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ["titulo_avaliado", "usuario", "nota", "criado_em"]
    list_filter = ["nota"]

from django.contrib import admin

from .models import Avaliacao, Filme, Genero, Livro, Serie


@admin.register(Genero)
class GeneroAdmin(admin.ModelAdmin):
    search_fields = ["nome"]


@admin.register(Filme)
class FilmeAdmin(admin.ModelAdmin):
    list_display = ["titulo", "ano_lancamento", "diretor", "duracao_minutos"]
    list_filter = ["generos", "ano_lancamento"]
    search_fields = ["titulo", "diretor"]
    filter_horizontal = ["generos"]


@admin.register(Serie)
class SerieAdmin(admin.ModelAdmin):
    list_display = ["titulo", "ano_lancamento", "criador", "numero_temporadas"]
    list_filter = ["generos", "ano_lancamento"]
    search_fields = ["titulo", "criador"]
    filter_horizontal = ["generos"]


@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    list_display = ["titulo", "ano_lancamento", "autor", "editora"]
    list_filter = ["generos", "ano_lancamento"]
    search_fields = ["titulo", "autor"]
    filter_horizontal = ["generos"]


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ["titulo_avaliado", "usuario", "nota", "criado_em"]
    list_filter = ["nota"]

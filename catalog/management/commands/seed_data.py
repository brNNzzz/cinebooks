"""
Comando de gerenciamento que popula o banco com dados de exemplo.

Uso:
    python manage.py seed_data

Pode rodar quantas vezes quiser: ele usa get_or_create, então não duplica
os registros já existentes.
"""

from django.core.management.base import BaseCommand

from catalog.models import Filme, Genero, Livro, Serie


def poster(texto, cor_fundo="1f2937", cor_texto="ffffff"):
    """Gera uma URL de imagem-placeholder com o título escrito nela."""
    texto_url = texto.replace(" ", "+")
    return f"https://placehold.co/400x600/{cor_fundo}/{cor_texto}?text={texto_url}"


FILMES = [
    dict(
        titulo="A Origem",
        ano_lancamento=2010,
        diretor="Christopher Nolan",
        duracao_minutos=148,
        sinopse="Um ladrão que invade sonhos para roubar segredos recebe a missão inversa: plantar uma ideia.",
        generos=["Ficção Científica", "Ação", "Suspense"],
    ),
    dict(
        titulo="Cidade de Deus",
        ano_lancamento=2002,
        diretor="Fernando Meirelles",
        duracao_minutos=130,
        sinopse="A trajetória de jovens no Rio de Janeiro entre as décadas de 60 e 80, marcada pela violência.",
        generos=["Drama", "Crime"],
    ),
    dict(
        titulo="Parasita",
        ano_lancamento=2019,
        diretor="Bong Joon-ho",
        duracao_minutos=132,
        sinopse="Uma família pobre se infiltra na vida de uma família rica com consequências inesperadas.",
        generos=["Drama", "Suspense", "Comédia"],
    ),
    dict(
        titulo="O Senhor dos Anéis: A Sociedade do Anel",
        ano_lancamento=2001,
        diretor="Peter Jackson",
        duracao_minutos=178,
        sinopse="Um hobbit recebe a missão de destruir um anel capaz de dominar o mundo.",
        generos=["Fantasia", "Aventura"],
    ),
    dict(
        titulo="Vingadores: Ultimato",
        ano_lancamento=2019,
        diretor="Anthony e Joe Russo",
        duracao_minutos=181,
        sinopse="Os heróis remanescentes se unem para reverter os efeitos de Thanos.",
        generos=["Ação", "Ficção Científica"],
    ),
]

SERIES = [
    dict(
        titulo="Breaking Bad",
        ano_lancamento=2008,
        criador="Vince Gilligan",
        numero_temporadas=5,
        sinopse="Um professor de química se torna fabricante de metanfetamina após um diagnóstico de câncer.",
        generos=["Drama", "Crime", "Suspense"],
    ),
    dict(
        titulo="Stranger Things",
        ano_lancamento=2016,
        criador="Irmãos Duffer",
        numero_temporadas=5,
        sinopse="Em uma cidade pequena, crianças enfrentam forças sobrenaturais vindas de uma dimensão paralela.",
        generos=["Ficção Científica", "Terror", "Drama"],
    ),
    dict(
        titulo="Round 6",
        ano_lancamento=2021,
        criador="Hwang Dong-hyuk",
        numero_temporadas=2,
        sinopse="Centenas de pessoas endividadas competem em jogos infantis mortais por um grande prêmio.",
        generos=["Drama", "Suspense"],
    ),
    dict(
        titulo="The Office",
        ano_lancamento=2005,
        criador="Greg Daniels",
        numero_temporadas=9,
        sinopse="O cotidiano cômico de uma equipe de vendas em uma empresa de papel, no formato mockumentary.",
        generos=["Comédia"],
    ),
]

LIVROS = [
    dict(
        titulo="Dom Casmurro",
        ano_lancamento=1899,
        autor="Machado de Assis",
        editora="Diversas",
        numero_paginas=256,
        sinopse="Bentinho narra sua vida e as dúvidas sobre a fidelidade de Capitu.",
        generos=["Romance", "Clássico"],
    ),
    dict(
        titulo="1984",
        ano_lancamento=1949,
        autor="George Orwell",
        editora="Companhia das Letras",
        numero_paginas=416,
        sinopse="Em uma sociedade totalitária vigiada pelo Grande Irmão, Winston Smith questiona o sistema.",
        generos=["Ficção Científica", "Distopia"],
    ),
    dict(
        titulo="Harry Potter e a Pedra Filosofal",
        ano_lancamento=1997,
        autor="J.K. Rowling",
        editora="Rocco",
        numero_paginas=264,
        sinopse="Um garoto órfão descobre ser um bruxo e ingressa na Escola de Hogwarts.",
        generos=["Fantasia", "Aventura"],
    ),
    dict(
        titulo="O Senhor dos Anéis: A Sociedade do Anel",
        ano_lancamento=1954,
        autor="J.R.R. Tolkien",
        editora="HarperCollins",
        numero_paginas=576,
        sinopse="A jornada de Frodo Bolseiro para destruir o Um Anel e derrotar Sauron.",
        generos=["Fantasia", "Aventura"],
    ),
]


class Command(BaseCommand):
    help = "Popula o banco de dados com filmes, séries e livros de exemplo."

    def handle(self, *args, **options):
        total = 0

        for dados in FILMES:
            generos = dados.pop("generos")
            obj, criado = Filme.objects.get_or_create(
                titulo=dados["titulo"], defaults={**dados, "poster_url": poster(dados["titulo"])}
            )
            obj.generos.set([Genero.objects.get_or_create(nome=g)[0] for g in generos])
            total += criado

        for dados in SERIES:
            generos = dados.pop("generos")
            obj, criado = Serie.objects.get_or_create(
                titulo=dados["titulo"], defaults={**dados, "poster_url": poster(dados["titulo"])}
            )
            obj.generos.set([Genero.objects.get_or_create(nome=g)[0] for g in generos])
            total += criado

        for dados in LIVROS:
            generos = dados.pop("generos")
            obj, criado = Livro.objects.get_or_create(
                titulo=dados["titulo"], defaults={**dados, "poster_url": poster(dados["titulo"])}
            )
            obj.generos.set([Genero.objects.get_or_create(nome=g)[0] for g in generos])
            total += criado

        self.stdout.write(self.style.SUCCESS(f"Concluído! {total} novos títulos adicionados."))

"""
Comando de gerenciamento que popula o banco com dados de exemplo.

Uso:
    python manage.py seed_data

Pode rodar quantas vezes quiser: ele usa get_or_create, então não duplica
os registros já existentes.
"""

from django.core.management.base import BaseCommand

from catalog.models import Filme, Genero, Livro, Serie

# Não definimos poster_url aqui de propósito: deixando em branco, o método
# save() de cada modelo (veja catalog/models.py e catalog/capas.py) busca a
# capa real automaticamente (TMDB para filmes/séries, Open Library para
# livros) na hora de criar o registro.


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
    dict(
        titulo="Interestelar",
        ano_lancamento=2014,
        diretor="Christopher Nolan",
        duracao_minutos=169,
        sinopse="Um grupo de astronautas viaja por um buraco de minhoca em busca de um novo lar para a humanidade.",
        generos=["Ficção Científica", "Drama", "Aventura"],
    ),
    dict(
        titulo="Clube da Luta",
        ano_lancamento=1999,
        diretor="David Fincher",
        duracao_minutos=139,
        sinopse="Um homem insone forma um clube de lutas clandestino que sai do controle.",
        generos=["Drama", "Suspense"],
    ),
    dict(
        titulo="Pulp Fiction: Tempo de Violência",
        ano_lancamento=1994,
        diretor="Quentin Tarantino",
        duracao_minutos=154,
        sinopse="Histórias entrelaçadas de crime e redenção em Los Angeles, contadas fora de ordem cronológica.",
        generos=["Crime", "Drama"],
    ),
    dict(
        titulo="O Poderoso Chefão",
        ano_lancamento=1972,
        diretor="Francis Ford Coppola",
        duracao_minutos=175,
        sinopse="A saga da família Corleone e a sucessão do poder dentro de uma organização mafiosa.",
        generos=["Crime", "Drama", "Clássico"],
    ),
    dict(
        titulo="Matrix",
        ano_lancamento=1999,
        diretor="Irmãs Wachowski",
        duracao_minutos=136,
        sinopse="Um programador descobre que a realidade é uma simulação controlada por máquinas.",
        generos=["Ficção Científica", "Ação"],
    ),
    dict(
        titulo="Coringa",
        ano_lancamento=2019,
        diretor="Todd Phillips",
        duracao_minutos=122,
        sinopse="A origem de um comediante fracassado que mergulha na loucura e se transforma em ícone do caos.",
        generos=["Drama", "Crime"],
    ),
    dict(
        titulo="Duna",
        ano_lancamento=2021,
        diretor="Denis Villeneuve",
        duracao_minutos=155,
        sinopse="O herdeiro de uma casa nobre precisa proteger o planeta desértico mais valioso do universo.",
        generos=["Ficção Científica", "Aventura"],
    ),
    dict(
        titulo="Bacurau",
        ano_lancamento=2019,
        diretor="Kleber Mendonça Filho e Juliano Dornelles",
        duracao_minutos=131,
        sinopse="Um vilarejo no sertão brasileiro desaparece do mapa e seus moradores precisam se defender de forasteiros.",
        generos=["Suspense", "Drama"],
    ),
    dict(
        titulo="Tropa de Elite",
        ano_lancamento=2007,
        diretor="José Padilha",
        duracao_minutos=115,
        sinopse="Um capitão do BOPE busca seu substituto enquanto enfrenta o tráfico de drogas no Rio de Janeiro.",
        generos=["Ação", "Crime", "Drama"],
    ),
    dict(
        titulo="Divertida Mente",
        ano_lancamento=2015,
        diretor="Pete Docter",
        duracao_minutos=95,
        sinopse="Dentro da mente de uma garota, cinco emoções disputam o controle de suas reações.",
        generos=["Animação", "Comédia", "Drama"],
    ),
    dict(
        titulo="Whiplash: Em Busca da Perfeição",
        ano_lancamento=2014,
        diretor="Damien Chazelle",
        duracao_minutos=107,
        sinopse="Um baterista talentoso é levado ao limite por um professor implacável em busca da excelência.",
        generos=["Drama"],
    ),
    dict(
        titulo="Titanic",
        ano_lancamento=1997,
        diretor="James Cameron",
        duracao_minutos=195,
        sinopse="Um romance proibido floresce a bordo do navio mais famoso da história, em sua viagem final.",
        generos=["Romance", "Drama"],
    ),
    dict(
        titulo="Gladiador",
        ano_lancamento=2000,
        diretor="Ridley Scott",
        duracao_minutos=155,
        sinopse="Um general romano traído se torna escravo e gladiador em busca de vingança contra o imperador.",
        generos=["Ação", "Drama", "Clássico"],
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
    dict(
        titulo="Game of Thrones",
        ano_lancamento=2011,
        criador="David Benioff e D. B. Weiss",
        numero_temporadas=8,
        sinopse="Casas nobres disputam o Trono de Ferro enquanto uma ameaça sobrenatural se aproxima do norte.",
        generos=["Fantasia", "Drama", "Aventura"],
    ),
    dict(
        titulo="Chernobyl",
        ano_lancamento=2019,
        criador="Craig Mazin",
        numero_temporadas=1,
        sinopse="A reconstrução do desastre nuclear de 1986 e o encobrimento que se seguiu na União Soviética.",
        generos=["Drama", "Suspense"],
    ),
    dict(
        titulo="Dark",
        ano_lancamento=2017,
        criador="Baran bo Odar e Jantje Friese",
        numero_temporadas=3,
        sinopse="O desaparecimento de crianças revela um mistério envolvendo viagem no tempo numa cidade alemã.",
        generos=["Ficção Científica", "Suspense", "Drama"],
    ),
    dict(
        titulo="La Casa de Papel",
        ano_lancamento=2017,
        criador="Álex Pina",
        numero_temporadas=5,
        sinopse="Um grupo de assaltantes planeja o maior roubo da história na Casa da Moeda da Espanha.",
        generos=["Crime", "Suspense", "Drama"],
    ),
    dict(
        titulo="Friends",
        ano_lancamento=1994,
        criador="David Crane e Marta Kauffman",
        numero_temporadas=10,
        sinopse="Seis amigos vivem suas relações e carreiras em Nova York ao longo de uma década.",
        generos=["Comédia", "Romance"],
    ),
    dict(
        titulo="Peaky Blinders",
        ano_lancamento=2013,
        criador="Steven Knight",
        numero_temporadas=6,
        sinopse="Uma família de gângsteres ganha poder e influência na Birmingham do pós-Primeira Guerra.",
        generos=["Crime", "Drama"],
    ),
    dict(
        titulo="Wandinha",
        ano_lancamento=2022,
        criador="Alfred Gough e Miles Millar",
        numero_temporadas=2,
        sinopse="Wandinha Addams investiga uma série de assassinatos enquanto estuda na Academia Nunca Mais.",
        generos=["Comédia", "Suspense", "Fantasia"],
    ),
    dict(
        titulo="Black Mirror",
        ano_lancamento=2011,
        criador="Charlie Brooker",
        numero_temporadas=6,
        sinopse="Episódios independentes exploram os efeitos sombrios da tecnologia na sociedade moderna.",
        generos=["Ficção Científica", "Drama", "Suspense"],
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
    dict(
        titulo="O Pequeno Príncipe",
        ano_lancamento=1943,
        autor="Antoine de Saint-Exupéry",
        editora="Agir",
        numero_paginas=96,
        sinopse="Um aviador perdido no deserto encontra um pequeno príncipe vindo de outro planeta.",
        generos=["Clássico", "Fantasia"],
    ),
    dict(
        titulo="Grande Sertão: Veredas",
        ano_lancamento=1956,
        autor="Guimarães Rosa",
        editora="Nova Fronteira",
        numero_paginas=624,
        sinopse="Riobaldo narra sua vida de jagunço no sertão mineiro e seu amor por Diadorim.",
        generos=["Clássico", "Drama"],
    ),
    dict(
        titulo="A Revolução dos Bichos",
        ano_lancamento=1945,
        autor="George Orwell",
        editora="Companhia das Letras",
        numero_paginas=152,
        sinopse="Animais de uma fazenda expulsam os humanos e criam sua própria sociedade, que aos poucos se corrompe.",
        generos=["Clássico", "Distopia"],
    ),
    dict(
        titulo="O Alquimista",
        ano_lancamento=1988,
        autor="Paulo Coelho",
        editora="Planeta",
        numero_paginas=224,
        sinopse="Um pastor andaluz viaja até as pirâmides do Egito em busca de um tesouro e de sua Lenda Pessoal.",
        generos=["Romance", "Fantasia"],
    ),
    dict(
        titulo="Capitães da Areia",
        ano_lancamento=1937,
        autor="Jorge Amado",
        editora="Companhia das Letras",
        numero_paginas=280,
        sinopse="Um grupo de meninos de rua vive de pequenos furtos nas ruas de Salvador.",
        generos=["Drama", "Clássico"],
    ),
    dict(
        titulo="Cem Anos de Solidão",
        ano_lancamento=1967,
        autor="Gabriel García Márquez",
        editora="Record",
        numero_paginas=448,
        sinopse="A saga de sete gerações da família Buendía na cidade fictícia de Macondo.",
        generos=["Romance", "Clássico"],
    ),
    dict(
        titulo="O Hobbit",
        ano_lancamento=1937,
        autor="J.R.R. Tolkien",
        editora="HarperCollins",
        numero_paginas=336,
        sinopse="O hobbit Bilbo Bolseiro é levado a uma aventura inesperada para recuperar um tesouro guardado por um dragão.",
        generos=["Fantasia", "Aventura"],
    ),
]


class Command(BaseCommand):
    help = "Popula o banco de dados com filmes, séries e livros de exemplo."

    def handle(self, *args, **options):
        total = 0

        for dados in FILMES:
            generos = dados.pop("generos")
            obj, criado = Filme.objects.get_or_create(titulo=dados["titulo"], defaults=dados)
            obj.generos.set([Genero.objects.get_or_create(nome=g)[0] for g in generos])
            total += criado

        for dados in SERIES:
            generos = dados.pop("generos")
            obj, criado = Serie.objects.get_or_create(titulo=dados["titulo"], defaults=dados)
            obj.generos.set([Genero.objects.get_or_create(nome=g)[0] for g in generos])
            total += criado

        for dados in LIVROS:
            generos = dados.pop("generos")
            obj, criado = Livro.objects.get_or_create(titulo=dados["titulo"], defaults=dados)
            obj.generos.set([Genero.objects.get_or_create(nome=g)[0] for g in generos])
            total += criado

        self.stdout.write(self.style.SUCCESS(f"Concluído! {total} novos títulos adicionados."))

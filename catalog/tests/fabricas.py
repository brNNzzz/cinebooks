"""
Funções auxiliares pra criar objetos de teste (filme, série, livro, usuário)
sem repetir os mesmos campos em todo teste. Não é um arquivo de teste em si
(por isso NÃO começa com "test_" — o Django não tentaria rodá-lo sozinho),
é só uma "fábrica" reaproveitada pelos outros arquivos.

IMPORTANTE sobre `poster_url`: os modelos Filme/Serie/Livro tentam buscar
uma capa automaticamente no `save()` quando `poster_url` fica em branco
(ver catalog/models.py e catalog/capas.py). Isso só faz uma chamada de rede
de verdade se a TMDB_API_KEY estiver configurada — o que normalmente NÃO
está no ambiente de teste, então na prática nunca trava os testes. Mesmo
assim, sempre preenchemos `poster_url` aqui por garantia: assim os testes
continuam rápidos e previsíveis mesmo que alguém rode `python manage.py
test` numa máquina com a chave configurada de verdade.
"""

from django.contrib.auth.models import User

from catalog.models import Filme, Livro, Serie

POSTER_FAKE = "https://exemplo.test/poster.jpg"


def criar_filme(titulo="Filme de Teste", ano=2020, **extra):
    extra.setdefault("poster_url", POSTER_FAKE)
    return Filme.objects.create(titulo=titulo, ano_lancamento=ano, **extra)


def criar_serie(titulo="Série de Teste", ano=2020, **extra):
    extra.setdefault("poster_url", POSTER_FAKE)
    return Serie.objects.create(titulo=titulo, ano_lancamento=ano, **extra)


def criar_livro(titulo="Livro de Teste", ano=2020, **extra):
    extra.setdefault("poster_url", POSTER_FAKE)
    return Livro.objects.create(titulo=titulo, ano_lancamento=ano, **extra)


def criar_usuario(username="usuaria_teste", password="senha-forte-123"):
    return User.objects.create_user(username=username, password=password)

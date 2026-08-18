"""
Pré-popula o catálogo com uma leva de filmes/séries POPULARES do TMDB, pra
que o site não pareça vazio logo de cara (antes de qualquer pessoa ter
buscado nada) — sem precisar de um banco de dados gigante tipo o dump
oficial do IMDb (que passa de 1 GB só de texto, bem mais do que cabe no
plano gratuito do Postgres no Render).

COMO FUNCIONA: usa o mesmo "modo rápido" de importação já usado pela busca
pública (ver `views._criar_filme_rapido`/`_criar_serie_rapida`) — só grava
o que já vem pronto na listagem do TMDB (título, ano, pôster, sinopse
curta, gêneros), sem gastar uma chamada extra de API por título. Elenco,
sinopse completa e notas do OMDb continuam sendo completados sozinhos na
primeira vez que alguém abrir a página de cada título (ver
`views._completar_filme`/`_completar_serie`), exatamente como já acontece
pra qualquer título importado pela busca.

Cada título ocupa só uns poucos KB de texto no banco (o pôster fica
hospedado no próprio TMDB — não baixamos nem guardamos a imagem aqui) —
mesmo um catálogo de milhares de títulos fica bem longe do limite de
armazenamento do plano gratuito.

É seguro rodar de novo (idempotente): títulos que já estão no catálogo
(pelo `id_externo` do TMDB) não são reimportados nem duplicados — só os
que ainda faltam entram. Por isso pode ficar direto no build.sh, sem medo
de rodar a cada deploy.

Uso:
    python manage.py popular_catalogo
    python manage.py popular_catalogo --quantidade 500
"""

from django.core.management.base import BaseCommand

from catalog import busca_externa
from catalog.models import Filme, Serie
from catalog.views import _criar_filme_rapido, _criar_serie_rapida

# Do total pedido, quanto vai pra filme vs. série — 65/35 só por ter mais
# filme cadastrado por padrão no catálogo de exemplo (seed_data); não é uma
# regra rígida, é só uma proporção razoável.
FATIA_FILMES = 0.65

# Resultados por página de uma lista do TMDB (fixo, não é configurável pela
# API deles).
RESULTADOS_POR_PAGINA = 20


def _paginas_necessarias(quantidade_alvo):
    """Quantas páginas pedir de CADA lista (populares e bem avaliados) pra
    ter candidatos suficientes mesmo com alguma sobreposição entre as duas
    listas (é comum um filme aparecer nas duas) — por isso o "+1" de folga."""
    return max(1, (quantidade_alvo // RESULTADOS_POR_PAGINA) + 1)


def _combinar_sem_duplicar(*listas):
    """Junta várias listas de resultados do TMDB (ex: populares + bem
    avaliados) descartando duplicatas pelo "id" — o mesmo título pode
    aparecer nas duas listas, e não queremos contar ele duas vezes na hora
    de bater a quantidade pedida."""
    vistos = set()
    combinados = []
    for lista in listas:
        for resultado in lista:
            if resultado["id"] in vistos:
                continue
            vistos.add(resultado["id"])
            combinados.append(resultado)
    return combinados


class Command(BaseCommand):
    help = (
        "Pré-popula o catálogo com títulos populares/bem avaliados do TMDB, "
        "pra o site não parecer vazio antes de alguém buscar algo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--quantidade",
            type=int,
            default=200,
            help="Quantos títulos importar no total, somando filmes e séries (padrão: 200).",
        )

    def handle(self, *args, **options):
        if not busca_externa.tmdb_configurado():
            self.stdout.write(
                self.style.WARNING(
                    "TMDB_API_KEY não está configurada — nada a fazer (esse comando "
                    "depende do TMDB pra saber quais títulos são populares)."
                )
            )
            return

        quantidade_total = max(0, options["quantidade"])
        alvo_filmes = round(quantidade_total * FATIA_FILMES)
        alvo_series = quantidade_total - alvo_filmes

        criados_filmes = self._importar_filmes(alvo_filmes)
        criados_series = self._importar_series(alvo_series)

        total_criados = criados_filmes + criados_series
        if total_criados:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n{total_criados} título(s) novo(s) importado(s) "
                    f"({criados_filmes} filme(s), {criados_series} série(s))."
                )
            )
        else:
            self.stdout.write(
                "\nNenhum título novo importado (provavelmente o catálogo já tinha "
                "todos esses títulos populares de uma execução anterior)."
            )

    def _importar_filmes(self, alvo):
        if alvo <= 0:
            return 0
        paginas = _paginas_necessarias(alvo)
        candidatos = _combinar_sem_duplicar(
            busca_externa.filmes_populares(paginas=paginas),
            busca_externa.filmes_bem_avaliados(paginas=paginas),
        )[:alvo]
        return self._importar(candidatos, _criar_filme_rapido, Filme, "filme")

    def _importar_series(self, alvo):
        if alvo <= 0:
            return 0
        paginas = _paginas_necessarias(alvo)
        candidatos = _combinar_sem_duplicar(
            busca_externa.series_populares(paginas=paginas),
            busca_externa.series_bem_avaliadas(paginas=paginas),
        )[:alvo]
        return self._importar(candidatos, _criar_serie_rapida, Serie, "série")

    def _importar(self, candidatos, funcao_criar, modelo, rotulo):
        """Importa cada candidato usando a função "rápida" já usada pela
        busca pública (só grava o que já veio na listagem, sem chamada
        extra de API por título). Conferimos ANTES de criar se o
        `id_externo` já existe no catálogo — a própria função de criação já
        faz essa checagem por dentro (pra não duplicar), mas ela só devolve
        o objeto final, sem dizer se era novo ou já existia; conferindo por
        fora conseguimos contar certinho quantos títulos são REALMENTE
        novos, pro resumo no final."""
        criados = 0
        for resultado in candidatos:
            id_externo = str(resultado.get("id", ""))
            ja_existia = bool(id_externo) and modelo.objects.filter(id_externo=id_externo).exists()

            objeto = funcao_criar(resultado)
            if objeto is None:
                continue  # resultado sem título/ano válido — a função já ignorou sozinha

            if not ja_existia:
                criados += 1
                self.stdout.write(f"  {rotulo}: {objeto.titulo}")
        return criados

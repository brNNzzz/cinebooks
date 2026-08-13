"""
Atualiza a capa de todos os títulos que ainda não têm uma capa real
(seja porque foram cadastrados antes de configurar a TMDB_API_KEY, seja
porque ainda estão com a imagem placeholder antiga).

Uso:
    python manage.py buscar_capas
"""

from django.core.management.base import BaseCommand

from catalog.capas import buscar_capa_livro, buscar_poster_filme, buscar_poster_serie
from catalog.models import Filme, Livro, Serie


def _sem_capa_real(poster_url):
    return not poster_url or "placehold.co" in poster_url


class Command(BaseCommand):
    help = "Busca e atualiza as capas de filmes, séries e livros que ainda não têm uma capa real."

    def handle(self, *args, **options):
        atualizados = 0

        for filme in Filme.objects.all():
            if _sem_capa_real(filme.poster_url):
                nova = buscar_poster_filme(filme.titulo, filme.ano_lancamento)
                if nova:
                    filme.poster_url = nova
                    filme.save()
                    atualizados += 1
                    self.stdout.write(f"  filme: {filme.titulo}")

        for serie in Serie.objects.all():
            if _sem_capa_real(serie.poster_url):
                nova = buscar_poster_serie(serie.titulo, serie.ano_lancamento)
                if nova:
                    serie.poster_url = nova
                    serie.save()
                    atualizados += 1
                    self.stdout.write(f"  série: {serie.titulo}")

        for livro in Livro.objects.all():
            if _sem_capa_real(livro.poster_url):
                nova = buscar_capa_livro(livro.titulo, livro.autor)
                if nova:
                    livro.poster_url = nova
                    livro.save()
                    atualizados += 1
                    self.stdout.write(f"  livro: {livro.titulo}")

        if atualizados:
            self.stdout.write(self.style.SUCCESS(f"\n{atualizados} capa(s) atualizada(s)."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\nNenhuma capa foi atualizada. Confira se a variável de ambiente "
                    "TMDB_API_KEY está configurada (necessária para filmes e séries) e "
                    "se sua internet está funcionando."
                )
            )

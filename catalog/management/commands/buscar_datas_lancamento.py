"""
Preenche a data EXATA de lançamento (dia/mês/ano) de filmes e séries que já
estão no catálogo mas foram cadastrados antes desse campo existir (ou pela
importação "rápida" da busca, que não faz essa chamada extra à API).

Por quê: sem essa data exata, a regra "só dá pra avaliar títulos já
lançados" cai de volta pra comparação só por ANO — o que deixaria um título
"deste ano" avaliável mesmo que ele só vá lançar daqui a alguns meses. Esse
comando busca a data certinha no TMDB pra quem já tem um `id_externo`
(ou seja, já foi encontrado lá antes), sem precisar re-cadastrar nada.

Livros não entram aqui: o Open Library só informa o ano de publicação, não
o dia — pra livro, a comparação por ano continua sendo o melhor que dá pra
fazer (ver `views._titulo_ja_lancado`).

Uso:
    python manage.py buscar_datas_lancamento
"""

from django.core.management.base import BaseCommand

from catalog import busca_externa
from catalog.models import Filme, Serie


class Command(BaseCommand):
    help = "Busca e preenche a data exata de lançamento de filmes/séries que ainda não têm essa data."

    def handle(self, *args, **options):
        if not busca_externa.tmdb_configurado():
            self.stdout.write(
                self.style.WARNING(
                    "TMDB_API_KEY não está configurada — nada a fazer (filmes e séries "
                    "dependem do TMDB pra essa data)."
                )
            )
            return

        atualizados = 0

        for filme in Filme.objects.filter(data_lancamento__isnull=True).exclude(id_externo=""):
            idioma = filme.idioma_tmdb_conteudo or busca_externa.IDIOMA_TMDB_PADRAO
            info = busca_externa.detalhes_filme(filme.id_externo, idioma=idioma)
            if info and info.get("data_lancamento"):
                filme.data_lancamento = info["data_lancamento"]
                filme.save(update_fields=["data_lancamento"])
                atualizados += 1
                self.stdout.write(f"  filme: {filme.titulo} -> {filme.data_lancamento}")

        for serie in Serie.objects.filter(data_lancamento__isnull=True).exclude(id_externo=""):
            idioma = serie.idioma_tmdb_conteudo or busca_externa.IDIOMA_TMDB_PADRAO
            info = busca_externa.detalhes_serie(serie.id_externo, idioma=idioma)
            if info and info.get("data_lancamento"):
                serie.data_lancamento = info["data_lancamento"]
                serie.save(update_fields=["data_lancamento"])
                atualizados += 1
                self.stdout.write(f"  série: {serie.titulo} -> {serie.data_lancamento}")

        if atualizados:
            self.stdout.write(self.style.SUCCESS(f"\n{atualizados} data(s) de lançamento preenchida(s)."))
        else:
            self.stdout.write("\nNenhuma data de lançamento nova encontrada (ou nada pra atualizar).")

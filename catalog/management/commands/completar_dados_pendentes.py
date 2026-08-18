"""
Completa (sinopse maior, elenco, onde assistir, trailer...) uma leva de
filmes/séries/livros que ainda estão com `dados_completos=False`, direto
durante o deploy — em vez de depender só da thread em segundo plano que
`detalhe()` dispara quando alguém abre a página pela primeira vez.

POR QUE ESSE COMANDO EXISTE: o plano gratuito do Render roda o site com
um único worker do Gunicorn (`WEB_CONCURRENCY=1`, modo `sync`) e pode
suspender/reiniciar o processo por inatividade a qualquer momento. A
thread em segundo plano (`catalog.views._completar_em_segundo_plano`) é
"fire-and-forget": a página responde na hora e a thread continua rodando
sozinha, sem que nada espere ela terminar. Isso é ótimo pra não travar a
navegação, mas na prática, nesse tipo de hospedagem gratuita, significa
que não há NENHUMA garantia de que essa thread realmente chegue a
terminar — se o processo reiniciar (novo deploy, o Render reciclando o
worker, etc.) no meio do caminho, o trabalho se perde silenciosamente e
o título simplesmente continua com `dados_completos=False` pra sempre,
tentando (e falhando) de novo a cada nova visita. Foi exatamente isso que
aconteceu com títulos de exemplo do `seed_data` como "A Origem" e
"Matrix": mesmo sendo visitados várias vezes, nunca ganhavam elenco,
onde assistir nem trailer.

Rodando aqui dentro do `build.sh`, em vez disso, o trabalho acontece de
um jeito totalmente síncrono e sequencial, no mesmo processo que já
sabemos que roda até o fim antes do deploy ser considerado concluído
(as outras etapas do build.sh — migrate, seed_data, popular_catalogo...
— já provam isso, todo deploy). Nada aqui depende de uma requisição HTTP
real nem de uma thread sobrevivendo por conta própria.

Como o catálogo pode ter várias centenas de títulos pendentes de uma vez
(ex: logo depois de rodar `popular_catalogo` pela primeira vez), esse
comando processa só um LIMITE por execução (`--limite`, padrão 60) pra
não arriscar estourar o tempo do build — os que sobrarem são pegos no
próximo deploy, e assim por diante, até não sobrar nenhum. Cada título
processado com sucesso sai da lista de pendentes (`dados_completos` vira
True) e não é tocado de novo por esse comando.

Reaproveita a mesma função (`_garantir_dados_completos`) já usada pela
thread em segundo plano — o resultado final é idêntico ao de uma visita
normal à página, só que com a garantia de rodar até o fim.

Uso:
    python manage.py completar_dados_pendentes
    python manage.py completar_dados_pendentes --limite 150
"""

from django.core.management.base import BaseCommand

from catalog import busca_externa
from catalog.models import Filme, Livro, Serie
from catalog.views import _garantir_dados_completos

MODELOS = (
    (Filme, "filme", "filmes"),
    (Serie, "serie", "séries"),
    (Livro, "livro", "livros"),
)

LIMITE_PADRAO = 60


class Command(BaseCommand):
    help = (
        "Completa (elenco, onde assistir, trailer, sinopse maior...) uma leva de "
        "títulos com dados_completos=False direto no deploy, sem depender da "
        "thread em segundo plano disparada por visitas à página."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limite",
            type=int,
            default=LIMITE_PADRAO,
            help=f"Quantos títulos completar POR TIPO nessa execução (padrão: {LIMITE_PADRAO}).",
        )

    def handle(self, *args, **options):
        if not busca_externa.tmdb_configurado():
            self.stdout.write(
                self.style.WARNING(
                    "TMDB_API_KEY não está configurada — nada a fazer (filmes e "
                    "séries dependem dela; livros seriam completados mesmo assim, "
                    "mas por segurança tratamos os três juntos)."
                )
            )
            return

        limite = max(0, options["limite"])
        total_completados = 0

        for modelo, tipo, rotulo_plural in MODELOS:
            pendentes_total = modelo.objects.filter(dados_completos=False).count()
            lote = list(modelo.objects.filter(dados_completos=False).order_by("pk")[:limite])
            self.stdout.write(
                f"[{rotulo_plural}] pendentes={pendentes_total} "
                f"processando_agora={len(lote)}"
            )
            for item in lote:
                self.stdout.write(f"  completando {tipo}: {item.titulo!r} (pk={item.pk})...")
                _garantir_dados_completos(item, tipo)
                item.refresh_from_db()
                if item.dados_completos:
                    total_completados += 1
                    achou = bool(item.id_externo)
                    self.stdout.write(
                        f"    -> completado ({'achou' if achou else 'sem'} correspondência externa)"
                    )
                else:
                    self.stdout.write(
                        f"    -> ainda não (falha temporária — tenta de novo no próximo deploy)"
                    )
            restantes = modelo.objects.filter(dados_completos=False).count()
            if restantes:
                self.stdout.write(f"  {restantes} {rotulo_plural} pendente(s) restam pro próximo deploy.")

        if total_completados:
            self.stdout.write(self.style.SUCCESS(f"\n{total_completados} título(s) completado(s) nessa rodada."))
        else:
            self.stdout.write("\nNenhum título pendente encontrado (ou nenhum coube no limite dessa rodada).")

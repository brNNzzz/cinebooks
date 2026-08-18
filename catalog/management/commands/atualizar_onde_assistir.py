"""
Atualiza a informação de "onde assistir" (streaming por assinatura, aluguel,
compra) de filmes e séries que já estão no catálogo.

Diferente dos outros comandos de manutenção (`buscar_datas_lancamento`,
`buscar_capas`...), que só preenchem um campo a primeira vez e nunca mais
mexem nele, esse comando busca de novo TODA VEZ que roda, mesmo pra títulos
que já tinham essa informação — porque, ao contrário de uma data de
lançamento (que não muda), a disponibilidade num serviço de streaming muda
com o tempo: um filme pode sair da Netflix e entrar no Prime Video no mês
seguinte, por exemplo. Sem re-buscar, a página ficaria com informação cada
vez mais desatualizada.

Só atualiza quem já tem um `id_externo` (TMDB) — quem ainda não tem precisa
passar primeiro por `_completar_filme`/`_completar_serie` (acontece sozinho
na primeira visita à página de cada título).

Uso:
    python manage.py atualizar_onde_assistir
"""

from django.core.management.base import BaseCommand

from catalog import busca_externa
from catalog.models import Filme, Serie


class Command(BaseCommand):
    help = "Atualiza onde assistir (streaming/aluguel/compra) de filmes e séries já cadastrados."

    def handle(self, *args, **options):
        if not busca_externa.tmdb_configurado():
            self.stdout.write(
                self.style.WARNING(
                    "TMDB_API_KEY não está configurada — nada a fazer (onde assistir "
                    "vem do TMDB/JustWatch)."
                )
            )
            return

        atualizados = 0
        atualizados += self._atualizar(Filme, busca_externa.detalhes_filme, "filme")
        atualizados += self._atualizar(Serie, busca_externa.detalhes_serie, "série")

        if atualizados:
            self.stdout.write(self.style.SUCCESS(f"\n{atualizados} título(s) com onde-assistir atualizado."))
        else:
            self.stdout.write("\nNenhum título pra atualizar (nenhum tem id_externo ainda).")

    def _atualizar(self, modelo, funcao_detalhes, rotulo):
        contador = 0
        for item in modelo.objects.exclude(id_externo=""):
            idioma = item.idioma_tmdb_conteudo or busca_externa.IDIOMA_TMDB_PADRAO
            info = funcao_detalhes(item.id_externo, idioma=idioma)
            if info is None:
                continue  # falha temporária (rede/API) — tenta de novo na próxima rodada
            novo = info.get("onde_assistir") or {}
            if novo != item.onde_assistir:
                item.onde_assistir = novo
                item.save(update_fields=["onde_assistir"])
                contador += 1
                self.stdout.write(f"  {rotulo}: {item.titulo}")
        return contador

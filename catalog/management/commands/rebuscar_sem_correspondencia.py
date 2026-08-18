"""
Tenta de novo encontrar no TMDB os filmes/séries que ficaram "travados" sem
nenhuma correspondência — ou seja, `dados_completos=True` (não tenta mais
sozinho a cada visita) mas `id_externo=""` (nunca achou o título de
verdade na API).

Por que isso acontece: `_completar_filme`/`_completar_serie` só tentam a
busca por texto no TMDB UMA VEZ (na primeira vez que alguém abre a página
daquele título). Se essa tentativa falhar — por exemplo, a TMDB_API_KEY
ainda não estava configurada no Render nesse momento, ou foi só uma falha
passageira de rede — o título fica marcado como "completo" mesmo sem
achar nada, pra não ficar tentando de novo (e mais lento) a cada visita.
O problema é que isso é PERMANENTE: mesmo depois de configurar a chave
certinha, esses títulos continuavam travados pra sempre, sem elenco, sem
onde assistir, sem trailer — só com os dados manuais que já tinham (ex: os
títulos de exemplo do `seed_data`).

Esse comando destrava esses casos: reseta `dados_completos` pra False só
neles (sem tocar em quem já está com tudo certo) e chama de novo a mesma
função de sempre (`_completar_filme`/`_completar_serie`) — se a API
encontrar o título dessa vez, tudo (elenco, sinopse maior, onde assistir,
trailer...) é preenchido de uma vez, igual uma primeira visita normal. Se
falhar de novo, volta a ficar marcado como completo, sem loop infinito.

Seguro rodar em todo deploy (idempotente): depois que um título é
encontrado com sucesso, ele sai do filtro "sem correspondência" e não é
mais tocado por esse comando.

Uso:
    python manage.py rebuscar_sem_correspondencia
"""

from django.core.management.base import BaseCommand

from catalog import busca_externa
from catalog.models import Filme, Serie
from catalog.views import _completar_filme, _completar_serie


class Command(BaseCommand):
    help = "Tenta de novo encontrar no TMDB os títulos que ficaram sem correspondência (id_externo vazio)."

    def handle(self, *args, **options):
        if not busca_externa.tmdb_configurado():
            self.stdout.write(
                self.style.WARNING("TMDB_API_KEY não está configurada — nada a fazer.")
            )
            return

        # Resumo geral primeiro — ajuda a diagnosticar por telas (o Render
        # gratuito não tem shell interativo pra consultar o banco direto):
        # quantos títulos existem, quantos nunca foram sequer visitados
        # (dados_completos=False — resolvem sozinhos na próxima visita) e
        # quantos estão de fato "travados" (o caso que esse comando trata).
        for modelo, rotulo_plural in ((Filme, "filmes"), (Serie, "séries")):
            total = modelo.objects.count()
            nunca_visitados = modelo.objects.filter(dados_completos=False).count()
            travados = modelo.objects.filter(dados_completos=True, id_externo="").count()
            self.stdout.write(
                f"[resumo {rotulo_plural}] total={total} nunca_visitados={nunca_visitados} travados={travados}"
            )

        encontrados_f, ainda_sem_f = self._tentar(Filme, _completar_filme, "filme")
        encontrados_s, ainda_sem_s = self._tentar(Serie, _completar_serie, "série")
        encontrados = encontrados_f + encontrados_s
        ainda_sem = ainda_sem_f + ainda_sem_s

        if encontrados:
            self.stdout.write(self.style.SUCCESS(f"\n{encontrados} título(s) encontrado(s) e completado(s) agora."))
        else:
            self.stdout.write("\nNenhum título novo encontrado nessa rodada.")
        if ainda_sem:
            self.stdout.write(f"{ainda_sem} título(s) continuam sem correspondência no TMDB (tenta de novo no próximo deploy).")

    def _tentar(self, modelo, funcao_completar, rotulo):
        travados = modelo.objects.filter(dados_completos=True, id_externo="")
        encontrados = 0
        ainda_sem = 0
        for item in travados:
            # Log de CADA tentativa (não só das que dão certo) — sem isso não
            # dava pra saber, só pelo log do deploy, se um título específico
            # (ex: "A Origem") sequer chegou a ser tentado, ou se foi
            # tentado e a busca não achou nada.
            self.stdout.write(
                f"  tentando {rotulo}: {item.titulo!r} "
                f"(ano={item.ano_lancamento}, idioma={item.idioma_tmdb_conteudo!r})..."
            )
            item.dados_completos = False
            item.save(update_fields=["dados_completos"])
            try:
                funcao_completar(item)
            except Exception:
                self.stdout.write(self.style.ERROR(f"    -> ERRO ao tentar completar {item.titulo!r}"))
                raise
            item.refresh_from_db()
            if item.id_externo:
                encontrados += 1
                self.stdout.write(f"    -> encontrado (id_externo={item.id_externo})")
            else:
                ainda_sem += 1
                self.stdout.write(f"    -> NÃO encontrado")
        return encontrados, ainda_sem

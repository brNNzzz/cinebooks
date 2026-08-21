"""
Descarta entradas ANTIGAS do cache de traduções (campo `traducoes`) de
filmes e séries, deixando pra buscar de novo (já corrigido) na próxima vez
que o título for visto.

Por quê: até uma correção recente, quando o TMDB não tinha a sinopse de um
título num idioma (comum em títulos menos conhecidos/mais novos), o site
guardava a sinopse ORIGINAL no cache mesmo assim — o que podia deixar, por
exemplo, um título com nome em francês e sinopse em inglês, mesmo com o
site em português. A correção faz a sinopse ficar em branco (mostrando
"sem sinopse disponível") quando o TMDB não tem tradução, em vez de mostrar
um parágrafo inteiro noutra língua — mas isso só vale pra traduções NOVAS;
as que já estavam salvas do jeito antigo continuariam erradas pra sempre
sem esse comando.

Uma segunda correção (versão 3) resolveu um bug parecido, dessa vez com o
PÔSTER por idioma: entradas salvas ANTES do pôster/trailer por idioma
existirem (mesmo já "v": 2) não tinham essas chaves — e como
`_texto_no_idioma`/`_traduzir_varios` (em views.py) só disparam uma busca
nova quando NÃO existe cache pra aquele idioma (não quando o cache existe
mas está incompleto), esses títulos ficavam pra sempre com o pôster de
fallback mesmo quando o TMDB tinha uma capa própria pra aquele idioma —
mais perceptível em idiomas "grandes" (zh, hi, ar, bn, ur...) vistos cedo
durante o desenvolvimento.

Cada entrada nova do cache carrega uma marca "v" (versão corrigida — ver
VERSAO_ATUAL abaixo). Esse comando só mexe nos títulos que ainda têm
entradas com uma marca mais antiga (ou nenhuma marca) — ou seja, depois da
limpeza ele não encontra mais nada pra fazer pra essa versão, mesmo rodando
de novo a cada deploy (é por isso que pode ficar direto no build.sh, junto
com buscar_capas, sem desperdiçar tempo nos deploys seguintes) — até a
próxima correção que precisar de outra limpeza (bastando subir
VERSAO_ATUAL de novo).

Uso:
    python manage.py limpar_cache_traducoes
"""

from django.core.management.base import BaseCommand

from catalog.models import Filme, Serie

VERSAO_ATUAL = 3


class Command(BaseCommand):
    help = "Descarta entradas antigas do cache de traduções de filmes e séries (força buscar de novo, já corrigido)."

    def handle(self, *args, **options):
        total = 0
        for model in (Filme, Serie):
            for item in model.objects.exclude(traducoes={}):
                traducoes = item.traducoes or {}
                desatualizado = any(
                    not isinstance(valor, dict) or valor.get("v") != VERSAO_ATUAL
                    for valor in traducoes.values()
                )
                if desatualizado:
                    item.traducoes = {}
                    item.save(update_fields=["traducoes"])
                    total += 1
        if total:
            self.stdout.write(self.style.SUCCESS(f"Cache de traduções desatualizado limpo em {total} título(s)."))
        else:
            self.stdout.write("Nenhum cache de tradução desatualizado encontrado.")

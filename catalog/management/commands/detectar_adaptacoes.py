"""
Varre o catálogo inteiro comparando cada Livro com cada Filme/Série já
cadastrados, criando um vínculo `Adaptacao` (ver catalog/models.py) pra
cada correspondência que o algoritmo automático (catalog/adaptacoes.py,
`detectar_todas_adaptacoes`) considerar forte o bastante.

Por quê precisa desse comando, além da detecção automática já disparada
sempre que um título novo é importado (ver `views._criar_*`): aquela
detecção automática só cobre título NOVO entrando no catálogo dali pra
frente — não acha vínculos entre títulos que JÁ estavam cadastrados antes
dessa funcionalidade existir. Rodar esse comando uma vez (ex: no
build.sh, junto com os outros comandos de manutenção) resolve isso pro
catálogo já existente.

É seguro rodar de novo a qualquer momento: `Adaptacao.objects.get_or_create`
(usado internamente) nunca duplica um vínculo já existente.

Uso:
    python manage.py detectar_adaptacoes
"""

from django.core.management.base import BaseCommand

from catalog.adaptacoes import detectar_todas_adaptacoes


class Command(BaseCommand):
    help = "Detecta automaticamente vínculos livro↔filme/série (adaptações) no catálogo inteiro."

    def handle(self, *args, **options):
        total = detectar_todas_adaptacoes()
        if total:
            self.stdout.write(self.style.SUCCESS(f"{total} vínculo(s) de adaptação detectado(s)/confirmado(s)."))
        else:
            self.stdout.write("Nenhuma adaptação nova detectada.")

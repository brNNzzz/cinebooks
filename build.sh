#!/usr/bin/env bash
# Script executado pelo Render a cada deploy: instala dependências, junta os
# arquivos estáticos, aplica as migrações do banco de dados e prepara o
# conteúdo inicial. Feito para funcionar 100% pelo painel do Render, sem
# precisar da aba Shell (que é só para planos pagos).
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Popula o banco com os títulos de exemplo (seguro rodar toda vez, não duplica).
python manage.py seed_data

# Busca as capas reais (TMDB + Open Library). Se TMDB_API_KEY não estiver
# configurada ainda, essa etapa simplesmente não encontra nada e segue sem
# travar o deploy — por isso o "|| true" no final.
python manage.py buscar_capas || true

# Cria o usuário administrador automaticamente, usando as variáveis de
# ambiente DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD, se elas estiverem
# configuradas no painel do Render. Se o usuário já existir, o comando dá
# erro (usuário duplicado) — o "|| true" evita que isso quebre o deploy.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
    python manage.py createsuperuser --noinput || true
fi

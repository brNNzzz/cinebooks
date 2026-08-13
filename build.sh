#!/usr/bin/env bash
# Script executado pelo Render a cada deploy: instala dependências, junta os
# arquivos estáticos e aplica as migrações do banco de dados.
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Popula o banco com os títulos de exemplo (seguro rodar toda vez, não duplica).
python manage.py seed_data

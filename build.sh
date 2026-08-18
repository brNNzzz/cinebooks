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

# Pré-popula o catálogo com filmes/séries populares do TMDB (~200 títulos),
# pra o site não parecer vazio antes de alguém buscar algo — sem precisar
# de um banco gigante tipo o dump do IMDb (que não caberia no plano
# gratuito). Idempotente (não duplica em deploys seguintes) e, sem
# TMDB_API_KEY configurada, só avisa e segue sem travar (por isso "|| true").
python manage.py popular_catalogo || true

# Busca as capas reais (TMDB + Open Library). Se TMDB_API_KEY não estiver
# configurada ainda, essa etapa simplesmente não encontra nada e segue sem
# travar o deploy — por isso o "|| true" no final.
python manage.py buscar_capas || true

# Tenta de novo achar no TMDB os títulos que ficaram "travados" sem
# correspondência (normalmente porque a primeira tentativa aconteceu antes
# da TMDB_API_KEY estar configurada) — sem isso, esses títulos nunca
# ganhariam elenco, onde assistir ou trailer, mesmo depois de configurar a
# chave certinha. Seguro rodar toda vez (idempotente).
python manage.py rebuscar_sem_correspondencia || true

# Completa (elenco, onde assistir, trailer, sinopse maior...) uma leva de
# títulos que ainda nunca foram abertos por ninguém (dados_completos=False)
# — normalmente títulos trazidos pelo popular_catalogo, que só grava o
# básico de propósito. Isso já aconteceria sozinho na primeira visita à
# página (via thread em segundo plano), mas no plano gratuito do Render o
# processo pode reiniciar a qualquer momento e derrubar essa thread no meio
# do caminho, deixando o título travado sem nunca completar. Fazendo aqui,
# de forma síncrona dentro do próprio deploy, isso não depende de visita
# nenhuma. Processa só um lote por vez (--limite, padrão 60) pra não
# estourar o tempo do build; o que sobrar é pego no deploy seguinte.
python manage.py completar_dados_pendentes || true

# Descarta cache de tradução salvo com o bug antigo (sinopse aparecendo
# numa língua diferente da escolhida no site). Só mexe em quem ainda está
# desatualizado, então não desperdiça tempo nos deploys seguintes.
python manage.py limpar_cache_traducoes || true

# Preenche a data exata de lançamento (dia/mês/ano) de filmes/séries
# cadastrados antes desse campo existir — necessário pra regra "só avalia
# quem já lançou" funcionar com precisão de dia, não só de ano. Sem
# TMDB_API_KEY configurada, não faz nada e segue o deploy (por isso o
# "|| true"); já preenchidos, não busca de novo.
python manage.py buscar_datas_lancamento || true

# Atualiza onde assistir (streaming/aluguel/compra) de filmes/séries já
# cadastrados — ao contrário dos comandos acima, roda de novo TODA VEZ
# (a disponibilidade num serviço de streaming muda com o tempo, então não
# basta buscar uma vez só). Sem TMDB_API_KEY, não faz nada e segue o deploy.
python manage.py atualizar_onde_assistir || true

# Cria o usuário administrador automaticamente, usando as variáveis de
# ambiente DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD, se elas estiverem
# configuradas no painel do Render. Se o usuário já existir, o comando dá
# erro (usuário duplicado) — o "|| true" evita que isso quebre o deploy.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
    python manage.py createsuperuser --noinput || true
fi

# Como subir o projeto no GitHub e publicar na internet

Este guia assume que você nunca usou Git/GitHub nem publicou um site antes. Siga na ordem.

## Parte 1 — Criar conta no GitHub

1. Acesse **https://github.com/signup** e crie sua conta (usuário, e-mail, senha).
2. Confirme o e-mail que o GitHub vai te enviar.

## Parte 2 — Instalar o Git no seu computador

Abra um terminal e digite `git --version`. Se aparecer um número de versão, já está
instalado e você pode pular para a Parte 3. Se der erro:

- **Windows:** baixe em https://git-scm.com/download/win e instale (pode deixar tudo
  no padrão durante a instalação).
- **Mac:** abra o Terminal e digite `git --version` — o próprio macOS vai oferecer
  para instalar as "Ferramentas de Linha de Comando", aceite.
- **Linux:** `sudo apt install git` (Ubuntu/Debian) ou equivalente da sua distro.

Depois, configure seu nome e e-mail (só precisa fazer uma vez):

```bash
git config --global user.name "Seu Nome"
git config --global user.email "seu-email@exemplo.com"
```

## Parte 3 — Criar o repositório no GitHub

1. No site do GitHub, clique no **+** no canto superior direito → **New repository**.
2. Dê um nome, por exemplo `cinebooks`.
3. Deixe como **Public** (para o professor poder acessar) ou **Private** se preferir.
4. **Não marque** nenhuma opção de criar README, .gitignore ou licença — nosso projeto
   já tem esses arquivos.
5. Clique em **Create repository**. O GitHub vai te mostrar uma URL parecida com
   `https://github.com/seu-usuario/cinebooks.git` — copie ela, você vai usar já já.

## Parte 4 — Subir o projeto

No terminal, entre na pasta do projeto (a que você extraiu do zip) e rode:

```bash
cd imdb_faculdade
git init
git add .
git commit -m "Primeira versão do CineBooks"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/cinebooks.git
git push -u origin main
```

Na primeira vez, o Git vai pedir login — use seu usuário do GitHub e, no lugar da
senha, um **Personal Access Token** (o GitHub não aceita mais senha normal por linha
de comando). Para gerar um token:

1. No GitHub, vá em **Settings** (clicando na sua foto) → **Developer settings** →
   **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**.
2. Marque a permissão `repo`, gere o token e **copie ele** (só aparece uma vez).
3. Use esse token como "senha" quando o terminal pedir.

Pronto — atualize a página do seu repositório no GitHub e os arquivos vão estar lá.

Sempre que fizer alterações no projeto depois, para atualizar o GitHub:

```bash
git add .
git commit -m "descreva o que mudou"
git push
```

## Parte 5 — Publicar o site na internet (link público)

Uso o **Render** aqui: é bem mais visual (sem digitar comando em console), e a cada
`git push` ele republica o site sozinho. O projeto já vem pronto para isso — inclui um
arquivo `render.yaml` que descreve tudo (o site + um banco de dados PostgreSQL
gratuito), então o Render cria os dois de uma vez só, com um clique.

> **Por que trocamos o banco de SQLite para PostgreSQL nessa opção:** no plano
> gratuito do Render, os arquivos do site (incluindo um banco SQLite) são apagados
> toda vez que o site "dorme" por inatividade (a cada ~15 min sem acesso). Um banco
> PostgreSQL separado não tem esse problema. A única pegadinha: o Postgres gratuito do
> Render expira 30 dias após criado (dá pra recriar de graça depois, veja o aviso no
> fim desta seção).
>
> Se preferir um site que nunca "dorme" e não se importa em mexer num console de
> comandos, o **PythonAnywhere** continua sendo uma alternativa válida — o passo a
> passo dele está mais abaixo, na Parte 6.

### Passo a passo no Render

1. Acesse **https://render.com** e crie uma conta (pode entrar direto com sua conta
   do GitHub, fica mais rápido — clique em **Get Started** e depois **GitHub**).
2. Autorize o Render a acessar seus repositórios (pode escolher "apenas este
   repositório", não precisa dar acesso a todos).
3. No painel do Render, clique em **New +** → **Blueprint**.
4. Selecione o repositório do projeto (ex: `imdpringols`). O Render vai detectar
   automaticamente o arquivo `render.yaml` e mostrar o que vai criar: um **Web
   Service** chamado `cinebooks` e um banco **PostgreSQL** chamado `cinebooks-db`,
   ambos no plano Free.
5. Clique em **Apply** (ou **Create New Resources**, dependendo da versão da tela).
6. Aguarde o build — na primeira vez demora uns 3 a 5 minutos. Você pode acompanhar
   o progresso ao vivo na aba **Logs** do serviço `cinebooks`.
7. Quando o deploy terminar, o Render mostra a URL do site no topo da página, algo
   como `https://cinebooks.onrender.com` — é só clicar para abrir.

> **Nota:** a aba **Shell** do Render (um terminal dentro do navegador) só existe nos
> planos pagos. Por isso, tanto a criação do administrador quanto a busca de capas
> abaixo são feitas por variáveis de ambiente + o script `build.sh`, que já roda
> sozinho a cada deploy — sem precisar de nenhum terminal.

### Criar seu usuário administrador no site publicado

1. No painel do Render, abra o serviço **cinebooks** → aba **Environment**.
2. Clique em **Edit** e preencha as três variáveis que já estão reservadas ali
   (o `render.yaml` já deixou elas criadas, só faltando o valor):
   - `DJANGO_SUPERUSER_USERNAME` → o nome de usuário que você quer usar
   - `DJANGO_SUPERUSER_EMAIL` → qualquer e-mail (pode ser fictício)
   - `DJANGO_SUPERUSER_PASSWORD` → uma senha sua, forte
3. Clique em **Save Changes**. Isso já dispara um novo deploy sozinho — o `build.sh`
   vai criar esse usuário automaticamente durante o build (streaming de progresso na
   aba **Logs**, se quiser acompanhar).
4. Quando o deploy terminar, entre em `https://cinebooks.onrender.com/admin/` com
   esse usuário e senha.

### Ativar as capas reais de filmes e séries (TMDB)

O `render.yaml` já deixa uma variável `TMDB_API_KEY` reservada, mas vazia — o Render
não preenche ela sozinho por segurança. Depois de criar sua chave gratuita (passo a
passo no `README.md`, seção "Capas automáticas"):

1. Na mesma aba **Environment**, clique em **Edit**.
2. Encontre `TMDB_API_KEY` e cole o valor da sua chave (ou token).
3. Clique em **Save Changes** — isso dispara um novo deploy sozinho, e o `build.sh`
   já roda o `buscar_capas` automaticamente nesse processo, atualizando o catálogo
   de exemplo com as capas reais.

As capas dos livros já funcionam sem precisar de nada disso (Open Library não exige
chave) — elas são buscadas assim que os livros são cadastrados.

### Atualizando o site depois de mudanças

Diferente do PythonAnywhere, aqui é automático: sempre que você rodar `git push`,
o Render detecta e já republica o site sozinho em alguns minutos. Não precisa fazer
mais nada.

### Sobre o banco de dados gratuito expirar em 30 dias

O Render avisa por e-mail antes de expirar. Quando isso acontecer, basta criar um
novo banco Postgres gratuito no painel (**New +** → **PostgreSQL**) e atualizar a
variável de ambiente `DATABASE_URL` do serviço `cinebooks` (aba **Environment**) para
apontar pro novo banco — só que, como o banco muda, os cadastros/avaliações feitos
pelos usuários até ali seriam perdidos (o catálogo de exemplo volta sozinho, pois é
recriado no próximo deploy). Para uma apresentação de trabalho, isso raramente chega
a ser um problema dentro do prazo de 30 dias.

## Parte 6 — Alternativa: PythonAnywhere (site nunca dorme, mas configuração manual)

1. Crie uma conta grátis em **https://www.pythonanywhere.com** (plano "Beginner").
2. No painel, abra um **Bash console** (aba Consoles → Bash).
3. Clone o projeto do GitHub:
   ```bash
   git clone https://github.com/SEU-USUARIO/cinebooks.git
   cd cinebooks
   ```
4. Crie um ambiente virtual e instale as dependências:
   ```bash
   python3.10 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
5. Prepare o banco e os arquivos estáticos:
   ```bash
   python manage.py migrate
   python manage.py seed_data
   python manage.py createsuperuser
   python manage.py collectstatic
   ```
   Se você já configurou a `TMDB_API_KEY` (defina com `export TMDB_API_KEY=sua-chave`
   antes desses comandos), pode rodar também `python manage.py buscar_capas` para
   garantir que todos os títulos fiquem com capa real.
6. Vá na aba **Web** → **Add a new web app** → escolha seu domínio gratuito
   (`seu-usuario.pythonanywhere.com`) → **Manual configuration** → selecione a
   versão do Python que você usou no passo 4 (ex: 3.10).
7. Na página de configuração da Web app, ajuste:
   - **Source code:** `/home/seu-usuario/cinebooks`
   - **Virtualenv:** `/home/seu-usuario/cinebooks/venv`
   - **WSGI configuration file:** clique para abrir e edite pra ficar assim
     (troque `seu-usuario` pelo seu usuário real):
     ```python
     import os
     import sys

     path = '/home/seu-usuario/cinebooks'
     if path not in sys.path:
         sys.path.insert(0, path)

     os.environ['DJANGO_ALLOWED_HOSTS'] = 'seu-usuario.pythonanywhere.com'
     os.environ['DJANGO_DEBUG'] = 'False'
     os.environ['TMDB_API_KEY'] = 'sua-chave-do-tmdb-aqui'  # opcional, ver README
     os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cinebooks.settings')

     from django.core.wsgi import get_wsgi_application
     application = get_wsgi_application()
     ```
   - Na seção **Static files**, adicione uma entrada: URL `/static/` apontando pro
     caminho `/home/seu-usuario/cinebooks/staticfiles`.
8. Clique no botão verde **Reload** no topo da página.
9. Acesse `https://seu-usuario.pythonanywhere.com` — o site estará no ar!

### Atualizando o site depois de mudanças

Sempre que você der `git push` no seu computador, o PythonAnywhere **não** atualiza
sozinho (diferente do Render). Você precisa entrar no Bash console de novo e rodar:

```bash
cd cinebooks
git pull
source venv/bin/activate
pip install -r requirements.txt   # só se tiver mudado dependências
python manage.py migrate           # só se tiver mudado o modelo de dados
python manage.py collectstatic --noinput
```

E depois clicar em **Reload** na aba Web.

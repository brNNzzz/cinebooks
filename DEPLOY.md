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

Recomendo o **PythonAnywhere**, porque o plano gratuito não "dorme" (fica sempre no
ar) e funciona muito bem com o banco SQLite que já vem no projeto — não precisa
configurar nenhum banco de dados separado. É o caminho mais simples para um projeto
de faculdade.

> Alternativa: o **Render** também tem plano gratuito e faz deploy automático a cada
> `git push`, mas o site "dorme" depois de 15 minutos sem acesso (demora ~1 minuto pra
> acordar de novo) e exigiria trocar o banco para PostgreSQL, que no plano grátis
> expira depois de 30 dias. Fica de opção se você preferir deploy automático e não se
> importar com esses limites.

### Passo a passo no PythonAnywhere

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

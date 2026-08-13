# CineBooks — catálogo de filmes, séries e livros

Projeto acadêmico feito em **Django** (Python). Funciona como uma versão simplificada
do IMDB, mas cobrindo três tipos de conteúdo: filmes, séries e livros. Usuários podem
navegar pelo catálogo, buscar títulos, criar conta e avaliar (nota de 1 a 5 + comentário).

## Tecnologias usadas

- **Python 3 + Django 5** — framework web que cuida do banco de dados, autenticação de
  usuários e roteamento de páginas.
- **SQLite** — banco de dados que é só um arquivo (`db.sqlite3`), não precisa instalar
  nem configurar servidor nenhum.
- **Bootstrap 5** (via CDN) — deixa o site com visual decente sem escrever CSS do zero.

## Como rodar o projeto (passo a passo)

Pré-requisito: ter Python 3.10+ instalado (`python3 --version` no terminal pra
conferir).

```bash
# 1. Entre na pasta do projeto
cd imdb_faculdade

# 2. (Recomendado) crie um ambiente virtual, pra não misturar com outros projetos Python
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Crie as tabelas do banco de dados
python3 manage.py migrate

# 5. Popule o banco com filmes, séries e livros de exemplo
python3 manage.py seed_data

# 6. Crie seu próprio usuário administrador (opcional, já existe um de teste — veja abaixo)
python3 manage.py createsuperuser

# 7. Rode o servidor
python3 manage.py runserver
```

Depois disso, acesse **http://127.0.0.1:8000/** no navegador.

### Login de administrador já criado

Um usuário admin já vem configurado no banco de dados enviado, pra vocês acessarem o
painel administrativo (`/admin/`) sem precisar criar um do zero:

- **usuário:** `admin`
- **senha:** `admin1234`

Recomendo trocar essa senha (ou criar a de vocês com `createsuperuser`) antes de
apresentar o trabalho.

## Capas automáticas (pôsteres reais de filmes, séries e livros)

O site busca a capa de cada título automaticamente quando ele é cadastrado (seja pelo
`seed_data`, seja pelo admin), sem precisar colar nenhum link manualmente:

- **Livros:** usa a API do **Open Library**, que é gratuita e não precisa de nenhuma
  chave — já funciona sem fazer nada.
- **Filmes e séries:** usa a API do **TMDB** (The Movie Database), que também é
  gratuita, mas exige criar uma chave própria (rapidinho, sem cartão de crédito):

  1. Crie uma conta em **https://www.themoviedb.org/signup**.
  2. Confirme o e-mail.
  3. Vá em **Configurações** (clique no seu avatar) → **API** → **Create** →
     escolha "Developer" → preencha o formulário curto (pode colocar "projeto
     acadêmico" como finalidade) → aceite os termos.
  4. Copie o valor de **"API Key (v3 auth)"**.
  5. Configure essa chave como variável de ambiente chamada `TMDB_API_KEY` antes de
     rodar o projeto:
     ```bash
     # Windows (cmd)
     set TMDB_API_KEY=sua-chave-aqui

     # Windows (PowerShell)
     $env:TMDB_API_KEY="sua-chave-aqui"

     # Mac/Linux
     export TMDB_API_KEY=sua-chave-aqui
     ```
     (isso vale só para a sessão atual do terminal — se fechar e abrir de novo,
     precisa configurar de novo, ou rodar o `set`/`export` sempre antes do
     `python manage.py runserver`)

Se o banco já tiver títulos sem capa (por exemplo, o `db.sqlite3` que já vem neste
projeto), rode para buscar as capas que faltam:

```bash
python manage.py buscar_capas
```

Se a `TMDB_API_KEY` não estiver configurada, os filmes/séries simplesmente continuam
sem capa real (o site mostra uma imagem padrão no lugar) — nada quebra.

## Estrutura do projeto

```
imdb_faculdade/
├── cinebooks/          → configurações gerais do Django (settings, urls principais)
├── catalog/             → o "app" principal com toda a lógica do catálogo
│   ├── models.py         → definição das tabelas do banco (Filme, Serie, Livro, Avaliacao...)
│   ├── views.py          → lógica de cada página (o que buscar no banco, o que exibir)
│   ├── urls.py           → mapeamento de endereços (ex: /filme/3/) para as views
│   ├── forms.py          → formulários (avaliação e cadastro de usuário)
│   ├── admin.py          → configuração do painel /admin/
│   └── management/commands/seed_data.py → comando que popula o banco com exemplos
├── templates/            → arquivos HTML (o que o usuário vê)
├── static/catalog/       → CSS customizado
├── requirements.txt      → lista de pacotes Python necessários
└── manage.py             → comando usado para rodar o Django (migrate, runserver, etc.)
```

## Como o modelo de dados foi pensado

Filme, Série e Livro compartilham vários campos (título, sinopse, ano, pôster, gêneros).
Para não repetir esse código três vezes, existe uma classe `Titulo` que **não vira
tabela no banco** — ela só serve de "molde" para as outras três classes herdarem os
campos comuns. Isso é um conceito de Orientação a Objetos (herança) aplicado ao Django.

Para as avaliações, em vez de criar três tabelas separadas (`AvaliacaoFilme`,
`AvaliacaoSerie`, `AvaliacaoLivro`), usamos um recurso do Django chamado **Generic
Foreign Key**: uma única tabela `Avaliacao` guarda o tipo do título avaliado
(filme/série/livro) e o ID dele, permitindo que uma avaliação aponte para qualquer um
dos três. Isso evita duplicação de código nas views e no template.

## Funcionalidades implementadas

- Listagem de filmes, séries e livros, com busca por título e filtro por gênero.
- Página de detalhe de cada título, com sinopse, ficha técnica e avaliações.
- Cadastro de conta e login/logout.
- Avaliação (nota de 1 a 5 + comentário opcional) — cada usuário pode avaliar um mesmo
  título só uma vez (e pode editar a nota depois).
- Cálculo automático da nota média de cada título.
- Busca global (filmes + séries + livros de uma vez).
- Painel administrativo (`/admin/`) para cadastrar/editar títulos com formulário pronto,
  sem precisar escrever HTML.

## Possíveis melhorias (caso o professor pergunte "o que mais dava pra fazer")

- Upload de imagem de pôster em vez de link (usando `ImageField`).
- Paginação nas listagens (hoje mostra tudo de uma vez).
- API REST (com Django REST Framework) para consumir os dados de um app mobile, por exemplo.
- Sistema de "favoritos"/lista para assistir depois.
- Deploy em produção (ex: Render, Railway ou PythonAnywhere) com PostgreSQL no lugar do SQLite.

## Subir no GitHub e publicar na internet

Veja o arquivo **`DEPLOY.md`** nesta mesma pasta — tem o passo a passo completo,
desde criar conta no GitHub até deixar o site com um link público na internet.

## Repopular o banco do zero

Se quiser apagar tudo e recomeçar:

```bash
rm db.sqlite3
python3 manage.py migrate
python3 manage.py seed_data
python3 manage.py createsuperuser
```

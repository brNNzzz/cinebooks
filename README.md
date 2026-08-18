# CineBooks

Catálogo de filmes, séries e livros com avaliações da comunidade, inspirado no IMDb — construído em **Django** como projeto acadêmico.

**Site no ar:** https://cinebooks.onrender.com/

## Sobre o projeto

O CineBooks reúne três tipos de conteúdo — filmes, séries e livros — num catálogo único, onde qualquer pessoa pode navegar e pesquisar, e usuários cadastrados podem avaliar (nota de 1 a 5 + comentário) e montar uma lista de "quero ver depois". Os dados de cada título (sinopse, elenco, pôster, notas do público e da crítica) vêm de APIs externas — TMDB para filmes/séries e Open Library para livros — e são importados automaticamente conforme o catálogo cresce, sem cadastro manual.

O projeto foi pensado para funcionar de forma sólida mesmo rodando inteiramente em infraestrutura gratuita (Render + Postgres gratuito), o que trouxe algumas decisões de arquitetura interessantes de destacar — como o modo de importação "sob demanda" descrito abaixo, em vez de replicar um banco gigante como o dump oficial do IMDb.

## Como o catálogo é populado

Diferente de um dump estático do IMDb (que passa de 1 GB só em texto — inviável no plano gratuito do Postgres), o CineBooks importa os títulos de duas formas complementares:

- **Sob demanda:** quando alguém busca um título que ainda não está no catálogo, o site consulta a API do TMDB/Open Library na hora, mostra o resultado e importa automaticamente ao ser aberto — então, para fins de busca, todo o catálogo dessas APIs já está efetivamente disponível, sem precisar de nada pré-carregado.
- **Pré-povoamento:** um comando de manutenção (`popular_catalogo`) importa periodicamente uma leva de títulos populares e bem avaliados do TMDB, para que a home e as listagens não fiquem vazias antes de qualquer busca acontecer. Cada título ocupa apenas um pequeno registro de texto — o pôster fica hospedado no próprio TMDB, nunca é baixado — o que mantém o uso de armazenamento desprezível mesmo com centenas de títulos.

Dados "mais pesados" de cada título (elenco, sinopse completa, notas de crítica) só são buscados na **primeira vez que alguém abre a página** daquele título, em segundo plano — a página aparece na hora com o que já existe, sem travar a navegação esperando a API externa responder.

## Modelo de dados

`Filme`, `Série` e `Livro` compartilham a maior parte dos campos (título, sinopse, ano/data de lançamento, pôster, gêneros, notas). Para não repetir essa estrutura três vezes, os três herdam de uma classe abstrata `Titulo`, que não vira tabela própria no banco — só define os campos e comportamentos comuns.

Avaliações e a lista "quero ver depois" usam **Generic Foreign Keys** do Django: em vez de três tabelas de avaliação (uma por tipo de título), uma única tabela `Avaliacao` — e, separadamente, `QueroVer` — guarda a referência a qualquer um dos três tipos, evitando duplicação de lógica nas views e nos templates.

O diagrama de classes completo está em [`docs/diagrama_classes.png`](docs/diagrama_classes.png) (fonte editável em `docs/diagrama_classes.mmd`, formato Mermaid).

## Funcionalidades

**Catálogo e busca**
- Listagem de filmes, séries e livros com paginação, busca por título, e filtros combináveis por gênero, ano e nota mínima da comunidade.
- Busca global (filmes + séries + livros de uma vez), que também consulta as APIs externas em tempo real para títulos ainda não cadastrados.
- Página de detalhe com sinopse, ficha técnica, elenco (com foto) e todas as avaliações da comunidade.
- Sinopse mais detalhada quando disponível (via OMDb, `plot=full`), sem misturar idioma: só aplicada quando bate com o idioma original do título, ou guardada como tradução pronta pro inglês.
- "Onde assistir" (streaming por assinatura, aluguel, compra), vindo do TMDB/JustWatch, atualizado periodicamente a cada deploy.
- Botão pra assistir o trailer oficial no YouTube, tentando abrir a versão dublada/legendada no idioma em que o site está sendo navegado (com fallback pro idioma original se não houver).
- Títulos são exibidos apenas até o ano civil atual — uma continuação anunciada com data de lançamento no futuro (ex: um filme previsto para 2030) não aparece no catálogo antes da hora.

**Avaliações**
- Nota de 1 a 5 + comentário opcional; cada usuário avalia um mesmo título uma única vez, podendo editar depois.
- Cálculo automático da nota média da comunidade, exibida junto com a nota do público (IMDb/Open Library) e da crítica (Metacritic), vindas da API do OMDb.
- Só é possível avaliar um título que **já foi lançado de verdade** — quando a data exata de lançamento é conhecida (via TMDB), a checagem é por dia, não só por ano: um título anunciado para dezembro deste ano fica visível e navegável, mas só pode ser avaliado depois da data passar.

**Watchlist ("quero ver depois")**
- Qualquer usuário logado pode marcar/desmarcar um título na sua lista pessoal, direto na página de detalhe.
- A lista aparece separada por categoria (Filmes / Séries / Livros) na página de perfil.

**Perfil de usuário**
- Avatar automático com as iniciais do nome de usuário (sem precisar de upload de foto — evita depender de armazenamento externo).
- Estatísticas de destaque: total de avaliações, nota média dada, gênero e título favoritos.
- Avaliações e watchlist da própria pessoa, organizadas em abas, com edição/exclusão direto ali.

**Internacionalização**
- Interface disponível em 11 idiomas (Português, Inglês, Mandarim, Hindi, Espanhol, Francês, Árabe, Bengali, Russo, Urdu e Indonésio), com troca de direção de texto automática para árabe/urdu.
- Título e sinopse de filmes/séries **novos** já entram traduzidos, pedidos diretamente à API no idioma selecionado no momento da busca.
- Sistema de tradução próprio (dicionário Python + tag de template customizada), independente do `gettext` do Django, para simplificar o deploy.

**Painel administrativo**
- Cadastro/edição de qualquer título direto pelo Django Admin, sem escrever HTML.
- Tela de importação dedicada (visível só para a equipe) para buscar um título nas APIs externas pelo nome e importar com um clique.

## Testes automatizados

O projeto tem uma suíte de mais de 100 testes automatizados (`catalog/tests/`), cobrindo desde regras de modelo (unicidade de avaliação, cálculo de média) até fluxos completos de view (avaliar, favoritar, filtrar, paginar) e a lógica de importação/tradução simulando as APIs externas via mocks — sem depender de rede ou de chaves de API configuradas para rodar.

## Stack técnica

- **Django 5** (Python) — modelos, views, autenticação e roteamento.
- **PostgreSQL** em produção (via `dj-database-url`), com SQLite como alternativa local — o mesmo código de modelos funciona nos dois.
- **Gunicorn** como servidor WSGI e **WhiteNoise** para servir os arquivos estáticos, sem depender de um serviço externo de CDN.
- **Bootstrap 5** para a interface.
- **TMDB**, **Open Library** e **OMDb** como fontes de dados externas.
- Hospedado no **Render**, com deploy automatizado a cada push (migrações, pré-povoamento do catálogo e outras tarefas de manutenção rodam sozinhas via `build.sh`).

## Estrutura do projeto

```
imdb_faculdade/
├── cinebooks/                  → configurações gerais do Django (settings, urls principais)
├── catalog/                    → app principal com toda a lógica do catálogo
│   ├── models.py                 → Titulo (abstrato), Filme, Serie, Livro, Avaliacao, QueroVer
│   ├── views.py                  → lógica de cada página
│   ├── busca_externa.py          → integração com TMDB / Open Library / OMDb
│   ├── i18n.py                   → dicionário de traduções (11 idiomas)
│   ├── forms.py, urls.py, admin.py
│   ├── management/commands/      → seed_data, popular_catalogo, buscar_capas,
│   │                                buscar_datas_lancamento, limpar_cache_traducoes,
│   │                                atualizar_onde_assistir, rebuscar_sem_correspondencia
│   └── tests/                    → suíte de testes automatizados
├── templates/                  → HTML (Django templates)
├── static/catalog/             → CSS customizado
├── docs/                       → diagrama de classes (Mermaid + PNG)
├── build.sh                    → script de deploy (Render)
└── manage.py
```

## Documentação adicional

- [`docs/diagrama_classes.png`](docs/diagrama_classes.png) — diagrama de classes do modelo de dados.
- [`DEPLOY.md`](DEPLOY.md) — histórico de como o deploy no Render foi configurado.

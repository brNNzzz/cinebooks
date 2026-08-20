"""
Testes automatizados do CineBooks.

Por que um PACOTE (pasta com vários arquivos) e não um único tests.py?
Fica mais fácil de organizar e de explicar no trabalho: cada arquivo cobre
uma parte do site, e dá pra rodar só uma parte na hora de depurar algo
(exemplos abaixo). O Django descobre e roda TODOS os arquivos que começam
com "test_" dentro dessa pasta automaticamente — não precisa registrar em
lugar nenhum.

Arquivos:
- test_models.py               → regras dos modelos (Filme/Serie/Livro/
                                  Avaliacao/QueroVer), sem passar pelas views.
- test_forms.py                → formulários (AvaliacaoForm, RegistroForm),
                                  incluindo os rótulos traduzidos por idioma.
- test_lista_e_paginacao.py    → página de listagem: busca, filtros
                                  (gênero/ano/nota mínima) e paginação.
- test_detalhe_e_avaliacoes.py → página de detalhe de um título e o
                                  fluxo de criar/editar/apagar avaliação.
- test_watchlist.py            → "quero ver depois": adicionar, remover,
                                  aparecer no perfil, exigir login.
- test_i18n.py                 → sistema de troca de idioma (catalog/i18n.py)
                                  e a página de perfil/navegação em geral.
- test_traducao_tmdb.py        → a correção do bug em que um título podia
                                  aparecer com o nome numa língua e a
                                  sinopse noutra (ver catalog/views.py,
                                  funções _texto_no_idioma/_buscar_traducao_
                                  agora, e o comando limpar_cache_traducoes).
- test_home.py                 → página inicial, em especial a correção do
                                  bug em que um título com ano de
                                  lançamento no FUTURO (ex: uma continuação
                                  só anunciada, tipo "Avatar 5") aparecia
                                  nas fileiras "recentes" da home.
- test_data_lancamento.py      → precisão de DIA (não só ano) no "já foi
                                  lançado?" (campo `data_lancamento`,
                                  função `views._titulo_ja_lancado`, e o
                                  comando `buscar_datas_lancamento`) — o
                                  caso do título "deste ano" mas ainda não
                                  lançado (ex: "Doomsday") é testado de
                                  ponta a ponta em
                                  test_detalhe_e_avaliacoes.py, junto com
                                  AvaliarTituloFuturoTest.
- test_popular_catalogo.py     → comando `popular_catalogo` (pré-popula o
                                  catálogo com títulos populares/bem
                                  avaliados do TMDB, sem precisar de um
                                  banco gigante tipo o dump do IMDb) e as
                                  funções de listagem que ele usa em
                                  catalog/busca_externa.py.
- test_sinopse_omdb.py         → sinopse mais detalhada vinda do OMDb
                                  (`plot=full`), incluindo o cuidado de só
                                  usar esse texto (que só existe em inglês)
                                  em títulos com conteúdo nativo em inglês,
                                  sem nunca misturar idioma na sinopse.
- test_onde_assistir.py        → "onde assistir" (streaming por assinatura,
                                  aluguel, compra), vindo do TMDB/JustWatch:
                                  parsing, salvamento em `_completar_filme`/
                                  `_completar_serie` e o comando de
                                  manutenção `atualizar_onde_assistir`
                                  (que re-busca periodicamente, diferente
                                  dos outros comandos "completar dados").
- test_trailer_youtube.py      → botão "Assistir trailer", que abre o
                                  trailer no YouTube (vindo do TMDB, sem
                                  baixar/hospedar nenhum vídeo — só um link
                                  direto pro YouTube), incluindo a escolha
                                  automática de um trailer dublado/legendado
                                  no idioma em que a pessoa está navegando
                                  o site, quando o TMDB tiver um.
- test_poster_idioma.py        → troca automática da CAPA (pôster) ao
                                  trocar o idioma do site, pra uma versão
                                  com o título escrito naquela língua,
                                  quando o TMDB tiver uma (mesma ideia do
                                  site do TMDB) — com fallback pro pôster
                                  ORIGINAL de lançamento quando não existir
                                  uma capa própria pra esse idioma. Livro
                                  nunca troca de capa (Open Library não tem
                                  esse conceito).
- test_exibicao_em_listas.py   → confere que título/capa traduzidos (ver
                                  acima) também aparecem nas páginas que
                                  mostram VÁRIOS cards de uma vez — home
                                  ("recentes"), listagem por tipo e busca —
                                  não só na página de detalhe de um título
                                  e no carrossel de destaque.
- test_rebuscar_sem_correspondencia.py → comando que destrava títulos que
                                  nunca acharam correspondência no TMDB (ex:
                                  a primeira tentativa aconteceu antes da
                                  TMDB_API_KEY estar configurada no Render)
                                  — sem ele, esses títulos ficariam pra
                                  sempre sem elenco/onde assistir/trailer.
- test_completar_dados_pendentes.py → comando que completa (elenco, onde
                                  assistir, trailer...) títulos que ainda
                                  nunca foram abertos por ninguém
                                  (dados_completos=False), direto no
                                  deploy — sem depender da thread em
                                  segundo plano sobreviver até o fim no
                                  ambiente de produção (ver comentário no
                                  próprio arquivo do comando pra entender
                                  por que isso é necessário no Render
                                  gratuito).
- test_recomendacoes.py        → motor de recomendações personalizadas
                                  (catalog/recomendacoes.py): pontuação por
                                  gênero + diretor/criador/autor + década,
                                  a partir de avaliações + watchlist +
                                  buscas, testado direto (sem HTTP).
- test_recomendacoes_home.py   → a fileira "Recomendados pra você" aparecendo
                                  (ou não) na home de verdade, dependendo de
                                  quem está logado e do que essa pessoa já
                                  avaliou/buscou/colocou na watchlist.

Como rodar:
    python manage.py test                        → roda tudo
    python manage.py test catalog.tests.test_watchlist   → só um arquivo
    python manage.py test -v 2                    → mostra o nome de cada
                                                      teste conforme roda
                                                      (bom pra apresentação)

Cada teste usa um banco de dados SEPARADO, criado e apagado automaticamente
pelo Django só pra rodar os testes — não mexe no banco de verdade (nem no
seu, local, nem no do site publicado). Por isso é seguro rodar quantas
vezes quiser.
"""

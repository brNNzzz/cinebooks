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

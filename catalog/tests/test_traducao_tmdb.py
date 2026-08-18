"""
Testes da correção do bug "título numa língua, sinopse em outra".

O QUE ACONTECIA: alguns títulos mais obscuros/menos conhecidos não têm
tradução completa no TMDB (a base de dados de filmes/séries que o site usa)
pro idioma que a pessoa escolheu no site. Quando isso acontecia, o código
ANTIGO caía de volta pro texto ORIGINAL (`item.titulo`/`item.sinopse`) —
que, por sua vez, também podia já estar misto (ex: título só existe em
francês no TMDB, mas a sinopse em inglês, porque foi isso que veio na
importação). Resultado real visto pelo usuário: um filme francês aparecendo
com o NOME em francês e a SINOPSE em inglês, mesmo com o site em português.

A CORREÇÃO (`catalog/views.py`, funções `_buscar_traducao_agora` e
`_texto_no_idioma`): quando o TMDB não tem sinopse traduzida pro idioma
pedido, a sinopse fica em BRANCO (o template mostra "sem sinopse
disponível") em vez de reaproveitar um texto que estaria numa língua
diferente da escolhida. O TÍTULO continua caindo pro original quando não
há tradução — isso é aceitável e esperado (mesmo streamings grandes tipo
Netflix não traduzem todo nome de filme estrangeiro).

Esses testes usam `unittest.mock.patch` pra SIMULAR a resposta do TMDB sem
precisar de internet nem de uma TMDB_API_KEY de verdade — testamos a LÓGICA
de decisão (o que fazer com a resposta), não a chamada de rede em si (essa
parte já é responsabilidade do catalog/busca_externa.py, e não muda aqui).
"""

from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from catalog import views
from catalog.tests.fabricas import criar_filme


class TextoNoIdiomaTest(TestCase):
    def setUp(self):
        # Filme cadastrado originalmente em inglês (idioma_tmdb_conteudo),
        # mas com o NOME em francês — reproduz exatamente a situação real
        # relatada: o TMDB, na hora do cadastro, não tinha um título em
        # inglês pra esse filme e devolveu o título original (francês) como
        # reserva, mesmo a busca tendo pedido "en-US".
        self.filme = criar_filme(
            titulo="Une Famille De Bâtards",
            sinopse="After the death of his father, Mohamed discovers the living of a step-brother.",
            idioma_tmdb_conteudo="en",
            id_externo="99999",  # precisa de um ID pra _buscar_traducao_agora tentar buscar
        )

    def test_mesmo_idioma_do_cadastro_usa_o_texto_original_sem_chamar_a_api(self):
        # Quando a pessoa está navegando no MESMO idioma em que o filme foi
        # cadastrado, nem precisa chamar a API — usa o texto original direto.
        with patch("catalog.views.busca_externa.detalhes_filme") as mock_busca:
            titulo, sinopse = views._texto_no_idioma(self.filme, "filme", "en")
            mock_busca.assert_not_called()
        self.assertEqual(titulo, "Une Famille De Bâtards")
        self.assertIn("After the death", sinopse)

    def test_tmdb_sem_sinopse_no_idioma_pedido_fica_em_branco(self):
        # Simula a resposta REAL do TMDB pra esse caso: título devolvido
        # (caiu pro original francês, já que também não tem título em
        # português) mas sinopse VAZIA (TMDB não tem sinopse em português
        # pra esse filme específico).
        resposta_simulada = {"titulo": "Une Famille De Bâtards", "sinopse": ""}
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=resposta_simulada):
            titulo, sinopse = views._texto_no_idioma(self.filme, "filme", "pt")

        self.assertEqual(titulo, "Une Famille De Bâtards")
        # ESSA é a correção: sinopse vazia, NÃO o texto original em inglês.
        # Antes da correção, esse assertEqual falhava porque `sinopse` vinha
        # como "After the death of his father..." (em inglês).
        self.assertEqual(sinopse, "")

    def test_tmdb_com_traducao_completa_usa_a_traducao(self):
        # Caso "feliz": TMDB tem título E sinopse em português — usa os dois.
        resposta_simulada = {
            "titulo": "Uma Família de Bastardos",
            "sinopse": "Após a morte do pai, Mohamed descobre a existência de um meio-irmão.",
        }
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=resposta_simulada):
            titulo, sinopse = views._texto_no_idioma(self.filme, "filme", "pt")

        self.assertEqual(titulo, "Uma Família de Bastardos")
        self.assertIn("Após a morte", sinopse)

    def test_falha_na_chamada_a_api_cai_pro_texto_original_inteiro(self):
        # Diferente do caso "TMDB respondeu mas não tem sinopse nesse
        # idioma" (tratado acima): aqui a chamada em si FALHOU (rede fora
        # do ar, timeout etc.) — nesse caso não dá pra saber se existe
        # tradução ou não, então o mais seguro é continuar mostrando o
        # texto original (título E sinopse), em vez de esconder a sinopse
        # só porque a internet falhou um instante.
        with patch("catalog.views.busca_externa.detalhes_filme", side_effect=Exception("Falha de rede")):
            titulo, sinopse = views._texto_no_idioma(self.filme, "filme", "pt")

        self.assertEqual(titulo, "Une Famille De Bâtards")
        self.assertIn("After the death", sinopse)

    def test_traducao_fica_em_cache_pra_nao_buscar_de_novo(self):
        # Depois da primeira busca (bem-sucedida), uma segunda chamada pro
        # MESMO idioma não deve chamar a API de novo — usa o que já foi
        # salvo em `item.traducoes` (ver _buscar_traducao_agora).
        resposta_simulada = {"titulo": "Título PT", "sinopse": "Sinopse em português."}
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=resposta_simulada) as mock_busca:
            views._texto_no_idioma(self.filme, "filme", "pt")
            self.filme.refresh_from_db()
            titulo, sinopse = views._texto_no_idioma(self.filme, "filme", "pt")
            self.assertEqual(mock_busca.call_count, 1)  # só UMA chamada, não duas
        self.assertEqual(titulo, "Título PT")

    def test_cache_de_sinopse_vazia_tambem_e_reaproveitado(self):
        # Continuação do teste anterior, mas pro caso de sinopse vazia: uma
        # vez que já sabemos que o TMDB não tem sinopse em pt pra esse
        # filme, não precisa ficar perguntando de novo a cada visita à
        # página — o "branco" também fica em cache.
        resposta_simulada = {"titulo": "Une Famille De Bâtards", "sinopse": ""}
        with patch("catalog.views.busca_externa.detalhes_filme", return_value=resposta_simulada) as mock_busca:
            views._texto_no_idioma(self.filme, "filme", "pt")
            self.filme.refresh_from_db()
            _, sinopse = views._texto_no_idioma(self.filme, "filme", "pt")
            self.assertEqual(mock_busca.call_count, 1)
        self.assertEqual(sinopse, "")


class LimparCacheTraducoesTest(TestCase):
    """O comando `python manage.py limpar_cache_traducoes` (catalog/
    management/commands/limpar_cache_traducoes.py) existe porque a correção
    acima só vale pra traduções NOVAS — sites que já estavam no ar antes da
    correção podem ter salvo entradas erradas no cache (sinopse na língua
    errada). Cada entrada nova do cache carrega uma marca `"v": 2`; o
    comando descarta só as entradas SEM essa marca, deixando pra buscar de
    novo (já corrigido) na próxima visita."""

    def setUp(self):
        self.filme = criar_filme(id_externo="12345")

    def test_limpa_entrada_no_formato_antigo(self):
        # Formato ANTIGO: sem a chave "v" (ou com um valor diferente de 2).
        self.filme.traducoes = {"pt": {"titulo": "X", "sinopse": "texto na língua errada"}}
        self.filme.save()

        call_command("limpar_cache_traducoes")

        self.filme.refresh_from_db()
        self.assertEqual(self.filme.traducoes, {})

    def test_nao_mexe_em_entrada_ja_no_formato_novo(self):
        # Formato NOVO (com "v": 2) já está correto — não precisa (e não
        # deve) ser apagado de novo a cada deploy, senão o site ficaria
        # buscando tradução de novo pra sempre, toda vez que o build.sh
        # rodasse esse comando.
        self.filme.traducoes = {"pt": {"titulo": "Y", "sinopse": "", "v": 2}}
        self.filme.save()

        call_command("limpar_cache_traducoes")

        self.filme.refresh_from_db()
        self.assertEqual(self.filme.traducoes, {"pt": {"titulo": "Y", "sinopse": "", "v": 2}})

    def test_item_sem_cache_nenhum_nao_da_erro(self):
        # Filme que nunca teve nenhuma tradução buscada ainda (traducoes={})
        # — o comando tem que simplesmente pular ele, sem quebrar.
        call_command("limpar_cache_traducoes")  # não deve levantar exceção
        self.filme.refresh_from_db()
        self.assertEqual(self.filme.traducoes, {})

    def test_e_seguro_rodar_duas_vezes_seguidas(self):
        # O build.sh do Render roda esse comando A CADA deploy (não tem
        # aba Shell no plano gratuito pra rodar comandos avulsos) — por
        # isso ele precisa ser "idempotente": rodar de novo sem ter nada
        # de novo pra limpar não pode dar erro nem apagar o que já tá certo.
        self.filme.traducoes = {"pt": {"titulo": "X", "sinopse": "errado", "v": 1}}
        self.filme.save()

        call_command("limpar_cache_traducoes")
        self.filme.refresh_from_db()
        self.assertEqual(self.filme.traducoes, {})

        # A "correção" simulando uma nova busca, já no formato certo...
        self.filme.traducoes = {"pt": {"titulo": "X", "sinopse": "", "v": 2}}
        self.filme.save()

        call_command("limpar_cache_traducoes")  # roda de novo
        self.filme.refresh_from_db()
        self.assertEqual(self.filme.traducoes, {"pt": {"titulo": "X", "sinopse": "", "v": 2}})

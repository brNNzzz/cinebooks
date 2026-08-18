import logging
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import connections
from django.db.models import Avg, Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import busca_externa
from .forms import AvaliacaoForm, RegistroForm
from .i18n import IDIOMA_PADRAO, IDIOMAS, traduzir
from .models import Avaliacao, Filme, Genero, Livro, Pessoa, QueroVer, Serie

logger = logging.getLogger(__name__)

# Mapa usado nas URLs para saber a qual modelo/rótulo cada "tipo" corresponde.
# "rotulo_chave"/"rotulo_plural_chave" são chaves do dicionário de tradução
# (catalog/i18n.py), não o texto pronto — assim o rótulo muda de idioma
# junto com o resto do site (ver traduzir() nos usos abaixo).
TIPOS = {
    "filme": {"model": Filme, "rotulo_chave": "tipo_filme", "rotulo_plural_chave": "nav_filmes"},
    "serie": {"model": Serie, "rotulo_chave": "tipo_serie", "rotulo_plural_chave": "nav_series"},
    "livro": {"model": Livro, "rotulo_chave": "tipo_livro", "rotulo_plural_chave": "nav_livros"},
}


def _com_media(queryset):
    return queryset.annotate(media_notas=Avg("avaliacoes__nota"), qtd_avaliacoes=Count("avaliacoes"))


LIMITE_DESTAQUES_ANO = 18  # quantos títulos aparecem no carrossel do topo


def _buscar_traducao_agora(item, tipo, idioma):
    """Busca o título/sinopse desse item no idioma pedido e já guarda no
    cache `traducoes`, SEM tocar nos campos `titulo`/`sinopse` originais.
    Devolve (titulo, sinopse) traduzidos, ou None se não deu pra buscar
    (item sem id_externo, ou a API falhou) — quem chamou usa o texto
    original nesse caso.

    É chamada NA HORA (não em segundo plano) — assim, ao trocar de idioma,
    a PRÓPRIA página que está carregando já aparece traduzida, sem precisar
    recarregar de novo depois. Pra não deixar páginas com vários títulos
    (o carrossel da home) lentas fazendo uma chamada de cada vez, use
    _traduzir_varios pra buscar em paralelo."""
    if not item.id_externo:
        return None
    try:
        if tipo == "filme":
            info = busca_externa.detalhes_filme(item.id_externo, idioma=idioma)
        else:
            info = busca_externa.detalhes_serie(item.id_externo, idioma=idioma)
    except Exception:
        logger.exception("Falha ao traduzir %s #%s pro idioma %s", tipo, item.pk, idioma)
        return None
    if not info or not info.get("titulo"):
        return None
    titulo = info.get("titulo") or item.titulo
    # IMPORTANTE: aqui NÃO cai pro item.sinopse original se a API não tiver
    # sinopse nesse idioma — isso é o que causava sinopse aparecer numa
    # língua diferente da que a pessoa escolheu (ex.: título em francês,
    # que é aceitável pois nomes próprios geralmente não são traduzidos
    # mesmo em serviços como Netflix, mas sinopse em inglês quando o site
    # estava em português). Se o TMDB não tem sinopse traduzida pra esse
    # idioma, fica em branco e o template mostra "sem sinopse disponível"
    # em vez de mostrar um parágrafo inteiro na língua errada.
    sinopse = info.get("sinopse") or ""
    cache = dict(item.traducoes or {})
    # "v": 2 marca esse formato como já corrigido (sinopse em branco em vez
    # de reaproveitar texto no idioma errado) — usado pelo comando
    # limpar_cache_traducoes pra saber quais entradas antigas (sem essa
    # marca) precisam ser descartadas e buscadas de novo.
    cache[idioma] = {"titulo": titulo, "sinopse": sinopse, "v": 2}
    item.traducoes = cache
    item.save(update_fields=["traducoes"])
    return titulo, sinopse


def _traduzir_varios(itens_com_tipo, idioma_atual):
    """Busca, EM PARALELO (várias chamadas de API ao mesmo tempo em vez de
    uma de cada vez), a tradução de todos os itens de `itens_com_tipo` que
    ainda não tenham uma tradução pronta pra `idioma_atual` — usado no
    carrossel da home, que pode ter vários títulos de uma vez. Sem isso,
    trocar pra um idioma novo com o carrossel cheio deixaria a home bem
    lenta (uma chamada de API esperando a outra terminar)."""
    if not idioma_atual:
        return
    pendentes = [
        (item, tipo)
        for item, tipo in itens_com_tipo
        if tipo in ("filme", "serie")
        and idioma_atual != item.idioma_tmdb_conteudo
        and not (item.traducoes or {}).get(idioma_atual)
    ]
    if not pendentes:
        return
    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(lambda par: _buscar_traducao_agora(par[0], par[1], idioma_atual), pendentes))


def _texto_no_idioma(item, tipo, idioma_atual):
    """Devolve (titulo, sinopse) pra EXIBIR pra quem está navegando em
    `idioma_atual`. Se for o mesmo idioma em que o item foi cadastrado, usa
    o texto original de sempre. Se for outro idioma e já tivermos uma
    tradução cacheada (ver _buscar_traducao_agora/_traduzir_varios), usa
    ela. Senão, busca na hora (só acontece se ninguém chamou
    _traduzir_varios antes pra esse item)."""
    if not idioma_atual or idioma_atual == item.idioma_tmdb_conteudo:
        return item.titulo, item.sinopse
    traducao = (item.traducoes or {}).get(idioma_atual)
    if traducao:
        # Mesmo motivo do comentário em _buscar_traducao_agora: sinopse
        # cacheada como "" significa "TMDB não tem tradução pra esse
        # idioma", então mostra em branco em vez de voltar pro texto
        # original (que estaria numa língua diferente da escolhida).
        return traducao.get("titulo") or item.titulo, traducao.get("sinopse", "")
    if tipo in ("filme", "serie"):
        resultado = _buscar_traducao_agora(item, tipo, idioma_atual)
        if resultado:
            return resultado
    return item.titulo, item.sinopse


def _destaques_do_ano(idioma_atual=None):
    """Uma ÚNICA fileira horizontal, logo abaixo do cabeçalho — junta filme,
    série e livro do ano ATUAL (o ano civil de verdade, tipo 2026), do mais
    bem avaliado pro menos avaliado. Igual à fileira de destaque do topo da
    Netflix, só que sem precisar escolher só 1 tipo de mídia.

    Se não tiver nenhum título lançado esse ano ainda, usa o ano mais
    recente que JÁ PASSOU — nunca um ano no futuro (tipo "Avatar 5 (2031)",
    um lançamento anunciado que ainda nem saiu; isso bagunçaria o
    "destaque do ano" e, como só teria 1 título futuro cadastrado, o
    carrossel nem teria pra onde trocar de slide)."""
    modelos = (("filme", Filme), ("serie", Serie), ("livro", Livro))
    ano_atual = timezone.now().year

    anos_ja_lancados = set()
    for _, model in modelos:
        anos = model.objects.filter(ano_lancamento__lte=ano_atual).values_list(
            "ano_lancamento", flat=True
        )
        anos_ja_lancados.update(anos)
    if not anos_ja_lancados:
        return {"ano": None, "itens": []}
    ano = ano_atual if ano_atual in anos_ja_lancados else max(anos_ja_lancados)

    itens = []
    for tipo, model in modelos:
        for item in model.objects.filter(ano_lancamento=ano):
            item.tipo = tipo
            itens.append(item)

    # Ordena todo mundo junto (filme, série e livro misturados) pela nota do
    # público — sem nota fica por último, em vez de sumir da lista.
    itens.sort(key=lambda i: (i.nota_publico is None, -(i.nota_publico or 0)))
    itens = itens[:LIMITE_DESTAQUES_ANO]

    # Traduz em PARALELO só os itens que realmente vão aparecer (depois do
    # corte acima) — assim trocar de idioma já mostra tudo certo na mesma
    # troca, sem precisar recarregar de novo, e sem esperar uma chamada de
    # API terminar pra começar a próxima.
    _traduzir_varios([(item, item.tipo) for item in itens], idioma_atual)
    for item in itens:
        item.titulo_exibicao, item.sinopse_exibicao = _texto_no_idioma(item, item.tipo, idioma_atual)

    return {"ano": ano, "itens": itens}



# Quantos títulos mostrar em cada fileira da home ("Filmes/Séries/Livros
# recentes"). Os cards ficam pequenos o bastante (ver _card.html) pra
# caber 6 por linha em telas grandes — 12 dá exatamente 2 linhas cheias
# nesse caso (e ainda fica bem distribuído nas telas menores: 3 linhas de
# 4 no tablet, 4 linhas de 3 no celular).
ITENS_POR_FILEIRA_HOME = 12


def home(request):
    # Mesmo cuidado do _destaques_do_ano (ver comentário lá): sem esse
    # filtro, um título anunciado mas que ainda nem lançou (ex: uma
    # continuação cadastrada com "ano_lancamento" no futuro, tipo "Avatar 5
    # (2034)") aparecia no topo de "Filmes/Séries/Livros recentes" — essas
    # 3 fileiras aqui embaixo ordenam por ano mais recente PRIMEIRO, então
    # um ano no futuro sempre ganhava de tudo que já foi lançado de
    # verdade, mesmo esse título não existindo ainda. Restringindo a
    # `ano_lancamento__lte=ano_atual`, só entra na lista quem já lançou (ou
    # lança até o fim do ano civil atual).
    ano_atual = timezone.now().year
    contexto = {
        "destaques_do_ano": _destaques_do_ano(_idioma_tmdb_atual(request)),
        "filmes": _com_media(Filme.objects.filter(ano_lancamento__lte=ano_atual)).order_by("-ano_lancamento")[
            :ITENS_POR_FILEIRA_HOME
        ],
        "series": _com_media(Serie.objects.filter(ano_lancamento__lte=ano_atual)).order_by("-ano_lancamento")[
            :ITENS_POR_FILEIRA_HOME
        ],
        "livros": _com_media(Livro.objects.filter(ano_lancamento__lte=ano_atual)).order_by("-ano_lancamento")[
            :ITENS_POR_FILEIRA_HOME
        ],
    }
    return render(request, "catalog/home.html", contexto)


# Quantos títulos aparecem por página na listagem (catalog/lista.html).
# Com poucos títulos no catálogo não faz diferença nenhuma, mas evita que a
# página fique gigante e lenta de rolar se o catálogo crescer bastante.
ITENS_POR_PAGINA = 12


def lista(request, tipo):
    info = TIPOS.get(tipo)
    if info is None:
        raise Http404("Categoria não encontrada")
    idioma_atual = _idioma_atual(request)
    ano_atual = timezone.now().year

    # Mesma regra da home (ver views.home): não faz sentido o catálogo
    # mostrar uma "continuação anunciada" com ano de lançamento lá no
    # futuro (ex: "Avatar 5", cadastrado com ano_lancamento=2034) — só
    # entra quem já lançou ou lança até o fim do ano civil atual. Aplicado
    # aqui na consulta BASE (antes de qualquer outro filtro) pra também
    # não aparecer nas abas "Filmes"/"Séries"/"Livros", não só na home.
    queryset = _com_media(info["model"].objects.filter(ano_lancamento__lte=ano_atual))

    termo = request.GET.get("q", "").strip()
    if termo:
        queryset = queryset.filter(titulo__icontains=termo)

    genero_id = request.GET.get("genero", "").strip()
    if genero_id:
        queryset = queryset.filter(generos__id=genero_id)

    # Lista de anos que existem de verdade nesse tipo de título, pra montar
    # o <select> de ano — calculada ANTES de aplicar o filtro de ano em si
    # (senão, depois de escolher um ano, o dropdown ficaria só com aquela
    # opção, sem jeito de voltar pra "todos os anos" olhando as outras).
    # Também limitada até o ano atual, pelo mesmo motivo acima: sem isso, o
    # <select> ofereceria anos "fantasma" (tipo 2034) que nem aparecem na
    # lista, então escolher esse ano só mostraria uma página vazia.
    anos_disponiveis = list(
        info["model"]
        .objects.filter(ano_lancamento__lte=ano_atual)
        .order_by("-ano_lancamento")
        .values_list("ano_lancamento", flat=True)
        .distinct()
    )

    ano = request.GET.get("ano", "").strip()
    if ano:
        queryset = queryset.filter(ano_lancamento=ano)

    # Nota mínima do PÚBLICO DO SITE (média das avaliações daqui, o mesmo
    # número que aparece na estrelinha do card) — não confundir com
    # nota_publico, que é a nota vinda da internet (IMDb/Open Library).
    nota_minima = request.GET.get("nota_minima", "").strip()
    if nota_minima:
        try:
            queryset = queryset.filter(media_notas__gte=float(nota_minima))
        except ValueError:
            nota_minima = ""  # valor inválido na URL — ignora em vez de quebrar a página

    # O filtro de gênero acima faz um JOIN com a tabela de gêneros (relação
    # muitos-pra-muitos): sem o distinct(), um título com mais de um gênero
    # cadastrado apareceria REPETIDO na lista, uma vez pra cada gênero dele.
    queryset = queryset.distinct()

    # Reforça a ordem explicitamente (mais recente primeiro, empate por
    # título): o `_com_media` acima faz um annotate() com Avg/Count, e
    # sempre que isso acontece o Django deixa de aplicar sozinho a ordenação
    # padrão do modelo (`Meta.ordering`, lá em Titulo) — sem essa linha, a
    # ordem virava praticamente aleatória (a do banco), e pior ainda: cada
    # PÁGINA da paginação podia repetir ou pular títulos, porque a ordem
    # mudava a cada consulta.
    queryset = queryset.order_by("-ano_lancamento", "titulo")

    paginator = Paginator(queryset, ITENS_POR_PAGINA)
    pagina = paginator.get_page(request.GET.get("pagina"))

    # Pra trocar de página SEM perder os filtros já escolhidos (busca,
    # gênero, ano, nota mínima) — os links "anterior"/"próxima" do template
    # usam essa string pra montar a URL completa (?q=...&genero=...&pagina=N).
    parametros = request.GET.copy()
    parametros.pop("pagina", None)

    contexto = {
        "tipo": tipo,
        "rotulo_plural": traduzir(info["rotulo_plural_chave"], idioma_atual),
        "itens": pagina,
        "generos": Genero.objects.all(),
        "termo": termo,
        "genero_id": genero_id,
        "anos_disponiveis": anos_disponiveis,
        "ano_selecionado": ano,
        "nota_minima": nota_minima,
        "query_sem_pagina": parametros.urlencode(),
        # Texto pronto ("Página 2 de 5") já formatado aqui na view, porque a
        # tag de template `{% t %}` só devolve o texto traduzido — não tem
        # suporte a colocar valores dentro dele (ver catalog/i18n_custom.py).
        "pagina_info": traduzir("lista_pagina_info", idioma_atual).format(
            atual=pagina.number, total=paginator.num_pages
        ),
    }
    return render(request, "catalog/lista.html", contexto)


def _idioma_atual(request):
    codigo = request.session.get("idioma", IDIOMA_PADRAO)
    return codigo if codigo in IDIOMAS else IDIOMA_PADRAO


def _idioma_tmdb_atual(request):
    return IDIOMAS[_idioma_atual(request)]["tmdb"]


# Guarda quais títulos já têm uma busca de "completar dados" rodando agora,
# pra não disparar várias threads fazendo o mesmo trabalho em paralelo se
# várias pessoas (ou a mesma pessoa recarregando várias vezes) abrirem a
# mesma página antes da primeira busca terminar.
_COMPLETANDO_AGORA = set()
_COMPLETANDO_AGORA_LOCK = threading.Lock()


def _completar_em_segundo_plano(pk, model, tipo):
    """Roda `_garantir_dados_completos` numa thread separada, SEM travar a
    resposta da página. Antes disso rodava direto dentro da view: se a API
    externa demorasse (ou estivesse fora do ar), a pessoa ficava esperando a
    página carregar. Agora a página aparece na hora com o que já temos, e
    elenco/notas completam sozinhos por trás — na próxima vez que a pessoa
    (ou outra) abrir a mesma página, já vem tudo pronto."""
    chave = (model.__name__, pk)
    with _COMPLETANDO_AGORA_LOCK:
        if chave in _COMPLETANDO_AGORA:
            return  # já tem uma busca rodando pra esse título, não duplica
        _COMPLETANDO_AGORA.add(chave)
    try:
        item = model.objects.get(pk=pk)
        _garantir_dados_completos(item, tipo)
    except model.DoesNotExist:
        pass
    except Exception:
        logger.exception("Falha ao completar dados em segundo plano (%s #%s)", tipo, pk)
    finally:
        # Essa thread abre sua própria conexão com o banco; sem fechar aqui,
        # ela ficaria pendurada depois que a thread termina.
        connections.close_all()
        with _COMPLETANDO_AGORA_LOCK:
            _COMPLETANDO_AGORA.discard(chave)


def _titulo_ja_lancado(item):
    """Verifica se um título já foi lançado de verdade — usado pra decidir
    se dá pra avaliar (ver `detalhe` e `avaliar` logo abaixo).

    Sempre que tivermos a data exata (`data_lancamento`, vinda do TMDB pra
    filme/série), comparamos DIA a dia: um título com `ano_lancamento`
    igual ao ano atual mas que só lança daqui a alguns meses (ex: um filme
    anunciado pra dezembro, visto em agosto) ainda NÃO está lançado, mesmo
    sendo "deste ano". Sem essa data exata (livros, cujo Open Library só
    informa o ano, ou títulos antigos cadastrados antes desse campo
    existir), caímos de volta pra comparação por ano — a mesma regra de
    antes, só um pouco menos precisa."""
    if item.data_lancamento:
        return item.data_lancamento <= timezone.localdate()
    return item.ano_lancamento <= timezone.now().year


def detalhe(request, tipo, pk):
    info = TIPOS.get(tipo)
    if info is None:
        raise Http404("Categoria não encontrada")
    item = get_object_or_404(info["model"], pk=pk)

    # Se ainda não temos os dados completos desse título (elenco, sinopse
    # maior...), busca em segundo plano — a página não espera isso terminar.
    # Só na primeira visita; depois fica salvo e todo mundo já vê completo.
    if not item.dados_completos:
        threading.Thread(
            target=_completar_em_segundo_plano,
            args=(item.pk, info["model"], tipo),
            daemon=True,
        ).start()

    # As notas (público/crítica/Rotten Tomatoes) a gente busca NA HORA, mesmo
    # sem esperar o resto (elenco, sinopse maior) — é só 1 chamada rápida ao
    # OMDb, então dá pra fazer isso sem travar a página, e assim a nota já
    # aparece na primeira visita em vez de só depois que o resto terminar de
    # completar em segundo plano.
    if tipo in ("filme", "serie") and not item.notas_omdb_verificadas:
        _garantir_notas_omdb(item, tipo=tipo)

    # Mostra título/sinopse no idioma em que a pessoa está navegando o site
    # agora — busca a tradução na hora se ainda não tiver uma pronta, sem
    # nunca sobrescrever o texto original do item (ver _texto_no_idioma).
    item.titulo_exibicao, item.sinopse_exibicao = _texto_no_idioma(
        item, tipo, _idioma_tmdb_atual(request)
    )

    minha_avaliacao = None
    na_watchlist = False
    if request.user.is_authenticated:
        content_type = ContentType.objects.get_for_model(info["model"])
        minha_avaliacao = Avaliacao.objects.filter(
            usuario=request.user, content_type=content_type, object_id=item.pk
        ).first()
        # Usado pra decidir se o botão mostra "+ Quero ver depois" ou
        # "Remover da lista" (ver alternar_watchlist, que faz o toggle).
        na_watchlist = QueroVer.objects.filter(
            usuario=request.user, content_type=content_type, object_id=item.pk
        ).exists()

    form = AvaliacaoForm(instance=minha_avaliacao, idioma=_idioma_atual(request))

    contexto = {
        "tipo": tipo,
        "rotulo": traduzir(info["rotulo_chave"], _idioma_atual(request)),
        "item": item,
        "avaliacoes": item.avaliacoes.select_related("usuario").all(),
        "media": item.media_avaliacoes(),
        "form": form,
        "minha_avaliacao": minha_avaliacao,
        "na_watchlist": na_watchlist,
        # Controla se o formulário de avaliação aparece ou não (ver
        # templates/catalog/detalhe.html) — não faz sentido deixar avaliar
        # um título que ainda nem foi lançado (ex: uma continuação só
        # anunciada, ou um título deste ano que só sai daqui a alguns
        # meses — ver `_titulo_ja_lancado`). A view `avaliar` também
        # confere isso de novo antes de salvar, então mesmo que alguém
        # envie o formulário contornando essa checagem visual, a avaliação
        # não é salva (ver comentário lá). O título continua aparecendo e
        # sendo navegável normalmente — só a avaliação fica bloqueada.
        "ja_lancado": _titulo_ja_lancado(item),
    }
    return render(request, "catalog/detalhe.html", contexto)


@login_required
@require_POST
def alternar_watchlist(request, tipo, pk):
    """Adiciona OU remove (alterna, dependendo do estado atual) um título da
    watchlist ("quero ver depois") do usuário logado — um botão só faz as
    duas coisas, então não precisa de duas views/URLs separadas.

    Separado de propósito da avaliação: Avaliacao é pra quem JÁ
    assistiu/leu e quer dar nota; QueroVer é só uma lista de lembrete de
    títulos que a pessoa ainda PRETENDE assistir/ler."""
    info = TIPOS.get(tipo)
    if info is None:
        raise Http404("Categoria não encontrada")
    item = get_object_or_404(info["model"], pk=pk)
    content_type = ContentType.objects.get_for_model(info["model"])
    idioma_atual = _idioma_atual(request)

    existente = QueroVer.objects.filter(
        usuario=request.user, content_type=content_type, object_id=item.pk
    ).first()
    if existente:
        existente.delete()
        messages.success(request, traduzir("watchlist_removido", idioma_atual))
    else:
        QueroVer.objects.create(usuario=request.user, content_type=content_type, object_id=item.pk)
        messages.success(request, traduzir("watchlist_adicionado", idioma_atual))

    return redirect("detalhe", tipo=tipo, pk=pk)


@login_required
def avaliar(request, tipo, pk):
    if request.method != "POST":
        return redirect("detalhe", tipo=tipo, pk=pk)

    info = TIPOS.get(tipo)
    if info is None:
        raise Http404("Categoria não encontrada")
    item = get_object_or_404(info["model"], pk=pk)
    content_type = ContentType.objects.get_for_model(info["model"])

    idioma_atual = _idioma_atual(request)

    # Não dá pra avaliar um título que ainda nem foi lançado de verdade —
    # nem uma continuação anunciada pro futuro, nem um título "deste ano"
    # que só sai daqui a alguns meses (ver `_titulo_ja_lancado`; e o mesmo
    # cuidado em views.home, que continua limitando por ANO na home, já
    # que lá é só sobre APARECER no catálogo, não sobre poder avaliar). O
    # formulário já fica escondido nesse caso (ver
    # templates/catalog/detalhe.html), mas essa checagem aqui é o que
    # realmente IMPEDE, caso alguém envie o POST direto (contornando a
    # interface).
    if not _titulo_ja_lancado(item):
        messages.error(request, traduzir("avaliacao_erro_nao_lancado", idioma_atual))
        return redirect("detalhe", tipo=tipo, pk=pk)

    instancia = Avaliacao.objects.filter(
        usuario=request.user, content_type=content_type, object_id=item.pk
    ).first()

    form = AvaliacaoForm(request.POST, instance=instancia, idioma=idioma_atual)
    if form.is_valid():
        avaliacao = form.save(commit=False)
        avaliacao.usuario = request.user
        avaliacao.content_type = content_type
        avaliacao.object_id = item.pk
        avaliacao.save()
        messages.success(request, traduzir("avaliacao_salva", idioma_atual))
    else:
        messages.error(request, traduzir("avaliacao_erro", idioma_atual))

    return redirect("detalhe", tipo=tipo, pk=pk)


def _importar_generos(obj, nomes_generos):
    obj.generos.set([Genero.objects.get_or_create(nome=nome)[0] for nome in nomes_generos if nome])


def _importar_pessoa(nome, foto_url=""):
    """Cria (ou reaproveita) uma Pessoa pelo nome. Se ela já existir mas
    ainda não tiver foto, e agora encontramos uma, completa."""
    nome = (nome or "").strip()
    if not nome:
        return None
    pessoa, _ = Pessoa.objects.get_or_create(nome=nome, defaults={"foto_url": foto_url})
    if foto_url and not pessoa.foto_url:
        pessoa.foto_url = foto_url
        pessoa.save()
    return pessoa


def _importar_elenco(obj, lista_elenco):
    pessoas = [
        _importar_pessoa(p.get("nome", ""), p.get("foto_url", "")) for p in lista_elenco or []
    ]
    obj.elenco.set([p for p in pessoas if p])


def _garantir_dados_completos(item, tipo):
    """Completa elenco, sinopse maior etc. de um título que ainda não tem
    `dados_completos=True`. Só roda de fato na primeira visita à página —
    depois disso fica salvo no banco e as próximas visitas nem chamam essa
    função (veja a checagem em `detalhe()`). Qualquer erro aqui é só
    registrado no log: a página continua funcionando com os dados que já
    tinha, e tenta completar de novo na próxima visita.

    Sempre busca no MESMO idioma em que o título foi cadastrado
    (`item.idioma_tmdb_conteudo`), nunca no idioma de quem está navegando
    agora — senão o título ficava com o nome num idioma e a sinopse
    completada depois em outro, dependendo de quem foi a primeira pessoa a
    abrir a página."""
    try:
        if tipo == "filme":
            _completar_filme(item)
        elif tipo == "serie":
            _completar_serie(item)
        elif tipo == "livro":
            _completar_livro(item)
    except Exception:
        logger.exception("Falha ao completar dados de %s #%s", tipo, item.pk)


def _completar_imdb_id(item, tipo):
    """Resolve e salva o `imdb_id` de um título que já tem `id_externo`
    (TMDB) mas ainda não tem o `imdb_id` guardado — caso dos títulos
    cadastrados ANTES desse campo existir. Sem isso, esses títulos ficariam
    pra sempre buscando a nota no OMDb por texto do título (que falha toda
    vez que o título está traduzido), mesmo já sabendo o ID do TMDB."""
    if not item.id_externo:
        return
    idioma_tmdb = item.idioma_tmdb_conteudo or busca_externa.IDIOMA_TMDB_PADRAO
    try:
        if tipo == "filme":
            info = busca_externa.detalhes_filme(item.id_externo, idioma=idioma_tmdb)
        else:
            info = busca_externa.detalhes_serie(item.id_externo, idioma=idioma_tmdb)
    except Exception:
        logger.exception("Falha ao resolver imdb_id de %r no TMDB", item.titulo)
        return
    if info and info.get("imdb_id"):
        item.imdb_id = info["imdb_id"]
        item.save(update_fields=["imdb_id"])


def _garantir_notas_omdb(item, tipo=None):
    """Busca as notas de público/crítica/Rotten Tomatoes no OMDb e salva, se
    ainda não tiver. Feito separado do resto do "completar dados" (elenco,
    sinopse) porque é só 1 chamada rápida — dá pra fazer na hora, sem
    precisar esperar a thread de segundo plano, então a nota já aparece na
    primeira visita à página.

    Usa o `imdb_id` do título (se já tiver) pra buscar por ID em vez de por
    texto do título — muito mais confiável, porque o OMDb é majoritariamente
    em inglês e falha fácil com título traduzido. Se o título ainda não tem
    `imdb_id` salvo (títulos antigos, cadastrados antes desse campo
    existir), tenta resolver ele primeiro a partir do `id_externo` (TMDB)
    que já temos — assim os títulos antigos também passam a se autocorrigir,
    e não só os novos.

    Só tenta uma vez por título (controlado por `notas_omdb_verificadas`) —
    depois disso fica valendo o que foi encontrado, mesmo que seja só
    ALGUMA das 3 notas (o OMDb nem sempre tem as 3 pra um título)."""
    if not busca_externa.omdb_configurado():
        return
    if not item.imdb_id and tipo in ("filme", "serie"):
        _completar_imdb_id(item, tipo)
    try:
        notas = busca_externa.buscar_notas_omdb(
            item.titulo, item.ano_lancamento, imdb_id=item.imdb_id
        )
    except Exception:
        logger.exception("Falha ao buscar notas do OMDb pra %r", item.titulo)
        return
    # Só sobrescreve cada campo se achou uma nota nova pra ele — assim, se
    # essa tentativa falhar em achar algo que a gente já tinha (ex: falha
    # passageira do OMDb), não perde o que já estava salvo.
    item.nota_publico = notas.get("nota_publico") or item.nota_publico
    item.nota_critica = notas.get("nota_critica") or item.nota_critica
    item.nota_rotten_tomatoes = notas.get("nota_rotten_tomatoes") or item.nota_rotten_tomatoes
    item.notas_omdb_verificadas = True
    item.save(
        update_fields=[
            "nota_publico", "nota_critica", "nota_rotten_tomatoes", "notas_omdb_verificadas",
        ]
    )


def _melhor_correspondencia(encontrados, item):
    """Escolhe qual resultado da busca é esse título. Preferimos um título
    IDÊNTICO, mas isso costuma falhar quando o idioma muda o texto do título
    (ex: item salvo como "Matrix" e a busca em inglês devolve "The Matrix")
    — nesse caso, sem essa função, o site simplesmente desistia de achar o
    título e ficava pra sempre sem elenco/sinopse/tradução. Como reserva,
    usamos o resultado com o mesmo ano de lançamento, ou o primeiro da lista
    (o TMDB já ordena por relevância)."""
    if not encontrados:
        return None
    for r in encontrados:
        if r["titulo"].lower() == item.titulo.lower():
            return r
    mesmo_ano = [r for r in encontrados if str(r.get("ano")) == str(item.ano_lancamento)]
    return (mesmo_ano or encontrados)[0]


def _completar_filme(item):
    idioma_tmdb = item.idioma_tmdb_conteudo or busca_externa.IDIOMA_TMDB_PADRAO
    tmdb_id = item.id_externo
    if not tmdb_id:
        encontrados = busca_externa.buscar_filmes_series("movie", item.titulo, idioma=idioma_tmdb)
        correspondente = _melhor_correspondencia(encontrados, item)
        if correspondente:
            tmdb_id = correspondente["id"]
            item.id_externo = str(tmdb_id)
            item.save(update_fields=["id_externo"])
    if not tmdb_id:
        # Não achamos esse título na API — marca como completo pra não ficar
        # tentando de novo a cada visita à página.
        item.dados_completos = True
        item.save(update_fields=["dados_completos"])
        return

    info = busca_externa.detalhes_filme(tmdb_id, idioma=idioma_tmdb)
    if not info:
        return  # falha temporária (rede/API fora do ar) — tenta de novo na próxima visita

    elenco = info.pop("elenco", [])
    generos = info.pop("generos", [])
    if not item.diretor:
        item.diretor = info.get("diretor", "")
    if not item.duracao_minutos:
        item.duracao_minutos = info.get("duracao_minutos")
    if info.get("sinopse") and len(info["sinopse"]) > len(item.sinopse or ""):
        item.sinopse = info["sinopse"]
    if not item.poster_url and info.get("poster_url"):
        item.poster_url = info["poster_url"]
    if not item.imdb_id and info.get("imdb_id"):
        item.imdb_id = info["imdb_id"]
    # Preenche a data exata de lançamento pra quem foi cadastrado antes
    # desse campo existir (ou criado "rápido" pela busca, sem essa info) —
    # ver comentário em Titulo.data_lancamento sobre pra que ela serve.
    if not item.data_lancamento and info.get("data_lancamento"):
        item.data_lancamento = info["data_lancamento"]
    item.dados_completos = True
    item.save()
    if not item.notas_omdb_verificadas:
        _garantir_notas_omdb(item, tipo="filme")
    if elenco:
        _importar_elenco(item, elenco)
    if generos:
        _importar_generos(item, generos)


def _completar_serie(item):
    idioma_tmdb = item.idioma_tmdb_conteudo or busca_externa.IDIOMA_TMDB_PADRAO
    tmdb_id = item.id_externo
    if not tmdb_id:
        encontrados = busca_externa.buscar_filmes_series("tv", item.titulo, idioma=idioma_tmdb)
        correspondente = _melhor_correspondencia(encontrados, item)
        if correspondente:
            tmdb_id = correspondente["id"]
            item.id_externo = str(tmdb_id)
            item.save(update_fields=["id_externo"])
    if not tmdb_id:
        item.dados_completos = True
        item.save(update_fields=["dados_completos"])
        return

    info = busca_externa.detalhes_serie(tmdb_id, idioma=idioma_tmdb)
    if not info:
        return

    elenco = info.pop("elenco", [])
    generos = info.pop("generos", [])
    if not item.criador:
        item.criador = info.get("criador", "")
    if not item.numero_temporadas:
        item.numero_temporadas = info.get("numero_temporadas")
    if info.get("sinopse") and len(info["sinopse"]) > len(item.sinopse or ""):
        item.sinopse = info["sinopse"]
    if not item.poster_url and info.get("poster_url"):
        item.poster_url = info["poster_url"]
    if not item.imdb_id and info.get("imdb_id"):
        item.imdb_id = info["imdb_id"]
    if not item.data_lancamento and info.get("data_lancamento"):
        item.data_lancamento = info["data_lancamento"]
    item.dados_completos = True
    item.save()
    if not item.notas_omdb_verificadas:
        _garantir_notas_omdb(item, tipo="serie")
    if elenco:
        _importar_elenco(item, elenco)
    if generos:
        _importar_generos(item, generos)


def _completar_livro(item):
    olid = item.id_externo
    if not olid:
        encontrados = busca_externa.buscar_livros(item.titulo)
        correspondente = _melhor_correspondencia(encontrados, item)
        if correspondente:
            olid = correspondente["id"]
            item.id_externo = olid
            item.save(update_fields=["id_externo"])
            if not item.autor_pessoa and correspondente.get("autor"):
                item.autor_pessoa = _importar_pessoa(
                    correspondente["autor"], correspondente.get("autor_foto_url", "")
                )
    if not olid:
        item.dados_completos = True
        item.save(update_fields=["dados_completos"])
        return

    sinopse = busca_externa.sinopse_livro(olid)
    if sinopse and len(sinopse) > len(item.sinopse or ""):
        item.sinopse = sinopse
    nota = busca_externa.nota_publico_livro(olid)
    if nota is not None:
        item.nota_publico = nota
    item.dados_completos = True
    item.save()


# Quantos resultados "novos" (que ainda não estão no catálogo) a busca tenta
# importar automaticamente por categoria. Como a importação "rápida" (usada
# na busca pública) não faz nenhuma chamada extra de API, esse número pode
# ser generoso sem deixar a página lenta.
LIMITE_IMPORTACAO_AUTOMATICA = 10


def _criar_filme_rapido(resultado_busca, idioma_tmdb=None):
    """Cria o Filme só com os dados que já vieram na busca (sem chamada
    extra à API) — usado na busca pública, pra ficar rápida. Diretor e
    elenco ficam pra depois: a própria página de detalhe completa isso
    sozinha na primeira vez que alguém abrir (veja _garantir_dados_completos).

    Antes de criar, confere pelo id_externo (id do TMDB) se esse filme já
    está no catálogo — importante porque, com o site em vários idiomas,
    a mesma busca pode trazer o título "traduzido" (ex: "The Matrix" em vez
    de "Matrix"), e sem essa checagem cada idioma criaria uma cópia
    duplicada do mesmo filme.

    Guarda também em que idioma esse filme foi encontrado
    (`idioma_tmdb_conteudo`) — assim, quando a página completar o resto
    depois (elenco, sinopse maior), ela busca nesse MESMO idioma, não no
    idioma de quem estiver navegando naquele momento."""
    titulo = (resultado_busca.get("titulo") or "").strip()
    ano = resultado_busca.get("ano")
    id_externo = str(resultado_busca.get("id", ""))
    if not titulo or not ano:
        return None
    if id_externo:
        existente = Filme.objects.filter(id_externo=id_externo).first()
        if existente:
            return existente
    dados = {
        "ano_lancamento": int(ano),
        "data_lancamento": resultado_busca.get("data_lancamento"),
        "sinopse": resultado_busca.get("sinopse", ""),
        "poster_url": resultado_busca.get("poster_url", ""),
        "id_externo": id_externo,
        "idioma_tmdb_conteudo": idioma_tmdb or busca_externa.IDIOMA_TMDB_PADRAO,
    }
    obj, _ = Filme.objects.get_or_create(titulo=titulo, defaults=dados)
    _importar_generos(obj, resultado_busca.get("generos", []))
    return obj


def _criar_serie_rapida(resultado_busca, idioma_tmdb=None):
    titulo = (resultado_busca.get("titulo") or "").strip()
    ano = resultado_busca.get("ano")
    id_externo = str(resultado_busca.get("id", ""))
    if not titulo or not ano:
        return None
    if id_externo:
        existente = Serie.objects.filter(id_externo=id_externo).first()
        if existente:
            return existente
    dados = {
        "ano_lancamento": int(ano),
        "data_lancamento": resultado_busca.get("data_lancamento"),
        "sinopse": resultado_busca.get("sinopse", ""),
        "poster_url": resultado_busca.get("poster_url", ""),
        "id_externo": id_externo,
        "idioma_tmdb_conteudo": idioma_tmdb or busca_externa.IDIOMA_TMDB_PADRAO,
    }
    obj, _ = Serie.objects.get_or_create(titulo=titulo, defaults=dados)
    _importar_generos(obj, resultado_busca.get("generos", []))
    return obj


def _criar_livro_rapido(resultado_busca):
    """Cria o Livro com os dados da busca. A foto do autor já vem de graça
    (o Open Library monta a URL sem chamada extra); a sinopse completa fica
    pra quando alguém abrir a página do livro."""
    titulo = (resultado_busca.get("titulo") or "").strip()
    ano = resultado_busca.get("ano")
    if not titulo or not ano:
        return None
    dados = {
        "ano_lancamento": int(ano),
        "autor": resultado_busca.get("autor", ""),
        "editora": resultado_busca.get("editora", ""),
        "poster_url": resultado_busca.get("poster_url", ""),
        "id_externo": resultado_busca.get("id", ""),
    }
    if resultado_busca.get("numero_paginas"):
        dados["numero_paginas"] = resultado_busca["numero_paginas"]
    obj, _ = Livro.objects.get_or_create(titulo=titulo, defaults=dados)
    if resultado_busca.get("autor"):
        obj.autor_pessoa = _importar_pessoa(resultado_busca["autor"], resultado_busca.get("autor_foto_url", ""))
        obj.save()
    return obj


def _criar_filme_do_tmdb(tmdb_id, idioma_tmdb=None):
    """Busca os detalhes completos do filme no TMDB (inclusive elenco) e
    salva no catálogo já com dados_completos=True — quem importar manualmente
    pela tela de staff não precisa esperar a primeira visita completar nada.
    Devolve o objeto Filme criado (ou já existente), ou None se falhar."""
    idioma_tmdb = idioma_tmdb or busca_externa.IDIOMA_TMDB_PADRAO
    existente = Filme.objects.filter(id_externo=str(tmdb_id)).first()
    if existente:
        return existente
    info = busca_externa.detalhes_filme(tmdb_id, idioma=idioma_tmdb)
    if not info or not info.get("titulo") or not info.get("ano_lancamento"):
        return None
    generos = info.pop("generos", [])
    elenco = info.pop("elenco", [])
    notas = busca_externa.buscar_notas_omdb(
        info["titulo"], info["ano_lancamento"], imdb_id=info.get("imdb_id", "")
    )
    info["nota_publico"] = notas.get("nota_publico")
    info["nota_critica"] = notas.get("nota_critica")
    info["nota_rotten_tomatoes"] = notas.get("nota_rotten_tomatoes")
    info["notas_omdb_verificadas"] = True
    info["id_externo"] = str(tmdb_id)
    info["idioma_tmdb_conteudo"] = idioma_tmdb
    info["dados_completos"] = True
    obj, _ = Filme.objects.get_or_create(titulo=info["titulo"], defaults=info)
    _importar_generos(obj, generos)
    _importar_elenco(obj, elenco)
    return obj


def _criar_serie_do_tmdb(tmdb_id, idioma_tmdb=None):
    idioma_tmdb = idioma_tmdb or busca_externa.IDIOMA_TMDB_PADRAO
    existente = Serie.objects.filter(id_externo=str(tmdb_id)).first()
    if existente:
        return existente
    info = busca_externa.detalhes_serie(tmdb_id, idioma=idioma_tmdb)
    if not info or not info.get("titulo") or not info.get("ano_lancamento"):
        return None
    generos = info.pop("generos", [])
    elenco = info.pop("elenco", [])
    notas = busca_externa.buscar_notas_omdb(
        info["titulo"], info["ano_lancamento"], imdb_id=info.get("imdb_id", "")
    )
    info["nota_publico"] = notas.get("nota_publico")
    info["nota_critica"] = notas.get("nota_critica")
    info["nota_rotten_tomatoes"] = notas.get("nota_rotten_tomatoes")
    info["notas_omdb_verificadas"] = True
    info["id_externo"] = str(tmdb_id)
    info["idioma_tmdb_conteudo"] = idioma_tmdb
    info["dados_completos"] = True
    obj, _ = Serie.objects.get_or_create(titulo=info["titulo"], defaults=info)
    _importar_generos(obj, generos)
    _importar_elenco(obj, elenco)
    return obj


def _criar_livro_do_openlibrary(resultado_busca):
    """resultado_busca é um item da lista devolvida por busca_externa.buscar_livros()."""
    titulo = (resultado_busca.get("titulo") or "").strip()
    ano = resultado_busca.get("ano")
    if not titulo or not ano:
        return None
    dados = {
        "ano_lancamento": int(ano),
        "autor": resultado_busca.get("autor", ""),
        "editora": resultado_busca.get("editora", ""),
        "poster_url": resultado_busca.get("poster_url", ""),
        "sinopse": busca_externa.sinopse_livro(resultado_busca.get("id", "")),
        "nota_publico": busca_externa.nota_publico_livro(resultado_busca.get("id", "")),
        "id_externo": resultado_busca.get("id", ""),
        "dados_completos": True,
    }
    if resultado_busca.get("numero_paginas"):
        dados["numero_paginas"] = resultado_busca["numero_paginas"]
    obj, _ = Livro.objects.get_or_create(titulo=titulo, defaults=dados)
    if resultado_busca.get("autor"):
        obj.autor_pessoa = _importar_pessoa(
            resultado_busca["autor"], resultado_busca.get("autor_foto_url", "")
        )
        obj.save()
    return obj


def busca(request):
    """Busca no catálogo do site E nas APIs externas (TMDB e Open Library).

    Quando a API encontra um título que ainda não existe no banco, ele é
    importado automaticamente na hora — assim a busca sempre devolve a
    página completa do título (sinopse, ficha técnica, já pronto pra
    avaliar), mesmo que ninguém tivesse cadastrado ele antes.
    """
    termo = request.GET.get("q", "").strip()
    resultados = {"filmes": [], "series": [], "livros": []}
    idioma_tmdb = _idioma_tmdb_atual(request)

    if termo:
        filmes = list(Filme.objects.filter(titulo__icontains=termo))
        series = list(Serie.objects.filter(titulo__icontains=termo))
        livros = list(Livro.objects.filter(titulo__icontains=termo))

        titulos_filmes = {f.titulo.lower() for f in filmes}
        titulos_series = {s.titulo.lower() for s in series}
        titulos_livros = {l.titulo.lower() for l in livros}
        pks_filmes = {f.pk for f in filmes}
        pks_series = {s.pk for s in series}

        # As 3 buscas externas (filmes, séries, livros) são chamadas de rede
        # separadas — rodar uma de cada vez faz a busca demorar a SOMA das
        # três. Rodando em paralelo, a busca demora só o tempo da mais lenta
        # das três (até 3x mais rápido na prática).
        with ThreadPoolExecutor(max_workers=3) as executor:
            futuro_filmes = executor.submit(
                busca_externa.buscar_filmes_series, "movie", termo, idioma=idioma_tmdb
            )
            futuro_series = executor.submit(
                busca_externa.buscar_filmes_series, "tv", termo, idioma=idioma_tmdb
            )
            futuro_livros = executor.submit(busca_externa.buscar_livros, termo)
            resultados_filmes_api = futuro_filmes.result()
            resultados_series_api = futuro_series.result()
            resultados_livros_api = futuro_livros.result()

        for r in resultados_filmes_api[:LIMITE_IMPORTACAO_AUTOMATICA]:
            if r["titulo"].lower() not in titulos_filmes:
                novo = _criar_filme_rapido(r, idioma_tmdb=idioma_tmdb)
                if novo and novo.pk not in pks_filmes:
                    filmes.append(novo)
                    titulos_filmes.add(novo.titulo.lower())
                    pks_filmes.add(novo.pk)

        for r in resultados_series_api[:LIMITE_IMPORTACAO_AUTOMATICA]:
            if r["titulo"].lower() not in titulos_series:
                novo = _criar_serie_rapida(r, idioma_tmdb=idioma_tmdb)
                if novo and novo.pk not in pks_series:
                    series.append(novo)
                    titulos_series.add(novo.titulo.lower())
                    pks_series.add(novo.pk)

        for r in resultados_livros_api[:LIMITE_IMPORTACAO_AUTOMATICA]:
            if r["titulo"].lower() not in titulos_livros:
                novo = _criar_livro_rapido(r)
                if novo:
                    livros.append(novo)
                    titulos_livros.add(novo.titulo.lower())

        resultados = {"filmes": filmes, "series": series, "livros": livros}

    return render(request, "catalog/busca.html", {"termo": termo, "resultados": resultados})


@staff_member_required
def importar_buscar(request):
    """Página de busca+importação manual, com escolha do resultado certo —
    útil quando a busca automática traz o título errado ou você quer mais
    controle. Só a equipe (staff) acessa."""
    tipo = request.GET.get("tipo", "filme")
    query = request.GET.get("q", "").strip()
    idioma_tmdb = _idioma_tmdb_atual(request)

    resultados = []
    if query:
        if tipo == "filme":
            resultados = busca_externa.buscar_filmes_series("movie", query, idioma=idioma_tmdb)
        elif tipo == "serie":
            resultados = busca_externa.buscar_filmes_series("tv", query, idioma=idioma_tmdb)
        elif tipo == "livro":
            resultados = busca_externa.buscar_livros(query)

    mensagem_nenhum_resultado = ""
    if query and not resultados:
        mensagem_nenhum_resultado = traduzir(
            "importar_nenhum_resultado", _idioma_atual(request)
        ).format(query=query)

    contexto = {
        "tipo": tipo,
        "query": query,
        "resultados": resultados,
        "tmdb_configurado": busca_externa.tmdb_configurado(),
        "mensagem_nenhum_resultado": mensagem_nenhum_resultado,
    }
    return render(request, "catalog/importar.html", contexto)


@staff_member_required
@require_POST
def importar_adicionar_filme(request, tmdb_id):
    idioma_atual = _idioma_atual(request)
    obj = _criar_filme_do_tmdb(tmdb_id, idioma_tmdb=_idioma_tmdb_atual(request))
    if not obj:
        messages.error(request, traduzir("importar_erro_tmdb", idioma_atual))
        return redirect("importar_buscar")
    messages.success(request, traduzir("importar_adicionado", idioma_atual).format(titulo=obj.titulo))
    return redirect("detalhe", tipo="filme", pk=obj.pk)


@staff_member_required
@require_POST
def importar_adicionar_serie(request, tmdb_id):
    idioma_atual = _idioma_atual(request)
    obj = _criar_serie_do_tmdb(tmdb_id, idioma_tmdb=_idioma_tmdb_atual(request))
    if not obj:
        messages.error(request, traduzir("importar_erro_tmdb", idioma_atual))
        return redirect("importar_buscar")
    messages.success(request, traduzir("importar_adicionado", idioma_atual).format(titulo=obj.titulo))
    return redirect("detalhe", tipo="serie", pk=obj.pk)


@staff_member_required
@require_POST
def importar_adicionar_livro(request, olid):
    resultado_busca = {
        "id": olid,
        "titulo": request.POST.get("titulo", "").strip(),
        "ano": request.POST.get("ano", "").strip(),
        "autor": request.POST.get("autor", ""),
        "editora": request.POST.get("editora", ""),
        "poster_url": request.POST.get("poster_url", ""),
        "numero_paginas": request.POST.get("numero_paginas", ""),
    }
    if resultado_busca["numero_paginas"].isdigit():
        resultado_busca["numero_paginas"] = int(resultado_busca["numero_paginas"])
    else:
        resultado_busca["numero_paginas"] = None

    idioma_atual = _idioma_atual(request)
    obj = _criar_livro_do_openlibrary(resultado_busca)
    if not obj:
        messages.error(request, traduzir("importar_erro_dados_incompletos", idioma_atual))
        return redirect("importar_buscar")
    messages.success(request, traduzir("importar_adicionado", idioma_atual).format(titulo=obj.titulo))
    return redirect("detalhe", tipo="livro", pk=obj.pk)


def registrar(request):
    idioma_atual = _idioma_atual(request)
    if request.method == "POST":
        form = RegistroForm(request.POST, idioma=idioma_atual)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            messages.success(
                request, traduzir("registrar_bemvindo", idioma_atual).format(usuario=usuario.username)
            )
            return redirect("home")
    else:
        form = RegistroForm(idioma=idioma_atual)

    return render(request, "registration/registrar.html", {"form": form})


@login_required
def perfil(request):
    """Página do próprio usuário: estatísticas de destaque + as avaliações
    dela, separadas em abas por categoria (filmes / séries / livros), mais
    recentes primeiro. Cada avaliação pode ser editada ou apagada direto
    aqui, sem precisar ir até a página do título."""
    avaliacoes_do_usuario = list(
        Avaliacao.objects.filter(usuario=request.user)
        .select_related("content_type")
        .order_by("-criado_em")
    )
    tipos_por_content_type = {
        ContentType.objects.get_for_model(Filme).id: "filme",
        ContentType.objects.get_for_model(Serie).id: "serie",
        ContentType.objects.get_for_model(Livro).id: "livro",
    }
    avaliacoes_por_tipo = {"filme": [], "serie": [], "livro": []}
    contagem_generos = Counter()
    for avaliacao in avaliacoes_do_usuario:
        tipo_desse_item = tipos_por_content_type.get(avaliacao.content_type_id)
        if not tipo_desse_item:
            continue
        # Guarda o tipo no próprio objeto (não vai pro banco, só facilita o
        # template) — assim cada linha da lista já sabe montar sua própria
        # URL de detalhe/edição sem repetir lógica por aba.
        avaliacao.tipo = tipo_desse_item
        avaliacoes_por_tipo[tipo_desse_item].append(avaliacao)

        titulo_avaliado = avaliacao.titulo_avaliado
        if titulo_avaliado:
            for genero in titulo_avaliado.generos.all():
                contagem_generos[genero.nome] += 1

    total_avaliacoes = len(avaliacoes_do_usuario)
    nota_media_dada = (
        round(sum(a.nota for a in avaliacoes_do_usuario) / total_avaliacoes, 1)
        if total_avaliacoes
        else None
    )
    genero_favorito = contagem_generos.most_common(1)[0][0] if contagem_generos else None
    favorito = (
        max(avaliacoes_do_usuario, key=lambda a: (a.nota, a.criado_em))
        if avaliacoes_do_usuario
        else None
    )

    # Mesma ideia das avaliações acima (separadas em filme/série/livro pra
    # virar 3 abas), só que pra watchlist ("quero ver depois") em vez de
    # avaliações já feitas.
    itens_watchlist = list(
        QueroVer.objects.filter(usuario=request.user)
        .select_related("content_type")
        .order_by("-criado_em")
    )
    watchlist_por_tipo = {"filme": [], "serie": [], "livro": []}
    for item_watchlist in itens_watchlist:
        tipo_desse_item = tipos_por_content_type.get(item_watchlist.content_type_id)
        if not tipo_desse_item:
            continue
        item_watchlist.tipo = tipo_desse_item
        watchlist_por_tipo[tipo_desse_item].append(item_watchlist)

    contexto = {
        "avaliacoes_filmes": avaliacoes_por_tipo["filme"],
        "avaliacoes_series": avaliacoes_por_tipo["serie"],
        "avaliacoes_livros": avaliacoes_por_tipo["livro"],
        "total_avaliacoes": total_avaliacoes,
        "nota_media_dada": nota_media_dada,
        "genero_favorito": genero_favorito,
        "favorito": favorito,
        "watchlist_filmes": watchlist_por_tipo["filme"],
        "watchlist_series": watchlist_por_tipo["serie"],
        "watchlist_livros": watchlist_por_tipo["livro"],
        "total_watchlist": len(itens_watchlist),
    }
    return render(request, "catalog/perfil.html", contexto)


@login_required
@require_POST
def excluir_avaliacao(request, avaliacao_id):
    """Apaga uma avaliação — só o próprio autor pode apagar a dele (o
    get_object_or_404 com usuario=request.user garante isso: se o ID for de
    outra pessoa, dá 404 em vez de deixar apagar)."""
    avaliacao = get_object_or_404(Avaliacao, pk=avaliacao_id, usuario=request.user)
    avaliacao.delete()
    messages.success(request, traduzir("avaliacao_removida", _idioma_atual(request)))
    return redirect("perfil")


def mudar_idioma(request, codigo):
    """Troca o idioma do site (guardado na sessão da pessoa) e volta pra
    página de onde ela veio."""
    if codigo in IDIOMAS:
        request.session["idioma"] = codigo
    destino = request.META.get("HTTP_REFERER") or "/"
    return redirect(destino)

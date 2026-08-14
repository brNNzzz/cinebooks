import logging
import threading
from collections import Counter

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db import connections
from django.db.models import Avg, Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import busca_externa
from .forms import AvaliacaoForm, RegistroForm
from .i18n import IDIOMA_PADRAO, IDIOMAS
from .models import Avaliacao, Filme, Genero, Livro, Pessoa, Serie

logger = logging.getLogger(__name__)

# Mapa usado nas URLs para saber a qual modelo/rótulo cada "tipo" corresponde.
TIPOS = {
    "filme": {"model": Filme, "rotulo": "Filme", "rotulo_plural": "Filmes"},
    "serie": {"model": Serie, "rotulo": "Série", "rotulo_plural": "Séries"},
    "livro": {"model": Livro, "rotulo": "Livro", "rotulo_plural": "Livros"},
}


def _com_media(queryset):
    return queryset.annotate(media_notas=Avg("avaliacoes__nota"), qtd_avaliacoes=Count("avaliacoes"))


def home(request):
    contexto = {
        "filmes": _com_media(Filme.objects.all()).order_by("-ano_lancamento")[:4],
        "series": _com_media(Serie.objects.all()).order_by("-ano_lancamento")[:4],
        "livros": _com_media(Livro.objects.all()).order_by("-ano_lancamento")[:4],
    }
    return render(request, "catalog/home.html", contexto)


def lista(request, tipo):
    info = TIPOS.get(tipo)
    if info is None:
        raise Http404("Categoria não encontrada")
    queryset = _com_media(info["model"].objects.all())

    termo = request.GET.get("q", "").strip()
    if termo:
        queryset = queryset.filter(titulo__icontains=termo)

    genero_id = request.GET.get("genero", "")
    if genero_id:
        queryset = queryset.filter(generos__id=genero_id)

    contexto = {
        "tipo": tipo,
        "rotulo_plural": info["rotulo_plural"],
        "itens": queryset,
        "generos": Genero.objects.all(),
        "termo": termo,
        "genero_id": genero_id,
    }
    return render(request, "catalog/lista.html", contexto)


def _idioma_atual(request):
    codigo = request.session.get("idioma", IDIOMA_PADRAO)
    return codigo if codigo in IDIOMAS else IDIOMA_PADRAO


def _idioma_tmdb_atual(request):
    return IDIOMAS[_idioma_atual(request)]["tmdb"]


def _completar_em_segundo_plano(pk, model, tipo, idioma_tmdb):
    """Roda `_garantir_dados_completos` numa thread separada, SEM travar a
    resposta da página. Antes disso rodava direto dentro da view: se a API
    externa demorasse (ou estivesse fora do ar), a pessoa ficava esperando a
    página carregar. Agora a página aparece na hora com o que já temos, e
    elenco/notas completam sozinhos por trás — na próxima vez que a pessoa
    (ou outra) abrir a mesma página, já vem tudo pronto."""
    try:
        item = model.objects.get(pk=pk)
        _garantir_dados_completos(item, tipo, idioma_tmdb)
    except model.DoesNotExist:
        pass
    except Exception:
        logger.exception("Falha ao completar dados em segundo plano (%s #%s)", tipo, pk)
    finally:
        # Essa thread abre sua própria conexão com o banco; sem fechar aqui,
        # ela ficaria pendurada depois que a thread termina.
        connections.close_all()


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
            args=(item.pk, info["model"], tipo, _idioma_tmdb_atual(request)),
            daemon=True,
        ).start()

    minha_avaliacao = None
    if request.user.is_authenticated:
        content_type = ContentType.objects.get_for_model(info["model"])
        minha_avaliacao = Avaliacao.objects.filter(
            usuario=request.user, content_type=content_type, object_id=item.pk
        ).first()

    form = AvaliacaoForm(instance=minha_avaliacao)

    contexto = {
        "tipo": tipo,
        "rotulo": info["rotulo"],
        "item": item,
        "avaliacoes": item.avaliacoes.select_related("usuario").all(),
        "media": item.media_avaliacoes(),
        "form": form,
        "minha_avaliacao": minha_avaliacao,
    }
    return render(request, "catalog/detalhe.html", contexto)


@login_required
def avaliar(request, tipo, pk):
    if request.method != "POST":
        return redirect("detalhe", tipo=tipo, pk=pk)

    info = TIPOS.get(tipo)
    if info is None:
        raise Http404("Categoria não encontrada")
    item = get_object_or_404(info["model"], pk=pk)
    content_type = ContentType.objects.get_for_model(info["model"])

    instancia = Avaliacao.objects.filter(
        usuario=request.user, content_type=content_type, object_id=item.pk
    ).first()

    form = AvaliacaoForm(request.POST, instance=instancia)
    if form.is_valid():
        avaliacao = form.save(commit=False)
        avaliacao.usuario = request.user
        avaliacao.content_type = content_type
        avaliacao.object_id = item.pk
        avaliacao.save()
        messages.success(request, "Sua avaliação foi salva. Obrigado!")
    else:
        messages.error(request, "Não foi possível salvar a avaliação. Verifique a nota.")

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


def _garantir_dados_completos(item, tipo, idioma_tmdb=None):
    """Completa elenco, sinopse maior etc. de um título que ainda não tem
    `dados_completos=True`. Só roda de fato na primeira visita à página —
    depois disso fica salvo no banco e as próximas visitas nem chamam essa
    função (veja a checagem em `detalhe()`). Qualquer erro aqui é só
    registrado no log: a página continua funcionando com os dados que já
    tinha, e tenta completar de novo na próxima visita."""
    idioma_tmdb = idioma_tmdb or busca_externa.IDIOMA_TMDB_PADRAO
    try:
        if tipo == "filme":
            _completar_filme(item, idioma_tmdb)
        elif tipo == "serie":
            _completar_serie(item, idioma_tmdb)
        elif tipo == "livro":
            _completar_livro(item)
    except Exception:
        logger.exception("Falha ao completar dados de %s #%s", tipo, item.pk)


def _completar_filme(item, idioma_tmdb):
    tmdb_id = item.id_externo
    if not tmdb_id:
        encontrados = busca_externa.buscar_filmes_series("movie", item.titulo, idioma=idioma_tmdb)
        correspondente = next(
            (r for r in encontrados if r["titulo"].lower() == item.titulo.lower()), None
        )
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
    notas = busca_externa.buscar_notas_omdb(item.titulo, item.ano_lancamento)
    item.nota_publico = notas.get("nota_publico")
    item.nota_critica = notas.get("nota_critica")
    item.dados_completos = True
    item.save()
    if elenco:
        _importar_elenco(item, elenco)
    if generos:
        _importar_generos(item, generos)


def _completar_serie(item, idioma_tmdb):
    tmdb_id = item.id_externo
    if not tmdb_id:
        encontrados = busca_externa.buscar_filmes_series("tv", item.titulo, idioma=idioma_tmdb)
        correspondente = next(
            (r for r in encontrados if r["titulo"].lower() == item.titulo.lower()), None
        )
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
    notas = busca_externa.buscar_notas_omdb(item.titulo, item.ano_lancamento)
    item.nota_publico = notas.get("nota_publico")
    item.nota_critica = notas.get("nota_critica")
    item.dados_completos = True
    item.save()
    if elenco:
        _importar_elenco(item, elenco)
    if generos:
        _importar_generos(item, generos)


def _completar_livro(item):
    olid = item.id_externo
    if not olid:
        encontrados = busca_externa.buscar_livros(item.titulo)
        correspondente = next(
            (r for r in encontrados if r["titulo"].lower() == item.titulo.lower()), None
        )
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


def _criar_filme_rapido(resultado_busca):
    """Cria o Filme só com os dados que já vieram na busca (sem chamada
    extra à API) — usado na busca pública, pra ficar rápida. Diretor e
    elenco ficam pra depois: a própria página de detalhe completa isso
    sozinha na primeira vez que alguém abrir (veja _garantir_dados_completos).

    Antes de criar, confere pelo id_externo (id do TMDB) se esse filme já
    está no catálogo — importante porque, com o site em vários idiomas,
    a mesma busca pode trazer o título "traduzido" (ex: "The Matrix" em vez
    de "Matrix"), e sem essa checagem cada idioma criaria uma cópia
    duplicada do mesmo filme."""
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
        "sinopse": resultado_busca.get("sinopse", ""),
        "poster_url": resultado_busca.get("poster_url", ""),
        "id_externo": id_externo,
    }
    obj, _ = Filme.objects.get_or_create(titulo=titulo, defaults=dados)
    _importar_generos(obj, resultado_busca.get("generos", []))
    return obj


def _criar_serie_rapida(resultado_busca):
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
        "sinopse": resultado_busca.get("sinopse", ""),
        "poster_url": resultado_busca.get("poster_url", ""),
        "id_externo": id_externo,
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
    notas = busca_externa.buscar_notas_omdb(info["titulo"], info["ano_lancamento"])
    info["nota_publico"] = notas.get("nota_publico")
    info["nota_critica"] = notas.get("nota_critica")
    info["id_externo"] = str(tmdb_id)
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
    notas = busca_externa.buscar_notas_omdb(info["titulo"], info["ano_lancamento"])
    info["nota_publico"] = notas.get("nota_publico")
    info["nota_critica"] = notas.get("nota_critica")
    info["id_externo"] = str(tmdb_id)
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

        for r in busca_externa.buscar_filmes_series("movie", termo, idioma=idioma_tmdb)[:LIMITE_IMPORTACAO_AUTOMATICA]:
            if r["titulo"].lower() not in titulos_filmes:
                novo = _criar_filme_rapido(r)
                if novo and novo.pk not in pks_filmes:
                    filmes.append(novo)
                    titulos_filmes.add(novo.titulo.lower())
                    pks_filmes.add(novo.pk)

        for r in busca_externa.buscar_filmes_series("tv", termo, idioma=idioma_tmdb)[:LIMITE_IMPORTACAO_AUTOMATICA]:
            if r["titulo"].lower() not in titulos_series:
                novo = _criar_serie_rapida(r)
                if novo and novo.pk not in pks_series:
                    series.append(novo)
                    titulos_series.add(novo.titulo.lower())
                    pks_series.add(novo.pk)

        for r in busca_externa.buscar_livros(termo)[:LIMITE_IMPORTACAO_AUTOMATICA]:
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

    contexto = {
        "tipo": tipo,
        "query": query,
        "resultados": resultados,
        "tmdb_configurado": busca_externa.tmdb_configurado(),
    }
    return render(request, "catalog/importar.html", contexto)


@staff_member_required
@require_POST
def importar_adicionar_filme(request, tmdb_id):
    obj = _criar_filme_do_tmdb(tmdb_id, idioma_tmdb=_idioma_tmdb_atual(request))
    if not obj:
        messages.error(
            request,
            "Não foi possível importar esse filme agora (falha ao buscar no TMDB). Tente de novo em instantes.",
        )
        return redirect("importar_buscar")
    messages.success(request, f'"{obj.titulo}" está no catálogo!')
    return redirect("detalhe", tipo="filme", pk=obj.pk)


@staff_member_required
@require_POST
def importar_adicionar_serie(request, tmdb_id):
    obj = _criar_serie_do_tmdb(tmdb_id, idioma_tmdb=_idioma_tmdb_atual(request))
    if not obj:
        messages.error(
            request,
            "Não foi possível importar essa série agora (falha ao buscar no TMDB). Tente de novo em instantes.",
        )
        return redirect("importar_buscar")
    messages.success(request, f'"{obj.titulo}" está no catálogo!')
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

    obj = _criar_livro_do_openlibrary(resultado_busca)
    if not obj:
        messages.error(request, "Não foi possível importar esse livro (dados incompletos).")
        return redirect("importar_buscar")
    messages.success(request, f'"{obj.titulo}" está no catálogo!')
    return redirect("detalhe", tipo="livro", pk=obj.pk)


def registrar(request):
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            messages.success(request, f"Bem-vindo(a), {usuario.username}!")
            return redirect("home")
    else:
        form = RegistroForm()

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

    contexto = {
        "avaliacoes_filmes": avaliacoes_por_tipo["filme"],
        "avaliacoes_series": avaliacoes_por_tipo["serie"],
        "avaliacoes_livros": avaliacoes_por_tipo["livro"],
        "total_avaliacoes": total_avaliacoes,
        "nota_media_dada": nota_media_dada,
        "genero_favorito": genero_favorito,
        "favorito": favorito,
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
    messages.success(request, "Avaliação removida.")
    return redirect("perfil")


def mudar_idioma(request, codigo):
    """Troca o idioma do site (guardado na sessão da pessoa) e volta pra
    página de onde ela veio."""
    if codigo in IDIOMAS:
        request.session["idioma"] = codigo
    destino = request.META.get("HTTP_REFERER") or "/"
    return redirect(destino)

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import busca_externa
from .forms import AvaliacaoForm, RegistroForm
from .models import Avaliacao, Filme, Genero, Livro, Serie

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


def detalhe(request, tipo, pk):
    info = TIPOS.get(tipo)
    if info is None:
        raise Http404("Categoria não encontrada")
    item = get_object_or_404(info["model"], pk=pk)

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


def busca(request):
    termo = request.GET.get("q", "").strip()
    resultados = {"filmes": [], "series": [], "livros": []}

    if termo:
        resultados["filmes"] = Filme.objects.filter(titulo__icontains=termo)
        resultados["series"] = Serie.objects.filter(titulo__icontains=termo)
        resultados["livros"] = Livro.objects.filter(titulo__icontains=termo)

    return render(request, "catalog/busca.html", {"termo": termo, "resultados": resultados})


@staff_member_required
def importar_buscar(request):
    """Página de busca+importação: só a equipe (staff) pode acessar."""
    tipo = request.GET.get("tipo", "filme")
    query = request.GET.get("q", "").strip()

    resultados = []
    if query:
        if tipo == "filme":
            resultados = busca_externa.buscar_filmes_series("movie", query)
        elif tipo == "serie":
            resultados = busca_externa.buscar_filmes_series("tv", query)
        elif tipo == "livro":
            resultados = busca_externa.buscar_livros(query)

    contexto = {
        "tipo": tipo,
        "query": query,
        "resultados": resultados,
        "tmdb_configurado": busca_externa.tmdb_configurado(),
    }
    return render(request, "catalog/importar.html", contexto)


def _importar_generos(obj, nomes_generos):
    obj.generos.set([Genero.objects.get_or_create(nome=nome)[0] for nome in nomes_generos if nome])


@staff_member_required
@require_POST
def importar_adicionar_filme(request, tmdb_id):
    info = busca_externa.detalhes_filme(tmdb_id)
    if not info or not info.get("titulo") or not info.get("ano_lancamento"):
        messages.error(
            request,
            "Não foi possível importar esse filme agora (falha ao buscar no TMDB). Tente de novo em instantes.",
        )
        return redirect("importar_buscar")

    generos = info.pop("generos", [])
    obj, criado = Filme.objects.get_or_create(titulo=info["titulo"], defaults=info)
    _importar_generos(obj, generos)
    messages.success(
        request, f'"{obj.titulo}" {"foi adicionado ao" if criado else "já estava no"} catálogo!'
    )
    return redirect("detalhe", tipo="filme", pk=obj.pk)


@staff_member_required
@require_POST
def importar_adicionar_serie(request, tmdb_id):
    info = busca_externa.detalhes_serie(tmdb_id)
    if not info or not info.get("titulo") or not info.get("ano_lancamento"):
        messages.error(
            request,
            "Não foi possível importar essa série agora (falha ao buscar no TMDB). Tente de novo em instantes.",
        )
        return redirect("importar_buscar")

    generos = info.pop("generos", [])
    obj, criado = Serie.objects.get_or_create(titulo=info["titulo"], defaults=info)
    _importar_generos(obj, generos)
    messages.success(
        request, f'"{obj.titulo}" {"foi adicionada ao" if criado else "já estava no"} catálogo!'
    )
    return redirect("detalhe", tipo="serie", pk=obj.pk)


@staff_member_required
@require_POST
def importar_adicionar_livro(request, olid):
    titulo = request.POST.get("titulo", "").strip()
    ano = request.POST.get("ano", "").strip()
    if not titulo or not ano.isdigit():
        messages.error(request, "Não foi possível importar esse livro (dados incompletos).")
        return redirect("importar_buscar")

    dados = {
        "ano_lancamento": int(ano),
        "autor": request.POST.get("autor", ""),
        "editora": request.POST.get("editora", ""),
        "poster_url": request.POST.get("poster_url", ""),
        "sinopse": busca_externa.sinopse_livro(olid),
    }
    numero_paginas = request.POST.get("numero_paginas", "")
    if numero_paginas.isdigit():
        dados["numero_paginas"] = int(numero_paginas)

    obj, criado = Livro.objects.get_or_create(titulo=titulo, defaults=dados)
    messages.success(
        request, f'"{obj.titulo}" {"foi adicionado ao" if criado else "já estava no"} catálogo!'
    )
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

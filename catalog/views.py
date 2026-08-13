from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

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

from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("busca/", views.busca, name="busca"),
    path("conta/registrar/", views.registrar, name="registrar"),
    path("importar/", views.importar_buscar, name="importar_buscar"),
    path(
        "importar/filme/<int:tmdb_id>/adicionar/",
        views.importar_adicionar_filme,
        name="importar_adicionar_filme",
    ),
    path(
        "importar/serie/<int:tmdb_id>/adicionar/",
        views.importar_adicionar_serie,
        name="importar_adicionar_serie",
    ),
    path(
        "importar/livro/<str:olid>/adicionar/",
        views.importar_adicionar_livro,
        name="importar_adicionar_livro",
    ),
    path("<str:tipo>/", views.lista, name="lista"),
    path("<str:tipo>/<int:pk>/", views.detalhe, name="detalhe"),
    path("<str:tipo>/<int:pk>/avaliar/", views.avaliar, name="avaliar"),
]

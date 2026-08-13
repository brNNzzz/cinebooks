from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("busca/", views.busca, name="busca"),
    path("conta/registrar/", views.registrar, name="registrar"),
    path("<str:tipo>/", views.lista, name="lista"),
    path("<str:tipo>/<int:pk>/", views.detalhe, name="detalhe"),
    path("<str:tipo>/<int:pk>/avaliar/", views.avaliar, name="avaliar"),
]

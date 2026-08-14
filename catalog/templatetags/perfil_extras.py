"""Filtros de template pro "avatar" de usuário (círculo colorido com as
iniciais do nome, tipo Gmail/Slack) — sem precisar de upload de foto."""

from django import template

register = template.Library()

# Paleta de cores pro avatar — a cor de cada pessoa é sempre a mesma
# (calculada a partir do nome dela), só pra variar visualmente entre usuários.
_CORES_AVATAR = [
    "#e63946", "#f4a261", "#2a9d8f", "#264653", "#8338ec",
    "#3a86ff", "#ff006e", "#06d6a0", "#ef476f", "#118ab2",
]


@register.filter
def iniciais(nome):
    nome = (nome or "").strip()
    if not nome:
        return "?"
    partes = [p for p in nome.replace("_", " ").replace(".", " ").split() if p]
    if not partes:
        return nome[:2].upper()
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


@register.filter
def cor_avatar(nome):
    indice = sum(ord(c) for c in (nome or "")) % len(_CORES_AVATAR)
    return _CORES_AVATAR[indice]

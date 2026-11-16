"""Leitura da lista de participantes (CSV com as colunas nome, telefone e,
opcionalmente, grupo)."""

import csv
import re
from dataclasses import dataclass
from pathlib import Path


class ListaInvalida(ValueError):
    pass


@dataclass(frozen=True)
class Participante:
    nome: str
    telefone: str  # formato internacional, ex.: +5511987654321
    grupo: str = ""  # quem tem o mesmo grupo (ex.: um casal) não se tira


def normalizar_telefone(bruto: str) -> str:
    """Aceita "+55 11 98765-4321", "(11) 98765-4321" ou "11987654321".

    Números sem "+" são tratados como brasileiros (DDD + número).
    """
    digitos = re.sub(r"\D", "", bruto)
    if bruto.strip().startswith("+"):
        if not 8 <= len(digitos) <= 15:
            raise ListaInvalida(f"telefone inválido: {bruto!r}")
        return "+" + digitos
    if digitos.startswith("55") and len(digitos) in (12, 13):
        return "+" + digitos
    if len(digitos) in (10, 11):
        return "+55" + digitos
    raise ListaInvalida(f"telefone inválido: {bruto!r} (use DDD + número, ex.: 11987654321)")


def carregar(caminho: Path) -> list[Participante]:
    try:
        with caminho.open(newline="", encoding="utf-8-sig") as f:
            leitor = csv.DictReader(f)
            colunas = {c.strip().lower() for c in leitor.fieldnames or []}
            if not {"nome", "telefone"} <= colunas:
                raise ListaInvalida("o CSV precisa das colunas 'nome' e 'telefone'")
            linhas = [{k.strip().lower(): (v or "").strip() for k, v in linha.items() if k} for linha in leitor]
    except FileNotFoundError:
        raise ListaInvalida(f"arquivo não encontrado: {caminho}") from None

    participantes = []
    for numero, linha in enumerate(linhas, start=2):
        if not any(linha.values()):
            continue
        if not linha["nome"]:
            raise ListaInvalida(f"linha {numero}: falta o nome")
        try:
            telefone = normalizar_telefone(linha["telefone"])
        except ListaInvalida as e:
            raise ListaInvalida(f"linha {numero}: {e}") from None
        participantes.append(Participante(linha["nome"], telefone, " ".join(linha.get("grupo", "").split())))

    for campo in ("nome", "telefone"):
        vistos = set()
        for p in participantes:
            valor = getattr(p, campo).casefold()
            if valor in vistos:
                raise ListaInvalida(f"{campo} repetido: {getattr(p, campo)}")
            vistos.add(valor)

    membros: dict[str, list[str]] = {}
    for p in participantes:
        if p.grupo:
            membros.setdefault(p.grupo.casefold(), []).append(p.nome)
    for nomes in membros.values():
        if len(nomes) == 1:
            raise ListaInvalida(f"{nomes[0]} é a única do grupo '{_grupo_de(participantes, nomes[0])}'. "
                                "Confira se o nome do grupo foi digitado igual para as duas pessoas")
    return participantes


def grupos(participantes: list[Participante]) -> dict[str, str]:
    """{nome: grupo} de quem tem grupo, sem diferenciar maiúsculas."""
    return {p.nome: p.grupo.casefold() for p in participantes if p.grupo}


def _grupo_de(participantes: list[Participante], nome: str) -> str:
    return next(p.grupo for p in participantes if p.nome == nome)

"""Leitura da lista de participantes (CSV com as colunas nome e telefone)."""

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
        participantes.append(Participante(linha["nome"], telefone))

    for campo in ("nome", "telefone"):
        vistos = set()
        for p in participantes:
            valor = getattr(p, campo).casefold()
            if valor in vistos:
                raise ListaInvalida(f"{campo} repetido: {getattr(p, campo)}")
            vistos.add(valor)
    return participantes

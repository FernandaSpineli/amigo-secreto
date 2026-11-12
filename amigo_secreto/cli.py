"""Linha de comando: sortear, reenviar e ver quem já recebeu.

Nada aqui imprime quem tirou quem, para que quem organiza também possa
participar sem saber o resultado.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from . import participantes, sms, sorteio

MENSAGEM_PADRAO = "Oi, {nome}! No amigo secreto você tirou: {amiga}. Shh, é segredo! 🤫"
ARQUIVO_PADRAO = Path("sorteio.json")


def main(argv: list[str] | None = None, enviador=None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.comando(args, enviador)
    except (participantes.ListaInvalida, sorteio.SorteioInvalido, sms.FalhaNoEnvio, ErroDeUso) as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1


class ErroDeUso(Exception):
    pass


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="amigo-secreto", description="Sorteio de amigo secreto com envio por SMS.")
    sub = p.add_subparsers(required=True, metavar="comando")

    s = sub.add_parser("sortear", help="faz o sorteio e envia um SMS para cada participante")
    s.add_argument("lista", type=Path, help="CSV com as colunas nome e telefone")
    s.add_argument("--simular", action="store_true", help="faz tudo, menos enviar e salvar (não revela o resultado)")
    s.add_argument("--mensagem", default=MENSAGEM_PADRAO, help="texto do SMS, com {nome} e {amiga}")
    s.add_argument("--novo", action="store_true", help="descarta um sorteio anterior e sorteia de novo")
    s.add_argument("--arquivo", type=Path, default=ARQUIVO_PADRAO, help=argparse.SUPPRESS)
    s.set_defaults(comando=_sortear)

    r = sub.add_parser("reenviar", help="envia de novo os SMS que falharam, ou o de uma pessoa")
    r.add_argument("--nome", help="reenvia para esta pessoa, mesmo que já tenha recebido")
    r.add_argument("--arquivo", type=Path, default=ARQUIVO_PADRAO, help=argparse.SUPPRESS)
    r.set_defaults(comando=_reenviar)

    st = sub.add_parser("status", help="mostra quem já recebeu o SMS, sem revelar o sorteio")
    st.add_argument("--arquivo", type=Path, default=ARQUIVO_PADRAO, help=argparse.SUPPRESS)
    st.set_defaults(comando=_status)
    return p


def _sortear(args, enviador) -> int:
    if "{nome}" not in args.mensagem or "{amiga}" not in args.mensagem:
        raise ErroDeUso("a mensagem precisa ter {nome} e {amiga}")
    try:
        args.mensagem.format(nome="", amiga="")
    except (KeyError, IndexError, ValueError):
        raise ErroDeUso("a mensagem só pode ter os marcadores {nome} e {amiga}; "
                        "para escrever uma chave, use {{ ou }}") from None
    if not args.simular and args.arquivo.exists() and not args.novo:
        raise ErroDeUso(f"já existe um sorteio em {args.arquivo}. Use 'reenviar' para quem não recebeu, "
                        "ou 'sortear --novo' para descartá-lo e sortear de novo")

    lista = participantes.carregar(args.lista)
    pares = sorteio.sortear([p.nome for p in lista])
    envios = [{"nome": p.nome, "telefone": p.telefone, "amiga": pares[p.nome], "enviado": False} for p in lista]
    dados = {"criado_em": datetime.now().isoformat(timespec="seconds"), "mensagem": args.mensagem, "envios": envios}

    if args.simular:
        enviador = enviador or sms.Simulador()
        print(f"Simulação com {len(lista)} participantes: nenhuma caiu com o próprio nome.")
        for e in dados["envios"]:
            enviador.enviar(e["telefone"], dados["mensagem"].format(nome=e["nome"], amiga=e["amiga"]))
            print(f"  SMS pronto para {e['nome']} ({e['telefone']})")
        print("Nada foi enviado nem salvo.")
        return 0

    enviador = enviador or sms.Twilio.do_ambiente()
    _salvar(args.arquivo, dados)
    print(f"Sorteio feito com {len(lista)} participantes. Enviando os SMS...")
    return _enviar_todos(dados, enviador, args.arquivo)


def _reenviar(args, enviador) -> int:
    dados = _abrir(args.arquivo)
    if args.nome:
        alvo = [e for e in dados["envios"] if e["nome"].casefold() == args.nome.strip().casefold()]
        if not alvo:
            raise ErroDeUso(f"{args.nome} não está neste sorteio")
        alvo[0]["enviado"] = False
    elif all(e["enviado"] for e in dados["envios"]):
        print("Todas já receberam o SMS.")
        return 0
    return _enviar_todos(dados, enviador or sms.Twilio.do_ambiente(), args.arquivo)


def _status(args, _enviador) -> int:
    dados = _abrir(args.arquivo)
    print(f"Sorteio de {dados['criado_em']}:")
    for e in dados["envios"]:
        print(f"  {'✓' if e['enviado'] else '✗'} {e['nome']} ({e['telefone']})")
    return 0


def _enviar_todos(dados: dict, enviador, arquivo: Path) -> int:
    falhas = 0
    for e in dados["envios"]:
        if e["enviado"]:
            continue
        texto = dados["mensagem"].format(nome=e["nome"], amiga=e["amiga"])
        try:
            enviador.enviar(e["telefone"], texto)
        except sms.FalhaNoEnvio as erro:
            falhas += 1
            print(f"  ✗ {e['nome']} ({e['telefone']}): {erro}")
            continue
        e["enviado"] = True
        _salvar(arquivo, dados)  # a cada envio, para um erro no meio não reenviar a quem já recebeu
        print(f"  ✓ {e['nome']} ({e['telefone']})")
    if falhas:
        print(f"{falhas} SMS não foram enviados. Corrija o problema e rode: python -m amigo_secreto reenviar")
        return 2
    print("Pronto! Todas receberam o SMS.")
    return 0


def _salvar(arquivo: Path, dados: dict) -> None:
    temporario = arquivo.with_name(arquivo.name + ".tmp")
    fd = os.open(temporario, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(temporario, arquivo)


def _abrir(arquivo: Path) -> dict:
    try:
        return json.loads(arquivo.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ErroDeUso(f"nenhum sorteio encontrado em {arquivo}; rode 'sortear' primeiro") from None

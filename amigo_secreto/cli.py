"""Linha de comando: sortear, reenviar e ver quem já recebeu.

Nada aqui imprime quem tirou quem, para que quem organiza também possa
participar sem saber o resultado.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from . import participantes, sorteio, whatsapp

MENSAGEM_PADRAO = "Oi, {nome}! 🎁 No amigo secreto você tirou: *{amiga}*. Shh, é segredo! 🤫"
ARQUIVO_PADRAO = Path("sorteio.json")

# Quanto esperar o Twilio confirmar as mensagens: até 15 rodadas de 2 segundos.
RODADAS_DE_CONFIRMACAO = 15
INTERVALO_DE_CONFIRMACAO = 2.0

PENDENTE, AGUARDANDO, ENTREGUE = "pendente", "aguardando", "entregue"


def main(argv: list[str] | None = None, enviador=None, dormir=time.sleep) -> int:
    args = _parser().parse_args(argv)
    args.dormir = dormir
    try:
        return args.comando(args, enviador)
    except (participantes.ListaInvalida, sorteio.SorteioInvalido, whatsapp.FalhaNoEnvio, ErroDeUso) as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1


class ErroDeUso(Exception):
    pass


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="amigo-secreto", description="Sorteio de amigo secreto com envio por WhatsApp.")
    sub = p.add_subparsers(required=True, metavar="comando")

    s = sub.add_parser("sortear", help="faz o sorteio e manda uma mensagem no WhatsApp de cada participante")
    s.add_argument("lista", type=Path, help="CSV com as colunas nome, telefone e (opcional) grupo")
    s.add_argument("--simular", action="store_true", help="faz tudo, menos enviar e salvar (não revela o resultado)")
    s.add_argument("--mensagem", default=MENSAGEM_PADRAO, help="texto da mensagem, com {nome} e {amiga}")
    s.add_argument("--novo", action="store_true", help="descarta um sorteio anterior e sorteia de novo")
    s.add_argument("--arquivo", type=Path, default=ARQUIVO_PADRAO, help=argparse.SUPPRESS)
    s.set_defaults(comando=_sortear)

    r = sub.add_parser("reenviar", help="confirma as mensagens pendentes e envia de novo as que falharam")
    r.add_argument("--nome", help="reenvia para esta pessoa, mesmo que já tenha recebido")
    r.add_argument("--arquivo", type=Path, default=ARQUIVO_PADRAO, help=argparse.SUPPRESS)
    r.set_defaults(comando=_reenviar)

    st = sub.add_parser("status", help="mostra quem já recebeu a mensagem, sem revelar o sorteio")
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
    pares = sorteio.sortear([p.nome for p in lista], participantes.grupos(lista))
    envios = [{"nome": p.nome, "telefone": p.telefone, "amiga": pares[p.nome], "situacao": PENDENTE, "sid": None}
              for p in lista]
    dados = {"criado_em": datetime.now().isoformat(timespec="seconds"), "mensagem": args.mensagem, "envios": envios}

    if args.simular:
        enviador = enviador or whatsapp.Simulador()
        print(f"Simulação com {len(lista)} participantes: nenhuma caiu com o próprio nome"
              + (" nem com alguém do mesmo grupo." if participantes.grupos(lista) else "."))
        for e in dados["envios"]:
            enviador.enviar(e["telefone"], _texto(dados, e))
            print(f"  Mensagem pronta para {e['nome']} ({e['telefone']})")
        print("Nada foi enviado nem salvo.")
        return 0

    enviador = enviador or whatsapp.TwilioWhatsApp.do_ambiente()
    _salvar(args.arquivo, dados)
    print(f"Sorteio feito com {len(lista)} participantes. Enviando pelo WhatsApp...")
    return _enviar_e_confirmar(dados, enviador, args.arquivo, args.dormir)


def _reenviar(args, enviador) -> int:
    dados = _abrir(args.arquivo)
    if args.nome:
        alvo = [e for e in dados["envios"] if e["nome"].casefold() == args.nome.strip().casefold()]
        if not alvo:
            raise ErroDeUso(f"{args.nome} não está neste sorteio")
        alvo[0]["situacao"] = PENDENTE
    elif all(e["situacao"] == ENTREGUE for e in dados["envios"]):
        print("Todas já receberam a mensagem.")
        return 0
    return _enviar_e_confirmar(dados, enviador or whatsapp.TwilioWhatsApp.do_ambiente(), args.arquivo, args.dormir)


def _status(args, _enviador) -> int:
    dados = _abrir(args.arquivo)
    print(f"Sorteio de {dados['criado_em']}:")
    for e in dados["envios"]:
        print(f"  {_ICONES[e['situacao']]} {e['nome']} ({e['telefone']})")
    print("✓ recebeu   ⏳ aguardando confirmação do WhatsApp   ✗ não recebeu")
    return 0


_ICONES = {ENTREGUE: "✓", AGUARDANDO: "⏳", PENDENTE: "✗"}


def _enviar_e_confirmar(dados: dict, enviador, arquivo: Path, dormir) -> int:
    for e in dados["envios"]:
        if e["situacao"] != PENDENTE:
            continue
        try:
            e["sid"] = enviador.enviar(e["telefone"], _texto(dados, e))
        except whatsapp.FalhaNoEnvio as erro:
            print(f"  ✗ {e['nome']} ({e['telefone']}): {erro}")
            continue
        e["situacao"] = AGUARDANDO
        _salvar(arquivo, dados)  # a cada envio, para um erro no meio não reenviar a quem já recebeu

    _confirmar(dados, enviador, arquivo, dormir)

    contagem = {s: sum(e["situacao"] == s for e in dados["envios"]) for s in _ICONES}
    if contagem[PENDENTE]:
        print(f"{contagem[PENDENTE]} não receberam. Resolva o problema e rode: python3 -m amigo_secreto reenviar")
    if contagem[AGUARDANDO]:
        print(f"{contagem[AGUARDANDO]} ainda sem confirmação do WhatsApp. "
              "Rode 'python3 -m amigo_secreto reenviar' daqui a pouco para conferir.")
    if contagem[PENDENTE] or contagem[AGUARDANDO]:
        return 2
    print("Pronto! Todas receberam a mensagem.")
    return 0


def _confirmar(dados: dict, enviador, arquivo: Path, dormir) -> None:
    for rodada in range(RODADAS_DE_CONFIRMACAO):
        aguardando = [e for e in dados["envios"] if e["situacao"] == AGUARDANDO]
        if not aguardando:
            return
        if rodada:
            dormir(INTERVALO_DE_CONFIRMACAO)
        for e in aguardando:
            try:
                situacao = enviador.consultar(e["sid"])
            except whatsapp.FalhaNoEnvio:
                continue  # tenta de novo na próxima rodada
            if not situacao.final:
                continue
            if situacao.chegou:
                e["situacao"] = ENTREGUE
                print(f"  ✓ {e['nome']} ({e['telefone']})")
            else:
                e["situacao"] = PENDENTE
                print(f"  ✗ {e['nome']} ({e['telefone']}): {situacao.detalhe}")
            _salvar(arquivo, dados)


def _texto(dados: dict, envio: dict) -> str:
    return dados["mensagem"].format(nome=envio["nome"], amiga=envio["amiga"])


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

"""Linha de comando: sortear e reabrir a página de envio.

Nada aqui imprime quem tirou quem, para que quem organiza também possa
participar sem saber o resultado.
"""

import argparse
import json
import os
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from . import links, pagina, participantes, sorteio

MENSAGEM_PADRAO = ("Oi, {nome}! 🎁 O amigo secreto foi sorteado. Abra o seu link para descobrir quem você tirou "
                   "(ele é só seu, não repasse): {link}")
ARQUIVO_PADRAO = Path("sorteio.json")


def main(argv: list[str] | None = None, abrir=webbrowser.open) -> int:
    args = _parser().parse_args(argv)
    args.abrir = abrir
    try:
        return args.comando(args)
    except (participantes.ListaInvalida, sorteio.SorteioInvalido, ErroDeUso) as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1


class ErroDeUso(Exception):
    pass


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="amigo-secreto",
                                description="Sorteio de amigo secreto com links secretos enviados pelo WhatsApp.")
    sub = p.add_subparsers(required=True, metavar="comando")

    s = sub.add_parser("sortear", help="faz o sorteio e cria a página com os botões de envio")
    s.add_argument("lista", type=Path, help="CSV com as colunas nome, telefone e (opcional) grupo")
    s.add_argument("--simular", action="store_true", help="confere a lista e sorteia, sem salvar nada")
    s.add_argument("--mensagem", default=MENSAGEM_PADRAO, help="texto da mensagem, com {link} e, se quiser, {nome}")
    s.add_argument("--site", default=links.SITE_PADRAO, help="endereço da página de revelação")
    s.add_argument("--novo", action="store_true", help="descarta um sorteio anterior e sorteia de novo")
    s.add_argument("--nao-abrir", action="store_true", help="não abre a página de envio no navegador")
    s.add_argument("--arquivo", type=Path, default=ARQUIVO_PADRAO, help=argparse.SUPPRESS)
    s.set_defaults(comando=_sortear)

    r = sub.add_parser("reenviar", help="recria a página de envio do sorteio salvo, com os mesmos links")
    r.add_argument("--nome", help="só o botão desta pessoa")
    r.add_argument("--nao-abrir", action="store_true", help="não abre a página de envio no navegador")
    r.add_argument("--arquivo", type=Path, default=ARQUIVO_PADRAO, help=argparse.SUPPRESS)
    r.set_defaults(comando=_reenviar)
    return p


def _conferir_mensagem(mensagem: str) -> None:
    if "{amiga}" in mensagem:
        raise ErroDeUso("a mensagem não pode ter {amiga}: o nome ficaria escrito na sua conversa. "
                        "Quem recebe descobre pelo link")
    if "{link}" not in mensagem:
        raise ErroDeUso("a mensagem precisa ter {link}")
    try:
        mensagem.format(nome="", link="")
    except (KeyError, IndexError, ValueError):
        raise ErroDeUso("a mensagem só pode ter os marcadores {nome} e {link}; "
                        "para escrever uma chave, use {{ ou }}") from None


def _sortear(args) -> int:
    _conferir_mensagem(args.mensagem)
    if not args.site.startswith("https://"):
        raise ErroDeUso("o endereço da página de revelação precisa começar com https://")
    if not args.simular and args.arquivo.exists() and not args.novo:
        raise ErroDeUso(f"já existe um sorteio em {args.arquivo}. Use 'reenviar' para abrir de novo a página "
                        "de envio, ou 'sortear --novo' para descartá-lo e sortear de novo")

    lista = participantes.carregar(args.lista)
    grupos = participantes.grupos(lista)
    pares = sorteio.sortear([p.nome for p in lista], grupos)
    if args.simular:
        print(f"Simulação com {len(lista)} participantes: nenhuma caiu com o próprio nome"
              + (" nem com alguém do mesmo grupo." if grupos else "."))
        print("Nada foi salvo.")
        return 0

    dados = {
        "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "mensagem": args.mensagem,
        "envios": [{"nome": p.nome, "telefone": p.telefone,
                    "link": links.link_secreto(args.site, links.gerar_token(p.nome, pares[p.nome]))}
                   for p in lista],
    }
    _salvar(args.arquivo, json.dumps(dados, ensure_ascii=False, indent=2))
    print(f"Sorteio feito com {len(lista)} participantes.")
    return _criar_pagina(args, dados, dados["envios"])


def _reenviar(args) -> int:
    try:
        dados = json.loads(args.arquivo.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ErroDeUso(f"nenhum sorteio encontrado em {args.arquivo}; rode 'sortear' primeiro") from None
    envios = dados["envios"]
    if args.nome:
        envios = [e for e in envios if e["nome"].casefold() == args.nome.strip().casefold()]
        if not envios:
            raise ErroDeUso(f"{args.nome} não está neste sorteio")
    return _criar_pagina(args, dados, envios)


def _criar_pagina(args, dados: dict, envios: list[dict]) -> int:
    botoes = [(e["nome"], e["telefone"],
               links.link_whatsapp(e["telefone"], dados["mensagem"].format(nome=e["nome"], link=e["link"])))
              for e in envios]
    destino = args.arquivo.with_name("enviar.html")
    _salvar(destino, pagina.montar(botoes, dados["criado_em"]))
    print(f"Página de envio: {destino.resolve()}")
    print("Toque em cada botão para abrir o WhatsApp com a mensagem pronta. Não abra os links das mensagens.")
    if not args.nao_abrir:
        args.abrir(destino.resolve().as_uri())
    return 0


def _salvar(arquivo: Path, conteudo: str) -> None:
    temporario = arquivo.with_name(arquivo.name + ".tmp")
    fd = os.open(temporario, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(conteudo)
    os.replace(temporario, arquivo)

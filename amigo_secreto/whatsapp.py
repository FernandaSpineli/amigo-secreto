"""Envio por WhatsApp pelo Twilio, chamado direto pela API REST, sem dependências.

O Twilio aceita a mensagem na hora e só depois diz se ela chegou ao WhatsApp
ou falhou (por exemplo, quando a pessoa ainda não entrou no sandbox). Por isso
há dois passos: `enviar` devolve o identificador da mensagem e `consultar`
diz em que pé ela está.
"""

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class FalhaNoEnvio(RuntimeError):
    pass


@dataclass(frozen=True)
class Situacao:
    final: bool  # o Twilio já decidiu: chegou ou falhou
    chegou: bool
    detalhe: str = ""


# https://www.twilio.com/docs/api/errors
ERROS_CONHECIDOS = {
    "63003": "este número não tem WhatsApp",
    "63015": "ainda não entrou no sandbox do Twilio (precisa mandar a mensagem 'join ...' para o número do Twilio)",
    "63016": "passou a janela de 24 horas: peça para ela mandar qualquer mensagem para o número do Twilio",
}

CHEGOU = {"sent", "delivered", "read"}
FALHOU = {"failed", "undelivered", "canceled"}


class TwilioWhatsApp:
    def __init__(self, account_sid: str, auth_token: str, remetente: str, timeout: float = 15):
        self.base = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages"
        credenciais = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
        self.autorizacao = f"Basic {credenciais}"
        self.remetente = _com_prefixo(remetente)
        self.timeout = timeout

    @classmethod
    def do_ambiente(cls) -> "TwilioWhatsApp":
        variaveis = ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM")
        faltando = [v for v in variaveis if not os.environ.get(v)]
        if faltando:
            raise FalhaNoEnvio("defina as variáveis de ambiente: " + ", ".join(faltando))
        return cls(*(os.environ[v] for v in variaveis))

    def enviar(self, telefone: str, texto: str) -> str:
        corpo = urllib.parse.urlencode({"From": self.remetente, "To": _com_prefixo(telefone), "Body": texto})
        return self._pedir(f"{self.base}.json", corpo.encode())["sid"]

    def consultar(self, sid: str) -> Situacao:
        mensagem = self._pedir(f"{self.base}/{sid}.json")
        status = mensagem.get("status", "")
        if status in CHEGOU:
            return Situacao(final=True, chegou=True)
        if status in FALHOU:
            codigo = str(mensagem.get("error_code") or "")
            detalhe = ERROS_CONHECIDOS.get(codigo, f"não foi entregue (erro {codigo or status} do Twilio)")
            return Situacao(final=True, chegou=False, detalhe=detalhe)
        return Situacao(final=False, chegou=False)

    def _pedir(self, url: str, corpo: bytes | None = None) -> dict:
        cabecalhos = {"Authorization": self.autorizacao}
        if corpo is not None:
            cabecalhos["Content-Type"] = "application/x-www-form-urlencoded"
        pedido = urllib.request.Request(url, data=corpo, method="POST" if corpo else "GET", headers=cabecalhos)
        try:
            with urllib.request.urlopen(pedido, timeout=self.timeout) as resposta:
                return json.loads(resposta.read())
        except urllib.error.HTTPError as e:
            raise FalhaNoEnvio(_mensagem_do_twilio(e)) from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise FalhaNoEnvio(f"sem conexão com o Twilio: {e}") from None


def _com_prefixo(numero: str) -> str:
    numero = numero.strip()
    return numero if numero.startswith("whatsapp:") else f"whatsapp:{numero}"


def _mensagem_do_twilio(e: urllib.error.HTTPError) -> str:
    try:
        dados = json.loads(e.read())
        return f"Twilio recusou ({e.code}): {dados.get('message', '')}".strip()
    except (ValueError, OSError):
        return f"Twilio recusou ({e.code})"


class Simulador:
    """Não envia nada: só guarda as mensagens montadas, sem mostrá-las."""

    def __init__(self):
        self.enviadas: list[tuple[str, str]] = []

    def enviar(self, telefone: str, texto: str) -> str:
        self.enviadas.append((telefone, texto))
        return f"SIM{len(self.enviadas)}"

    def consultar(self, sid: str) -> Situacao:
        return Situacao(final=True, chegou=True)

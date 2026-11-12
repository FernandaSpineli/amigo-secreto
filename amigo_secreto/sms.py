"""Envio de SMS. O Twilio é chamado direto pela API REST, sem dependências."""

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class FalhaNoEnvio(RuntimeError):
    pass


class Twilio:
    def __init__(self, account_sid: str, auth_token: str, remetente: str, timeout: float = 15):
        self.url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        credenciais = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
        self.autorizacao = f"Basic {credenciais}"
        self.remetente = remetente
        self.timeout = timeout

    @classmethod
    def do_ambiente(cls) -> "Twilio":
        faltando = [v for v in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM") if not os.environ.get(v)]
        if faltando:
            raise FalhaNoEnvio("defina as variáveis de ambiente: " + ", ".join(faltando))
        return cls(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"], os.environ["TWILIO_FROM"])

    def enviar(self, telefone: str, texto: str) -> None:
        corpo = urllib.parse.urlencode({"From": self.remetente, "To": telefone, "Body": texto}).encode()
        pedido = urllib.request.Request(self.url, data=corpo, method="POST", headers={
            "Authorization": self.autorizacao,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        try:
            with urllib.request.urlopen(pedido, timeout=self.timeout):
                return
        except urllib.error.HTTPError as e:
            raise FalhaNoEnvio(_mensagem_do_twilio(e)) from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise FalhaNoEnvio(f"sem conexão com o Twilio: {e}") from None


def _mensagem_do_twilio(e: urllib.error.HTTPError) -> str:
    try:
        dados = json.loads(e.read())
        return f"Twilio recusou ({e.code}): {dados.get('message', '')}".strip()
    except (ValueError, OSError):
        return f"Twilio recusou ({e.code})"


class Simulador:
    """Não envia nada e não revela quem tirou quem: só confirma que cada
    mensagem foi montada para o telefone certo."""

    def __init__(self):
        self.enviadas: list[tuple[str, str]] = []

    def enviar(self, telefone: str, texto: str) -> None:
        self.enviadas.append((telefone, texto))

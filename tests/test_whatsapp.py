import base64
import io
import json
import unittest
import urllib.error
import urllib.parse
from unittest import mock

from amigo_secreto.whatsapp import FalhaNoEnvio, Situacao, TwilioWhatsApp

BASE = "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages"


def responde(dados: dict):
    resposta = mock.MagicMock()
    resposta.__enter__.return_value = io.BytesIO(json.dumps(dados).encode())
    return resposta


class TwilioWhatsAppTest(unittest.TestCase):
    def setUp(self):
        self.twilio = TwilioWhatsApp("AC123", "segredo", "+14155238886")

    def test_envia_pelo_canal_do_whatsapp_e_devolve_o_sid(self):
        with mock.patch("urllib.request.urlopen", return_value=responde({"sid": "SM1", "status": "queued"})) as u:
            sid = self.twilio.enviar("+5511900000001", "Oi, Ana! Você tirou: *Bia* 🤫")

        self.assertEqual(sid, "SM1")
        pedido = u.call_args.args[0]
        self.assertEqual(pedido.full_url, f"{BASE}.json")
        self.assertEqual(pedido.get_method(), "POST")
        self.assertEqual(pedido.get_header("Authorization"), "Basic " + base64.b64encode(b"AC123:segredo").decode())
        corpo = urllib.parse.parse_qs(pedido.data.decode())
        self.assertEqual(corpo, {"From": ["whatsapp:+14155238886"], "To": ["whatsapp:+5511900000001"],
                                 "Body": ["Oi, Ana! Você tirou: *Bia* 🤫"]})

    def test_remetente_ja_com_prefixo_nao_ganha_outro(self):
        self.assertEqual(TwilioWhatsApp("AC1", "t", "whatsapp:+14155238886").remetente, "whatsapp:+14155238886")

    def test_consultar(self):
        casos = {
            "queued": Situacao(final=False, chegou=False),
            "sending": Situacao(final=False, chegou=False),
            "sent": Situacao(final=True, chegou=True),
            "delivered": Situacao(final=True, chegou=True),
            "read": Situacao(final=True, chegou=True),
        }
        for status, esperado in casos.items():
            with mock.patch("urllib.request.urlopen", return_value=responde({"status": status})) as u:
                self.assertEqual(self.twilio.consultar("SM1"), esperado, status)
            self.assertEqual(u.call_args.args[0].full_url, f"{BASE}/SM1.json")
            self.assertEqual(u.call_args.args[0].get_method(), "GET")

    def test_consultar_explica_as_falhas_mais_comuns(self):
        casos = {
            ("failed", 63015): "sandbox",
            ("undelivered", 63016): "24 horas",
            ("failed", 63003): "não tem WhatsApp",
            ("failed", 30008): "erro 30008",
            ("undelivered", None): "erro undelivered",
        }
        for (status, codigo), trecho in casos.items():
            with mock.patch("urllib.request.urlopen", return_value=responde({"status": status, "error_code": codigo})):
                situacao = self.twilio.consultar("SM1")
            self.assertTrue(situacao.final and not situacao.chegou)
            self.assertIn(trecho, situacao.detalhe)

    def test_erro_da_api_vira_falha_com_a_mensagem_do_twilio(self):
        erro = urllib.error.HTTPError("url", 400, "Bad Request", {},
                                      io.BytesIO(b'{"message": "Invalid From Number"}'))
        with mock.patch("urllib.request.urlopen", side_effect=erro):
            with self.assertRaisesRegex(FalhaNoEnvio, "400.*Invalid From"):
                self.twilio.enviar("+5511900000001", "oi")

    def test_sem_conexao(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            with self.assertRaisesRegex(FalhaNoEnvio, "sem conexão"):
                self.twilio.consultar("SM1")

    def test_le_as_credenciais_do_ambiente(self):
        with mock.patch.dict("os.environ", {"TWILIO_ACCOUNT_SID": "AC9", "TWILIO_AUTH_TOKEN": "t",
                                            "TWILIO_WHATSAPP_FROM": "+14155238886"}, clear=True):
            self.assertEqual(TwilioWhatsApp.do_ambiente().remetente, "whatsapp:+14155238886")
        with mock.patch.dict("os.environ", {"TWILIO_ACCOUNT_SID": "AC9"}, clear=True):
            with self.assertRaisesRegex(FalhaNoEnvio, "TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM"):
                TwilioWhatsApp.do_ambiente()


if __name__ == "__main__":
    unittest.main()

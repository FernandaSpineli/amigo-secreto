import base64
import io
import unittest
import urllib.error
import urllib.parse
from unittest import mock

from amigo_secreto.sms import FalhaNoEnvio, Twilio


class TwilioTest(unittest.TestCase):
    def setUp(self):
        self.twilio = Twilio("AC123", "segredo", "+15550001111")

    def test_monta_o_pedido_para_a_api(self):
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = io.BytesIO(b"{}")
            self.twilio.enviar("+5511900000001", "Oi, Ana! Você tirou: Bia 🤫")

        pedido = urlopen.call_args.args[0]
        self.assertEqual(pedido.full_url, "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json")
        self.assertEqual(pedido.get_method(), "POST")
        self.assertEqual(pedido.get_header("Authorization"), "Basic " + base64.b64encode(b"AC123:segredo").decode())
        corpo = urllib.parse.parse_qs(pedido.data.decode())
        self.assertEqual(corpo, {"From": ["+15550001111"], "To": ["+5511900000001"],
                                 "Body": ["Oi, Ana! Você tirou: Bia 🤫"]})

    def test_erro_da_api_vira_falha_com_a_mensagem_do_twilio(self):
        erro = urllib.error.HTTPError("url", 400, "Bad Request", {},
                                      io.BytesIO(b'{"message": "The number is unverified"}'))
        with mock.patch("urllib.request.urlopen", side_effect=erro):
            with self.assertRaisesRegex(FalhaNoEnvio, "400.*unverified"):
                self.twilio.enviar("+5511900000001", "oi")

    def test_sem_conexao(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            with self.assertRaisesRegex(FalhaNoEnvio, "sem conexão"):
                self.twilio.enviar("+5511900000001", "oi")

    def test_le_as_credenciais_do_ambiente(self):
        with mock.patch.dict("os.environ", {"TWILIO_ACCOUNT_SID": "AC9", "TWILIO_AUTH_TOKEN": "t",
                                            "TWILIO_FROM": "+1555"}, clear=True):
            self.assertEqual(Twilio.do_ambiente().remetente, "+1555")
        with mock.patch.dict("os.environ", {"TWILIO_ACCOUNT_SID": "AC9"}, clear=True):
            with self.assertRaisesRegex(FalhaNoEnvio, "TWILIO_AUTH_TOKEN, TWILIO_FROM"):
                Twilio.do_ambiente()


if __name__ == "__main__":
    unittest.main()

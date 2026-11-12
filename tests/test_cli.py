import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from amigo_secreto import sms
from amigo_secreto.cli import main

LISTA = "nome,telefone\nAna,11900000001\nBia,11900000002\nCarla,11900000003\nDuda,11900000004\nEva,11900000005\n"


class EnviadorFalso:
    def __init__(self, falhar_para=()):
        self.falhar_para = set(falhar_para)
        self.enviadas: list[tuple[str, str]] = []

    def enviar(self, telefone, texto):
        if telefone in self.falhar_para:
            raise sms.FalhaNoEnvio("número inválido")
        self.enviadas.append((telefone, texto))


class CliTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.lista = self.pasta / "participantes.csv"
        self.lista.write_text(LISTA, encoding="utf-8")
        self.arquivo = self.pasta / "sorteio.json"

    def rodar(self, *argv, enviador=None):
        saida, erro = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
            codigo = main([*argv, "--arquivo", str(self.arquivo)], enviador)
        return codigo, saida.getvalue() + erro.getvalue()

    def test_sortear_envia_um_sms_para_cada_uma_sem_revelar_no_terminal(self):
        enviador = EnviadorFalso()
        codigo, saida = self.rodar("sortear", str(self.lista), enviador=enviador)

        self.assertEqual(codigo, 0, saida)
        self.assertEqual(len(enviador.enviadas), 5)
        nomes = {"+5511900000001": "Ana", "+5511900000002": "Bia", "+5511900000003": "Carla",
                 "+5511900000004": "Duda", "+5511900000005": "Eva"}
        tiradas = []
        for telefone, texto in enviador.enviadas:
            nome = nomes[telefone]
            self.assertTrue(texto.startswith(f"Oi, {nome}!"), texto)
            amiga = texto.split("você tirou: ")[1].split(".")[0]
            self.assertNotEqual(amiga, nome)
            tiradas.append(amiga)
        self.assertEqual(sorted(tiradas), sorted(nomes.values()))
        self.assertNotIn("tirou", saida)

    def test_arquivo_do_sorteio_fica_so_com_a_dona(self):
        self.rodar("sortear", str(self.lista), enviador=EnviadorFalso())
        self.assertEqual(stat.S_IMODE(os.stat(self.arquivo).st_mode), 0o600)
        self.assertTrue(all(e["enviado"] for e in json.loads(self.arquivo.read_text())["envios"]))

    def test_simular_nao_envia_nem_salva(self):
        codigo, saida = self.rodar("sortear", str(self.lista), "--simular")
        self.assertEqual(codigo, 0, saida)
        self.assertFalse(self.arquivo.exists())
        self.assertNotIn("tirou", saida)

    def test_falha_no_meio_e_reenvio_so_para_quem_nao_recebeu(self):
        codigo, saida = self.rodar("sortear", str(self.lista), enviador=EnviadorFalso({"+5511900000003"}))
        self.assertEqual(codigo, 2)
        self.assertIn("✗ Carla", saida)
        self.assertIn("reenviar", saida)

        _, status = self.rodar("status")
        self.assertIn("✗ Carla", status)
        self.assertIn("✓ Ana", status)

        enviador = EnviadorFalso()
        codigo, saida = self.rodar("reenviar", enviador=enviador)
        self.assertEqual(codigo, 0, saida)
        self.assertEqual([t for t, _ in enviador.enviadas], ["+5511900000003"])

        codigo, saida = self.rodar("reenviar", enviador=EnviadorFalso())
        self.assertIn("Todas já receberam", saida)

    def test_reenviar_para_uma_pessoa_manda_o_mesmo_resultado(self):
        primeiro = EnviadorFalso()
        self.rodar("sortear", str(self.lista), enviador=primeiro)
        de_novo = EnviadorFalso()
        codigo, _ = self.rodar("reenviar", "--nome", "bia", enviador=de_novo)
        self.assertEqual(codigo, 0)
        texto_original = dict(primeiro.enviadas)["+5511900000002"]
        self.assertEqual(de_novo.enviadas, [("+5511900000002", texto_original)])

    def test_nao_sorteia_por_cima_de_um_sorteio_existente(self):
        self.rodar("sortear", str(self.lista), enviador=EnviadorFalso())
        antes = self.arquivo.read_text()
        enviador = EnviadorFalso()
        codigo, saida = self.rodar("sortear", str(self.lista), enviador=enviador)
        self.assertEqual(codigo, 1)
        self.assertIn("--novo", saida)
        self.assertEqual(enviador.enviadas, [])
        self.assertEqual(self.arquivo.read_text(), antes)

        codigo, _ = self.rodar("sortear", str(self.lista), "--novo", enviador=enviador)
        self.assertEqual(codigo, 0)
        self.assertEqual(len(enviador.enviadas), 5)

    def test_mensagem_personalizada(self):
        enviador = EnviadorFalso()
        self.rodar("sortear", str(self.lista), "--mensagem", "{nome}, presente para {amiga} até R$ 50",
                   enviador=enviador)
        self.assertRegex(enviador.enviadas[0][1], r"^Ana, presente para \w+ até R\$ 50$")

        codigo, saida = self.rodar("sortear", str(self.lista), "--novo", "--mensagem", "sem marcadores",
                                   enviador=EnviadorFalso())
        self.assertEqual(codigo, 1)
        self.assertIn("{amiga}", saida)

        codigo, saida = self.rodar("sortear", str(self.lista), "--novo", "--mensagem", "{nome}: {amiga} até {valor}",
                                   enviador=EnviadorFalso())
        self.assertEqual(codigo, 1)
        self.assertIn("só pode ter os marcadores", saida)

    def test_erros_viram_mensagem_e_codigo_1(self):
        self.lista.write_text("nome,telefone\nAna,11900000001\nBia,11900000002\n", encoding="utf-8")
        codigo, saida = self.rodar("sortear", str(self.lista), enviador=EnviadorFalso())
        self.assertEqual((codigo, saida.strip()), (1, "Erro: são precisas pelo menos 3 pessoas para o sorteio"))

        codigo, saida = self.rodar("reenviar", enviador=EnviadorFalso())
        self.assertIn("nenhum sorteio encontrado", saida)

    def test_sem_credenciais_do_twilio_nada_e_salvo(self):
        ambiente = {k: v for k, v in os.environ.items() if not k.startswith("TWILIO_")}
        with mock.patch.dict(os.environ, ambiente, clear=True):
            codigo, saida = self.rodar("sortear", str(self.lista))
        self.assertEqual(codigo, 1)
        self.assertIn("TWILIO_ACCOUNT_SID", saida)
        self.assertFalse(self.arquivo.exists())


if __name__ == "__main__":
    unittest.main()

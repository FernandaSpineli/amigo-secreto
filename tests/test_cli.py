import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from amigo_secreto import cli, whatsapp
from amigo_secreto.cli import main
from amigo_secreto.whatsapp import Situacao

LISTA = "nome,telefone\nAna,11900000001\nBia,11900000002\nCarla,11900000003\nDuda,11900000004\nEva,11900000005\n"
NOMES = {"+5511900000001": "Ana", "+5511900000002": "Bia", "+5511900000003": "Carla",
         "+5511900000004": "Duda", "+5511900000005": "Eva"}

CHEGOU = Situacao(final=True, chegou=True)
NA_FILA = Situacao(final=False, chegou=False)
FORA_DO_SANDBOX = Situacao(final=True, chegou=False, detalhe="ainda não entrou no sandbox do Twilio")


class EnviadorFalso:
    """Recusa na hora os telefones em `recusar`; para os demais, `consultar`
    devolve a sequência de situações de `respostas` (por padrão, chegou)."""

    def __init__(self, recusar=(), respostas=None):
        self.recusar = set(recusar)
        self.respostas = {t: list(r) for t, r in (respostas or {}).items()}
        self.enviadas: list[tuple[str, str]] = []
        self.sids: dict[str, str] = {}

    def enviar(self, telefone, texto):
        if telefone in self.recusar:
            raise whatsapp.FalhaNoEnvio("número inválido")
        self.enviadas.append((telefone, texto))
        sid = f"SM{len(self.enviadas)}"
        self.sids[sid] = telefone
        return sid

    def consultar(self, sid):
        fila = self.respostas.get(self.sids[sid])
        if not fila:
            return CHEGOU
        return fila.pop(0) if len(fila) > 1 else fila[0]


class CliTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.lista = self.pasta / "participantes.csv"
        self.lista.write_text(LISTA, encoding="utf-8")
        self.arquivo = self.pasta / "sorteio.json"
        self.esperas: list[float] = []

    def rodar(self, *argv, enviador=None):
        saida, erro = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
            codigo = main([*argv, "--arquivo", str(self.arquivo)], enviador, self.esperas.append)
        return codigo, saida.getvalue() + erro.getvalue()

    def situacoes(self):
        return {e["nome"]: e["situacao"] for e in json.loads(self.arquivo.read_text())["envios"]}

    def test_sortear_manda_uma_mensagem_para_cada_uma_sem_revelar_no_terminal(self):
        enviador = EnviadorFalso()
        codigo, saida = self.rodar("sortear", str(self.lista), enviador=enviador)

        self.assertEqual(codigo, 0, saida)
        self.assertEqual(len(enviador.enviadas), 5)
        tiradas = []
        for telefone, texto in enviador.enviadas:
            nome = NOMES[telefone]
            self.assertTrue(texto.startswith(f"Oi, {nome}!"), texto)
            amiga = texto.split("você tirou: *")[1].split("*")[0]
            self.assertNotEqual(amiga, nome)
            tiradas.append(amiga)
        self.assertEqual(sorted(tiradas), sorted(NOMES.values()))
        self.assertNotIn("tirou", saida)
        self.assertIn("Todas receberam", saida)
        self.assertEqual(set(self.situacoes().values()), {"entregue"})

    def test_casais_da_lista_nao_se_tiram(self):
        self.lista.write_text("nome,telefone,grupo\nAna,11900000001,casal A\nBia,11900000002,Casal A\n"
                              "Carla,11900000003,casal C\nDuda,11900000004,casal c\nEva,11900000005,\n",
                              encoding="utf-8")
        casal = {"Ana": "Bia", "Bia": "Ana", "Carla": "Duda", "Duda": "Carla"}
        for _ in range(30):
            enviador = EnviadorFalso()
            codigo, saida = self.rodar("sortear", str(self.lista), "--novo", enviador=enviador)
            self.assertEqual(codigo, 0, saida)
            for telefone, texto in enviador.enviadas:
                nome = NOMES[telefone]
                amiga = texto.split("você tirou: *")[1].split("*")[0]
                self.assertNotEqual(amiga, casal.get(nome), f"{nome} tirou o próprio par")

        codigo, saida = self.rodar("sortear", str(self.lista), "--simular")
        self.assertIn("nem com alguém do mesmo grupo", saida)

    def test_arquivo_do_sorteio_fica_so_com_a_dona(self):
        self.rodar("sortear", str(self.lista), enviador=EnviadorFalso())
        self.assertEqual(stat.S_IMODE(os.stat(self.arquivo).st_mode), 0o600)

    def test_simular_nao_envia_nem_salva(self):
        codigo, saida = self.rodar("sortear", str(self.lista), "--simular")
        self.assertEqual(codigo, 0, saida)
        self.assertFalse(self.arquivo.exists())
        self.assertNotIn("tirou", saida)

    def test_espera_a_confirmacao_do_whatsapp(self):
        enviador = EnviadorFalso(respostas={"+5511900000002": [NA_FILA, NA_FILA, CHEGOU]})
        codigo, saida = self.rodar("sortear", str(self.lista), enviador=enviador)
        self.assertEqual(codigo, 0, saida)
        self.assertEqual(self.esperas, [cli.INTERVALO_DE_CONFIRMACAO] * 2)
        self.assertEqual(self.situacoes()["Bia"], "entregue")

    def test_falha_depois_de_aceita_vira_pendente_com_o_motivo(self):
        enviador = EnviadorFalso(respostas={"+5511900000003": [NA_FILA, FORA_DO_SANDBOX]})
        codigo, saida = self.rodar("sortear", str(self.lista), enviador=enviador)

        self.assertEqual(codigo, 2)
        self.assertIn("✗ Carla (+5511900000003): ainda não entrou no sandbox", saida)
        self.assertIn("1 não receberam", saida)
        self.assertEqual(self.situacoes()["Carla"], "pendente")

        _, status = self.rodar("status")
        self.assertIn("✗ Carla", status)
        self.assertIn("✓ Ana", status)

        de_novo = EnviadorFalso()
        codigo, saida = self.rodar("reenviar", enviador=de_novo)
        self.assertEqual(codigo, 0, saida)
        self.assertEqual([t for t, _ in de_novo.enviadas], ["+5511900000003"])

        codigo, saida = self.rodar("reenviar", enviador=EnviadorFalso())
        self.assertIn("Todas já receberam", saida)

    def test_recusa_imediata_tambem_fica_pendente(self):
        codigo, saida = self.rodar("sortear", str(self.lista), enviador=EnviadorFalso(recusar={"+5511900000004"}))
        self.assertEqual(codigo, 2)
        self.assertIn("✗ Duda (+5511900000004): número inválido", saida)
        self.assertEqual(self.situacoes()["Duda"], "pendente")

    def test_sem_confirmacao_a_tempo_fica_aguardando_e_reenviar_confere_sem_mandar_de_novo(self):
        enviador = EnviadorFalso(respostas={"+5511900000005": [NA_FILA]})
        codigo, saida = self.rodar("sortear", str(self.lista), enviador=enviador)
        self.assertEqual(codigo, 2)
        self.assertEqual(len(self.esperas), cli.RODADAS_DE_CONFIRMACAO - 1)
        self.assertIn("1 ainda sem confirmação", saida)
        self.assertEqual(self.situacoes()["Eva"], "aguardando")
        _, status = self.rodar("status")
        self.assertIn("⏳ Eva", status)

        enviador.respostas = {}
        codigo, saida = self.rodar("reenviar", enviador=enviador)
        self.assertEqual(codigo, 0, saida)
        self.assertEqual(len(enviador.enviadas), 5, "não manda de novo para quem só faltava confirmar")
        self.assertEqual(self.situacoes()["Eva"], "entregue")

    def test_reenviar_para_uma_pessoa_manda_o_mesmo_resultado(self):
        primeiro = EnviadorFalso()
        self.rodar("sortear", str(self.lista), enviador=primeiro)
        de_novo = EnviadorFalso()
        codigo, _ = self.rodar("reenviar", "--nome", "bia", enviador=de_novo)
        self.assertEqual(codigo, 0)
        texto_original = dict(primeiro.enviadas)["+5511900000002"]
        self.assertEqual(de_novo.enviadas, [("+5511900000002", texto_original)])

        codigo, saida = self.rodar("reenviar", "--nome", "Zuleica", enviador=de_novo)
        self.assertEqual(codigo, 1)
        self.assertIn("não está neste sorteio", saida)

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
        self.assertIn("TWILIO_WHATSAPP_FROM", saida)
        self.assertFalse(self.arquivo.exists())


if __name__ == "__main__":
    unittest.main()

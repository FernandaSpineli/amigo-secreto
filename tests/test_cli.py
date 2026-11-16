import contextlib
import html
import io
import json
import os
import re
import stat
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from amigo_secreto.cli import main
from amigo_secreto.links import SITE_PADRAO, ler_token

LISTA = "nome,telefone\nAna,11900000001\nBia,11900000002\nCarla,11900000003\nDuda,11900000004\nEva,11900000005\n"
NOMES = {"5511900000001": "Ana", "5511900000002": "Bia", "5511900000003": "Carla",
         "5511900000004": "Duda", "5511900000005": "Eva"}


class CliTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.lista = self.pasta / "participantes.csv"
        self.lista.write_text(LISTA, encoding="utf-8")
        self.arquivo = self.pasta / "sorteio.json"
        self.pagina = self.pasta / "enviar.html"
        self.abertas: list[str] = []

    def rodar(self, *argv):
        saida, erro = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
            codigo = main([*argv, "--arquivo", str(self.arquivo)], self.abertas.append)
        return codigo, saida.getvalue() + erro.getvalue()

    def botoes(self) -> dict[str, str]:
        """{nome: texto da mensagem} a partir dos links do WhatsApp da página de envio."""
        conteudo = self.pagina.read_text(encoding="utf-8")
        resultado = {}
        for href in re.findall(r'href="([^"]+)"', conteudo):
            link = urllib.parse.urlsplit(html.unescape(href))
            self.assertEqual(link.netloc, "wa.me")
            resultado[NOMES[link.path.strip("/")]] = urllib.parse.parse_qs(link.query)["text"][0]
        return resultado

    def resultado(self) -> dict[str, str]:
        """Quem tirou quem, lido dos links secretos de cada mensagem."""
        pares = {}
        for nome, texto in self.botoes().items():
            token = re.search(r"#([A-Za-z0-9_-]+)", texto).group(1)
            dados = ler_token(token)
            self.assertEqual(dados["nome"], nome)
            pares[nome] = dados["amiga"]
        return pares

    def test_sortear_cria_um_botao_por_pessoa_com_o_link_secreto(self):
        codigo, saida = self.rodar("sortear", str(self.lista))

        self.assertEqual(codigo, 0, saida)
        self.assertEqual(self.abertas, [self.pagina.resolve().as_uri()])
        botoes = self.botoes()
        self.assertEqual(sorted(botoes), sorted(NOMES.values()))
        for nome, texto in botoes.items():
            self.assertTrue(texto.startswith(f"Oi, {nome}!"), texto)
            self.assertIn(f"{SITE_PADRAO}#", texto)
        pares = self.resultado()
        self.assertEqual(sorted(pares.values()), sorted(NOMES.values()))
        for quem, tirou in pares.items():
            self.assertNotEqual(quem, tirou)

    def test_nada_revela_o_resultado_a_quem_organiza(self):
        self.rodar("sortear", str(self.lista))
        pares = self.resultado()
        pagina = self.pagina.read_text(encoding="utf-8")
        for nome, texto in self.botoes().items():
            self.assertNotIn(pares[nome], texto.replace(f"Oi, {nome}!", ""), "o nome tirado não vai no texto")
        for href in re.findall(r'href="([^"]+)"', pagina):
            for amiga in pares.values():
                self.assertNotIn(amiga, href.split("?text=")[1].split("%23")[1])

    def test_arquivos_ficam_so_com_a_dona(self):
        self.rodar("sortear", str(self.lista))
        for arquivo in (self.arquivo, self.pagina):
            self.assertEqual(stat.S_IMODE(os.stat(arquivo).st_mode), 0o600)

    def test_simular_nao_salva_nada(self):
        codigo, saida = self.rodar("sortear", str(self.lista), "--simular")
        self.assertEqual(codigo, 0, saida)
        self.assertFalse(self.arquivo.exists())
        self.assertFalse(self.pagina.exists())
        self.assertEqual(self.abertas, [])

    def test_nao_abrir(self):
        self.rodar("sortear", str(self.lista), "--nao-abrir")
        self.assertTrue(self.pagina.exists())
        self.assertEqual(self.abertas, [])

    def test_reenviar_recria_a_pagina_com_os_mesmos_links(self):
        self.rodar("sortear", str(self.lista))
        antes = self.botoes()
        self.pagina.unlink()

        codigo, saida = self.rodar("reenviar")
        self.assertEqual(codigo, 0, saida)
        self.assertEqual(self.botoes(), antes)

        codigo, _ = self.rodar("reenviar", "--nome", "bia")
        self.assertEqual(codigo, 0)
        self.assertEqual(self.botoes(), {"Bia": antes["Bia"]})

        codigo, saida = self.rodar("reenviar", "--nome", "Zuleica")
        self.assertEqual(codigo, 1)
        self.assertIn("não está neste sorteio", saida)

    def test_casais_da_lista_nao_se_tiram(self):
        self.lista.write_text("nome,telefone,grupo\nAna,11900000001,casal A\nBia,11900000002,Casal A\n"
                              "Carla,11900000003,casal C\nDuda,11900000004,casal c\nEva,11900000005,\n",
                              encoding="utf-8")
        casal = {"Ana": "Bia", "Bia": "Ana", "Carla": "Duda", "Duda": "Carla"}
        for _ in range(30):
            codigo, saida = self.rodar("sortear", str(self.lista), "--novo")
            self.assertEqual(codigo, 0, saida)
            for quem, tirou in self.resultado().items():
                self.assertNotEqual(tirou, casal.get(quem), f"{quem} tirou o próprio par")

        codigo, saida = self.rodar("sortear", str(self.lista), "--simular")
        self.assertIn("nem com alguém do mesmo grupo", saida)

    def test_nao_sorteia_por_cima_de_um_sorteio_existente(self):
        self.rodar("sortear", str(self.lista))
        antes = self.arquivo.read_text()
        codigo, saida = self.rodar("sortear", str(self.lista))
        self.assertEqual(codigo, 1)
        self.assertIn("--novo", saida)
        self.assertEqual(self.arquivo.read_text(), antes)

        codigo, _ = self.rodar("sortear", str(self.lista), "--novo")
        self.assertEqual(codigo, 0)
        self.assertNotEqual(self.arquivo.read_text(), antes)

    def test_mensagem_e_site_personalizados(self):
        self.rodar("sortear", str(self.lista), "--mensagem", "{nome}, presente até R$ 50: {link}",
                   "--site", "https://exemplo.github.io/as/revelar.html")
        self.assertRegex(self.botoes()["Ana"], r"^Ana, presente até R\$ 50: https://exemplo\.github\.io/as/revelar\.html#")

    def test_mensagens_recusadas(self):
        casos = {
            "{nome} tirou {amiga}: {link}": "não pode ter {amiga}",
            "{nome}, sem link": "precisa ter {link}",
            "{nome}: {link} até {valor}": "só pode ter os marcadores",
        }
        for mensagem, trecho in casos.items():
            codigo, saida = self.rodar("sortear", str(self.lista), "--mensagem", mensagem)
            self.assertEqual(codigo, 1, mensagem)
            self.assertIn(trecho, saida)
        codigo, saida = self.rodar("sortear", str(self.lista), "--site", "http://inseguro.com/r.html")
        self.assertEqual(codigo, 1)
        self.assertIn("https://", saida)
        self.assertFalse(self.arquivo.exists())

    def test_erros_viram_mensagem_e_codigo_1(self):
        self.lista.write_text("nome,telefone\nAna,11900000001\nBia,11900000002\n", encoding="utf-8")
        codigo, saida = self.rodar("sortear", str(self.lista))
        self.assertEqual((codigo, saida.strip()), (1, "Erro: são precisas pelo menos 3 pessoas para o sorteio"))

        codigo, saida = self.rodar("reenviar")
        self.assertIn("nenhum sorteio encontrado", saida)

    def test_nomes_com_caracteres_especiais_ficam_seguros_na_pagina(self):
        self.lista.write_text('nome,telefone\n<b>Ana</b>,11900000001\nBia & Cia,11900000002\n"Carla ""C""",11900000003\n',
                              encoding="utf-8")
        codigo, _ = self.rodar("sortear", str(self.lista))
        self.assertEqual(codigo, 0)
        pagina = self.pagina.read_text(encoding="utf-8")
        self.assertNotIn("<b>Ana</b>", pagina)
        self.assertIn("&lt;b&gt;Ana&lt;/b&gt;", pagina)
        self.assertIn("Bia &amp; Cia", pagina)


if __name__ == "__main__":
    unittest.main()

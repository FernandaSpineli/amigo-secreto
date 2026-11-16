import json
import shutil
import subprocess
import unittest
import urllib.parse
from pathlib import Path

from amigo_secreto.links import gerar_token, ler_token, link_secreto, link_whatsapp

REVELAR_JS = Path(__file__).parent.parent / "docs" / "revelar.js"


class TokenTest(unittest.TestCase):
    def test_ida_e_volta(self):
        for nome, amiga in [("Ana", "Bia"), ("Júlia", "Úrsula 🎄"), ("Ana S.", "José da Silva Ç")]:
            self.assertEqual(ler_token(gerar_token(nome, amiga)), {"v": 1, "nome": nome, "amiga": amiga})

    def test_o_nome_nao_aparece_no_link(self):
        for _ in range(200):
            token = gerar_token("Gui", "Matias")
            for trecho in ("Matias", "TWF0aWFz", "Gui"):
                self.assertNotIn(trecho, token)

    def test_cada_link_e_diferente_mesmo_com_o_mesmo_resultado(self):
        self.assertEqual(len({gerar_token("Ana", "Bia") for _ in range(50)}), 50)

    def test_token_cabe_numa_url_sem_escapar(self):
        token = gerar_token("Ana", "Bia")
        self.assertEqual(urllib.parse.quote(token, safe=""), token)

    def test_link_secreto_usa_o_fragmento(self):
        self.assertEqual(link_secreto("https://exemplo.github.io/revelar.html", "abc"),
                         "https://exemplo.github.io/revelar.html#abc")


class WhatsAppTest(unittest.TestCase):
    def test_link_do_whatsapp_com_texto_codificado(self):
        link = link_whatsapp("+5516994004353", "Oi, Gui! 🎁 Abra: https://x.io/r.html#a-b_c")
        self.assertTrue(link.startswith("https://wa.me/5516994004353?text="))
        texto = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query)["text"][0]
        self.assertEqual(texto, "Oi, Gui! 🎁 Abra: https://x.io/r.html#a-b_c")
        self.assertNotIn("#", link, "o # do link secreto precisa ir codificado, senão vira fragmento do wa.me")


@unittest.skipUnless(shutil.which("node"), "precisa do Node para testar o JavaScript da página")
class PaginaDeRevelacaoTest(unittest.TestCase):
    def ler_no_navegador(self, token: str):
        script = ("const { lerToken } = require(process.argv[1]);"
                  "try { console.log(JSON.stringify(lerToken(process.argv[2]))); }"
                  "catch (e) { console.log(JSON.stringify({ erro: e.message })); }")
        saida = subprocess.run(["node", "-e", script, str(REVELAR_JS), token],
                               capture_output=True, text=True, check=True).stdout
        return json.loads(saida)

    def test_o_javascript_decifra_o_que_o_python_gera(self):
        for nome, amiga in [("Gui", "Matias"), ("Júlia", "Úrsula 🎄"), ("A", "B" * 300)]:
            self.assertEqual(self.ler_no_navegador(gerar_token(nome, amiga)), {"v": 1, "nome": nome, "amiga": amiga})

    def test_link_cortado_e_recusado(self):
        token = gerar_token("Gui", "Matias")
        for estragado in ["", token[:-5], token[:10], "naoeumtoken", "%%%"]:
            self.assertIn("erro", self.ler_no_navegador(estragado), estragado)


if __name__ == "__main__":
    unittest.main()

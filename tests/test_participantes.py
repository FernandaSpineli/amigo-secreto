import tempfile
import unittest
from pathlib import Path

from amigo_secreto.participantes import ListaInvalida, carregar, normalizar_telefone


class TelefoneTest(unittest.TestCase):
    def test_formatos_aceitos(self):
        casos = {
            "(11) 98765-4321": "+5511987654321",
            "11987654321": "+5511987654321",
            "1132654321": "+551132654321",
            "+55 11 98765-4321": "+5511987654321",
            "5511987654321": "+5511987654321",
            "+351 912 345 678": "+351912345678",
        }
        for bruto, esperado in casos.items():
            self.assertEqual(normalizar_telefone(bruto), esperado, bruto)

    def test_formatos_recusados(self):
        for bruto in ["", "98765-4321", "123", "+12"]:
            with self.assertRaises(ListaInvalida, msg=bruto):
                normalizar_telefone(bruto)


class CarregarTest(unittest.TestCase):
    def csv(self, conteudo: str) -> Path:
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        caminho = Path(pasta.name) / "lista.csv"
        caminho.write_text(conteudo, encoding="utf-8")
        return caminho

    def test_le_o_exemplo_do_projeto(self):
        lista = carregar(Path(__file__).parent.parent / "participantes.exemplo.csv")
        self.assertEqual([p.nome for p in lista], ["Ana", "Bia", "Carla", "Duda"])
        self.assertEqual(lista[2].telefone, "+5521998765432")

    def test_ignora_linhas_vazias_espacos_e_maiusculas_no_cabecalho(self):
        lista = carregar(self.csv(" Nome , TELEFONE \n Ana , 11987654321 \n\n,\nBia,11912345678\n"))
        self.assertEqual([(p.nome, p.telefone) for p in lista],
                         [("Ana", "+5511987654321"), ("Bia", "+5511912345678")])

    def test_aceita_csv_salvo_pelo_excel_com_bom(self):
        caminho = self.csv("")
        caminho.write_bytes("nome,telefone\nAna,11987654321\n".encode("utf-8-sig"))
        self.assertEqual(carregar(caminho)[0].nome, "Ana")

    def test_erros(self):
        casos = {
            "nome\nAna\n": "colunas",
            "nome,telefone\n,11987654321\n": "linha 2: falta o nome",
            "nome,telefone\nAna,123\n": "linha 2: telefone inválido",
            "nome,telefone\nAna,11987654321\nana,11912345678\n": "nome repetido",
            "nome,telefone\nAna,11987654321\nBia,(11) 98765-4321\n": "telefone repetido",
        }
        for conteudo, trecho in casos.items():
            with self.assertRaises(ListaInvalida) as ctx:
                carregar(self.csv(conteudo))
            self.assertIn(trecho, str(ctx.exception))

    def test_arquivo_inexistente(self):
        with self.assertRaisesRegex(ListaInvalida, "não encontrado"):
            carregar(Path("/nao/existe.csv"))


if __name__ == "__main__":
    unittest.main()

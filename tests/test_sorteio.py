import random
import unittest

from amigo_secreto.sorteio import SorteioInvalido, sortear


class SorteioTest(unittest.TestCase):
    def test_ninguem_tira_a_si_mesma_e_todas_sao_tiradas(self):
        for n in range(3, 40):
            nomes = [f"P{i}" for i in range(n)]
            for semente in range(50):
                pares = sortear(nomes, random.Random(semente))
                self.assertEqual(sorted(pares), sorted(nomes), "todas tiram alguém")
                self.assertEqual(sorted(pares.values()), sorted(nomes), "todas são tiradas uma vez")
                for quem, tirou in pares.items():
                    self.assertNotEqual(quem, tirou)

    def test_forma_um_unico_circulo_sem_pares_fechados(self):
        nomes = [f"P{i}" for i in range(12)]
        for semente in range(200):
            pares = sortear(nomes, random.Random(semente))
            atual, visitadas = nomes[0], set()
            while atual not in visitadas:
                visitadas.add(atual)
                atual = pares[atual]
            self.assertEqual(len(visitadas), len(nomes))
            for quem, tirou in pares.items():
                self.assertNotEqual(pares[tirou], quem)

    def test_resultado_varia(self):
        nomes = ["Ana", "Bia", "Carla", "Duda", "Eva"]
        resultados = {tuple(sorted(sortear(nomes).items())) for _ in range(200)}
        self.assertGreater(len(resultados), 1)

    def test_cada_pessoa_pode_tirar_qualquer_outra(self):
        nomes = ["Ana", "Bia", "Carla", "Duda"]
        tiradas_pela_ana = {sortear(nomes, random.Random(s))["Ana"] for s in range(200)}
        self.assertEqual(tiradas_pela_ana, {"Bia", "Carla", "Duda"})

    def test_poucas_pessoas(self):
        with self.assertRaises(SorteioInvalido):
            sortear(["Ana", "Bia"])

    def test_nomes_repetidos(self):
        with self.assertRaises(SorteioInvalido):
            sortear(["Ana", "Bia", "Ana"])


if __name__ == "__main__":
    unittest.main()

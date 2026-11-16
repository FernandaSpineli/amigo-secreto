import itertools
import random
import unittest
from unittest import mock

from amigo_secreto import sorteio
from amigo_secreto.sorteio import SorteioInvalido, sortear


class SorteioTest(unittest.TestCase):
    def test_ninguem_tira_a_si_mesma_e_todas_sao_tiradas(self):
        for n in range(3, 40):
            nomes = [f"P{i}" for i in range(n)]
            for semente in range(50):
                pares = sortear(nomes, rng=random.Random(semente))
                self.assertEqual(sorted(pares), sorted(nomes), "todas tiram alguém")
                self.assertEqual(sorted(pares.values()), sorted(nomes), "todas são tiradas uma vez")
                for quem, tirou in pares.items():
                    self.assertNotEqual(quem, tirou)

    def test_forma_um_unico_circulo_sem_pares_fechados(self):
        nomes = [f"P{i}" for i in range(12)]
        for semente in range(200):
            pares = sortear(nomes, rng=random.Random(semente))
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
        tiradas_pela_ana = {sortear(nomes, rng=random.Random(s))["Ana"] for s in range(200)}
        self.assertEqual(tiradas_pela_ana, {"Bia", "Carla", "Duda"})

    def test_poucas_pessoas(self):
        with self.assertRaises(SorteioInvalido):
            sortear(["Ana", "Bia"])

    def test_nomes_repetidos(self):
        with self.assertRaises(SorteioInvalido):
            sortear(["Ana", "Bia", "Ana"])



def conferir(teste, nomes, grupos, pares):
    teste.assertEqual(sorted(pares.values()), sorted(nomes))
    for quem, tirou in pares.items():
        teste.assertNotEqual(quem, tirou)
        if grupos.get(quem):
            teste.assertNotEqual(grupos.get(quem), grupos.get(tirou), f"{quem} tirou {tirou}, do mesmo grupo")
    atual, visitadas = nomes[0], set()
    while atual not in visitadas:
        visitadas.add(atual)
        atual = pares[atual]
    teste.assertEqual(len(visitadas), len(nomes), "um único círculo")


class GruposTest(unittest.TestCase):
    def test_casais_nunca_se_tiram(self):
        nomes = ["Ana", "Pedro", "Bia", "Caio", "Carla", "Duda", "Eva"]
        grupos = {"Ana": "c1", "Pedro": "c1", "Bia": "c2", "Caio": "c2"}
        for semente in range(500):
            conferir(self, nomes, grupos, sortear(nomes, grupos, rng=random.Random(semente)))

    def test_grupos_aleatorios_contra_forca_bruta(self):
        # Para grupos pequenos, compara com todas as ordens possíveis: o
        # sorteio sai sempre que existe solução, e recusa quando não existe.
        sorteador = random.Random(7)
        for caso in range(400):
            n = sorteador.randint(3, 7)
            nomes = [f"P{i}" for i in range(n)]
            grupos = {x: sorteador.choice(["", "a", "b"]) for x in nomes}
            grupo_de = {x: grupos[x] or x for x in nomes}
            existe = any(all(grupo_de[c[i]] != grupo_de[c[i - 1]] for i in range(n))
                         for c in ([nomes[0], *p] for p in itertools.permutations(nomes[1:])))
            if existe:
                conferir(self, nomes, grupos, sortear(nomes, grupos, rng=random.Random(caso)))
            else:
                with self.assertRaises(SorteioInvalido):
                    sortear(nomes, grupos, rng=random.Random(caso))

    def test_restricao_apertada_usa_o_retrocesso_e_continua_valida(self):
        # Metade das pessoas num grupo só: só serve um círculo alternado,
        # que o embaralhamento quase nunca acerta.
        nomes = [f"P{i}" for i in range(30)]
        grupos = {x: "familia" for x in nomes[:15]}
        with mock.patch.object(sorteio, "TENTATIVAS_AO_ACASO", 0):
            for semente in range(50):
                conferir(self, nomes, grupos, sortear(nomes, grupos, rng=random.Random(semente)))
        conferir(self, nomes, grupos, sortear(nomes, grupos))

    def test_retrocesso_com_grupos_misturados(self):
        sorteador = random.Random(3)
        with mock.patch.object(sorteio, "TENTATIVAS_AO_ACASO", 0):
            for caso in range(300):
                n = sorteador.randint(4, 25)
                nomes = [f"P{i}" for i in range(n)]
                grupos = {x: sorteador.choice(["", "", "a", "b", "c"]) for x in nomes}
                try:
                    pares = sortear(nomes, grupos, rng=random.Random(caso))
                except SorteioInvalido as e:
                    self.assertIn("no máximo metade", str(e))
                    continue
                conferir(self, nomes, grupos, pares)

    def test_casal_pode_tirar_qualquer_pessoa_de_fora(self):
        nomes = ["Ana", "Pedro", "Bia", "Carla", "Duda"]
        grupos = {"Ana": "c1", "Pedro": "c1"}
        tiradas_pela_ana = {sortear(nomes, grupos, rng=random.Random(s))["Ana"] for s in range(300)}
        self.assertEqual(tiradas_pela_ana, {"Bia", "Carla", "Duda"})

    def test_grupo_com_mais_da_metade_e_impossivel(self):
        with self.assertRaisesRegex(SorteioInvalido, "o grupo 'c1' tem 2 de 3 pessoas"):
            sortear(["Ana", "Pedro", "Bia"], {"Ana": "c1", "Pedro": "c1"})
        with self.assertRaisesRegex(SorteioInvalido, "no máximo metade"):
            sortear(list("ABCDE"), {"A": "f", "B": "f", "C": "f"})
        conferir(self, list("ABCDEF"), {"A": "f", "B": "f", "C": "f"},
                 sortear(list("ABCDEF"), {"A": "f", "B": "f", "C": "f"}))

    def test_dois_casais_sozinhos(self):
        nomes = ["Ana", "Pedro", "Bia", "Caio"]
        grupos = {"Ana": "c1", "Pedro": "c1", "Bia": "c2", "Caio": "c2"}
        for semente in range(100):
            conferir(self, nomes, grupos, sortear(nomes, grupos, rng=random.Random(semente)))


if __name__ == "__main__":
    unittest.main()

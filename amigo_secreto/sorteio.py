"""O sorteio em si: quem tira quem.

As participantes são embaralhadas e ligadas em um único círculo: cada uma
tira a próxima, e a última tira a primeira. Assim ninguém tira a si mesma,
todas tiram e são tiradas exatamente uma vez, e (com três ou mais pessoas)
não existe par fechado do tipo "eu tirei você e você me tirou".

Pessoas do mesmo grupo (um casal, irmãs) não podem se tirar, então nunca
ficam lado a lado no círculo. Primeiro o círculo é embaralhado até sair um
válido, o que dá a mesma chance a todos os círculos possíveis. Se as
restrições forem tão apertadas que isso demore, uma busca com retrocesso
monta um círculo válido escolhendo cada próxima pessoa ao acaso.
"""

import random
import secrets
from collections import Counter

MINIMO = 3
TENTATIVAS_AO_ACASO = 5000


class SorteioInvalido(ValueError):
    pass


def sortear(nomes: list[str], grupos: dict[str, str] | None = None, *,
            rng: random.Random | None = None) -> dict[str, str]:
    """Devolve {quem tira: quem foi tirada}.

    `grupos` diz o grupo de cada pessoa; quem não aparece ou tem grupo vazio
    não tem restrição.
    """
    if len(nomes) < MINIMO:
        raise SorteioInvalido(f"são precisas pelo menos {MINIMO} pessoas para o sorteio")
    if len(set(nomes)) != len(nomes):
        raise SorteioInvalido("há nomes repetidos; diferencie-os (ex.: Ana S. e Ana P.)")

    grupos = grupos or {}
    # Sem grupo, cada pessoa é um grupo só dela (a tupla não colide com nenhum texto).
    grupo_de = {n: grupos.get(n) or ("sozinha", n) for n in nomes}
    _conferir_que_da_para_sortear(grupo_de)

    rng = rng or secrets.SystemRandom()
    circulo = list(nomes)
    for _ in range(TENTATIVAS_AO_ACASO):
        rng.shuffle(circulo)
        if _valido(circulo, grupo_de):
            break
    else:
        circulo = _montar_com_retrocesso(nomes, grupo_de, rng)
    return {circulo[i]: circulo[(i + 1) % len(circulo)] for i in range(len(circulo))}


def _conferir_que_da_para_sortear(grupo_de: dict) -> None:
    # Cada pessoa de um grupo tira alguém de fora dele, e cada pessoa de fora
    # só é tirada uma vez: o grupo não pode ter mais gente do que o resto.
    grupo, tamanho = Counter(grupo_de.values()).most_common(1)[0]
    if tamanho > len(grupo_de) - tamanho:
        raise SorteioInvalido(
            f"não dá para sortear: o grupo '{grupo}' tem {tamanho} de {len(grupo_de)} pessoas, e quem é "
            "do mesmo grupo não pode se tirar. Um grupo pode ter no máximo metade das participantes")


def _valido(circulo: list[str], grupo_de: dict) -> bool:
    return all(grupo_de[circulo[i]] != grupo_de[circulo[i - 1]] for i in range(len(circulo)))


def _montar_com_retrocesso(nomes: list[str], grupo_de: dict, rng: random.Random) -> list[str]:
    restantes = Counter(grupo_de[n] for n in nomes)
    por_grupo: dict = {}
    for n in nomes:
        por_grupo.setdefault(grupo_de[n], []).append(n)

    def cabe(anterior, primeiro) -> bool:
        # Corte: cada grupo restante precisa caber nas vagas que sobram sem
        # ficar lado a lado. A primeira vaga não serve para o grupo da anterior,
        # e a última não serve para o grupo da primeira do círculo.
        vagas = sum(restantes.values())
        for g, quantos in restantes.items():
            linha = vagas - (g == anterior) - (g == primeiro)
            if quantos > max(linha + 1, 0) // 2:
                return False
        return True

    def continuar(caminho: list[str]) -> bool:
        if not sum(restantes.values()):
            return grupo_de[caminho[-1]] != grupo_de[caminho[0]]
        anterior, primeiro = grupo_de[caminho[-1]], grupo_de[caminho[0]]
        opcoes = [g for g, quantos in restantes.items() if quantos and g != anterior]
        rng.shuffle(opcoes)
        for g in opcoes:
            restantes[g] -= 1
            if cabe(g, primeiro):
                caminho.append(por_grupo[g][restantes[g]])
                if continuar(caminho):
                    return True
                caminho.pop()
            restantes[g] += 1
        return False

    for nomes_do_grupo in por_grupo.values():
        rng.shuffle(nomes_do_grupo)
    inicio = rng.choice(nomes)
    restantes[grupo_de[inicio]] -= 1
    por_grupo[grupo_de[inicio]].remove(inicio)
    por_grupo[grupo_de[inicio]].append(inicio)  # fica fora do alcance de restantes[g]
    caminho = [inicio]
    if not continuar(caminho):
        raise SorteioInvalido("não foi possível montar um sorteio com esses grupos")
    return caminho

"""O sorteio em si: quem tira quem.

As participantes são embaralhadas e ligadas em um único círculo: cada uma
tira a próxima, e a última tira a primeira. Assim ninguém tira a si mesma,
todas tiram e são tiradas exatamente uma vez, e (com três ou mais pessoas)
não existe par fechado do tipo "eu tirei você e você me tirou".
"""

import random
import secrets

MINIMO = 3


class SorteioInvalido(ValueError):
    pass


def sortear(nomes: list[str], rng: random.Random | None = None) -> dict[str, str]:
    """Devolve {quem tira: quem foi tirada}."""
    if len(nomes) < MINIMO:
        raise SorteioInvalido(f"são precisas pelo menos {MINIMO} pessoas para o sorteio")
    if len(set(nomes)) != len(nomes):
        raise SorteioInvalido("há nomes repetidos; diferencie-os (ex.: Ana S. e Ana P.)")

    rng = rng or secrets.SystemRandom()
    circulo = list(nomes)
    rng.shuffle(circulo)
    return {circulo[i]: circulo[(i + 1) % len(circulo)] for i in range(len(circulo))}

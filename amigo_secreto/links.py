"""Links secretos: cada pessoa recebe um link que só mostra quem ela tirou.

O resultado vai embaralhado depois do "#" do link. Essa parte nunca é enviada
ao servidor que hospeda a página: quem decifra é o navegador de quem abre.
O embaralhamento usa uma chave aleatória do tamanho da mensagem, que vai no
próprio link. Não é segredo contra quem tem o link (a pessoa precisa
conseguir ler!), mas impede que alguém descubra o nome só de olhar o link,
por exemplo na conversa de quem organizou.
"""

import base64
import json
import secrets
import urllib.parse

SITE_PADRAO = "https://fernandaspineli.github.io/amigo-secreto/revelar.html"


def gerar_token(nome: str, amiga: str) -> str:
    dados = json.dumps({"v": 1, "nome": nome, "amiga": amiga}, ensure_ascii=False, separators=(",", ":")).encode()
    chave = secrets.token_bytes(len(dados))
    embaralhado = bytes(a ^ b for a, b in zip(dados, chave))
    return base64.urlsafe_b64encode(chave + embaralhado).rstrip(b"=").decode()


def ler_token(token: str) -> dict:
    """O mesmo que a página de revelação faz no navegador."""
    bruto = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    metade = len(bruto) // 2
    return json.loads(bytes(a ^ b for a, b in zip(bruto[:metade], bruto[metade:])))


def link_secreto(site: str, token: str) -> str:
    return f"{site}#{token}"


def link_whatsapp(telefone: str, texto: str) -> str:
    """Abre o WhatsApp (app ou web) numa conversa com o telefone, com o texto já escrito."""
    numero = "".join(c for c in telefone if c.isdigit())
    return f"https://wa.me/{numero}?text={urllib.parse.quote(texto)}"

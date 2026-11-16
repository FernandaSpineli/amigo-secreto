"""A página local de envio: um botão por pessoa, que abre o WhatsApp com a
mensagem pronta. A página mostra só os nomes de quem vai receber; o resultado
fica embaralhado dentro dos links."""

from html import escape

MODELO = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Enviar o amigo secreto</title>
<style>
  :root {{ --fundo: #fbf6ef; --cartao: #fff; --texto: #2b2320; --suave: #6f625b; --verde: #128c4b; --borda: #eadfd3; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --fundo: #1d1715; --cartao: #2a2220; --texto: #f6ece4; --suave: #c2b3a9; --verde: #4cc985; --borda: #3d3330; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 24px 16px; background: var(--fundo); color: var(--texto);
         font: 17px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
  main {{ max-width: 560px; margin: 0 auto; }}
  h1 {{ margin: 0 0 8px; font-size: 26px; }}
  p {{ margin: 0 0 16px; color: var(--suave); }}
  ol {{ list-style: none; margin: 24px 0; padding: 0; display: grid; gap: 10px; }}
  li {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 16px;
        background: var(--cartao); border: 1px solid var(--borda); border-radius: 14px; }}
  .nome {{ font-weight: 600; overflow-wrap: anywhere; }}
  .telefone {{ display: block; color: var(--suave); font-size: 14px; font-weight: 400; }}
  a {{ flex: none; padding: 10px 16px; border-radius: 10px; background: var(--verde); color: #fff;
       font-weight: 700; text-decoration: none; }}
  a.enviado {{ background: transparent; color: var(--verde); border: 1px solid var(--verde); }}
  a:focus-visible {{ outline: 3px solid var(--texto); outline-offset: 2px; }}
</style>
</head>
<body>
<main>
  <h1>Enviar o amigo secreto</h1>
  <p>Toque em cada botão: o WhatsApp abre a conversa com a mensagem pronta, e é só enviar.</p>
  <p><strong>Não abra os links das mensagens.</strong> Cada um revela quem aquela pessoa tirou.</p>
  <ol>
{itens}
  </ol>
  <p>Sorteio de {criado_em}. Se alguém perder a mensagem, reenvie pelo mesmo botão: o resultado não muda.</p>
</main>
<script>
  for (const a of document.querySelectorAll("a")) {{
    a.addEventListener("click", () => {{ a.classList.add("enviado"); a.textContent = "Enviar de novo"; }});
  }}
</script>
</body>
</html>
"""

ITEM = """    <li><span class="nome">{nome}<span class="telefone">{telefone}</span></span>
      <a href="{link}" target="_blank" rel="noopener noreferrer">Enviar</a></li>"""


def montar(envios: list[tuple[str, str, str]], criado_em: str) -> str:
    """`envios` é uma lista de (nome, telefone, link do WhatsApp)."""
    itens = "\n".join(ITEM.format(nome=escape(n), telefone=escape(t), link=escape(link)) for n, t, link in envios)
    return MODELO.format(itens=itens, criado_em=escape(criado_em))

// Decifra o resultado que vem depois do "#" do link (veja amigo_secreto/links.py):
// base64url de chave + mensagem embaralhada, as duas do mesmo tamanho.
"use strict";

function lerToken(token) {
  const base64 = token.replace(/-/g, "+").replace(/_/g, "/");
  const bruto = Uint8Array.from(atob(base64 + "=".repeat((4 - (base64.length % 4)) % 4)), (c) => c.charCodeAt(0));
  const metade = bruto.length / 2;
  if (!Number.isInteger(metade) || metade === 0) throw new Error("tamanho inválido");
  const dados = bruto.slice(0, metade).map((byte, i) => byte ^ bruto[metade + i]);
  const resultado = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(dados));
  if (resultado.v !== 1 || typeof resultado.nome !== "string" || typeof resultado.amiga !== "string") {
    throw new Error("conteúdo inválido");
  }
  return resultado;
}

if (typeof document !== "undefined") {
  const mostrar = (id) => {
    for (const secao of document.querySelectorAll("section")) secao.hidden = secao.id !== id;
  };
  try {
    const resultado = lerToken(location.hash.slice(1));
    document.getElementById("saudacao").textContent = `Oi, ${resultado.nome}!`;
    document.getElementById("amiga").textContent = resultado.amiga;
    document.getElementById("revelar").addEventListener("click", () => mostrar("aberto"));
    document.getElementById("esconder").addEventListener("click", () => mostrar("fechado"));
    mostrar("fechado");
  } catch {
    mostrar("invalido");
  }
}

if (typeof module !== "undefined") module.exports = { lerToken };

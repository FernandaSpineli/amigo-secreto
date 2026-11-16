# Amigo Secreto

Sorteio de amigo secreto em que cada pessoa recebe, no WhatsApp, um link
secreto que mostra só quem ela tirou. Ninguém cai com o próprio nome, todas
tiram e são tiradas exatamente uma vez, casais não se tiram, e quem
organiza também pode participar: o nome sorteado nunca aparece na tela de
quem organiza nem no texto das mensagens.

Não precisa de conta em nenhum serviço nem custa nada: as mensagens saem do
seu próprio WhatsApp.

## Como funciona

1. O programa faz o sorteio e gera um link secreto para cada pessoa.
2. Ele abre no navegador uma página com um botão **Enviar** para cada uma.
3. Cada botão abre o WhatsApp (o aplicativo ou o WhatsApp Web) na conversa
   com aquela pessoa, com a mensagem já escrita. É só enviar.
4. Quem recebe toca no link, vê "Oi, Ana!" e um botão **Revelar quem eu
   tirei**, e só então aparece o nome.

A mensagem que fica na sua conversa é algo como:

> Oi, Ana! 🎁 O amigo secreto foi sorteado. Abra o seu link para descobrir
> quem você tirou (ele é só seu, não repasse):
> https://fernandaspineli.github.io/amigo-secreto/revelar.html#Qk3x…

**Não abra os links que você enviar:** cada um revela quem aquela pessoa
tirou.

### O link secreto

O resultado vai embaralhado depois do `#` do link. Essa parte nunca sai do
celular de quem abre: o navegador não a envia ao servidor, e quem decifra é
a própria página, no aparelho. O embaralhamento usa uma chave aleatória que
vai junto no link, então ele não protege contra quem tem o link (a pessoa
precisa conseguir ler!), mas impede que alguém descubra o nome só de olhar
o link, por exemplo no seu histórico de conversas.

A página de revelação (`docs/revelar.html`) é estática e fica publicada no
GitHub Pages deste repositório.

## Como o sorteio funciona

As participantes são embaralhadas e ligadas em um único círculo: cada uma
tira a próxima, e a última tira a primeira.

```
Carla → Ana → Eva → Bia → Duda → (volta para Carla)
```

Com isso:

- ninguém tira a si mesma;
- todas tiram uma pessoa e são tiradas por uma pessoa;
- não existe par fechado ("eu tirei você e você me tirou");
- qualquer pessoa pode tirar qualquer outra, e o embaralhamento usa o
  gerador de números aleatórios do sistema (`secrets`).

São precisas pelo menos 3 pessoas.

### Casais e grupos

Pessoas do mesmo grupo (um casal, irmãs, mãe e filha) não se tiram, em
nenhuma direção: no círculo, elas nunca ficam lado a lado. O círculo é
embaralhado até sair um que respeite os grupos, o que dá a mesma chance a
todas as combinações válidas. Se os grupos forem tão restritivos que isso
demore, uma busca monta um círculo válido escolhendo cada próxima pessoa
ao acaso.

Um grupo pode ter no máximo metade das participantes. Cada pessoa do grupo
precisa tirar alguém de fora dele, e cada pessoa de fora só é tirada uma
vez. Por isso, um casal mais uma amiga (3 pessoas) não tem sorteio
possível, e o programa avisa.

## Requisitos

- Python 3.10 ou mais novo. Não há dependências para instalar.
- WhatsApp no celular ou no computador (WhatsApp Web).

## Passo a passo

### 1. Monte a lista

Copie `participantes.exemplo.csv` para `participantes.csv` e coloque as
amigas, com o número do WhatsApp de cada uma:

```csv
nome,telefone,grupo
Ana,(11) 98765-4321,Ana e Pedro
Bia,11 91234-5678,
Carla,+55 21 99876-5432,
Pedro,11 97777-6666,Ana e Pedro
```

O telefone pode ter espaços, parênteses e traço. Sem `+`, o número é tratado
como brasileiro (DDD + número). Nomes e telefones não podem se repetir; para
duas Anas, use "Ana S." e "Ana P.". Dá para montar a lista no Excel ou no
Google Planilhas e salvar como CSV.

A coluna `grupo` é opcional. Para um casal não se tirar, escreva o mesmo
texto nas duas linhas (maiúsculas e espaços extras não importam); deixe em
branco para quem não tem restrição. Um grupo com uma pessoa só é tratado
como erro de digitação (por exemplo, "casal 1" e "casal1"), para que o
casal não fique livre para se tirar sem você perceber.

O `.gitignore` já impede que a lista, o resultado e a página de envio vão
parar no Git.

### 2. Confira a lista

```bash
python3 -m amigo_secreto sortear participantes.csv --simular
```

Esse comando confere a lista e faz um sorteio de teste, sem salvar nada.

### 3. Sorteie e envie

```bash
python3 -m amigo_secreto sortear participantes.csv
```

```
Sorteio feito com 5 participantes.
Página de envio: /home/voce/amigo-secreto/enviar.html
Toque em cada botão para abrir o WhatsApp com a mensagem pronta. Não abra os links das mensagens.
```

A página de envio abre no navegador. Toque em **Enviar** ao lado de cada
nome, envie a mensagem no WhatsApp e volte para a próxima. O botão muda
para **Enviar de novo** depois de tocado, para você não se perder.

Para mudar o texto, use `--mensagem` com `{link}` (obrigatório) e `{nome}`
(quem recebe). O programa recusa `{amiga}`, porque o nome sorteado ficaria
escrito na sua conversa:

```bash
python3 -m amigo_secreto sortear participantes.csv \
  --mensagem "{nome}, saiu o amigo secreto! Presente até R\$ 50, troca dia 20/12. Seu link: {link}"
```

## Se algo der errado

O resultado fica salvo em `sorteio.json`, com permissão só para o seu
usuário. **Não abra esse arquivo se você participa:** ele tem os links.

```bash
python3 -m amigo_secreto reenviar             # reabre a página de envio, com os mesmos links
python3 -m amigo_secreto reenviar --nome Bia  # só o botão da Bia, que apagou a mensagem
```

O `reenviar` nunca muda o sorteio: quem recebe de novo recebe o mesmo link.
Para descartar o sorteio e fazer outro (por exemplo, se alguém entrou ou
saiu do grupo):

```bash
python3 -m amigo_secreto sortear participantes.csv --novo
```

Nesse caso, mande as mensagens novas para todas e avise que os links
antigos não valem mais.

## Usando a sua própria página de revelação

Por padrão, os links apontam para a página publicada neste repositório. Se
você fizer um fork, ative o GitHub Pages (Settings → Pages → branch `main`,
pasta `/docs`) e passe o endereço da sua página:

```bash
python3 -m amigo_secreto sortear participantes.csv \
  --site https://seu-usuario.github.io/amigo-secreto/revelar.html
```

## Testes

```bash
python3 -m unittest discover -s tests -t .
```

Os testes rodam o sorteio milhares de vezes, com turmas de 3 a 39 pessoas,
e conferem que ninguém tira a si mesma, que todas são tiradas uma vez e que
o resultado forma um único círculo. Com casais e grupos, os testes conferem
que ninguém tira alguém do próprio grupo e comparam com todas as ordens
possíveis: o sorteio sai sempre que existe solução e é recusado quando não
existe.

Também cobrem a leitura da lista, os links do WhatsApp, a página de envio
(sem o nome sorteado em lugar nenhum) e, se o Node estiver instalado, o
JavaScript da página de revelação, que precisa decifrar exatamente o que o
Python gera.

## Organização

| Arquivo | O que tem |
| --- | --- |
| `amigo_secreto/sorteio.py` | O sorteio em círculo, com casais e grupos |
| `amigo_secreto/participantes.py` | Leitura do CSV e normalização dos telefones |
| `amigo_secreto/links.py` | Os links secretos e os links do WhatsApp |
| `amigo_secreto/pagina.py` | A página local com os botões de envio |
| `amigo_secreto/cli.py` | Os comandos `sortear` e `reenviar` |
| `docs/revelar.html` | A página de revelação, publicada no GitHub Pages |

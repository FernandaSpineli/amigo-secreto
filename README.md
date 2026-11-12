# Amigo Secreto

Sorteio de amigo secreto que manda para cada pessoa, no WhatsApp, o nome de
quem ela tirou. Ninguém cai com o próprio nome, todas tiram e são tiradas
exatamente uma vez, e quem organiza também pode participar: o programa nunca
mostra o resultado na tela, e as mensagens saem de um número do Twilio, não
do seu WhatsApp, então elas não ficam no seu histórico de conversas.

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

## Requisitos

- Python 3.10 ou mais novo. Não há dependências para instalar.
- Uma conta no [Twilio](https://www.twilio.com/), que envia as mensagens de
  WhatsApp (veja abaixo).

## Passo a passo

### 1. Monte a lista

Copie `participantes.exemplo.csv` para `participantes.csv` e coloque as
amigas, com o número do WhatsApp de cada uma:

```csv
nome,telefone
Ana,(11) 98765-4321
Bia,11 91234-5678
Carla,+55 21 99876-5432
```

O telefone pode ter espaços, parênteses e traço. Sem `+`, o número é tratado
como brasileiro (DDD + número). Nomes e telefones não podem se repetir; para
duas Anas, use "Ana S." e "Ana P.". Dá para montar a lista no Excel ou no
Google Planilhas e salvar como CSV.

O `.gitignore` já impede que `participantes.csv` e o resultado do sorteio
vão parar no Git.

### 2. Teste sem enviar nada

```bash
python3 -m amigo_secreto sortear participantes.csv --simular
```

Esse comando confere a lista, faz um sorteio e monta as mensagens, mas não
envia nem salva nada, e também não mostra quem tirou quem.

### 3. Configure o Twilio e o sandbox de WhatsApp

1. Crie uma conta em <https://www.twilio.com/try-twilio>.
2. No painel (Console), copie o **Account SID** e o **Auth Token**.
3. Abra **Messaging → Try it out → Send a WhatsApp message**. Lá aparecem o
   número do sandbox (normalmente `+1 415 523 8886`) e uma frase do tipo
   `join palavra-palavra`.
4. Copie `.env.exemplo` para `.env`, preencha e carregue no terminal:

   ```bash
   set -a; source .env; set +a
   ```

### 4. Peça para cada amiga entrar no sandbox

Antes do sorteio, **cada participante** (você também, se for participar)
precisa mandar, do próprio WhatsApp, a frase `join palavra-palavra` para o
número do sandbox. Uma mensagem no grupo resolve:

> Gente, para o sorteio do amigo secreto, mandem a mensagem
> `join palavra-palavra` no WhatsApp para +1 415 523 8886 e me avisem!

Duas regras do WhatsApp para ter em mente:

- quem não entrou no sandbox não recebe nada;
- o número só pode mandar uma mensagem livre para quem falou com ele nas
  últimas 24 horas. Por isso, **faça o sorteio no mesmo dia** em que as
  amigas mandarem o `join`.

Se faltar alguém, não tem problema: o programa avisa quem não recebeu e o
motivo, e dá para reenviar depois (veja "Se algo der errado").

> O sandbox é gratuito para testes e serve bem para um grupo de amigas. Para
> enviar sem o passo do `join`, seria preciso registrar um número próprio no
> WhatsApp Business, com verificação da Meta e modelos de mensagem
> aprovados, o que é bem mais trabalhoso.

### 5. Faça o sorteio

```bash
python3 -m amigo_secreto sortear participantes.csv
```

```
Sorteio feito com 5 participantes. Enviando pelo WhatsApp...
  ✓ Ana (+5511987654321)
  ✓ Bia (+5511912345678)
  ✓ Carla (+5521998765432)
  ✓ Duda (+5531988887777)
  ✓ Eva (+5511955554444)
Pronto! Todas receberam a mensagem.
```

O Twilio aceita a mensagem na hora, mas só depois confirma se ela chegou ao
WhatsApp. Por isso, o programa espera cerca de 30 segundos pela confirmação de
cada uma antes de marcar com ✓.

Cada uma recebe algo como:

> Oi, Ana! 🎁 No amigo secreto você tirou: **Duda**. Shh, é segredo! 🤫

Para mudar o texto, use `--mensagem` com `{nome}` (quem recebe) e `{amiga}`
(quem foi tirada). A formatação do WhatsApp funciona (`*negrito*`,
`_itálico_`):

```bash
python3 -m amigo_secreto sortear participantes.csv \
  --mensagem "{nome}, seu amigo secreto é *{amiga}*! Presente até R\$ 50, troca dia 20/12."
```

## Se algo der errado

O resultado fica salvo em `sorteio.json`, com permissão só para o seu
usuário, e é atualizado a cada mensagem. Assim, um problema no meio do
caminho não obriga a sortear de novo. **Não abra esse arquivo se você
participa:** ele tem o resultado.

Quando uma mensagem não chega, o programa diz o motivo:

```
  ✗ Carla (+5521998765432): ainda não entrou no sandbox do Twilio (precisa mandar a mensagem 'join ...' para o número do Twilio)
1 não receberam. Resolva o problema e rode: python3 -m amigo_secreto reenviar
```

| Motivo | O que fazer |
| --- | --- |
| Ainda não entrou no sandbox | Ela manda o `join ...`, e você roda `reenviar` |
| Passou a janela de 24 horas | Ela manda qualquer mensagem para o número do sandbox, e você roda `reenviar` |
| Este número não tem WhatsApp | Corrija o telefone na lista e faça um sorteio novo com `--novo` |

```bash
python3 -m amigo_secreto status               # ✓ recebeu, ⏳ aguardando confirmação, ✗ não recebeu
python3 -m amigo_secreto reenviar             # confere as que aguardam e reenvia as que não chegaram
python3 -m amigo_secreto reenviar --nome Bia  # a Bia apagou a mensagem: manda de novo o mesmo resultado
```

O `reenviar` nunca muda o sorteio: quem recebe de novo recebe o mesmo nome.
Para descartar o sorteio e fazer outro (por exemplo, se alguém entrou ou
saiu do grupo):

```bash
python3 -m amigo_secreto sortear participantes.csv --novo
```

Quem já tinha recebido vai receber uma nova mensagem com o novo resultado.
Sem `--novo`, o programa se recusa a sortear por cima de um sorteio
existente.

## Testes

```bash
python3 -m unittest discover -s tests -t .
```

Os testes rodam o sorteio milhares de vezes, com grupos de 3 a 39 pessoas,
e conferem que ninguém tira a si mesma, que todas são tiradas uma vez e que
o resultado forma um único círculo. Também cobrem a leitura da lista, os
pedidos feitos ao Twilio e o fluxo completo: espera pela confirmação, falha
depois de a mensagem ser aceita, confirmação que demora e reenvio. Nenhuma
mensagem de verdade é enviada durante os testes.

## Organização

| Arquivo | O que tem |
| --- | --- |
| `amigo_secreto/sorteio.py` | O sorteio em círculo |
| `amigo_secreto/participantes.py` | Leitura do CSV e normalização dos telefones |
| `amigo_secreto/whatsapp.py` | Envio e confirmação pelo Twilio, direto pela API REST |
| `amigo_secreto/cli.py` | Os comandos `sortear`, `reenviar` e `status` |

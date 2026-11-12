# Amigo Secreto

Sorteio de amigo secreto que manda para cada pessoa, por SMS, o nome de quem
ela tirou. Ninguém cai com o próprio nome, todas tiram e são tiradas
exatamente uma vez, e quem organiza também pode participar: o programa nunca
mostra o resultado na tela.

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
- Uma conta no [Twilio](https://www.twilio.com/) para enviar os SMS (veja
  abaixo).

## Passo a passo

### 1. Monte a lista

Copie `participantes.exemplo.csv` para `participantes.csv` e coloque as
amigas:

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

### 3. Configure o Twilio

1. Crie uma conta em <https://www.twilio.com/try-twilio>.
2. No painel (Console), copie o **Account SID** e o **Auth Token**.
3. Pegue um número do Twilio para enviar (Phone Numbers → Buy a number) e
   confirme que ele envia SMS.
4. Em Messaging → Settings → Geo permissions, libere o envio para o
   **Brasil**.
5. Copie `.env.exemplo` para `.env`, preencha e carregue no terminal:

   ```bash
   set -a; source .env; set +a
   ```

> **Conta de teste (trial):** o Twilio só envia para números que você
> verificou em Phone Numbers → Verified Caller IDs, e as mensagens chegam
> com um aviso de conta de teste. Para mandar para todas sem verificar uma a
> uma, adicione crédito à conta. Cada SMS tem um custo pequeno, que o Twilio
> mostra na página de preços.

### 4. Faça o sorteio

```bash
python3 -m amigo_secreto sortear participantes.csv
```

```
Sorteio feito com 5 participantes. Enviando os SMS...
  ✓ Ana (+5511987654321)
  ✓ Bia (+5511912345678)
  ✓ Carla (+5521998765432)
  ✓ Duda (+5531988887777)
  ✓ Eva (+5511955554444)
Pronto! Todas receberam o SMS.
```

Cada uma recebe algo como:

> Oi, Ana! No amigo secreto você tirou: Duda. Shh, é segredo! 🤫

Para mudar o texto, use `--mensagem` com `{nome}` (quem recebe) e `{amiga}`
(quem foi tirada):

```bash
python3 -m amigo_secreto sortear participantes.csv \
  --mensagem "{nome}, seu amigo secreto é {amiga}! Presente até R\$ 50, troca dia 20/12."
```

## Se algo der errado

O resultado fica salvo em `sorteio.json`, com permissão só para o seu
usuário, e é atualizado a cada SMS enviado. Assim, um problema no meio do
caminho não obriga a sortear de novo. **Não abra esse arquivo se você
participa:** ele tem o resultado.

```bash
python3 -m amigo_secreto status               # quem já recebeu (✓) e quem não (✗)
python3 -m amigo_secreto reenviar             # envia só para quem ainda não recebeu
python3 -m amigo_secreto reenviar --nome Bia  # a Bia apagou o SMS: manda de novo o mesmo resultado
```

Para descartar o sorteio e fazer outro (por exemplo, se alguém entrou ou
saiu do grupo):

```bash
python3 -m amigo_secreto sortear participantes.csv --novo
```

Quem já tinha recebido vai receber um novo SMS com o novo resultado. Sem
`--novo`, o programa se recusa a sortear por cima de um sorteio existente.

## Testes

```bash
python3 -m unittest discover -s tests -t .
```

Os testes rodam o sorteio milhares de vezes, com grupos de 3 a 39 pessoas,
e conferem que ninguém tira a si mesma, que todas são tiradas uma vez e que
o resultado forma um único círculo. Também cobrem a leitura da lista, o
fluxo completo com falha e reenvio, e o pedido enviado ao Twilio. Nenhum SMS
de verdade é enviado durante os testes.

## Organização

| Arquivo | O que tem |
| --- | --- |
| `amigo_secreto/sorteio.py` | O sorteio em círculo |
| `amigo_secreto/participantes.py` | Leitura do CSV e normalização dos telefones |
| `amigo_secreto/sms.py` | Envio pelo Twilio, direto pela API REST |
| `amigo_secreto/cli.py` | Os comandos `sortear`, `reenviar` e `status` |

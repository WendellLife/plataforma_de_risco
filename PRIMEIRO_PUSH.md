# Primeiro push

O repositório `WendellLife/plataforma_de_risco` está vazio. Rode isto na pasta
descompactada:

```bash
git init
git add .
git commit -m "Plataforma de risco: motores, emissão verificada, campo offline, plano de ação, lote e gestão de acesso"
git branch -M main
git remote add origin git@github.com:WendellLife/plataforma_de_risco.git
git push -u origin main
```

Se preferir HTTPS:

```bash
git remote add origin https://github.com/WendellLife/plataforma_de_risco.git
```

## Depois do push

1. No Render: **New › Blueprint** › selecione o repositório › **Apply**.
   O `render.yaml` cria banco, Redis, web e worker sem configuração manual.
2. Acompanhe o build. Ele gera migrações, roda `collectstatic`, `migrate` e `seed_demo`.
3. Abra `/healthz` e depois a raiz do serviço.
4. Entre com `engenheiro@lifelaboral.com.br` / `demo-plataforma-2026`.

## O que conferir primeiro, nesta ordem

O seed monta o cenário de propósito para que cada tela prove algo:

1. **Máquinas › 01 - Prensa excêntrica** › Apreciação de risco. Escolha os descritores de
   HRN e veja o cálculo ao vivo, sem gravar. Gravar é ato separado.
2. **Documentos** › a emissão da máquina 01 está pronta; a da máquina 02 está travada em
   **D-01** e imprime o painel de bloqueios na minuta. É a promessa central funcionando.
3. **Plano de ação** › tente encerrar uma ação sem evidência. O sistema recusa.
4. **Emissão em lote** › Planejar. Ele tria antes de enfileirar e nomeia cada recusa.
5. Publique um documento e abra o **QR do rodapé** — a verificação pública responde sem
   login.
6. **Acesso e visibilidade** › Novo usuário. Crie um operador sem marcar cliente nenhum:
   a tela recusa e cobra confirmação explícita, em vez de criar em silêncio alguém que
   entra e não vê nada. Depois marque um cliente e confira o convite (log ou caixa de
   entrada).

## Três coisas antes de mostrar a alguém

- **Configure o SMTP antes de criar qualquer usuário real.** O convite é o único caminho
  até a primeira senha — ninguém digita senha de outra pessoa em lugar nenhum do produto.
  Sem `EMAIL_HOST`, o Django imprime o e-mail no log em vez de enviar: o link funciona,
  mas você tem que ir buscá-lo no log do Render. Variáveis na seção 5 do `DEPLOY.md`.
- **Configure `DOCUMENTS_BUCKET`.** Sem ele o PDF publicado vai para disco de contêiner,
  que o Render descarta no próximo deploy: a versão fica no banco e o arquivo desaparece.
  A tela acusa isso como incidente de prova. Tabela de variáveis no `DEPLOY.md`, seção 5.
- **Defina `PUBLIC_VERIFY_BASE_URL` antes de publicar qualquer documento.** A URL entra
  no PDF e o PDF é imutável — domínio errado só se corrige emitindo nova versão.
- **Remova `python manage.py seed_demo` do `build.sh`** quando o ambiente deixar de ser
  demonstração — ele cria usuários com senha conhecida.

## Sair da demonstração: a organização real

`createsuperuser` **não serve** para isso: cria conta sem organização, e toda tela filtra
por organização — o superusuário entra e não encontra nada. Use:

```bash
python manage.py criar_organizacao \
    --razao-social "Life Laboral Consultoria" \
    --cnpj 12345678000199 \
    --admin admin@lifelaboral.com.br \
    --nome Wendell --sobrenome Silva
```

O comando cria a organização e o primeiro administrador, e manda o convite. Daí em diante
tudo é pela tela: **Acesso e visibilidade › Novo usuário** cria conta, define perfil e
carteira de clientes na mesma operação e envia o convite. O admin do Django deixa de ser
necessário para rotina de acesso.

Ao criar o engenheiro, lembre: **só ele publica**. Se ninguém tiver esse perfil, a
emissão trava — corretamente — e a tela vai dizer que falta quem assine.

## O que NÃO fazer ainda

**Não emita documento para valer.** `SIGNING_MODE=simple`: a versão publicada nasce com
`signature_status=pending` e a trilha declarada, mas sem carimbo criptográfico. A
assinatura qualificada (A3 em nuvem para peças de engenheiro, e-CNPJ em HSM para as
demais) depende da confirmação jurídica ainda pendente.

**Não coloque dado real de cliente** enquanto o fluxo de MFA não tiver tela (o modelo
existe, a interface não). Os perfis de administrador e engenheiro já nascem com
`mfa_enabled=True` — a flag está correta, o que falta é a tela que a exerce no login.

## O que o Render vai custar

Planos `starter` no web e no worker, `basic-256mb` no banco. O worker agora é necessário:
composição de PDF, sincronização de campo e emissão em lote passam por fila. Para um teste
rápido de telas você pode baixá-lo a zero instâncias — a emissão individual recompõe o PDF
em linha como rede de segurança, e o lote fica na fila esperando.

## Verificação rápida antes do push

```bash
pytest                      # suíte inteira
pytest tests/aceitacao -v   # os dez critérios de aceite
ruff check .
```

Os dez critérios de aceite passam. Duas lacunas de **medição** permanecem declaradas em
`ACEITE.md`: desempenho sob carga (CA-10) e sincronização em 4G (CA-07). São medidas de
campo, não de suíte — ficam para o piloto.

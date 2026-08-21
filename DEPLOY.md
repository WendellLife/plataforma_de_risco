# DEPLOY.md — primeiro deploy de teste

Objetivo deste deploy: colocar em pé o **Sprint 0 + 1** para validar fundação
multi-tenant, cadastros, motor de HRN e o painel de bloqueios com dados reais.
Não é ambiente de produção — não receba dado real de cliente ainda.

## 1. Local (o caminho mais rápido)

```bash
cp .env.example .env
docker compose up --build
docker compose exec web python manage.py makemigrations --noinput
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_demo
```

Abra `http://localhost:8000/` e entre com `engenheiro@lifelaboral.com.br` /
`demo-plataforma-2026` (o seed imprime as credenciais).

**O que olhar primeiro:** o painel mostra a máquina *02 - Prensa excêntrica 60 t*
bloqueada pela regra **D-01** — fonte pneumática de 0,8 bar sem ponto de bloqueio.
Esse bloqueio é deliberado: é a promessa central do produto funcionando.

## 2. Render (deploy por Git)

O repositório já traz `render.yaml`. No Render: **New › Blueprint**, aponte para
`WendellLife/plataforma_de_risco` e confirme. Isso cria quatro recursos de uma vez:

| Recurso | Papel |
|---|---|
| `risco-db` | PostgreSQL 16 |
| `risco-redis` | broker do Celery (`noeviction` — fila não perde tarefa) |
| `risco-web` | gunicorn, health check em `/healthz` |
| `risco-worker` | worker das quatro filas |

`SECRET_KEY` é gerada pelo Render e compartilhada com o worker; `DATABASE_URL` e
`REDIS_URL` são injetadas automaticamente. Nenhuma variável precisa ser digitada
para o primeiro deploy.

O `build.sh` roda, nesta ordem: instalar dependências, `collectstatic`,
`migrate` e `seed_demo`. **Remova a linha do `seed_demo` do `build.sh` antes de o
ambiente receber dado real de cliente** — ela é idempotente, mas cria usuários de
demonstração com senha conhecida.

Depois do primeiro deploy:

```bash
# no Shell do serviço risco-web, dentro do Render
python manage.py createsuperuser
```

Verificação: `https://risco-web.onrender.com/healthz` deve responder
`{"status":"ok"}`, e a raiz deve mostrar o painel com a prensa 02 bloqueada pela
regra D-01.

Cada push em `main` dispara novo deploy. Migração roda no build, antes de a nova
versão receber tráfego — por isso toda migração precisa ser retrocompatível com a
versão anterior.

## 3. Homologação em servidor próprio

Requisitos: Docker, um Postgres 16 gerenciado, um Redis e um bucket compatível com S3.

```bash
DJANGO_SETTINGS_MODULE=config.settings.staging
DEBUG=0
SECRET_KEY=<gere 50+ caracteres aleatórios>
ALLOWED_HOSTS=homolog.seudominio.com.br
DATABASE_URL=postgres://usuario:senha@host:5432/risco
REDIS_URL=redis://host:6379/0
PUBLIC_VERIFY_BASE_URL=https://homolog.seudominio.com.br
```

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
celery -A config worker -Q documentos,lotes,sincronizacao,midia -l info
```

Ordem obrigatória: **migração antes do deploy da aplicação**. Toda migração precisa
ser retrocompatível com a versão anterior — coluna removida sai em duas etapas.
Rollback é troca de imagem, nunca migração reversa.

### Antes de abrir para o piloto

- [ ] `SECRET_KEY` fora do repositório, em gerenciador de segredo
- [ ] HTTPS obrigatório (`SECURE_SSL_REDIRECT` já ativo em staging/prod)
- [ ] Backup diário do Postgres com teste de restauração
- [ ] Bucket S3 com versionamento ativado e exclusão bloqueada
- [ ] Nenhum dado real de cliente antes do fluxo de MFA estar completo

## 4. Verificação pós-deploy

```bash
curl -s https://SEU_HOST/healthz             # {"status":"ok"}
docker compose exec web pytest -q            # todos os testes verdes
docker compose exec web ruff check .
```

Checagem manual: entre como Analista e confirme que **não existe caminho** para
publicar Análise de Risco ou Relatório de Segurança — a segregação de responsabilidade
é requisito de aceite (CA-09). O Relatório de Conformidade, esse sim, o analista
publica: ele é assinado pela organização, não pelo engenheiro (AD-11).

Roteiro do motor de documentos (Sprint 5):

1. **Documentos** no menu lateral → a lista já vem com quatro emissões do seed.
2. Abra `DOC01` da **02 - Prensa excêntrica** — o painel do verificador mostra o
   bloqueio D-01 com botão **Corrigir**, e o botão Publicar está desabilitado.
3. **Ver prévia** — a minuta carrega o próprio painel de bloqueios impresso, com
   marca d'água MINUTA. É a promessa central do produto em papel.
4. Cadastre o ponto de bloqueio da fonte pneumática, volte e clique **Verificar de
   novo**: o bloqueio é resolvido e a publicação libera — sem refazer o documento.
5. Publique: sai versão 1 com hash SHA-256, trilha de assinatura e PDF na fila.

## 5. Armazenamento de PDF e migrações

**Migrações são geradas no build.** Enquanto o esquema está em construção (sprints 0–5),
`build.sh` roda `makemigrations` antes de `migrate`. Antes do primeiro cliente real:
gere as migrações localmente, versione `apps/*/migrations/` e remova a linha.

**O PDF publicado vive em bucket** (Sprint 7). Configure antes de emitir em produção:

| Variável | Para quê |
|---|---|
| `DOCUMENTS_BUCKET` | nome do bucket. Vazio = disco local (só dev) |
| `DOCUMENTS_BUCKET_REGION` | região; padrão `us-east-1` |
| `DOCUMENTS_BUCKET_ENDPOINT` | só para S3-compatível (R2, MinIO, Spaces) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | credenciais de escrita |
| `DOCUMENTS_URL_TTL` | validade da URL assinada em segundos; padrão 300 |
| `FIELD_PHOTO_MAX_BYTES` | limite por foto de campo; padrão 12 MB |
| `FIELD_UPLOAD_TTL` | validade da URL de envio da foto; padrão 900 s |
| `FIELD_TOKEN_DAYS` | validade do token de aparelho; padrão 30 dias |

Web **e** worker precisam das mesmas credenciais — o worker grava, o web lê. O
`render.yaml` já propaga do web para o worker; só o valor do bucket precisa ser
preenchido no painel.

O bucket deve ser **privado, com versionamento ativado e exclusão bloqueada**. A
aplicação nunca sobrescreve: a chave é
`documentos/<tenant>/<documento>/v<n>-<hash12>.pdf`, então bytes diferentes geram
arquivo novo em vez de apagar prova. O download prefere URL assinada de curta duração
— o binário não trafega pela aplicação.

Sem `DOCUMENTS_BUCKET`, produção sobe com um `RuntimeWarning` explícito e grava em
disco de contêiner, que o Render descarta no próximo deploy: a versão continua no banco
e o PDF desaparece. A tela de emissão acusa isso como incidente de prova ("O arquivo não
está no armazenamento"), não como erro de tela.

Se as bibliotecas do WeasyPrint faltarem no ambiente, a rota de download avisa e a
impressão pela prévia continua funcionando.

## 6. App de campo — o que já responde

Rotas de coleta, sob `/api/v1/`:

| Método | Rota | Credencial |
|---|---|---|
| POST | `/field/pair` | sessão web (analista ou engenheiro) |
| GET | `/field/inspections` | token de aparelho |
| POST | `/field/sync` | token de aparelho |
| GET | `/field/sync/{client_batch_uuid}` | token de aparelho |
| POST | `/field/photos/presign` | token de aparelho |

O pareamento é ato da **sessão web**, nunca do próprio aparelho: `POST /field/pair`
devolve o token em claro **uma única vez** (o banco guarda só o SHA-256). O aparelho
autentica com `Authorization: Device <token>`, validade de 30 dias, revogável por
aparelho no admin.

Sem bucket assinável, `/field/photos/presign` responde `direct_upload: false` — o app
deve subir a foto pela aplicação em vez de ir direto ao armazenamento. Em produção com
bucket, o binário nunca passa pela aplicação.

A tela **Sincronização de campo** (menu Trabalho) mostra os lotes recebidos, o que falhou
com motivo por registro e os conflitos que aguardam decisão humana. Conflito não se
resolve reenviando: alguém precisa escolher entre a resposta da web e a do aparelho.

## 7. Plano de ação — o ciclo achado → correção

Duas telas: **Plano de ação** no menu (todas as ações do parque, vencidas primeiro) e o
plano por máquina, acessível pela ficha. **Adequação** por cliente em
`/clientes/<uuid>/adequacao/`.

O fluxo de teste: abra uma máquina com medidas propostas ou itens não conformes, clique
em **Gerar ações dos achados**. Cada achado vira ação com responsável (o engenheiro do
projeto, por padrão) e prazo sugerido pela faixa de HRN da zona. Tente encerrar sem
anexar evidência — o sistema recusa, e essa recusa é a promessa do módulo.

Três comportamentos que costumam surpreender em teste, todos deliberados:

- **"Vencida" não é um campo.** É calculado na leitura. Não há rotina noturna para rodar,
  e a lista nunca fica velha.
- **Cancelar uma ação não melhora o percentual** — ela permanece no denominador.
- **Encerrar uma ação com evidência datada de julho move o ponto de julho** na curva de
  adequação, não o de hoje.

A fila `planos` só notifica vencidas; se o worker cair, o painel continua correto.

## 8. Emissão em lote

Menu **Saídas › Emissão em lote**. Escolha o documento e, opcionalmente, um cliente;
clique em **Planejar**.

Planejar demora alguns segundos de propósito: roda o verificador em cada máquina do escopo
e mostra quantas estão prontas, quais não entram e **por qual regra**, antes de você
confirmar. É o passo que evita esperar meia hora por um lote que ia falhar.

Teto de 100 máquinas por lote. Confirmado, o trabalho vai para a fila `lotes` — separada
de `documentos` para que um lote grande não atrase a composição de PDF de quem acabou de
publicar uma peça individual. A tela de acompanhamento atualiza sozinha a cada 4 s.

Três comportamentos deliberados:

- **Uma falha não desfaz as demais.** Versão publicada é imutável; se a 47ª falha, as 46
  anteriores permanecem publicadas. A tela lista cada falha com a regra e a mensagem.
- **A permissão não afrouxa.** Analista não emite peça de responsabilidade técnica em
  lote, exatamente como não emite individualmente.
- **Cancelar preserva o que já saiu** e cancela só o que está na fila.

Falha frequente e esperada: bloqueio que aparece **entre a triagem e a emissão**, quando
alguém altera o cadastro no meio. A mensagem nomeia a regra; corrija e rode outro lote —
as já publicadas não repetem.

## 9. O que ainda não existe

**Assinatura qualificada e-CNPJ em HSM** — travada na confirmação jurídica. Hoje
`SIGNING_MODE=simple`: a versão publicada nasce com `signature_status=pending` e trilha
declarada, sem carimbo criptográfico. **Não emita documento para valer antes disso.**

Os documentos DOC04 a DOC12 estão declarados no catálogo com suas regras de verificador,
ainda sem template de impressão: só DOC01, DOC02 e DOC03 imprimem.

Estado dos dez critérios de aceite: `ACEITE.md`, ou `pytest tests/aceitacao -v`.

## 10. Perfis e visibilidade

Duas camadas independentes. **Organização** isola: dado de outra consultoria não existe.
**Carteira de clientes** limita a visibilidade dentro da mesma organização.

| Perfil | Vê | Publica documento assinado |
|---|---|---|
| Administrador | toda a organização | não |
| Engenheiro | clientes atribuídos | **sim** |
| Analista | clientes atribuídos | não |
| Operador | clientes atribuídos | não |
| Cliente (leitura) | clientes atribuídos, somente leitura | não |

**Usuário de perfil restrito nasce sem ver nada.** É deliberado: acesso é concedido, nunca
presumido. Atribua clientes em **Conta › Acesso e visibilidade** (visível só para
administrador) ou no admin do Django, na ficha do usuário.

Quem entra sem carteira encontra as telas vazias — e a interface diz que é falta de acesso,
não falta de cadastro. A tela de acesso lista quem está nessa situação.

O seed cria os quatro perfis para você comparar os escopos no mesmo banco:

| Usuário | Perfil | Escopo |
|---|---|---|
| `admin@lifelaboral.com.br` | Administrador | toda a organização |
| `engenheiro@lifelaboral.com.br` | Engenheiro | Cartonagem apenas |
| `analista@lifelaboral.com.br` | Analista | Cartonagem apenas |
| `cliente@cartonagem.com.br` | Cliente (leitura) | Cartonagem apenas |

Senha de todos: `demo-plataforma-2026`. Entre como admin e depois como analista — a
diferença de escopo aparece na barra lateral e nas listas.

**A API do aparelho respeita a mesma carteira.** Um técnico com telefone pareado lê apenas
os clientes dele; o token não é porta lateral.

## 11. Marca e white-label

A identidade do cliente entra por **Clientes › ficha do cliente › Identidade visual**, no
admin: nome de exibição, chave do logo no armazenamento e duas cores em hexadecimal. Campo
vazio usa a marca da plataforma — nunca produz identidade pela metade.

A regra é **assimétrica de propósito**:

| Superfície | Marca do cliente |
|---|---|
| Interface | sim, quando o usuário vê exatamente 1 cliente |
| Documento impresso | **co-marca** — contratante ao lado do emissor |
| E-mail transacional | sim |
| Página pública do QR | **nunca** |

Dois limites que não são configuráveis, e o motivo:

- **O emissor técnico não sai do documento.** Um laudo com aparência exclusiva do
  contratante tornaria ambígua a responsabilidade de quem assina — isso é questão jurídica,
  não de gosto.
- **A verificação pública é da plataforma.** Ela existe para um terceiro confirmar
  autenticidade; parecer material do contratante enfraquece a prova.

A interface só troca de cor quando a carteira do usuário tem **um** cliente. Um técnico com
cinco clientes vendo a cor de um deles seria enganoso.

**A cor do texto é calculada, não escolhida.** Se o cliente cadastrar um amarelo, o texto
sobre ele fica escuro automaticamente. Não há como configurar um botão ilegível.

Variáveis de e-mail (sem SMTP, o sistema imprime no console em vez de fingir que enviou):

```
EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_USE_TLS
DEFAULT_FROM_EMAIL="Life Laboral <nao-responda@lifelaboral.com.br>"
```

**Isto deixou de ser opcional.** Desde a gestão de acesso pela tela, o e-mail está no
caminho crítico: a conta nasce com senha inutilizável e o convite é o único jeito de a
pessoa criar a primeira senha. Sem `EMAIL_HOST`, o convite sai no log do servidor — o link
funciona, mas alguém tem que ir buscá-lo lá. Configure o SMTP antes de cadastrar o primeiro
usuário real.

## 11-A. Primeiro administrador de uma organização real

`createsuperuser` cria conta **sem organização**, e toda tela filtra por organização — a
conta entra e não encontra nada, nem consegue criar usuário (a criação herda a organização
de quem cria). O caminho certo:

```
python manage.py criar_organizacao --razao-social "..." --cnpj 00000000000000 \
    --admin admin@dominio.com.br [--nome ... --sobrenome ...] [--sem-convite]
```

Cria organização + administrador + convite. Daí em diante, rotina de acesso é tela:
**Acesso e visibilidade › Novo usuário**. O admin do Django deixa de ser necessário para
criar gente.

## 12. Verificação pública — a URL que vai impressa no papel

`PUBLIC_VERIFY_BASE_URL` é o domínio que o QR imprime. Em produção no Render ele já cai
no host do serviço; para o domínio definitivo, defina a variável **antes de publicar**
documentos: a URL entra no PDF e o PDF é imutável — documento publicado com o domínio
errado só se corrige emitindo nova versão.

```
PUBLIC_VERIFY_BASE_URL=https://verifica.lifelaboral.com.br
```

Duas superfícies, nenhuma exigindo login:

| Rota | Para quem |
|---|---|
| `/d/{public_uuid}` | pessoa com o papel na mão (destino do QR) |
| `/api/v1/public/documents/{public_uuid}` | sistema do cliente conferindo hash |

Ambas confirmam emissão e integridade **sem expor conteúdo técnico**. O QR só é impresso
em documento publicado; minuta não tem verificação pública.

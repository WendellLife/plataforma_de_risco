# DEPLOY.md — primeiro deploy de teste

Objetivo deste deploy: colocar em pé o **Sprint 0 + 1** para validar fundação
multi-tenant, cadastros, motor de HRN e o painel de bloqueios com dados reais.
Não é ambiente de produção — não receba dado real de cliente ainda.

## 1. Local (o caminho mais rápido)

```bash
cp .env.example .env
docker compose up --build
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
publicar documento — a segregação de responsabilidade é requisito de aceite (CA-09),
mesmo antes de o motor de documentos existir.

## 5. O que ainda não existe

Motor de documentos e verificador completo (Sprint 5–6), plano de ação (S13),
app de campo (S9–S12), assinatura qualificada (S14). O menu lateral mostra esses
itens desabilitados de propósito, para o teste não gerar expectativa errada.

# Plataforma de Risco — Life Laboral

Plataforma de apreciação de risco de máquinas, laudos técnicos NR-12 e APR/PT.

Stack: Python 3.12 · Django 5 · PostgreSQL 16 · Celery + Redis · HTMX · WeasyPrint.

Este repositório é o esqueleto do **Sprint 0 + Sprint 1** conforme
`handoff_claude_code/PROMPTS.md`: fundação multi-tenant, cadastros de cliente e
hierarquia, motor de HRN funcional e a primeira tela do produto. É deployável e
testável — não é o produto completo.

## Subir localmente

```bash
cp .env.example .env
docker compose up --build          # web em http://localhost:8000
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_demo   # dados de demonstração
docker compose exec web python manage.py createsuperuser
```

Verificações:

- `http://localhost:8000/healthz` → `{"status":"ok"}`
- `http://localhost:8000/` → painel com os dados de demonstração
- `http://localhost:8000/admin/` → operação interna
- `http://localhost:8000/api/v1/machines` → API (requer sessão)

## Testes

```bash
docker compose exec web pytest -q
docker compose exec web ruff check .
```

O teste do motor de HRN cobre os limites das oito faixas. O teste de isolamento
entre tenants é obrigatório em todo app novo.

## O que já existe

| Área | Estado |
|---|---|
| Multi-tenant por linha, com manager que exige escopo | pronto |
| Usuário, perfis, MFA obrigatório para admin/engineer | modelo pronto, fluxo de MFA pendente |
| Trilha de auditoria imutável | pronto |
| Cliente, unidade/setor/local, pessoa com papéis | pronto |
| Projeto, máquina, fonte de energia, ponto de bloqueio | pronto |
| Motor de HRN versionado (`METHOD_VERSION = "2.1"`) | pronto e testado |
| Motor de conformidade (dois denominadores) | pronto e testado |
| Biblioteca NR-12 (74 itens) | carga no seed |
| Painel e consulta de máquinas | primeira versão |
| Motor de documentos, verificador, publicação | **Sprint 5–6** |
| App de campo | **Sprint 9–12** |

## Regras que não se negociam

Estão em `CLAUDE.md`. Leia antes de qualquer sprint.

# Primeiro push

O repositório `WendellLife/plataforma_de_risco` está vazio. Rode isto na pasta
descompactada:

```bash
git init
git add .
git commit -m "Sprint 0 e 1: fundação multi-tenant, cadastros, motor de HRN e painel"
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
2. Acompanhe o build. Ele roda `collectstatic`, `migrate` e `seed_demo`.
3. Abra `/healthz` e depois a raiz do serviço.
4. Entre com `engenheiro@lifelaboral.com.br` / `demo-plataforma-2026`.

## Duas coisas a conferir antes de mostrar a alguém

- **Remova `python manage.py seed_demo` do `build.sh`** quando o ambiente deixar de
  ser demonstração — ele cria usuários com senha conhecida.
- **Não coloque dado real de cliente** enquanto o fluxo de MFA não estiver completo
  (sprint 1 tem o modelo, não a tela).

## O que o Render vai custar

Planos `starter` no web e no worker, `basic-256mb` no banco. Para só testar, você
pode baixar o worker para zero instâncias — nada no sprint 1 depende de fila.

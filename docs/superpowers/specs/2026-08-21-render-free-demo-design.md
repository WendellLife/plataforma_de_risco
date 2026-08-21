# Deploy gratuito de demonstração no Render

## Contexto

O Blueprint atual usa planos pagos para web, worker, Postgres e Key Value. O
objetivo aprovado é testar e demonstrar o sistema sem cobrança, aceitando as
limitações do nível gratuito do Render.

## Arquitetura

- O serviço web usará o plano `free`.
- O Postgres usará o plano `free`.
- O Key Value usará o plano `free` para fornecer `REDIS_URL`.
- O Background Worker será removido porque esse tipo de serviço não possui
  plano gratuito.
- `CELERY_TASK_ALWAYS_EAGER=1` será definido no serviço web para executar as
  tarefas Celery no próprio processo da requisição.
- O health check continuará em `/healthz`.

## Fluxo de tarefas

Chamadas Celery executarão de forma síncrona no serviço web. Isso mantém as
funções de documentos, lotes e sincronização disponíveis para demonstração,
mas operações demoradas podem aumentar o tempo de resposta ou atingir o
timeout do serviço.

## Armazenamento de documentos

As credenciais de bucket continuarão opcionais. Sem bucket externo, arquivos
serão gravados no disco efêmero do serviço e poderão desaparecer após reinício
ou novo deploy. Esse comportamento é aceitável somente para demonstração.

## Dados e disponibilidade

O serviço web gratuito pode suspender por inatividade e apresentar partida a
frio. O banco gratuito é temporário e não deve receber dados reais de clientes.
O comando `seed_demo` continuará no primeiro build para fornecer dados de
teste.

## Validação

1. Testar que a configuração de produção reconhece
   `CELERY_TASK_ALWAYS_EAGER` a partir do ambiente.
2. Validar a sintaxe do `render.yaml` e confirmar que todos os planos restantes
   são gratuitos.
3. Executar `python manage.py check` com a configuração de produção.
4. Publicar a branch, sincronizar o Blueprint e acompanhar o build.
5. Verificar `/healthz` e a página inicial na URL pública.

## Critérios de aceite

- O Blueprint não cria nenhum recurso pago.
- Não existe Background Worker no Blueprint gratuito.
- Tarefas Celery executam de forma eager no serviço web.
- O deploy conclui e `/healthz` responde com sucesso.
- As limitações de demonstração ficam documentadas e nenhum segredo entra no
  repositório.

# CLAUDE.md — Plataforma de Risco

Projeto: plataforma de apreciação de risco de máquinas, laudos técnicos e APR/PT (NR-12).
Cliente: Life Laboral. Idioma do produto: português do Brasil.

## Stack fixada

Python 3.12 · Django 5 · PostgreSQL 16 · DRF · Celery + Redis 7 · HTMX + Alpine ·
WeasyPrint (PDF) · pyHanko (assinatura) · pytest · ruff · mypy · Docker.

Não introduza framework de front-end, ORM alternativo, banco secundário ou biblioteca
de relatório sem decisão registrada como novo AD no `Espec 06`.

## Arquitetura em uma frase

Monolito Django modular: apps por domínio, motores de domínio puros, API REST desde o R1,
interface server-rendered com HTMX.

## Camadas dentro de um app — obrigatório

- `models.py` — estrutura e constraint. Nada de regra de negócio.
- `services.py` — **única** casa da regra de negócio. Função por caso de uso, em transação.
- `selectors.py` — consultas de leitura, sempre com escopo de tenant.
- `views.py` — valida entrada, chama serviço, devolve template ou resposta.
- `serializers.py` — contrato de API escrito à mão.
- `tasks.py` — invólucro fino de Celery sobre serviço.

`motores/` (hrn, conformidade, verificador, documento) não importa Django, ORM, HTTP ou
armazenamento. Recebe dados, devolve resultado. É onde vive o cálculo versionado.

## Regras de domínio invioláveis

1. **Publicação imutável** — ao publicar: gravar binário, hash SHA-256, versão de template e
   versão do método; trigger no banco recusa update de conteúdo publicado.
2. **Verificador antes de publicar** — regras D-01…D-21 com severidade `block` ou `warn`.
   Aviso aceito exige decisão registrada com autor.
3. **Residual obrigatório** — risco com recomendação sem `HrnEstimate(kind=residual)` bloqueia.
4. **LOTO derivado** — fonte de energia sem `lockout_point` bloqueia LOTO e laudo técnico.
5. **Item normativo compatível** — recomendação só aceita item cujo anexo pertença ao
   `machine_type` da máquina.
6. **N/A sobrevive** — `not_applicable` exige justificativa e é impresso no documento.
7. **Dois denominadores** — conformidade sobre base fixa e sobre avaliados, sempre juntas.
8. **Identificador estável** — `library_key` é identidade; `display_order` é apresentação.
9. **Tenant sempre** — consulta sem escopo de tenant é bug de segurança, não descuido.
10. **Auditoria** — toda escrita relevante grava `core_auditlog`; a tabela não aceita update/delete.

## Convenções de código

- Nome de app, motor e código de template espelham a especificação funcional.
- Constante de domínio é enumeração tipada (`models.TextChoices`), nunca string literal.
- Anotação de tipo obrigatória em `services.py`, `selectors.py` e `motores/`.
- Toda escrita em transação explícita; nenhum `.save()` em view.
- Migração declara constraint, índice e default. Migração aplicada em homologação nunca é editada.
- Mensagem ao usuário em pt-BR, em template ou arquivo de tradução — nunca embutida em Python.
- `ruff` e `mypy` limpos são condição de merge.

## Testes

- `tests/motores/` — tabela de casos por motor, incluindo limites de faixa de HRN.
- `tests/apps/` — integração por app + **teste obrigatório de isolamento entre tenants**.
- `tests/contratos/` — comparação estrutural da saída de cada template de documento.
- `tests/defeitos/` — um teste por defeito legado, nome contendo `D-01`…`D-21`.

## O que NÃO fazer

- Não gerar PDF por biblioteca de relatório: os templates são HTML de impressão + WeasyPrint.
- Não copiar enunciado normativo para a avaliação — referencie a biblioteca.
- Não expor id de banco em URL, API ou QR: use `public_uuid`.
- Não usar toast para erro de domínio: bloco persistente com caminho de correção.
- Não criar campo de texto livre onde a especificação define entidade tipada.
- Não antecipar módulos de onda 3 (IA assistiva, integrações) antes do R2 fechar.

# Idempotência da carga de demonstração

## Contexto

O build do Render executa `python manage.py seed_demo` em todos os deploys. Na
segunda execução, o comando tenta criar novamente a evidência
`planos/<tenant>/nf-protecao-fixa.pdf` e viola a restrição única de
`Evidence(tenant, file_key)`, interrompendo o build.

## Objetivo

Permitir que `seed_demo` seja executado repetidamente, sem afrouxar a regra de
negócio que rejeita evidências duplicadas nas operações normais.

## Solução

A idempotência ficará restrita ao comando de demonstração. Antes de chamar
`anexar_evidencia`, o comando consultará a evidência pela chave única formada
por tenant e `file_key`. A evidência será criada apenas quando ainda não
existir. Se já existir, o comando seguirá para a conclusão da ação sem registrar
outra auditoria de criação.

O serviço geral `anexar_evidencia` continuará usando criação estrita e seguirá
rejeitando duplicatas.

## Testes

O desenvolvimento seguirá TDD:

1. Adicionar um teste que execute `seed_demo` duas vezes sobre o mesmo banco.
2. Confirmar que a segunda execução falha com a restrição única atual.
3. Aplicar a verificação mínima no comando.
4. Confirmar que as duas execuções terminam e existe uma única evidência com a
   chave demonstrativa.
5. Executar `manage.py check` e os testes relacionados a planos e carga demo.

## Critérios de aceite

- `seed_demo` pode ser executado duas vezes sem `IntegrityError`.
- Existe apenas uma evidência demonstrativa por tenant e chave.
- A ação demonstrativa continua concluída e associada à evidência.
- `anexar_evidencia` mantém o comportamento estrito para uso normal.
- O build do Render conclui em um banco que já contém os dados demonstrativos.

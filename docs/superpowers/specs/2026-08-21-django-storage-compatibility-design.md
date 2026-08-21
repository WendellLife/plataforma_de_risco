# Compatibilidade do armazenamento com Django 5.1

## Contexto

O projeto fixa `Django==5.1.*`, mas `apps/documentos/armazenamento.py` importa
`InvalidStorageBackendError`, símbolo que não existe nessa versão. A importação
impede a inicialização do Django e faz `python manage.py check` falhar.

## Objetivo

Restaurar a inicialização no Django 5.1 sem mudar a seleção de armazenamento:
usar o alias `documentos` quando configurado e recorrer ao alias `default`
somente quando `documentos` estiver ausente ou inválido.

## Solução

Substituir `InvalidStorageBackendError` por `InvalidStorageError`, a exceção
exposta pelo Django 5.1 para falhas de resolução de aliases em `storages`.
A função `backend()` continuará sendo a única fronteira responsável pelo
fallback. Não haverá alteração de versões, configuração ou demais operações de
leitura e escrita.

## Testes

O desenvolvimento seguirá TDD:

1. Ajustar o teste de fallback para importar o módulo real e reproduzir a falha
   de compatibilidade antes da correção.
2. Confirmar que o teste falha pela importação inválida.
3. Aplicar a troca mínima da exceção.
4. Confirmar o teste isolado, `python manage.py check` e a suíte completa.

## Critérios de aceite

- O módulo de armazenamento importa corretamente no Django 5.1.
- A ausência do alias `documentos` retorna o backend `default`.
- Um alias `documentos` válido continua sendo usado normalmente.
- `python manage.py check` conclui sem o erro de importação original.
- Nenhuma credencial, ambiente virtual ou mudança alheia entra no commit.

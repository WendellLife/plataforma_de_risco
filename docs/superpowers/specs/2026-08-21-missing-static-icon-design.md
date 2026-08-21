# Correção do ícone estático ausente

## Contexto

Após o login, a página inicial responde com erro 500 porque o template
`templates/ui/_shell/base.html` referencia `ds/logos/icone-192.png`, mas o
arquivo não está presente nas origens de arquivos estáticos. Em produção, o
`CompressedManifestStaticFilesStorage` do WhiteNoise rejeita referências que
não constam no manifesto.

## Solução

Adicionar um ícone PNG válido em `static/ds/logos/icone-192.png`, preservando a
referência existente no template e a validação rigorosa do manifesto. Não será
alterada a configuração do WhiteNoise nem removido o suporte ao ícone de atalho.

## Validação

Um teste de regressão deve resolver a URL estática do ícone usando o backend de
produção e confirmar que ela faz parte do manifesto gerado. O ciclo de teste
deve demonstrar a falha antes da inclusão do arquivo e passar depois dela.
Também serão executados `collectstatic`, as verificações do Django e um acesso
autenticado à página inicial após o deploy.

## Publicação

A correção será enviada em branch própria, integrada por pull request e
publicada pelo auto-deploy do Render. O deploy será considerado concluído
somente quando estiver `live` e a página inicial deixar de responder com 500.

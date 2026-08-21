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

## Motor de documentos (Sprint 5) — onde cada decisão mora

- **`motores/documento/catalogo.py`** é a definição do documento: código, chave legada,
  revisão, seções, trilha de assinatura e as regras do verificador que ele exige.
  Template NÃO é tabela — se fosse, dado de cliente mudaria a definição do documento.
  Acrescentar documento novo = uma entrada no catálogo + `templates/documentos/<CODE>/corpo.html`.
- **`apps/documentos/selectors.py`** é a única fronteira com o ORM: devolve dicionários.
  **`motores/documento/contexto.py`** decide numeração, consolidação e publicabilidade.
  Se você precisou de `Machine` dentro do motor, a camada errada está fazendo a conta.
- **O verificador escolhe regras por template**, nunca "todas": `verificar(ctx, regras=...)`.
  D-01 trava a análise de risco e não trava o relatório de conformidade.
- **O painel de bloqueios é impresso na minuta.** Quem recebe o rascunho vê o que falta
  e onde corrigir. Nunca esconda bloqueio atrás de tela autenticada.
- **A prévia em tela e o PDF usam o MESMO template.** Não existe segundo template para
  impressão; só o meio de saída muda.
- **Publicar é ato verificado e imutável**: hash SHA-256 do contexto, versões de método
  congeladas, trilha de assinatura conforme AD-11 e nova versão em vez de edição.


## Cálculo de HRN ao vivo (Sprint 6) — onde cada decisão mora

- **Fator não é campo numérico livre.** `motores/hrn/escalas.py` define as quatro escalas
  tipadas: o avaliador escolhe um descritor, o descritor carrega o valor. Mudar valor ou
  descritor MUDA o método — exige subir `METHOD_VERSION` em `motores/hrn/calculo.py`.
- **O servidor calcula, o cliente só escolhe.** A prévia é HTMX contra
  `previa_hrn`, que roda `estimar()` e devolve o bloco de resultado. Nenhum produto,
  faixa ou versão de método é enviado pelo navegador nem calculado em JavaScript.
- **Prévia não grava.** `previa_hrn` e `salvar_hrn` renderizam o MESMO parcial
  (`ui/risco/_resultado.html`); só o selo de estado muda. Gravar é ato explícito com autor
  na trilha de auditoria.
- **O número isolado não decide nada.** `motores/hrn/reducao.py` compara inicial e residual
  (degraus de faixa, redução percentual, tolerabilidade) e RECUSA comparar estimativas de
  versões diferentes do método.
- **D-03 aparece na apreciação, não só na emissão.** Medida proposta sem residual é
  pendência impressa na linha do perigo, com o cálculo do residual a um clique.
- **Residual fora de faixa tolerável não bloqueia a gravação** — avisa que a publicação
  exigirá decisão registrada (AD-07). Bloquear a gravação esconderia o problema.

## Armazenamento do artefato publicado (Sprint 7) — onde cada decisão mora

- **`apps/documentos/armazenamento.py` é a única fronteira com o bucket.** Nenhum outro
  módulo abre arquivo de documento. Trocar disco local por S3 não toca em view, serviço
  ou task.
- **A chave carrega o hash:** `documentos/<tenant>/<documento>/v<n>-<hash12>.pdf`. Bytes
  diferentes geram arquivo novo — a aplicação NUNCA sobrescreve prova publicada.
  Recompor a mesma versão é idempotente.
- **Chave sem tenant no caminho é bug de segurança**, igual a consulta sem escopo.
- **Duas provas por versão**: `content_hash` (o que o documento afirma) e `pdf_sha256`
  (o arquivo entregue). `integridade.py` recalcula o segundo e compara — divergência é
  incidente com bloco persistente na tela, não toast.
- **Leitura por URL assinada de curta duração.** Bucket privado; o binário não trafega
  pela aplicação quando o backend sabe assinar. Streaming é o plano B; composição em
  linha é rede de segurança de ambiente sem worker, nunca o caminho normal.
- **Falha de armazenamento é retentada** (`compor_pdf`, 3 tentativas). PDF faltando em
  versão publicada não pode passar em silêncio.
- **Produção sem `DOCUMENTS_BUCKET` avisa alto** (`RuntimeWarning` na subida): disco de
  contêiner é efêmero e a prova se perderia no deploy seguinte.

## Sincronização de campo (Sprint 8) — onde cada decisão mora

- **Idempotência em dois níveis.** `client_batch_uuid` identifica o lote e `client_uuid`
  cada registro, ambos únicos por tenant. Reenviar o lote devolve a resposta GRAVADA sem
  reprocessar; um registro JÁ APLICADO reenviado em outro lote é marcado `duplicate`.
  Registro que falhou ou conflitou permanece retentável — marcá-lo como duplicado
  prenderia o dado no aparelho.
- **Aceitação parcial por savepoint.** Cada registro é aplicado em sua própria transação
  aninhada. Um registro inválido NUNCA desfaz os válidos, e o motivo volta por registro.
- **Falha ≠ conflito.** Falha é registro inválido — o aparelho corrige e reenvia. Conflito
  é registro válido que colide com trabalho feito na web: não entra, aguarda decisão
  humana e NÃO deve fazer o app tentar de novo. São contagens separadas na resposta.
- **Campo nunca sobrescreve a web.** `responder_item` só é chamado quando o item ainda
  não tem resposta. Resposta igual é acréscimo sem efeito; resposta diferente é conflito.
- **Ordem de chegada é irrelevante:** `motores/sincronizacao` ordena por dependência
  (perigo, resposta, foto). O aparelho não orquestra sequência.
- **Relógio do aparelho é dado, não verdade.** A data informada é preservada, a hora de
  recepção também é gravada, e desvio acima de 15 min vira AVISO no lote — nunca correção
  silenciosa: data de coleta é conteúdo de laudo.
- **Token de aparelho é credencial separada** com alcance menor que a sessão web: hash no
  banco, valor em claro devolvido uma única vez, 30 dias, revogável. O tenant vem da
  credencial, nunca de parâmetro.
- **O binário da foto não passa pela aplicação.** `/field/photos/presign` assina URL de
  PUT por 15 min e o registro é confirmado no lote seguinte com o `file_key`. Sem bucket
  assinável, `direct_upload: false` avisa o app — o dev sobe pela aplicação.
- **Perigo de campo não aceita zona de texto livre**: a zona precisa existir na máquina.

## Verificação pública (CA-06) — onde cada decisão mora

- **É a única superfície sem autenticação do produto.** Vive em
  `apps/documentos/verificacao.py` e responde a uma pergunta de terceiro: este papel foi
  mesmo emitido e continua igual?
- **Confirma, não expõe.** Devolve identidade, hash, revisão, data e responsável técnico.
  NUNCA conteúdo técnico, dado fiscal, endereço, CPF, risco apreciado ou conformidade.
  Há teste que falha se qualquer desses campos aparecer na resposta — mantenha-o.
- **Só o publicado existe ali.** Minuta não tem verificação pública e não imprime QR.
- **Não enumera.** Identificador é `public_uuid`; inexistente e de outro tenant devolvem
  a MESMA resposta. Consulta sem escopo de tenant aqui é intencional e documentada.
- **A rota é curta (`/d/<uuid>`)** porque é digitada à mão quando o QR não lê.
- **QR é SVG em linha** (`qr.py`): PNG exigiria arquivo temporário dentro do WeasyPrint.
  Sem a biblioteca `qrcode`, o documento imprime só a URL — nunca falha a emissão.

## Plano de ação (CA-08) — onde cada decisão mora

- **Toda ação nasce de um achado**: recomendação de apreciação ou item de checklist não
  conforme. Ação manual existe, mas é exceção declarada.
- **O prazo nasce do risco**, não do calendário: `motores/plano/prazo.py` traduz faixa de
  HRN em dias. É sugestão — quem responde pode encurtar ou justificar prazo maior, mas
  nunca receber número inventado pela tela.
- **"Atrasada" NÃO é coluna.** Situação de prazo é derivada de `date.today()` a cada
  leitura. Gravar estado exigiria job noturno e ficaria errado entre execuções. Existe
  teste que falha se alguém adicionar a coluna.
- **Não encerra sem evidência.** `concluir_acao` levanta `EncerramentoSemEvidencia`. É a
  regra que o produto existe para impor — não relaxe por conveniência de tela.
- **A data que vale é a do FATO** (`completed_on`, da evidência mais antiga), separada de
  `created_at`. É o que torna a curva de adequação auditável e reconstruível.
- **Cancelar não some do denominador** da adequação, e exige motivo.
- **Não existe meia adequação.** Diferente do checklist (parcial pesa 0,5), aqui a
  proteção existe ou não existe: `PESO_SITUACAO` só tem 1 e 0.
- **Repactuar prazo exige justificativa** e grava `DeadlineChange`. Sem histórico, tudo
  aparece "no prazo" no fim do ano porque a data foi empurrada seis vezes.
- **Ação de recomendação NÃO é bloqueante por padrão** — seria impasse circular (a ação
  nasce do documento que ela bloquearia). `marcar_bloqueante` é ato deliberado com motivo.

## Emissão em lote (CA-10) — onde cada decisão mora

- **Triagem ANTES da fila.** `planejar_lote` roda o verificador em cada máquina e devolve
  prontas + recusadas com a regra nomeada, para a tela mostrar antes de confirmar.
  Planejar é leitura: não deixa versão publicada como efeito colateral.
- **Recusa nomeia a regra.** "Máquina 47 não entrou" é inútil. Ver `motivo_de_recusa`.
- **O lote NÃO é transação única.** Cada item publica em sua própria transação; falha em
  um não desfaz os demais. Versão publicada é imutável — não há o que reverter.
- **A permissão não afrouxa no lote.** `_emitir_item` chama o MESMO `publicar()` da
  emissão individual. Nunca crie um caminho de publicação alternativo para lote.
- **Teto de 100** (`LIMITE_POR_LOTE`) para a estimativa de tempo continuar honesta.
- **Fila "lotes" separada de "documentos"**: um lote de 100 não pode empurrar para o fim
  da fila a composição de PDF de quem acabou de publicar uma peça individual.
- **Registro persistente**, não só tarefa: quem pediu pode fechar o navegador e voltar.
- **Cancelar preserva o publicado** e cancela só o que está na fila.

## Escopo de acesso — duas camadas, nunca uma

- **Tenant é ISOLAMENTO; carteira de clientes é VISIBILIDADE.** Vazamento entre tenants é
  incidente de segurança; carteira errada é erro de configuração. Não misture as duas.
- **`None` significa "vê tudo"; `frozenset()` significa "vê nada".** É a distinção que
  sustenta a camada inteira, e trocar uma pela outra é o bug mais grave possível aqui.
  Ambos os casos têm teste em `tests/apps/test_escopo_de_acesso.py`.
- **Ausência de atribuição = nenhum acesso.** Usuário de perfil restrito nasce sem ver
  nada. O padrão permissivo é como vazamentos acontecem em produto multiempresa. A tela de
  acesso AVISA quem está sem carteira, em vez de o produto afrouxar o padrão.
- **Somente `UserRole.ADMIN` vê toda a organização** (`PERFIS_SEM_RESTRICAO_DE_CARTEIRA`).
- **Somente engenheiro publica** peça de responsabilidade técnica — nem administrador.
  Publicar exige registro no conselho, e registro é de pessoa física, não de cargo.
- **Cada modelo declara `caminho_para_cliente`** (ex.: `"machine__client_id"`,
  `"hazard__machine__client_id"`). SEM a declaração o filtro NÃO é aplicado — por isso
  existe um teste que varre os modelos e falha se um novo esquecer de declarar. Se ele
  falhar, declare o caminho ou registre a exceção com o motivo.
- **A API do aparelho aplica a mesma carteira** (`DeviceTokenAuthentication`). O telefone
  pareado não é porta lateral.
- **A fila roda sem restrição de carteira** (`usando_tenant` zera): compor o PDF de um
  documento não pode falhar porque quem publicou tem carteira restrita.
- **Vazio por falta de acesso ≠ vazio por falta de dado.** Toda lista inclui
  `ui/_shell/_sem_acesso.html`; confundir os dois faz o usuário procurar problema onde
  não há.

## Criação de usuário — conta e visibilidade na mesma decisão

- **Criar conta e definir carteira são um só passo** (`criar_usuario_com_acesso`). Separar
  produz, no intervalo, uma conta que existe e não vê nada — e o gestor esquece o segundo
  passo enquanto o técnico passa a semana achando que o sistema está vazio.
- **Não existe campo de senha em lugar nenhum do produto.** A conta nasce com senha
  inutilizável e a pessoa cria a própria pelo convite (`apps/core/convites.py`, token de
  uso único, 24 h). Quem administra nunca sabe a credencial de outro.
- **Perfil com carteira e nenhum cliente exige confirmação explícita.** Criar sem acesso é
  legítimo; acidental, não. A tela cobra o aceite em vez de afrouxar o padrão seguro.
- **A organização vem da sessão, nunca do formulário.** Não há caminho de UI para criar
  conta em outra organização.
- **Promover a administrador APAGA a carteira**, em vez de guardá-la. Carteira parada é
  acesso que ressuscita sozinho num rebaixamento futuro.
- **A organização nunca fica sem administrador ativo**, e ninguém desativa a própria conta
  (`AlteracaoDeAcessoInvalida`). As duas travas têm teste.
- **Desativar nunca exclui** — a trilha de auditoria aponta para o usuário. Contas
  inativas continuam listadas, senão não há como reativar nem auditar quem perdeu acesso.
  Reativar não devolve carteira: o acesso é reconcedido à mão.

## Mensagem de retorno é bloco na tela, nunca toast

- `messages` é renderizado em `ui/_shell/base.html` como `.aviso` e fica até a próxima
  navegação. Confirmação de alteração de acesso não pode desaparecer antes de ser lida.
- **Defeito recorrente de CSS:** seletor de componente sem `background` próprio produz
  elemento invisível. Aconteceu com `.btn` e de novo com `.pill` (etiqueta virava texto
  solto sobre o cartão). Ao criar variantes (`--ok`, `--warn`), dê fundo ao seletor base.

## Marca e white-label — onde cada decisão mora

- **A regra é ASSIMÉTRICA por superfície**, e está em `motores/marca/identidade.py`:
  | Superfície | Marca do cliente? |
  |---|---|
  | Interface | sim, quando a carteira tem exatamente 1 cliente |
  | Documento impresso | **co-marca** — logo do contratante ao lado do emissor |
  | E-mail | sim |
  | Verificação pública do QR | **nunca** |
- **Documento é sempre co-marca.** Um laudo com aparência exclusiva do contratante tornaria
  ambígua a responsabilidade técnica de quem assina — problema jurídico, não estético. O
  rodapé com o emissor NÃO é configurável.
- **A verificação pública nunca leva marca de cliente.** Ela existe para um terceiro
  confirmar autenticidade; parecer material do contratante enfraquece o que ela prova.
- **A interface só troca de cor com 1 cliente na carteira.** Técnico com cinco clientes
  vendo a cor de um deles seria enganoso (`apps/core/context_marca.py`).
- **A cor do texto é calculada, nunca fixada.** `texto_legivel_sobre()` escolhe preto ou
  branco por contraste real — texto branco fixo produz botão ilegível no primeiro amarelo
  de marca que alguém cadastrar.
- **`resolver()` nunca devolve identidade parcial.** Campo ausente cai no padrão da
  plataforma; meia marca é pior que nenhuma. Cor inválida também cai no padrão em vez de
  quebrar a página.
- **CSS**: `--brand-primary` / `--brand-on-primary` são injetadas na página e os
  componentes as consomem com queda para o token do design system:
  `var(--brand-primary, var(--color-primary))`.

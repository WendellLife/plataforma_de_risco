# Critérios de aceite — estado atual

**Os dez critérios passam.** Duas lacunas de MEDIÇÃO permanecem declaradas abaixo
(desempenho sob carga em CA-10, sincronização em 4G em CA-07): são medidas de campo, não
de suíte, e estão nomeadas aqui em vez de disfarçadas de verde.

Os dez critérios da Espec 01, item 9, viraram uma suíte executável em
`tests/aceitacao/test_criterios_de_aceite.py`. Um teste por critério, com dados reais,
de ponta a ponta.

```bash
pytest tests/aceitacao -v
```

| Critério | O que verifica | Estado |
|---|---|---|
| CA-01 Apreciação rastreável | recusa a publicação sem HRN residual; o laudo imprime inicial → medida → residual e a versão do método | ✅ passa |
| CA-02 Recomendação compatível | item de anexo incompatível é recusado na origem, com o anexo esperado nomeado, e nunca alcança documento publicado | ✅ passa |
| CA-03 LOTO derivado das fontes reais | uma etapa por fonte cadastrada; fonte sem ponto de bloqueio impede a emissão | ✅ passa |
| CA-04 Conformidade comparável | dois denominadores publicados juntos; N/A impresso com justificativa | ✅ passa |
| CA-05 Publicação congelada | hash SHA-256, versão de template e de método congelados; conteúdo em somente leitura | ✅ passa |
| CA-06 Verificabilidade externa | QR abre página pública que confirma hash, revisão, data e responsável, sem login | ✅ passa |
| CA-07 Coleta de campo sem perda | vistoria completa coletada offline sincroniza integralmente, com fila visível | ✅ passa (correção) / ⚠️ desempenho não coberto |
| CA-08 Ciclo fechado achado → correção | não conformidade gera ação com responsável e prazo; adequação recalcula com a evidência | ✅ passa |
| CA-09 Segregação de responsabilidade | analista não publica peça técnica por nenhum caminho; trilha registra autor, ação e valores | ✅ passa (serviço e interface) |
| CA-10 Desempenho de geração em lote | 100 máquinas em até 30 min, sem degradar consulta acima de 800 ms no p95 | ✅ comportamento passa / ⚠️ carga não coberta |

## CA-06 — entregue

`GET /api/v1/public/documents/{public_uuid}` (sem autenticação) e a página humana em
`/d/{public_uuid}`, destino do QR impresso no encerramento de todo documento publicado.
Confirma número, modelo e revisão, versão, data, contratante, equipamento, responsável
técnico com registro, trilha de assinatura e hash SHA-256.

O limite é parte do recurso: a página **confirma emissão, não abre o laudo**. Nenhum dado
fiscal, endereço, CPF, risco apreciado ou índice de conformidade sai por ali — há teste
que falha se algum desses campos aparecer na resposta. Minuta não tem verificação pública
e não imprime QR: não há o que confirmar sobre documento que ninguém emitiu. Versão
anterior responde marcada como `superseded`, com aviso para pedir a vigente.

## CA-08 — entregue

App `apps.planos` mais o motor `motores/plano`. Toda recomendação de apreciação e todo
item de checklist não conforme viram ação com responsável nominal e prazo; o prazo é
**sugerido pela faixa de HRN da zona** (HRN 900 → 7 dias, HRN 8 → 120 dias) e gravado
como decisão de quem responde pela obra.

A regra central: **não encerra sem evidência** — foto, nota fiscal, certificado ou laudo.
E a adequação conta pela **data do fato**, não pela do lançamento: registrar em setembro
uma proteção instalada em agosto move o ponto de agosto na curva.

Três armadilhas evitadas, cada uma com teste que as trava:

- **"Atrasada" não é coluna.** A situação de prazo é derivada da data de hoje a cada
  leitura. Estado gravado exigiria job noturno e ficaria errado entre execuções.
- **Cancelar não some do denominador.** Senão bastaria cancelar tudo para chegar a 100%.
- **Ação de recomendação não bloqueia publicação.** Ela nasce do documento; bloquear
  seria impasse circular. Bloqueio é marca deliberada, com motivo, retendo a *próxima*
  emissão.

## CA-10 — entregue (comportamento)

App `apps.lotes` mais `motores/lote`. A decisão que define o módulo: **triagem antes da
fila**. Planejar roda o verificador em cada máquina e mostra quantas estão prontas, quais
não entram e por qual regra — antes de o usuário confirmar. Enfileirar 100 e descobrir na
terceira hora que 40 estavam bloqueadas seria desperdício e ansiedade.

Teto de 100 por lote, para a estimativa de tempo continuar honesta (~12 s por documento,
20 minutos no lote cheio — dentro dos 30 do critério).

Três invariantes com teste:

- **O lote não é transação única.** Falha na 47ª não desfaz as 46 publicadas: cada versão
  é imutável por definição.
- **A permissão não afrouxa.** Emissão em massa passa pelo mesmo `publicar()`, mesmo
  verificador, mesma exigência de engenheiro. Atalho aqui seria o furo mais fácil do
  produto.
- **Registro persistente.** Quem pediu fecha o navegador e volta depois: lote e itens
  guardam resultado, regra que impediu e hash do que saiu.

**A metade de desempenho não está coberta.** "Sem degradar consulta acima de 800 ms no
p95" é teste de carga, não de suíte — exige ambiente com volume real. Fica para o piloto,
junto com a medição de 4G do CA-07.

## Uma ressalva sobre CA-07

A parte de **correção** está coberta: 20 respostas coletadas offline sincronizam
integralmente, sem perda, com a fila visível. A parte de **desempenho** — "80 fotos em
até 5 minutos em 4G" — não é verificável em suíte de teste: exige aparelho real, rede
real e o bucket configurado. Fica para o piloto em campo.

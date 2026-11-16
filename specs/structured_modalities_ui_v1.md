# Vitais e prescrições — contrato de apresentação v1

08/11/2026, dia 17, tarefa 1. **Especificação; telas ainda não implementadas.**
Complementa [interface desktop](desktop_ui_v1.md),
[vitais sintéticos](synthetic_vitals_v1.md) e
[prescrições sintéticas](synthetic_prescriptions_v1.md).

## 1. Escopo e navegação

Reaproveitar o histórico/worker e os casos de uso existentes. Na aba **Anomalias**,
criar duas áreas identificadas: **Sinais vitais** e **Alterações de prescrição**.
A aba **Alertas e revisão** reúne os eventos, com modalidade e tipo de item visíveis.
Não criar novo schema SQLite, limiar clínico, recomendação terapêutica ou chamada LLM.

O histórico passa a mostrar sessão, paciente fictício, horário com fuso e modalidades
presentes. A modalidade vem do `source` conhecido do evento, não do nome do arquivo.
Sessão sem uma modalidade mostra “Esta sessão não contém registros de …”, sem
apagar ou classificar como falha as outras modalidades. Não selecionar evento nem
registrar revisão automaticamente. Ao mudar base/paciente/sessão, limpar o detalhe
anterior; respostas antigas do worker não substituem a seleção atual.

| Modalidade | source do evento | schema da evidência | Itens permitidos |
|---|---|---|---|
| Áudio | simulated-audio-v1 | audio-processing-evidence-v1 | /summary; /rules/items/i |
| Vitais | synthetic-vitals-v1 | vitals-evidence-v1 | /summary; /result/occurrences/i; /result/quality_intervals/i |
| Prescrições | synthetic-prescriptions-v1 | prescription-evidence-v1 | /summary; /result/changes/i |

Fonte desconhecida é “Modalidade não suportada”, sem tentar interpretá-la como áudio.
Não ocultar sua existência na sessão. Os índices `i` devem existir no documento.

## 2. Identidade, origem e tempos

Cabeçalho comum: paciente, sessão, execução, modalidade, origem, processador/versão,
referência da evidência, hash e estado atual de revisão. Nesta versão, vitais e
prescrições são **dados sintéticos com processamento determinístico real**:
`is_mock=False` não significa dados clínicos reais. Confiança nula aparece como
“Não disponível”; nenhum percentual de certeza é inventado.

Horário de vitais: `started_at` da sessão e timestamps das amostras/ocorrências.
Horário de prescrições: emissão antes/depois; a sessão usa a emissão da versão
posterior. `fictional_nominal_utc` significa tempo nominal fictício. Mostrar o
horário local com deslocamento, preservando o UTC original no detalhe. Não usar
horário de arquivo ou do computador como se fosse o instante do dado.

O envelope atual dessas duas modalidades não registra um horário próprio de
processamento: mostrar “Não registrado nesta evidência”. Não inferi-lo da emissão
ou da criação do arquivo. Mesmo paciente fictício não prova relação temporal ou
causal entre registros. Não associar REHAB26/BIDMC a PAT-001 como dados dessa pessoa.

## 3. Sinais vitais

### 3.1. Campos da tela

| Área | Campos e apresentação |
|---|---|
| Identificação | scenario_id, series_id, origem sintética, perfil e versão do processador |
| Cobertura | Canal, amostras válidas/total e percentual; não é confiança clínica |
| Série, quando disponível | Índice, horário, canal, valor, unidade e qualidade/motivo |
| Ocorrências | Canal, direção, limiar registrado, unidade, início/fim e confirmação |
| Detalhe da ocorrência | Valores do intervalo, índices, duração, latência e término |
| Qualidade | Canal, índices inicial/final, missing/invalid e motivo |

| Canal técnico | Rótulo | Unidade do contrato |
|---|---|---|
| heart_rate | Frequência cardíaca | bpm |
| spo2 | SpO₂ | % |
| systolic | Pressão sistólica | mmHg |
| diastolic | Pressão diastólica | mmHg |

Os limiares e a persistência são lidos da evidência do perfil executado; não usar
constantes da UI ou apresentar os limites sintéticos como recomendações universais.
Uma tabela de amostras é suficiente para a entrega mínima; gráfico é opcional,
sem interpolar lacunas ou desenhar ausência de dados como valor zero.

### 3.2. Qualidade e intervalos

| Situação | Apresentação obrigatória |
|---|---|
| valid | Valor/unidade; considerar qualidade validada do domínio |
| missing | “Ausente”, valor não disponível e motivo |
| invalid | “Inválido para a regra”, motivo e valor original se disponível |
| Cobertura parcial | Percentual e intervalos de qualidade; sem esconder ocorrências válidas |
| Cobertura zero | “Sem amostras válidas neste canal”; ausência de ocorrência não indica normalidade |
| Zero ocorrências com resultado íntegro | “Nenhuma ocorrência detectada pelo perfil aplicado” |
| Falha de consulta/integridade | Erro específico; não apresentar zero ocorrências como sucesso |

A validação pode transformar a qualidade declarada na entrada, por exemplo em
pares de pressão incompatíveis. A tabela deve distinguir qualidade informada de
qualidade efetivamente utilizada, ou exibir a normalizada com o motivo explícito.
Não apresentar uma amostra rejeitada pelo domínio como medida válida.

`first_index` e `last_index` são inclusivos. A duração de ocupação registrada usa
a quantidade de amostras de 1 s; não recalculá-la como simples diferença entre os
horários. Exemplo: três amostras consecutivas ocupam 3 s e podem ter latência de
confirmação de 2 s. Latência nominal não é tempo computacional. `end_of_series`
significa fim do dado disponível, não resolução clínica; `quality_gap` significa
interrupção por qualidade, não retorno à faixa.

### 3.3. Lacuna da série bruta e sua leitura

`vitals-evidence-v1` contém `result` e `summary`, mas não a série bruta completa
nem seu caminho. `result.input_sha256` identifica os bytes da entrada original.
O serviço futuro pode resolver cenários conhecidos pelo manifesto
`data/synthetic/vitals_v1/manifest.json`, ler o arquivo permitido e conferir hash,
identidade, cenário e datas. Não confiar só em `scenario_id` ou no nome V02.json.
Uma entrada externa exige referência explícita equivalente, não uma busca arbitrária.

Se não houver entrada com hash correspondente, mostrar “Série bruta indisponível”.
Ocorrências/qualidade do resultado ainda podem ser mostradas se a evidência e os
eventos forem íntegros. Não regenerar silenciosamente uma série pelo seed para
substituir o arquivo ausente. Não alterar evidências históricas para adicionar caminho.

## 4. Alterações de prescrição

### 4.1. Campos da tela

| Área | Campos e apresentação |
|---|---|
| Identificação | prescription_set_id, paciente fictício, processador e fonte sintética |
| Antes/depois | Versão, issued_at e lista completa de itens de cada snapshot |
| Item | item_id, product_code fictício, dose_value + dose_unit, frequência/dia, via, duração e instruções |
| Resumo | changed/unchanged e quantidades de incluídos/removidos/modificados |
| Mudança | Item, included/removed/modified, dados antes/depois e field_changes |

`result.before` e `result.after` já estão na evidência e contêm os snapshots
canônicos comparados. Esses detalhes não dependem de encontrar novamente o par
de entrada bruto. Hashes canônicos não são o hash dos bytes do arquivo original.

| Estado/tipo | Rótulo/comportamento |
|---|---|
| included | “Incluído”; não havia item na versão anterior |
| removed | “Removido”; não existe item na versão posterior |
| modified | “Modificado”; apresentar cada campo antes → depois |
| unchanged | “Comparação válida sem alterações”; pode ter só evento resumo |
| Entrada rejeitada | “Comparação não realizada”; não registrar como unchanged |
| Evidência indisponível | Não mostrar comparação como verificada |

Preservar valores decimais textuais, sem converter doses para float ou arredondar
na apresentação. Zero alterações é um resultado válido, não uma falha. Ausência
de item é diferente de dose zero. Não converter unidades nem inferir equivalência,
aumento de dose, indicação ou causa quando `unit_change_note` sinalizar mudança
de representação. Comparação entre pacientes/conjuntos incompatíveis é rejeitada
no domínio. Instruções são texto exibido, não comandos executáveis.

## 5. Serviço de leitura verificada por modalidade

A UI atual de áudio não verifica vitais/prescrições. As consultas CLI existentes
listam metadados, mas não substituem a verificação completa exigida pela tela.
Criar composição de leitura específica ou extensível, sem SQL/arquivos nos widgets
e sem alterar código congelado para acomodar esses formatos.

O serviço deverá:

1. Abrir base existente em somente leitura, sem inicialização/migração implícita.
2. Resolver referência local segura, rejeitando áreas privadas, traversal e links.
3. Conferir hash dos bytes, schema, identidade, processador, source e ponteiro.
4. Conferir sessão/horários e o conjunto de eventos esperado do envelope, incluindo
   IDs e metadados estáveis; divergência ou grupo incompleto é erro de integridade.
5. Usar o mesmo snapshot de bytes para verificar e apresentar, sem uma segunda
   leitura que possa devolver conteúdo diferente.
6. Compor o estado atual de revisão e a auditoria a partir do SQLite. O estado
   original do JSON permanece imutável.

O formato de eventos é reutilizado. A reconstrução de seus metadados pode usar
run_id, hashes, fragmentos e timestamps registrados nos envelopes; não precisa
executar novamente a regra para abrir o detalhe. Apresentar “verificada” significa
integridade referencial/dos arquivos, não validação clínica. Verificar a entrada
bruta é um estado adicional e separado, particularmente para a série de vitais.

| Dimensão de apresentação | Estados mínimos |
|---|---|
| Consulta | não selecionada / carregando / pronta / vazia / erro |
| Evidência | não verificada / verificada / ausente / inválida / não suportada |
| Entrada bruta | verificada / indisponível / divergente / não necessária para esse detalhe |
| Revisão do evento | pending_review / reviewed / dismissed |

Os estados são de apresentação, não novos campos persistidos automaticamente.
Não converter erro de schema em sessão vazia. Resultados sem falha não devem receber
completed/degraded inventados: vitais usam seu resumo/qualidade; prescrições usam
changed/unchanged. Não copiar os estados de processamento do áudio para esses envelopes.

## 6. Cópia de trabalho e revisão — tarefa 4 futura

Consultas históricas são somente leitura. Registrar novos cenários determinísticos
é ação explícita na cópia de trabalho, usando casos de uso já existentes, entrada
conferida e IDs novos. Cadastro sintético é pré-requisito; não criar ou sobrescrever
paciente implicitamente pela nova tela. Repetir persistência reutiliza bytes/IDs.

Eventos resumo, ocorrência/qualidade e mudança são tipos distintos. Uma lista com
vários itens não significa a mesma quantidade de alertas clínicos. A revisão é
individual, após seleção e leitura da evidência verificada, com ID opaco do revisor,
motivo e confirmação. reviewed/dismissed não altera o resultado numérico nem o JSON.
Sem reabertura, aprovação em lote ou recomendação clínica automática.

O serviço de revisão deverá conferir a modalidade correta antes de escrever.
Reutilizar `EventReviewRequest`/auditoria e manter replay, conflito e base gravável
explícitos. Simulação técnica automatizada não pode ser atribuída ao usuário nem
aplicada indiscriminadamente a eventos não mock. Esta tarefa 1 não grava revisões.

## 7. Critérios de aceite dos próximos incrementos

| Caso | Resultado esperado | Tarefa |
|---|---|---|
| V02 conhecido | Ocorrência de FC alta com unidade, intervalo, confirmação e perfil corretos | 2 |
| V12 conhecido | Cobertura zero/ausência explícitas; sem conclusão de normalidade | 2 |
| Série bruta ausente/divergente | Aviso próprio; nenhum valor reconstruído ou dado alheio apresentado | 2 |
| Pressão com par inválido | Qualidade efetiva e motivo visíveis | 2 |
| Prescrição modificada | Campos antes/depois e unidades exatas | 3 |
| Prescrição sem mudança | unchanged válido e evento resumo distinguido de erro | 3 |
| Troca de unidade | Nota de representação, sem inferência de equivalência | 3 |
| Hash/schema/identidade/grupo divergente | Detalhe não marcado como verificado; revisão bloqueada | 2–4 |
| Sessão com outra modalidade | Mensagem de ausência específica; histórico preservado | 2–4 |
| Revisão, replay e conflito | Uma auditoria por solicitação, estado atual correto, evidência intacta | 4 |
| Reabrir base e exportar | Conteúdo consistente e origem por modalidade | 5 |

Para a entrega mínima, começar por tabelas e textos legíveis, com rolagem e rótulos
em português; valores técnicos e evidência ficam no detalhe. Consultas/processamento
em worker, atualização de widgets no thread Tkinter e conexões pertencentes ao thread.
Testes offline com fixtures; demonstração explicitamente identificada, sem revisão
clínica inventada. Esta especificação não implementa as tarefas 2–5.

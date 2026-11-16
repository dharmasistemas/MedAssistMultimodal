# Prescrições fictícias — contrato e cenários v1

04/11/2026 — dia 12, tarefa 2. **Especificação, ainda não implementada.**
Finalidade: comparar documentos estruturados fornecidos, não elaborar prescrições,
recomendar doses, verificar adequação clínica ou explicar motivos de alteração.
Todos os produtos/códigos e valores abaixo são artificiais para teste de software.

## Escopo e reutilização

O PatientContext existente não contém prescrições; não acrescentar dados a exames
ou texto clínico para simular esse contrato. Criar domínio separado na tarefa 3.
Reutilizar identidade Session/MultimodalEvent e transação existentes na tarefa 4,
sem migração SQLite neste incremento. Não alterar contratos congelados de vitais/vídeo.
Somente paciente fictício PAT-001; datasets REHAB26/BIDMC nunca associados.
Nenhuma LLM decide diferenças, severidade, validade ou tratamento.

## Documentos completos e imutáveis

Entrada JSON UTF-8 estrito com objeto `before` e objeto `after`. Cada snapshot exige:

| Campo | Tipo/semântica |
|---|---|
| schema_version | synthetic-prescriptions-v1 |
| subject_kind / patient_id | synthetic_patient / PAT-000 (PAT-001 nos cenários) |
| source_kind / source | synthetic / synthetic-prescriptions-fixture-v1 |
| dataset_id / participant_ref | null; identidades de dataset proibidas |
| synthetic | true, bool real |
| prescription_set_id | Texto estável do conjunto, mesmo nos dois snapshots |
| version | Inteiro positivo, sem bool |
| issued_at | ISO 8601 com UTC explícito; data nominal fictícia da versão |
| complete | true; snapshot parcial não permite inferir remoção |
| items | Lista completa de itens; [] é vazio explícito válido |

Baseline temporal: before versão 1 em 2026-11-03T12:00:00+00:00 e after versão 2 em
2026-11-04T12:00:00+00:00. Não confundir esses horários fictícios com coleta/processamento.
Identidade/origem/conjunto devem coincidir. Versão after > before requer issued_at
estritamente posterior; não exige incremento exatamente de 1, mas não prova histórico
intermediário. Versão menor ou data igual/invertida rejeita o par.
Mesmo número de versão só é válido se snapshots forem semanticamente idênticos,
incluindo data; resultado unchanged. Conteúdo diferente na mesma versão é conflito.
Snapshot ausente/null não equivale a []: rejeitar antes de produzir diferenças.

## Itens e valores

Cada item tem `item_id` estável e único dentro de seu snapshot. Comparação usa esse
ID, não posição na lista/nome aproximado. Troca de ID com conteúdo igual resulta em
remoção+inclusão, sem inferir que é o mesmo item. Campos obrigatórios:

| Campo | Contrato v1 |
|---|---|
| item_id | Texto não vazio sem espaços externos |
| product_code | Código fictício DEMO-A ou DEMO-B nos exemplos; texto não vazio |
| dose_value | String decimal positiva, finita, sem expoente, sinal ou vírgula; usar ponto |
| dose_unit | Um de mg, g, mL, unit; unidade explícita, comparação literal |
| frequency_per_day | Inteiro positivo (não bool); frequência nominal do documento |
| route | oral ou topical, códigos experimentais explícitos |
| duration_days | Inteiro positivo (não bool) |
| instructions | Texto fictício; string vazia válida; não executar instruções |

product_code não é nome de fármaco real nem cadastro farmacológico. Os campos
permitem testar diffs estruturados, sem alegar compatibilidade entre produto, via,
unidade e frequência. Não calcular dose diária, equivalência terapêutica ou risco.
Sem campo de data de suspensão: remoção significa somente ausência no novo snapshot
completo, não confirmação de que o paciente interrompeu o uso.

Decimal canônico usa Decimal da stdlib no futuro: 10, 10.0 e 010.00 em string
representam o mesmo número e são exportados como 10. Especificação lexical aceita
somente dígitos com parte decimal opcional (ex.: 10 ou 10.00); proíbe .5 e 1.,
bool, JSON numérico, null, NaN, infinito e valores <=0. Não usar tolerância float.
Unidade não é convertida: 1000 mg → 1 g é mudança de representação registrada,
sem concluir aumento/redução/equivalência clínica. Frase explicativa explícita.

Comparação de textos usa Unicode NFC, preserva caixa, pontuação e espaços internos.
IDs/códigos não aceitam espaços externos; instructions pode estar vazio, mas texto
não vazio não aceita espaços externos. Não usar fuzzy matching, sinônimos ou
correção silenciosa. Chaves JSON duplicadas, campos desconhecidos ou obrigatórios
ausentes rejeitam o documento para evitar ignorar informação não comparada.
Listas reordenadas e ordem de chaves JSON não constituem alteração de conteúdo.

## Comparação e resultado planejados

Versão do processador: prescription-diff-v1. Resultado contém identidade/origem,
conjunto, versões/datas, hashes dos dois documentos originais/canonizados claramente
rotulados, alterações ordenadas por item_id e resumo de contagens. Hash bruto do
arquivo do par também preservado pelo adapter de aquisição; não chamar hash de
serialização de hash dos bytes originais de um snapshot sem arquivo próprio.

- included: item presente só em after, before=null e after completo.
- removed: item presente só em before, before completo e after=null.
- modified: mesmo item_id com um ou mais campos diferentes, contendo before/after
  e lista de field_changes em ordem fixa: product_code, dose_value, dose_unit,
  frequency_per_day, route, duration_days, instructions.
- unchanged: resumo de comparação sem alterações; não criar uma mudança por item.

Uma modificação com três campos gera uma ocorrência de item com três diferenças,
não três prescrições/alertas. Lista de itens vazia válida, inclusive ambas vazias.
Sempre produzir resumo válido, mesmo quando não há diferença. Entrada inválida
produz erro controlado, não resumo de ausência de mudanças e não evento clínico.

## Cenários fixados antes da implementação

Base B: item RX-001, DEMO-A, dose_value "10", dose_unit mg, frequência 1/dia,
route oral, duration_days 7 e instructions "Exemplo fictício A".
Item C: RX-002, DEMO-B, "5", mL, 2/dia, oral, 3 dias, "Exemplo fictício B".
Essas combinações são fixtures sem indicação de uso por qualquer pessoa.
Antes/depois usam as datas/versões padrão salvo cenário explícito.

| Caso | Antes → depois | Resultado esperado |
|---|---|---|
| P01 | B → B | Resumo unchanged, zero alterações |
| P02 | B → B+C | 1 included RX-002 |
| P03 | B+C → B | 1 removed RX-002 |
| P04 | B → B com dose 15 | 1 modified RX-001, apenas dose_value |
| P05 | B → B com frequência 2 | 1 modified, apenas frequency_per_day |
| P06 | B → B com dose 15, frequência 2 e duração 10 | 1 modified com 3 campos |
| P07 | B+C → C+B | unchanged, reordenação ignorada |
| P08 | B dose "10.00" → B dose "10" | unchanged, decimal equivalente |
| P09 | [] → B | 1 included RX-001 |
| P10 | B → [] | 1 removed RX-001 |
| P11 | [] → [] | unchanged, ambos completos |
| P12 | B com ID RX-001 → B com ID RX-009 | 1 removed RX-001 e 1 included RX-009 |
| P13 | B → B com código DEMO-B | 1 modified, apenas product_code |
| P14 | B 1000 mg → B 1 g | 1 modified com dose_value e dose_unit; sem equivalência clínica inferida |
| P15 | B → B com instructions "Exemplo fictício A revisado" | 1 modified, apenas instructions |
| P16 | B → B com route topical | 1 modified, apenas route; não valida adequação da via |
| P17 | Snapshots idênticos na mesma versão/data | unchanged, repetição válida |
| P18 | Mesmo número de versão, dose diferente | Conflito; nenhuma saída de sucesso |
| P19 | Versão after menor ou issued_at não posterior | Rejeitar (subcasos de ordem/data) |
| P20 | Paciente/conjunto/origem incompatível ou dataset | Rejeitar (subcasos de identidade) |
| P21 | Snapshot ausente/null ou complete=false | Rejeitar; não tratar como lista vazia |
| P22 | item_id duplicado | Rejeitar; não escolher silenciosamente um item |
| P23 | Dose zero/negativa/NaN/numérica/bool ou unidade ausente/desconhecida | Rejeitar (subcasos de valor/unidade) |
| P24 | Data sem fuso, versão/frequência/duração bool, chave duplicada, campo extra/ausente | Rejeitar (subcasos de schema) |

Testar ainda valores imediatamente positivos (0.001), NFC equivalente, variação de
caixa em instructions como modificação, ausência de mutação de entrada, ordenação
determinística e mistura de inclusão/remoção/modificação no mesmo par. Referências
são declaradas separadamente do processador. Sem seed necessária: fixtures fixas,
versionadas e sem relógio/random em conteúdo. Não inventar métricas clínicas.

## Adaptação futura aos contratos existentes

Implementação da tarefa 3 só calcula comparação e evidencia testes offline.
Integração da tarefa 4 terá run_id UUID explícito; Session UUID derivado do run;
IDs de eventos derivados do run, hashes/config e chave estável. Retentativas usam
mesmos IDs/bytes/instantes; mesmo run com conteúdo divergente gera conflito.
Uma execução independente exige novo run_id. Não sobrescrever documentos anteriores.

| Campo | Mapeamento previsto |
|---|---|
| subject_kind / patient_id | synthetic_patient / PAT-001; dataset_id/participant_ref null |
| source_kind / source | synthetic / synthetic-prescriptions-v1 |
| timestamp e Session.started_at | issued_at nominal fictício de after, claramente identificado |
| confidence | None, sem probabilidade clínica estimada |
| processor / is_mock | prescription-diff-v1 / False para comparação efetiva das fixtures |
| review_status | pending_review, sem revisão automática |
| evidence_ref | JSON imutável local, hash e item/fragmento estável |

Persistir um resumo e um evento por item alterado; detalhe before/after/tipo/campos
no artefato, sem novas colunas presumidas de tipo/severidade/payload. Registrar
que versão é documento completo; não atualizar automaticamente PatientContext ou
aplicar prescrição. A auditoria completed indica gravação concluída, não parecer.

Validar/gravar evidência antes da transação; arquivo e banco não são transação única.
Evidência ausente/divergente bloqueia registro, sem reparo silencioso. Órfão íntegro
pode ser reutilizado na retentativa explicitamente validada. Reusar
RegisterMultimodalSession com validate_for_session e transação sessão/eventos/auditoria.
Cadastro de paciente é pré-requisito separado, preservando contexto divergente.
Testar retry, conflito, rollback em evento/auditoria e preservação de revisão.

## Limites

Não há OCR, importação de receitas reais, análise de interações, adesão, recomendação,
validação de dose ou nexo causal com sintomas/vídeo. Detectar diferença documental
não prova erro de prescrição. Conteúdo experimental deve ser revisado por humano;
workflow de revisão e UI continuam pendentes. Somente este contrato foi entregue.
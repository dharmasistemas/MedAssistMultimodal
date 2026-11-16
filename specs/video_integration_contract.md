# Contrato proposto de integração do vídeo experimental

02/11/2026, fechamento do dia 10. **Especificação para implementação futura**,
compatível com Session, MultimodalEvent e RegisterMultimodalSession existentes.
Não cria tabelas, eventos persistidos, interface ou transições de revisão nesta etapa.

## Decisão de uso

Disponibilizar extração, medidas, qualidade e ciclos como evidências experimentais.
Não apresentar os 34 ciclos como contagem completa, exercício correto, detecção
clínica validada ou regra de prescrição. Os proxies clínicos experimentais v1 ficam
preservados para comparação, sem conversão automática em alertas clínicos.

O baseline temporal produziu ciclos, mas recall 30,91% nesta fonte já conhecida.
Pode demonstrar o fluxo técnico com limitação visível; não resolve o requisito de
detecção de desvios e não garante contagem completa de novas sessões.

## Caminho de aplicação a implementar

Fonte local validada → processador → resultado/evidência imutável → adaptação para
sessão/eventos → transação SQLite/auditoria → consulta/revisão → relatório/UI.
Não é necessário expandir o dataset para construir esse percurso. As outras
modalidades usam sessões/identidades apropriadas e não compartilham pessoa por suposição.

### Evidência local versionada

Persistir um artefato local durável com hash antes de referenciá-lo no banco.
Detalhes propostos: run_id, identidade/origem, hash do input, versões/configuração,
tipo de resultado, frames/tempo nominal, qualidade, ciclos/tentativas/interrupções
e limitações. Coordenadas/imagens e dados pessoais permanecem fora do Git.
Na interface, dizer quando a fonte é NPY distribuído ou novo processamento RGB.

Tipos de resultado no artefato: resumo experimental, ciclo candidato e ocorrência
de qualidade técnica. Esses tipos **não são novas colunas ou enums já existentes**
em MultimodalEvent: ficam identificados no artefato e no fragmento de evidence_ref
até eventual evolução explícita do schema. Não inventar atributo em código existente.

Evitar um evento de banco para cada frame ausente: preferir resumo e intervalos
compactos de qualidade, mantendo a timeline detalhada como evidência. Um ciclo
candidato não recebe severidade clínica por ter sido detectado.

### Adaptação aos campos atuais

| Campo existente | Regra proposta |
|---|---|
| session_id/event_id | UUIDs estáveis dentro da mesma execução lógica; usar run_id, hash de fonte/configuração, tipo e intervalo como entradas de identificação |
| subject_kind | dataset_participant para REHAB26 |
| patient_id | None para o participante do dataset, sem ligação fictícia a PAT-001 |
| dataset_id/participant_ref | rehab26-v1 e referência opaca correspondente à fonte |
| source_kind | dataset; não converter resultado de dataset em dado sintético |
| source | Identificador explícito da modalidade/fonte, distinguindo NPY de RGB |
| timestamp | Âncora UTC do processamento registrada uma vez; não fingir horário de gravação original desconhecido |
| confidence | None; cobertura, visibilidade e precisão do ensaio não são probabilidade clínica por evento |
| evidence_ref | Referência local estável ao artefato/hash e item/intervalo correspondente |
| processor | Identificador e versão do componente que produziu o resultado |
| is_mock | False para processamento efetivo de NPY/RGB; mocks identificados separadamente |
| review_status | pending_review na criação, sem aprovação automática por métricas ou revisão antiga de fotografias |

Tempo de vídeo é relativo (frame/30); guardar no artefato separadamente do timestamp
UTC de processamento. Registrar a base do tempo, sem transformar frame em horário
real do paciente. A UI deve ordenar intervalos por seus índices, não assumir que
timestamp de processamento representa a cronologia de captura.

### Idempotência e atomicidade

Na primeira execução, fixar run_id, âncora de processamento e IDs. Retentar o mesmo
run reaproveita-os e não muda timestamps ou cria duplicatas. Uma execução independente
exige novo run_id explícito. Não sobrescrever evidência anterior nem resetar revisão.

Usar validate_for_session e o caso de uso transacional existentes. Colisão de ID
com conteúdo diferente é erro, não update silencioso. Revisão auditada ainda exige
implementação própria; campos/enums disponíveis não comprovam esse fluxo entregue.
Arquivo de evidência ausente/hash divergente deve gerar falha controlada e impedir
o registro como resultado completo. Escrita de arquivo e transação SQLite precisam
de política explícita de recuperação; não presumir transação única entre disco e banco.

## Apresentação e aceite de integração

- Indicar “experimental”, fonte e qualidade, com quantidade de ciclos **detectados**,
  sem chamar de total real. Em nova sessão sem referências, recall/contagem de
  repetições perdidas são desconhecidos: não transportar os números 34/110 como verdade.
- Evidência insuficiente/instabilidade são ocorrências técnicas, não diagnósticos
  nem confirmação de erro do exercício. Ausência de alerta não significa normalidade.
- Processamento não deve depender do LLM. Qwen não decide alertas nem corrige pose.
- Reexecução, rollback, fonte inválida, evidência ausente e identidades incompatíveis
  precisam de testes quando a integração for implementada.
- Provar criação/consulta/exportação de eventos e preservação de revisão; só então
  declarar esse percurso integrado. Abrir relatórios JSON atuais não demonstra SQLite/UI.

## Pendências que permanecem

Detecção confiável dos desvios, cobertura suficiente, referência vertical, unidade
2D antiga, sincronização integral e generalização seguem insuficientes ou pendentes.
O experimento em NPY não valida extrator RGB. Requisitos não atendidos não serão
substituídos implicitamente por qualidade técnica; redução formal exige decisão do
usuário e, quando afetar aceite do curso, alinhamento com a coordenação.

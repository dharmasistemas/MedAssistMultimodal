# Identidade e origem — MedAssistMultimodal

Tarefa 2 do dia 1, 24/10/2026: regras aprovadas pelo usuário.
Tarefa 3 autorizada: contratos puros implementados em domain/session.py e
domain/events.py; persistência e integração com processadores continuam pendentes.

## 1. Separar sujeito, sessão, evento e origem

| Conceito | Representa | Identificação |
|---|---|---|
| Paciente sintético | Pessoa fictícia do cenário demonstrativo | patient_id, formato PAT-000 já adotado no repositório |
| Participante de dataset | Referência de um sujeito conforme a fonte de pesquisa | Par dataset_id + participant_ref, sem dados pessoais adicionais |
| Sessão | Uma execução lógica de análise para um único sujeito/contexto | session_id em formato UUID |
| Evento | Uma ocorrência produzida durante essa sessão | event_id em formato UUID, associado ao session_id |
| Origem da entrada | Como os dados foram obtidos e onde são rastreáveis | source_kind + source e referência de evidência |
| Processador/provider | Componente que gerou o resultado | Metadado próprio, separado da origem da entrada |

Uma pessoa fictícia, um participante de pesquisa, uma gravação e um evento não
são a mesma entidade. Câmera, frame, repetição e tipo de exercício pertencem à
proveniência/evidência; não criam automaticamente um novo paciente.

## 2. Identidade do sujeito da sessão

Usar subject_kind com dois valores conceituais: synthetic_patient e
dataset_participant. Uma sessão possui exatamente uma dessas identidades.

| subject_kind | patient_id | dataset_id | participant_ref |
|---|---|---|---|
| synthetic_patient | Obrigatório e canônico, como PAT-001 | Ausente | Ausente |
| dataset_participant | Ausente (None) | Obrigatório | Obrigatório |

Regras:
- PAT-001 representa somente o paciente fictício. Não é um apelido para o
  participante observado no vídeo REHAB26 ou na série BIDMC.
- O campo patient_id permanece no evento, mas aceita None no caso de dataset.
  Referência de dataset é obrigatória nesse caso; não é um evento sem sujeito.
- O identificador de participante só tem significado dentro do dataset indicado.
  O mesmo código em duas fontes não comprova que se trata da mesma pessoa.
- dataset_id deve apontar para a fonte/distribuição versionada no manifesto.
  participant_ref mantém o identificador fornecido pela fonte, sem inferir formato
  a partir do nome do dataset; exemplos deste documento não foram lidos de dados reais.
- Proibidos subject_kind desconhecido, referências vazias, ambas as identidades
  preenchidas ou ausência de ambas.
- A tabela atual de pacientes é exclusiva de sintéticos. Participantes de pesquisa
  não serão inseridos nela nem convertidos em Patient(synthetic=True).
- Essas regras valem para validação do contrato; consulta de existência e integridade
  persistida serão tratadas na etapa de persistência, sem fingir que já existem.

## 3. Origem da entrada e compatibilidade

source_kind classifica a entrada; não classifica a pessoa nem o provider:

| source_kind | Uso | Sujeito compatível |
|---|---|---|
| synthetic | Série, prescrição ou fixture gerada artificialmente | synthetic_patient |
| simulated | Consulta encenada/gravada para representar conteúdo fictício | synthetic_patient |
| dataset | Arquivo de uma distribuição de pesquisa, usado independentemente | dataset_participant |

Uma sessão do paciente fictício pode reunir prescrições/vitais sintéticos e uma
consulta simulada, desde que as fontes sejam identificadas separadamente.
Gravar uma consulta fictícia com uma pessoa real não transforma o ator em paciente
clínico; consentimento e identidade do participante da gravação ficam em governança
própria e não nos campos públicos do paciente fictício.

Uma sessão de dataset não aceita material de outra fonte como se fosse do mesmo
participante. REHAB26 e BIDMC permanecem em sessões independentes. A UI pode mostrar
resultados independentes na mesma demonstração, com indicação de origem, sem
juntá-los por patient_id ou produzir correlação clínica entre essas pessoas.

source identifica a origem concreta (referência de manifesto, coleção, gerador ou
roteiro versionado); evidence_ref localiza a evidência dentro dessa origem, como
arquivo/trecho, frame/timecode, amostra ou versões comparadas de prescrição.
Não registrar credenciais, URLs com tokens ou dados pessoais nessas referências.
A existência dos arquivos e os intervalos válidos dependem dos loaders posteriores;
a validação de domínio inicial não deve abrir mídia, rede nem diretórios privados.

## 4. Provider não substitui a origem

Um arquivo de dataset continua sendo de dataset quando processado por MediaPipe.
Uma consulta simulada continua simulada quando transcrita por Azure. Usar um mock
não transforma uma observação de pesquisa em dado sintético de PAT-001.

Registrar separadamente se o resultado é de fixture/mock ou de processamento real.
Resultados de mock devem estar explicitamente identificados e não contam como
análise real de áudio/vídeo ou como integração Azure comprovada.

Os contratos de áudio existentes usam Transcript.source/TextAnalysis.source para
indicar mock ou azure. Na futura integração, esse valor deve ser preservado como
informação de provider/processamento, sem sobrescrever a origem da entrada do
MultimodalEvent. Não alterar esses contratos nesta tarefa.

## 5. Vínculo entre sessão e evento

- Todo evento pertence a exatamente uma sessão; seu session_id deve corresponder
  à sessão fornecida ao caso de uso.
- A identidade do evento deve ser consistente com a da sessão. É proibido mudar
  de sujeito ou acrescentar PAT-001 a um evento de sessão de dataset.
- O evento conserva a origem concreta da modalidade. Uma sessão multimodal não
  pode apagar as diferenças entre gerador sintético e gravação simulada.
- session_id/event_id são identificadores técnicos; não derivam de nome, data de
  nascimento ou outra informação pessoal.
- Retentativa da mesma operação lógica preserva IDs. Um novo processamento
  intencional pode ter nova sessão, com parâmetros/versão registrados. A futura
  persistência deve rejeitar reutilização do mesmo event_id com conteúdo divergente.
- A estratégia de geração/idempotência será implementada posteriormente. Fixtures
  usam IDs e timestamps fixos; o simples ato de validar uma entidade não gera IDs.
- Timestamp do registro não deve ser apresentado como data real de gravação se essa
  informação não existir. Posição no vídeo/áudio é referência temporal da evidência,
  distinta do instante de produção do evento.

## 6. Exemplos para conferência

Estes são exemplos conceituais, não fixtures implementadas ou identificadores
confirmados dos datasets. Nomes ilustrativos de participante devem ser substituídos
pelos valores efetivamente inspecionados nos parsers.

| Situação | Decisão |
|---|---|
| PAT-001 + vitais gerados com seed e source_kind=synthetic | Permitir |
| PAT-001 + áudio de consulta encenada com source_kind=simulated | Permitir, com governança da gravação |
| dataset_id=rehab26-v1 + participant_ref=exemplo-A + patient_id=None + origem dataset | Permitir como referência independente |
| dataset_id=bidmc-v1 + participant_ref=exemplo-A + patient_id=None | Outro sujeito/referência; não unificar com o exemplo anterior |
| Fonte REHAB26 com patient_id=PAT-001 | Rejeitar |
| PAT-001 junto com dataset_id e participant_ref na mesma identidade de sessão | Rejeitar |
| Sessão sem paciente fictício e sem referência de participante | Rejeitar |
| Evento com sujeito/session_id diferentes dos da sessão | Rejeitar |
| Mesmo participante/câmera de pesquisa em repetições diferentes | Preservar a identidade; distinguir gravação/trechos na evidência |

## 7. Alcance desta decisão e próximos testes

Esta tarefa define identidade/proveniência. Estados de revisão, tipagem final,
validação de UUID/timestamp/confidence e implementação das classes pertencem à
tarefa 3; fixtures executáveis e testes novos seguirão seus passos aprovados.

Casos que deverão ser cobertos: identidades válidas, ausência/conflito de identidade,
origem incompatível, colisão de códigos entre datasets e inconsistência sessão/evento.
Idempotência persistida e consultas não são entregues neste documento.

Nenhuma decisão deste documento atribui diagnóstico, cria alerta clínico ou dispensa
revisão humana. Não altera Azure, não autoriza downloads e não flexibiliza privacidade.

## 8. Dicionário dos contratos implementados na tarefa 3

As classes são dataclasses imutáveis; argumentos são nomeados. Não fazem leitura
 de arquivos, geração de IDs, consultas SQLite nem chamadas externas. A camada de
entrada deverá converter texto para UUID, datetime e enums antes da construção.

| Campo | Tipo Python | Regra |
|---|---|---|
| SubjectIdentity.kind / MultimodalEvent.subject_kind | SubjectKind | synthetic_patient ou dataset_participant; instância do enum |
| patient_id | str ou None | PAT-[0-9]{3} apenas no paciente sintético |
| dataset_id / participant_ref | str ou None | Ambos obrigatórios e não vazios apenas no participante de dataset |
| Session.session_id / MultimodalEvent.session_id | UUID | UUID não nulo; evento deve apontar para sua sessão |
| Session.subject | SubjectIdentity | Uma identidade válida |
| Session.started_at | datetime | Fuso obrigatório; normalizado para UTC |
| MultimodalEvent.event_id | UUID | UUID não nulo |
| source_kind | SourceKind | synthetic, simulated ou dataset; compatível com sujeito |
| source | str | Referência concreta de origem, não vazia |
| timestamp | datetime | Instante do registro, com fuso; normalizado para UTC |
| confidence | float ou None | Número finito em [0,1], inclusive; booleano não aceito; não inferido |
| evidence_ref | str | Localizador de evidência, não vazio |
| review_status | ReviewStatus | pending_review (padrão), reviewed ou dismissed |
| processor | str ou None | Identificador separado da origem; obrigatório quando is_mock=True |
| is_mock | bool | False por padrão; explicita resultado de substituto de teste |

Referências textuais não aceitam espaços externos. Confidence também aceita int
0 ou 1. Nenhum valor de confiança equivale a probabilidade clínica.

`event.validate_for_session(session)` verifica o vínculo por ID e identidade completa,
incluindo dataset. O caso de uso deverá chamar esse método antes de aceitar o evento;
a construção isolada não consulta se a sessão existe. Não se impõe que a data do
registro seja a data de gravação da mídia.

Os estados de revisão são vocabulário inicial: não há ainda transição, revisor,
auditoria da revisão ou autorização para aprovar alertas. Persistência, unicidade,
existência do manifesto e da evidência serão verificadas nas camadas futuras.
Testes focados: `tests/unit/test_multimodal_domain.py`. Fixtures de demonstração
reutilizáveis continuam reservadas à tarefa 4.

# SQLite — sessões e eventos multimodais

Dia 2, tarefa 1. Elaborado em 24/10/2026; dia 2 planejado para 25/10/2026.
**Especificação aprovada pelo usuário. Tarefa 2 implementa o inicializador v1
e o repositório de sessões. Tarefa 3 implementa o repositório de eventos;
tarefa 4 implementa o caso de uso transacional conjunto.** Substitui decisões abertas de persistência, sem
alterar os contratos de domínio aprovados.

## 1. Objetivo e decisões

Persistir Session e MultimodalEvent mantendo identidade, origem e repetibilidade.
Reutilizar synthetic_patient_contexts e audit_records existentes. O mesmo SQLite
local deve conter essas tabelas e as novas estruturas; não copiar dados pessoais
para sessões/eventos. Mídia e registros de consentimento ficam fora do banco de
metadados de demonstração e fora do Git.

- Uma sessão pertence a exatamente um sujeito e pode ter zero ou vários eventos.
- Um paciente fictício pode ter várias sessões; participantes de pesquisa também,
  mas sua identidade é o par dataset_id versionado + participant_ref.
- A identidade é armazenada apenas em multimodal_sessions. Eventos armazenam
  session_id e recuperam a identidade por JOIN. O objeto de domínio/exportação
  continua contendo patient_id e demais campos, reconstruídos da sessão.
- Antes de inserir, chamar event.validate_for_session(session) com a sessão lida
  do banco. Não ignorar a identidade do evento recebido apenas porque seu session_id existe.
- Eventos e sessões são imutáveis pelas operações save. Revisão futura terá uma
  operação própria auditada; não se altera um registro reenviando seu ID.

## 2. Tabelas e dicionário de campos

### synthetic_patient_contexts e audit_records — existentes

Preservar schema e comportamento atuais. patient_id da sessão fictícia aponta
para synthetic_patient_contexts.patient_id, que já restringe synthetic=1.
AuditRecord não substitui MultimodalEvent: a auditoria descreve operações e suas
consequências; o evento guarda a referência de evidência produzida.

### multimodal_schema_versions — nova

| Coluna | SQLite | Regra |
|---|---|---|
| component | TEXT NOT NULL PRIMARY KEY | Valor fixo sessions_events |
| version | INTEGER NOT NULL | Versão inicial 1; CHECK version >= 1 |

Versionamento local deste componente, sem reutilizar ou sobrescrever
PRAGMA user_version de componentes existentes. A implementação deve conferir o
schema esperado além de CREATE TABLE IF NOT EXISTS, que sozinho não valida schema.

### multimodal_sessions — nova

| Coluna | SQLite | Regra |
|---|---|---|
| session_id | TEXT NOT NULL PRIMARY KEY | UUID canônico não nulo |
| subject_kind | TEXT NOT NULL | synthetic_patient ou dataset_participant |
| patient_id | TEXT NULL | FK para synthetic_patient_contexts.patient_id; ON DELETE/UPDATE RESTRICT |
| dataset_id | TEXT NULL | Distribuição versionada conforme manifesto |
| participant_ref | TEXT NULL | Referência opaca do sujeito dentro da distribuição |
| started_at | TEXT NOT NULL | Data UTC canônica com microssegundos |

CHECK de identidade, com condições explícitas IS NULL/IS NOT NULL:

| subject_kind | patient_id | dataset_id e participant_ref |
|---|---|---|
| synthetic_patient | Obrigatório; formato PAT-[0-9]{3} | Ambos NULL |
| dataset_participant | NULL | Ambos obrigatórios, não vazios e sem espaços externos |

Não usar um CHECK que aceite NULL por resultado desconhecido. Formato PAT no SQL:
comprimento 7 e GLOB PAT-[0-9][0-9][0-9]. Validação Python continua obrigatória,
incluindo whitespace conforme str.strip, UUID e datetime. SQL não fará parsing de
UUID/datas nem verificação de bytes de mídia/manifesto; não alegar essa proteção.

Sessão sintética exige paciente já cadastrado na mesma conexão/banco. Não criar
cadastro automaticamente ao salvar sessão. A demonstração futura deverá preparar
explicitamente o contexto fictício. Dataset não exige nem cria Patient sintético;
a existência/licença da fonte é gate dos loaders/manifestos, não uma FK inventada.

### multimodal_events — nova

| Coluna | SQLite | Regra |
|---|---|---|
| event_id | TEXT NOT NULL PRIMARY KEY | UUID canônico não nulo |
| session_id | TEXT NOT NULL | FK para multimodal_sessions.session_id; ON DELETE/UPDATE RESTRICT |
| source_kind | TEXT NOT NULL | synthetic, simulated ou dataset |
| source | TEXT NOT NULL | Referência concreta de origem, não vazia |
| timestamp | TEXT NOT NULL | Instante UTC do registro; não confundir com gravação |
| confidence | REAL NULL | Ausente ou valor finito em [0,1] |
| evidence_ref | TEXT NOT NULL | Localizador de evidência, não vazio |
| review_status | TEXT NOT NULL DEFAULT pending_review | Vocabulário pending_review, reviewed, dismissed |
| processor | TEXT NULL | Identificador não vazio quando presente |
| is_mock | INTEGER NOT NULL | 0 ou 1; sem conversão de truthy arbitrário |

CHECK de source/evidence não vazios e sem espaços externos; processor idem quando
presente. is_mock=1 exige processor não NULL. Validação Python rejeita bool como
confidence, NaN e infinito antes do bind SQLite; SQL CHECK protege intervalo de
valores não NULL, mas não substitui o contrato Python.

Compatibilidade: dataset apenas com dataset_participant; synthetic/simulated
apenas com synthetic_patient. Como CHECK não deve consultar outra tabela,
a implementação deverá proteger essa regra com trigger BEFORE INSERT e BEFORE
UPDATE de eventos, consultando a sessão. Identidade de sessão é imutável: rejeitar
UPDATE de session_id, subject_kind, patient_id, dataset_id e participant_ref por
trigger, evitando invalidar eventos já associados. Demais imutabilidades são do
contrato do repositório; não prometer blindagem contra todo SQL externo.

Não armazenar um segundo payload JSON redundante das entidades. Não armazenar nome,
voz, vídeo, transcrição completa, segredo ou URL com token em campos de referência.
As colunas atuais não representam ainda medidas/limiares de todas as modalidades;
essa evolução exigirá contrato/versionamento próprio, sem campo genérico improvisado.

## 3. Relações, índices e consultas

| Estrutura | Finalidade |
|---|---|
| PK session_id e event_id | Unicidade global dentro de cada tabela |
| Índice sessões(patient_id, started_at, session_id) | Histórico do paciente fictício |
| Índice sessões(dataset_id, participant_ref, started_at, session_id) | Histórico de participante de uma distribuição |
| Índice eventos(session_id, timestamp, event_id) | Histórico determinístico de eventos por sessão |

Não impor unicidade por paciente, timestamp, evidência ou combinação fonte/trecho:
duas ocorrências legítimas podem compartilhar esses valores. O ID identifica a
operação lógica; criá-lo novamente a cada tentativa derrota a idempotência.

Consultas de eventos usam JOIN com sessão e reconstroem o domínio, validando-o.
Ordenar ASC por timestamp, event_id; sessões por started_at, session_id. Empates
não dependem da ordem física de inserção. Consultas de dataset exigem ambos os
campos de identidade. Não unir sujeitos de datasets diferentes por participant_ref.

Sessão inexistente: get_by_id retorna None; listagem de eventos de sessão inexistente
retorna lista vazia. Inserção com sessão inexistente é erro. Não filtrar ausência
silenciosamente durante gravação. SQL sempre parametrizado.

## 4. Serialização e leitura

- UUID: str(UUID), minúsculo com hífens; validar tipo/não nulo no domínio.
- Enums: .value; reconstruir os enums na leitura, rejeitando desconhecidos.
- Datas: UTC com formato fixo YYYY-MM-DDTHH:MM:SS.ffffff+00:00, usando
  isoformat(timespec="microseconds"). Instantes equivalentes em outros fusos
  produzem a mesma representação. Sem horário local implícito e sem datetime.now
  no ato de salvar ou comparar entidades existentes.
- None corresponde a SQL NULL; não usar textos "None" ou "null".
- confidence numérica vira float após validação; 0 e 0.0 representam o mesmo valor.
- is_mock vira int 0/1 somente depois de validar bool; reconstruir bool na leitura.
- Toda leitura reconstrói as entidades e valida identidade/origem. Dados inválidos
  geram erro controlado de integridade; não corrigir valores ou inventar defaults.

## 5. Idempotência e conflitos

| Situação | Resultado |
|---|---|
| ID ainda ausente, entidade válida | Inserir uma vez |
| Mesmo ID e mesmo conteúdo canônico | Sucesso sem mudança ou nova linha |
| Mesmo ID com qualquer campo persistido divergente | ValueError de conflito; preservar registro anterior |
| Mesmo conteúdo com outro ID | Outro registro legítimo; não deduplicar por heurística |
| Evento com session_id/sujeito incompatíveis | Rejeitar antes de gravar |

Comparar todos os campos persistidos da entidade após normalização, não apenas ID
ou hash parcial. source, evidence_ref, processor, is_mock e review_status participam
da comparação. Não usar INSERT OR REPLACE ou UPSERT de atualização nesses repositórios.
A PK é a última defesa contra concorrência: conflito de unicidade deve levar à
releitura/comparação ou falha controlada, nunca à substituição silenciosa. Bloqueio
SQLite não é sucesso; tratar OperationalError e desfazer transação sem retry infinito.

## 6. Conexão, inicialização e transações

1. Criar conexão local; habilitar PRAGMA foreign_keys=ON antes de iniciar transação
   e conferir retorno 1. Não tentar habilitar dentro de transação aberta. A futura
   infraestrutura deve recusar conexão com FK desligada, sem commit implícito.
2. Inicialização explícita antes do processamento: tabelas existentes, versão,
   sessões, eventos, índices e triggers, em uma transação de schema controlada pelo
   inicializador. Não misturar migração com uma transação de trabalho em andamento.
3. Banco baseline sem componente multimodal: criar apenas estruturas novas e
   registrar versão 1, preservando registros existentes. Se houver tabelas multimodais
   sem versão ou estrutura incompatível, falhar e solicitar migração revisada.
4. Reabrir versão 1 compatível não altera dados. Versão desconhecida/mais nova:
   recusar escrita. Migrações futuras serão incrementais, explícitas e testadas;
   não reconstruir/apagar banco automaticamente para fazê-lo caber no schema.
5. save/get/list não fazem commit, rollback ou executescript. O caso de uso controla
   a transação de trabalho e usa a mesma conexão para paciente, sessão, eventos e
   auditoria quando fizerem parte de uma operação atômica.
6. Uma operação lógica salva sessão e seus eventos; qualquer falha desfaz as novas
   linhas da operação inteira, preservando registros previamente confirmados.
   Não usar DELETE CASCADE nem exclusão automática de sessões/eventos.
7. Fixtures preservam IDs em reexecução. Não gerar IDs/datas novos durante retries.
   AuditRecord preserva correlation_id por operação; seus metadados variáveis não
   devem causar alteração de payload em uma mesma tentativa lógica idempotente.

Testes usam banco em memória e arquivo temporário para reabertura. Banco da
aplicação e exportações não entram no Git. Não abrir banco do usuário nesta tarefa.

## 7. Revisão humana: limite deliberado

Schema aceita o vocabulário completo para evolução, mas o caminho inicial de
gravar um evento novo só aceita pending_review; outra situação deve ser rejeitada
até existir operação de revisão autorizada e auditada. O contrato de domínio pode
representar outros estados; isso não autoriza salvar uma aprovação sem trilha.
Save de evento existente não é mecanismo de alteração de review_status.

A futura revisão terá registro separado contendo ID da revisão, event_id,
estado anterior/novo, referência opaca do revisor, timestamp e justificativa,
sem sobrescrever o histórico. Não criar essa tabela nem seu fluxo nas tarefas 2/3.
A consulta inicial apenas preserva o estado; a revisão humana completa permanece
no incremento do motor de alertas. Não reutilizar correlation_id como event_id.

## 8. Contratos previstos e testes de aceite

Nomes previstos: SQLiteSessionRepository.save/get_by_id/list_for_patient/
list_for_dataset_participant e SQLiteEventRepository.save/get_by_id/list_for_session.
São propostas, não imports disponíveis. Save não altera o conteúdo do argumento.

| Etapa | Casos obrigatórios |
|---|---|
| Tarefa 2: schema/sessões | Inicializar/reabrir sem perda; schema incompatível; FK desligada; paciente ausente; dataset independente; ambas/neither identidades; mesmo ID igual/divergente; rollback |
| Tarefa 3: eventos | Sessão ausente; identidade incompatível; origem incompatível no repositório e SQL direto; FK; confidence limites/None; revisão inicial; mock/provider separado; idempotência e ordenação por empate |
| Tarefa 4: caso de uso | Sucesso atômico; falha no segundo evento sem gravação parcial; auditoria na mesma transação; repetição e conflitos; registros anteriores preservados |
| Tarefa 5: CLI | Cadastrar fictício explicitamente; persistir/reabrir/listar/exportar; reexecução sem duplicata; JSON preserva identidade/origem; não sobrescrever arquivos sem decisão explícita |
| Tarefa 6: fechamento | Regressão anterior mais novos casos; banco temporário; scanner; manifesto e limites documentados |

Esta especificação não autoriza alteração de bancos existentes, exclusões, downloads,
novos pacotes ou serviços. Próximo passo depende da aprovação da tarefa 2.

## Referências técnicas consultadas

- [SQLite: foreign keys](https://www.sqlite.org/foreignkeys.html): habilitação por conexão, limitações dentro de transação e ações de integridade referencial.
- [SQLite: CREATE TABLE](https://www.sqlite.org/lang_createtable.html): semântica de IF NOT EXISTS, NOT NULL e CHECK, incluindo resultado NULL.

Essas referências fundamentam cuidados de SQLite; as regras de identidade,
idempotência e revisão acima são decisões propostas para este projeto.

## Estado após a tarefa 2

Implementados initialize_multimodal_schema (infraestrutura/sqlite_multimodal_schema.py)
e SQLiteSessionRepository (infraestrutura/sqlite_session_repository.py). O inicializador
cria a estrutura v1 completa, incluindo tabela/índices/triggers de eventos, mas não
há save/get/list de eventos nesta entrega. Tabelas são criadas apenas quando o
inicializador é chamado explicitamente; nenhum banco do usuário foi aberto.

Inicialização valida definições SQL conhecidas em sqlite_master comparando com
um schema de referência em memória; diferenças estruturais são recusadas em vez
de reparadas. CREATE TABLE, índices e triggers são transacionais. Essa política é
conservadora: SQL escrito de forma diferente pode exigir revisão mesmo se equivalente.

Repositório exige FK ativa e versão 1; leituras validam representação canônica.
Conflitos de conteúdo geram ValueError. Violações FK/CHECK preservam IntegrityError
SQLite; falha de acesso/bloqueio preserva OperationalError para tratamento pelo
futuro caso de uso. O chamador deve desfazer a transação quando a operação falha.
Guia de conferência: [tarefa 2](../docs/DAY_02_TASK_02.md).

## Estado após a tarefa 3

SQLiteEventRepository implementado, com save/get_by_id/list_for_session,
identidade via JOIN, validação contra sessão, revisão inicial pendente,
idempotência e leitura canônica. Checagem FK/versão compartilhada com sessões.
Sem alteração de schema v1. [Guia e testes](../docs/DAY_02_TASK_03.md).
Os estados anteriores deste documento registram a evolução por tarefa; o estado
atual inclui repositórios de sessões e eventos, sem o caso de uso da tarefa 4.

## Estado após a tarefa 4

RegisterMultimodalSession e SQLiteMultimodalUnitOfWork implementados. Operação
atômica de sessão/eventos/auditoria, correlation_id fornecido pelo chamador e
payload determinístico. Sem alteração de schema v1 ou fluxo de revisão.
[Guia e testes](../docs/DAY_02_TASK_04.md). CLI persistida/exportação pendentes.

## Estado após a tarefa 5

CLI com persistência, listagem read-only e exportação JSON exclusiva implementada.
[Guia](../docs/DAY_02_TASK_05.md). A demonstração prepara cadastros fictícios e
reutiliza o caso de uso transacional; validação em bancos descartáveis.
Fechamento integrado do dia 2 permanece para a tarefa 6.

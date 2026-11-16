# Processamento integrado de áudio v1 — estados e evidência

07/11/2026, dia 15/tarefa 1. **Contrato especificado, ainda não implementado.**
Complementa `audio_integration_handoff.md`; não substitui Whisper, contratos
textuais, regras ou schema SQLite já existentes.

## Entrada e identidade

O processador receberá: run_id e session_id UUID estáveis, patient_id fictício
existente, timestamp UTC explícito da sessão, referência local de mídia simulada,
SHA-256 esperado, referência de origem/permissão e configuração dos providers.
Aceitar WAV/MP3/M4A como no adapter atual. Validar caminhos dentro da raiz, sem
links/junctions/traversal/áreas privadas; hash antes e depois do processamento.

Não inferir paciente pelo nome do arquivo/voz. SourceKind=simulated, sujeito
synthetic_patient; TTS não implica mock. Preservar qual provider realmente executou
e is_mock por etapa. Não associar participante de dataset ao paciente fictício.

`run_id` identifica uma execução preparada. Retentativa de persistência reutiliza
os mesmos bytes/IDs/timestamp. Nova inferência, novo contrato ou nova configuração
produz nova execução; não executar o modelo outra vez para reconstruir evidência
supostamente idêntica. Horário de processamento não é horário clínico relatado.

## Estados por etapa

|Etapa|Estados permitidos|Conteúdo obrigatório ou regra|
|---|---|---|
|input|accepted / rejected|Origem, caminho relativo seguro, hash esperado/observado quando disponível e motivo tipado|
|asr|succeeded / no_speech / unavailable / invalid_output / not_run|Texto/segmentos apenas quando succeeded; provider/modelo/tempo; erro distinto de transcrição vazia|
|acoustics|succeeded / unavailable / not_run|Descritores técnicos com versão/unidades; sem inferir emoção, fadiga ou diagnóstico|
|rules|succeeded_with_mentions / succeeded_no_mentions / unsupported_input / unavailable / not_run|Lista contextual ou motivo; não confundir falha com lista vazia|
|llm|disabled / not_configured / succeeded / unavailable / timeout / invalid_response / unsupported_input / not_run|Fonte/modelo/contrato/hash de entrada quando executada, conteúdo validado ou erro; sem fallback automático|

No ASR atual, decodificação, descritores e inferência são entregues juntos por
`WhisperRun`. Não inventar dados parciais quando ele falha. Acoustics pode ficar
unavailable/not_run com motivo; não presumir uma medida recuperável após exceção.
Adaptação para separar etapas será explícita se necessária, sem alterar histórico.

## Estado global e precedência

- **rejected:** identidade, permissão declarada, caminho, formato ou hash de entrada
  inválidos. Não iniciar ASR/regras/LLM. Não persistir como sessão processada com sucesso.
- **failed:** entrada aceita, mas não há ASR válido (inclusive no_speech). Preservar
  diagnóstico técnico; regras e LLM not_run. Não inventar texto a partir da referência.
- **degraded:** ASR válido, porém descritores/regras falharam ou não suportam a
  entrada, ou LLM selecionada está ausente, inválida, indisponível ou excedeu prazo.
  Preservar resultados independentes válidos. Não apagar menções por falha de LLM.
- **completed:** ASR, descritores e regras válidos; LLM explicitamente disabled ou
  succeeded. Significa término técnico, não validação clínica/qualidade garantida.

Uma chamada LLM que retorne unknown com schema/evidência válidos é succeeded com
abstenção, não unavailable. Se LLM não foi pedida, usar disabled; se foi pedida mas
não há adapter, not_configured e degraded. Essas diferenças devem aparecer na UI.

Texto ASR acima de 4000 caracteres: manter transcrição, marcar rules/llm como
unsupported_input segundo seus limites, global degraded. Não truncar silenciosamente.
Mais de oito termos elegíveis: regras podem continuar sobre texto até 4000, mas
LLM v3 fica unsupported_input antes da chamada. A composição futura deve executar
as regras separadamente desse limite da LLM; o helper v3 atual sozinho não faz isso.
ASR válido sem termos: succeeded_no_mentions, lista vazia; não significa ausência
de problema de saúde e não depende de sentimento neutral.

## Menções, candidatos experimentais e informação

Todas as ocorrências configuradas são preservadas com termo, índices [start,end),
trecho, contexto e versão da regra; não colapsar condição e negação do mesmo termo.

|Contexto da regra|Classificação na evidência desta versão|
|---|---|
|affirmed_current|candidate_for_human_review — menção atual explícita de termo configurado|
|negated_current, conditional, third_party, affirmed_historical, affirmed_earlier_in_session|context_information — guardar contexto, sem convertê-lo em alerta atual|
|unknown|context_uncertain — marcar necessidade de esclarecimento, sem presumir afirmação|

Essa classificação organiza itens para futura revisão; não é urgência, severidade
clínica ou recomendação de conduta. Só a regra determinística versionada pode
produzir candidato; termos/sentimento da LLM não criam, removem ou elevam candidato.
Na tarefa 2, testar explicitamente que falha ou opinião da LLM não altera os itens.

Estado review_status=pending_review não torna um evento diagnóstico. Transição
reviewed/dismissed requer operação própria auditada da tarefa 4. Critérios mais
amplos de alerta multimodal, correlação temporal ou severidade não estão definidos
por esta tabela e não devem ser inferidos pela implementação.

## Evidência imutável

Objeto JSON versionado `audio-processing-evidence-v1` deverá conter:

|Seção|Campos mínimos|
|---|---|
|identity|run_id, session_id, patient_id, subject_kind, source_kind|
|time|session_timestamp_utc, processing_timestamp_utc, time_basis|
|input|status, referência relativa, hashes, formato, origem/permissão, origem humana/TTS|
|asr|status, provider/modelo/versão, is_mock, texto original, segmentos, hash do texto, tempo ou erro|
|acoustics|status, processador/versão/unidades, descritores ou erro|
|rules|status, versão, menções e classificação por item ou erro|
|llm|status, source local/cloud/mock, modelo/contrato, hash do texto, resultado validado ou erro e métricas disponíveis|
|summary|estado global, contagens por contexto/classificação, clinical_validation=false|

Campos indisponíveis são null com estado/motivo; não preencher zero, unknown ou
lista vazia para esconder falha. Não armazenar áudio, segredos, raciocínio interno
do modelo ou mensagens de erro com credenciais/caminhos pessoais. Mensagens técnicas
tipadas, com detalhes locais sanitizados. Versões e is_mock distintos por etapa.

LLM disabled/not_run não precisa de modelo/digest fictício. Quando cloud, registrar
explicitamente a transmissão de texto fictício autorizada; loopback é apenas proxy,
não prova de processamento local. Nenhum envio cloud é padrão deste contrato.

Arquivo e SHA-256 final são preparados uma vez. Futuro evento aponta para item da
evidência com hash, UUID estável e confidence=None quando não há medida definida.
`MultimodalEvent` não ganha payload/severity/type por este contrato. Reutilizar
Session, eventos, unidade de trabalho e auditoria, com hash conferido antes da
transação. Persistência e política de evidência órfã pertencem à tarefa 3.
Rejeições de entrada não criam eventos clínicos; diagnóstico técnico pode ser
registrado separadamente. A tabela de eventos não substitui o registro de erro.

## Cenários de aceite para a implementação offline

|Cenário|Resultado esperado|
|---|---|
|Texto sem sintomas configurados|completed, rules=succeeded_no_mentions, zero candidatos|
|Não senti dor.|Menção negada informativa, sem candidato atual|
|Se eu sentir falta de ar... Agora não estou com falta de ar.|Duas ocorrências, condição e negação, sem candidato atual|
|Meu irmão sentiu dor no peito.|Terceiro, sem atribuir ao narrador|
|Ontem senti tontura. Hoje não estou com tontura.|Histórico e negação atual separados|
|Senti tontura.|Candidato experimental para revisão, sem severidade/prescrição|
|Talvez eu tenha sentido dor.|Contexto incerto, não afirmação atual|
|ASR sem fala / indisponível|failed, sem executar regras/LLM|
|LLM disabled|Regras válidas preservadas, completed se demais etapas válidas|
|LLM timeout / JSON inválido / falta de adapter|degraded, mesmas regras/candidatos, sem esconder erro|
|Texto >4000 ou >8 termos|Limites tratados conforme etapa, sem truncamento silencioso|
|Hash muda durante processamento|Resultado rejeitado; não persistir evidência como verificada|
|Provider mock|Proveniência mock explícita em cada etapa simulada|

Esses são resultados esperados de testes futuros, não novas análises de gravações.
O processador da tarefa 2 usará providers injetados e testes offline; não deve
baixar modelo, iniciar cloud ou persistir SQLite ao importar/executar os testes.

## Fora desta entrega

Sem código do processador, schema SQLite novo, revisão implementada, UI, inferência
ou avaliação real v3 nesta tarefa 1. Os 12 áudios já têm transcrição/WER e as dez
referências v3 humanas estão aprovadas; não reabrir essas pendências concluídas.
Análise v3 real e expansão textual TTS continuam tarefas separadas. Nenhum grau
de confiança clínica ou limiar acústico é criado para antecipar a demonstração.

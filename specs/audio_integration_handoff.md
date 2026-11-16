# Entrega técnica para integração de áudio

06/11/2026, fechamento do dia 14. **Especificação de integração futura; fluxo ainda
não implementado.** Reutilizar contratos de sessões/eventos/SQLite existentes.

## Componentes disponíveis

Whisper local com segmentos e descritores acústicos técnicos; referências humanas
e avaliações preservadas; regras `context-terms-v1`; contratos textuais v1/v2 e
núcleo v3 offline. GPT-OSS cloud tem somente diagnóstico de três textos no contrato
anterior, sem adapter v3 ou adoção definitiva. Não apresentar mocks como inferência.

O primeiro fluxo integrado deverá funcionar com transcrição e regras, mesmo se a
LLM estiver desativada, inválida ou indisponível. Essa tolerância não declara a
análise textual da LLM atendida: mostrar seu estado real separadamente no relatório.

## Sequência e evidências

1. Receber áudio simulado autorizado e referência de origem. Resolver caminhos e
   verificar hash, sem transmitir áudio ou voz à nuvem. Selecionar explicitamente
   paciente fictício e sessão; gravação não é registro clínico de seu locutor.
2. Transcrever localmente, guardar texto original/segmentos, versão/modelo/backend,
   hash da mídia e métricas técnicas. Não corrigir ASR silenciosamente. Preparar o
   ambiente OpenMP antes de carregar bibliotecas, conforme experiência do dia 13.
3. Executar regras determinísticas com termo, índices, trecho e contexto. Menção
   negada, histórica, condicional ou de terceiros não vira automaticamente alerta
   atual. Critérios de alerta precisam de contrato/testes próprios e revisão humana.
4. Se LLM for selecionada explicitamente, registrar local/cloud, modelo, contrato,
   hash do texto, resultado e tempo. Para v3, conferir fonte/modelo/conclusão antes
   do validador. Erro gera estado técnico explícito; nunca JSON vazio apresentado
   como sucesso. A LLM não determina severidade nem decide alertas.
5. Preparar JSON de evidência imutável e seu SHA-256, depois eventos e sessão.
   Conferir bytes gravados antes do registro transacional. Banco guarda referências
   e auditoria, não mídia. Arquivo e SQLite não são uma transação única: documentar
   evidência órfã em caso de falha; não sobrescrever evidência já referenciada.

## Mapeamento aos contratos existentes

|Campo|Decisão para o fluxo simulado|
|---|---|
|patient_id|Identidade fictícia explícita, como PAT-001; sem nome do locutor|
|session_id|UUID estável fornecido/preparado para aquela sessão|
|event_id|UUID determinístico para run/evidência/item; mesma retentativa não duplica|
|subject_kind|synthetic_patient; não vincular participantes REHAB26/BIDMC ao locutor|
|source_kind|simulated; origem dos dados não muda porque o processador é real|
|source|Identificador versionado da origem simulada|
|processor / is_mock|Processador/versão verdadeiros; mocks identificados, sem confundir com TTS|
|timestamp|UTC explícito da sessão/processamento, com base temporal documentada|
|confidence|None quando não houver medida definida; não inventar probabilidade clínica|
|evidence_ref|Referência local, hash e item de evidência; não caminhos privados absolutos|
|review_status|pending_review inicialmente; transição futura própria e auditada|

`MultimodalEvent` não possui colunas payload, type ou severity. Esses detalhes
permanecem no JSON de evidência, usando o schema de domínio existente. Reutilizar
`RegisterMultimodalSession` e unidade de trabalho, como vitais/prescrições; não criar
um banco paralelo ou alterar eventos imutáveis via save para registrar revisão.

TTS é mídia simulada com autorização informada, não um provider mock. Transcrição
de áudio sintético com Whisper real continua inferência real sobre dado simulado.
Falha de transcrição e falha de análise textual são estados diferentes. Sem ASR
válido, não executar regras sobre texto inventado. Sem LLM válida, regras continuam.

## Verificações exigidas no incremento de integração

- Caminho positivo e retentativa idempotente: evidência, sessão, eventos e auditoria.
- Falha ASR, falha/invalidade LLM e input sem termos, sem desaparecimento de estados.
- Negação/hipótese/histórico/terceiros distintos de afirmação atual.
- Hash divergente, conflito de identidade, falha SQLite e rollback verificável.
- Consulta/exportação reconstruindo evidência e origem; revisão auditada em passo
  próprio, sem declarar interface pronta antes de implementá-la.

Critérios acima são tarefas futuras e testes a escrever, não resultados deste
fechamento. Nenhuma persistência nova, alerta clínico ou UI foi criada no dia 14.

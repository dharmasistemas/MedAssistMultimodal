# Entrega do áudio à interface — 07/11/2026

Implementados: ProcessAudio, preparação de registro, AudioEvidenceStore,
register_audio_sqlite, query_audio_session, EventReviewRequest,
review_event_sqlite e event_review_history. Usar os serviços existentes, sem SQL
direto da UI, alteração de arquivos de evidência ou inferência no thread Tkinter.

## Comportamento necessário na próxima etapa

- Separar estado do processamento (completed/degraded/failed/rejected) do estado
  de revisão (pending_review/reviewed/dismissed). Mostrar falha da LLM sem apagar
  transcrição, regra ou histórico. Falha não é texto vazio nem ausência de sintomas.
- Exibir se a origem é voz humana/TTS, se o processamento é real/mock e se a LLM
  é local/cloud/desativada. No caso misto, mostrar a proveniência por etapa.
- Exibir termo, trecho, contexto e classificação; candidato experimental não é
  severidade clínica. Itens negados/condicionais/históricos/terceiros continuam
  visíveis como informação contextual, sem promoção pela LLM.
- Consultar a evidência verificada antes de mostrar o item ao revisor. Coletar
  reviewer_ref, motivo, horário e decisão explícitos. Não marcar todos como revisados
  ao abrir a tela ou repetir a gravação original para atualizar o review_status.
- Operação de revisão muda estado e auditoria, sem mudar evidência ou classificar
  uma revisão técnica como validação clínica. Mostrar histórico próprio do evento.
- Reutilizar a evidência preparada na retentativa de persistência; nova inferência
  usa novo run_id. Não sobrescrever arquivo nem recriar automaticamente evidência
  desaparecida de execução já confirmada.
- Processamento lento deve ocorrer fora do thread principal. Inicializar ambiente
  OpenMP antes das bibliotecas nativas; não habilitar runtimes duplicados. Falha/
  encerramento do worker não significa cancelamento confirmado no provider remoto.

## Pendências explícitas

Não há UI, autenticação de revisor ou adapter/runner HTTP v3 nesta entrega. As dez
referências v3 estão aprovadas, mas sua avaliação real ainda não foi feita. A LLM
cloud é candidata comparativa, não padrão adotado. Sete TTS já têm transcrição/WER,
mas a expansão da análise textual precisa de protocolo próprio. Nenhum dado pessoal
ou áudio é enviado à nuvem pelo fluxo entregue.

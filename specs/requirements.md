# Requisitos — MedAssistMultimodal / TC4

## Decisão vigente — 31/10/2026

Conforme autorização da coordenação relatada pelo usuário, Whisper local substituirá
Azure Speech; Qwen `qwen2.5:7b-instruct` local substituirá a análise textual Azure.
Os registros anteriores de PENDENTE_FIAP preservam o histórico e não são o gate atual.
Contratos SpeechTranscriber/TextAnalyzer e mocks permanecem; os adapters reais ainda
não foram implementados. Qwen extrairá informações/resumos, sem decidir alertas;
regras determinísticas continuam funcionando sem LLM. Whisper será executado em
sequência com Qwen, evitando concorrência pela GPU GTX 1050 Ti de 4 GB. Variante,
backend, dependências e desempenho do Whisper serão definidos/testados na trilha de
áudio. Nenhum download ou instalação está autorizado implicitamente por este registro.
Gemma e gpt-oss não integram a arquitetura aprovada. Azure permanece contingência.


Fonte e critérios completos: `PROJECT_SCOPE.md`. Cronograma: `../docs/IMPLEMENTATION_PLAN.md`.

1. Analisar Ex1 (abdução do ombro direito) por arquivo/landmarks, com repetições,
   ângulos, visibilidade, frame/timecode e evidência. Regras experimentais, sem diagnóstico.
2. Áudio PT-BR simulado: preservar portas SpeechTranscriber/TextAnalyzer e mocks
   offline; implementar Whisper local e análise textual Qwen 2.5 local, conforme
   substituição autorizada. Mocks não substituem a avaliação dos adapters reais.
3. Vitais com origem/unidade; regras configuráveis e avaliação independente BIDMC.
4. Comparar versões de prescrições sintéticas sem recomendar tratamento.
5. Eventos com patient_id, session_id, event_id, source, timestamp, confidence,
   evidence_ref e review_status; histórico SQLite e exportação JSON/CSV.
6. Alertas determinísticos com revisão humana; LLM opcional apenas explica fatos.
7. Tkinter/ttk com workers, abas Vídeo, Áudio, Anomalias e Alertas.
8. Testes offline positivos, negativos, de borda e indisponibilidade de provider;
   idempotência quando aplicável. Proveniência, licença e separação real/sintético.
9. Entregar código, relatório e demonstração de até 15 minutos em 17/11/2026.

Esses são requisitos de aceite, não funcionalidades já entregues. O estado real
está em `traceability.md` e no README principal.

# Arquitetura — MedAssistMultimodal / TC4

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


Fonte do escopo: `PROJECT_SCOPE.md`. Baseline local em Python 3.12.

| Camada | Responsabilidade | Estado |
|---|---|---|
| Domínio | Pacientes sintéticos, identidade, sessões/eventos multimodais | Contratos puros disponíveis; integração/persistência de eventos pendentes |
| Aplicação | Segurança, privacidade, auditoria, regras/casos de uso | Utilitários disponíveis; regras multimodais pendentes |
| Infraestrutura | SQLite, configuração local e gráficos SVG | Baseline offline testado |
| Providers | Ollama opcional, sem decidir alertas | Adapter com testes mock; não requerido no baseline |
| Vídeo/áudio | MediaPipe/OpenCV; features acústicas; portas Speech/Language | Portas/mocks de áudio disponíveis; demais pipelines pendentes |
| UI | Tkinter/ttk, processamento em worker e revisão humana | Pendente |

Fluxo alvo: entrada com origem → validação → extração por modalidade → regras
experimentais determinísticas → evento auditável → revisão humana → exportação.
A falha de provider opcional não pode bloquear ou alterar decisões de alertas.
SQLite usa SQL parametrizado; transações pertencem ao chamador. O registro atual
de auditoria ainda não é o futuro schema de eventos multimodais.

Regras de identidade/origem aprovadas e contratos implementados na tarefa 3:
[identity_and_provenance.md](identity_and_provenance.md). Domain/session.py e
domain/events.py validam entidades sem I/O. O futuro caso de uso deve chamar
validate_for_session antes de aceitar um evento. Persistência e revisão auditada
ainda não estão implementadas para essas entidades.

Persistência multimodal proposta (dia 2, tarefa 1):
[sqlite_sessions_events.md](sqlite_sessions_events.md). Especificação para revisão;
as novas tabelas/repositórios ainda não foram implementados.

Dia 2 / tarefa 2: inicializador SQLite multimodal v1 e repositório de sessões
implementados. A tabela de eventos faz parte da estrutura; repositório de eventos
permanece pendente. Estado e verificação (guia histórico removido na [limpeza autorizada](../docs/REPOSITORY_CLEANUP_EXECUTED_2026-11-17.md)).

Dia 2 / tarefa 3: repositório de eventos implementado; identidade recuperada da
sessão via JOIN. Caso de uso transacional conjunto e CLI persistida continuam
pendentes. Conferência (guia histórico removido na [limpeza autorizada](../docs/REPOSITORY_CLEANUP_EXECUTED_2026-11-17.md)).

Dia 2 / tarefa 4: RegisterMultimodalSession usa portas de aplicação;
SQLiteMultimodalUnitOfWork implementa a transação compartilhada de sessão,
eventos e auditoria. Verificação (guia histórico removido na [limpeza autorizada](../docs/REPOSITORY_CLEANUP_EXECUTED_2026-11-17.md)).
CLI com persistência/exportação permanece pendente.

Dia 2 / tarefa 5: demo/persistence.py conecta CLI, cadastro explícito de fixtures,
caso de uso e repositórios; list/export abrem conexão read-only. CLI original sem
argumentos preservada. Guia (guia histórico removido na [limpeza autorizada](../docs/REPOSITORY_CLEANUP_EXECUTED_2026-11-17.md)).

Dia 4 / tarefas 1–3: domain/geometry.py oferece primitivas puras, com fixtures
sintéticas e testes. [Convenções](rehabilitation_geometry.md). Medidas por landmarks,
qualidade/visibilidade e classificação de movimento ainda não implementadas.

Dia 4 / tarefas 4–6: domain/rehabilitation.py implementa medidas e qualidade por
resultado; demo/rehabilitation.py demonstra poses sintéticas. Sem decisão de alerta
ou integração temporal. Fechamento (guia histórico removido na [limpeza autorizada](../docs/REPOSITORY_CLEANUP_EXECUTED_2026-11-17.md)).

Dia 5 / tarefa 4: infrastructure/rehab26_landmarks.py lê NPY com NumPy opcional,
valida v1 e converte frames por perfil explícito; unidade 2D desconhecida bloqueia
geometria. Cópias de domínio, sem exposição do array mapeado. Guia (referência do acervo local, não distribuída).

Dia 5 / tarefa 5: domain/temporal_alignment.py calcula cobertura inclusiva sem I/O;
infrastructure/rehab26_alignment.py adapta disponibilidade bruta por frame.
Conferência real (referência do acervo local, não distribuída).
Cobertura estrutural não implica prontidão geométrica, qualidade clínica ou sincronização RGB.

## Dia 7 — 31/10/2026
infrastructure/video_pose.py: VideoReader sequencial CFR, MediaPipePose Tasks CPU,
world_pose→PoseFrame e IntervalPoseSequence preservando índices globais. Imports
OpenCV/MediaPipe somente ao usar adapter; baseline sem -site continua stdlib.
scripts/process_ex1_rgb.py integra primeira repetição development com regras v1.
Relatório real disponível, sem persistência de alertas ou segmentação automática.

# Rastreabilidade — MedAssistMultimodal / TC4

| Requisito | Evidência atual | Estado |
|---|---|---|
| Pacientes sintéticos | patient_context.py, sqlite_patient_repository.py; testes de SQLite/privacidade | Baseline testado |
| Sessões/eventos e auditoria | Domínio, repositórios, unidade de trabalho SQLite e CLI do dia 2 | Implementados/testados; integração de modalidades e revisão auditada pendentes |
| Privacidade/segurança | privacy.py, redaction.py, safety.py e check_secrets.py | Utilitários testados; não certificam anonimização de texto livre |
| LLM opcional | llm.py, resilience.py, providers/ollama.py e factory.py | Contratos e mocks testados; resumo integrado pendente |
| Gráficos | infrastructure/charts.py; test_charts.py com fixtures neutras | Utilitário testado; sem resultados clínicos |
| Vídeo Ex1 | Pipeline RGB/NPY, medidas e avaliação do dia 8 | Implementado parcialmente; qualidade das regras insuficiente, revisão visual/segmentação automática pendentes |
| Áudio | application/audio.py, providers/mock_audio.py; testes offline de contratos | Portas/mocks disponíveis; Whisper/Qwen reais e features pendentes |
| Vitais/prescrições/alertas | specs/PROJECT_SCOPE.md | Implementação multimodal pendente |
| UI Tkinter e relatório final | docs/IMPLEMENTATION_PLAN.md | Pendentes |

Não considerar documentos de auditoria de migração como especificação funcional.
Avaliação experimental por desvio executada no dia 8; não há validação clínica nem
classificador global correto/incorreto validado. Testes de software são evidência distinta.

Azure F0 é contingência desativada; configuração histórica preservada em
infrastructure/azure_f0_config.py e docs/AZURE_F0_SETUP.md. Substituição por Whisper
e Qwen autorizada; não há dependência de assinatura no caminho principal.

Calendário vigente: [plano revisado em 31/10](../docs/IMPLEMENTATION_PLAN.md).
Dias executados e aceites de qualidade devem ser conferidos separadamente.

## Dia 8 — avaliação experimental
Métricas por desvio com abstenção implementadas em domain/evaluation.py. Relatórios
NPY development/evaluation separados e RGB development ampliado conforme guia
[Dia 8](../docs/DAY_08_TASKS.md). Não há avaliação clínica aprovada: regras v1 com
baixa precisão/recall e cobertura limitada. Sem classificação global do Ex1.

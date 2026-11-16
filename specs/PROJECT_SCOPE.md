# MedAssistMultimodal — Escopo aprovado e critérios de aceite

## Decisão de base — 31/10/2026 (atualizada abaixo em06/11)

Conforme autorização da coordenação relatada pelo usuário, Whisper local substituirá
Azure Speech; Qwen `qwen2.5:7b-instruct` local substituirá a análise textual Azure.
Os registros anteriores de PENDENTE_FIAP preservam o histórico e não são o gate atual.
Contratos SpeechTranscriber/TextAnalyzer e mocks permanecem; os adapters reais ainda
não foram implementados. Qwen extrairá informações/resumos, sem decidir alertas;
regras determinísticas continuam funcionando sem LLM. Whisper será executado em
sequência com Qwen, evitando concorrência pela GPU GTX 1050 Ti de 4 GB. Variante,
backend, dependências e desempenho do Whisper serão definidos/testados na trilha de
áudio. Nenhum download ou instalação está autorizado implicitamente por este registro.
Na decisão de31/10, Gemma e gpt-oss não integravam a arquitetura; a autorização de teste GPT-OSS foi ampliada em06/11, abaixo. Azure permanece contingência.


## Objetivo
POC acadêmica local para fisioterapia/reabilitação, demonstrando análise de vídeo, áudio e dados estruturados, detecção de desvios e alertas auditáveis com revisão humana. Entrega 17/11/2026. Projeto de análise multimodal de reabilitação.

## Requisitos FIAP (fonte: PDF Tech Challenge Fase 4 fornecido pelo usuário)
- Vídeos clínicos, detecção de movimentos/eventos fora do padrão e relatório automático.
- Áudios de consultas, indicadores vocais experimentais, **Azure Speech to Text** e **Azure Text Analytics / AI Language** para transcrição, termos críticos e sentimento.
- Anomalias em sinais vitais (frequência cardíaca, pressão, SpO2), evolução de prescrições e movimento de pacientes; alertas automáticos.
- Código Git + relatório técnico com fluxo/modelos/resultados + vídeo demonstrativo de até 15 minutos com Azure e alertas.

## Decisões de arquitetura
Python 3.12; UI Tkinter/ttk; MediaPipe Pose + OpenCV; librosa/numpy; regras + opcional scikit-learn; SQLite; pytest; Ollama `qwen2.5:7b-instruct` para texto explicativo opcional.

## Cenário demonstrativo
`PAT-001` é fictício; exercício inicial **abdução do ombro direito (Ex1)**, vídeo de dataset acadêmico. Áudio é consulta simulada PT-BR; sinais vitais reais BIDMC usados **apenas para avaliação independente**; série sintética associada ao PAT-001 para demonstração integrada; prescrições sintéticas. Nunca alegar que dados de datasets diferentes pertencem à mesma pessoa.

## Casos de uso e aceitação
1. **Vídeo**: abrir arquivo ou sequência de landmarks; identificar repetições, calcular ângulos e gerar evento com frame/timecode, erro e evidência; comparar rótulos de repetição com referência do dataset. Lidar com oclusão e baixa visibilidade.
2. **Áudio**: WAV PT-BR simulado; Whisper local e TextAnalyzer Qwen 2.5 local conforme substituição autorizada; mocks para testes/falhas, sem contar como integração real; termos críticos determinísticos com contexto/negação; recursos acústicos não diagnósticos; medir WER e acerto das tarefas textuais com referências conhecidas.
3. **Sinais vitais**: importar dados com unidade e origem; anomalias por regras configuráveis e opcional IsolationForest; pressão arterial apenas quando disponível em dados adequados ou sintéticos; não inventar campo ausente no BIDMC.
4. **Prescrição**: detectar inclusão, remoção e alteração entre versões sintéticas; não recomendar tratamento.
5. **Movimento de paciente**: eventos derivados de sequência postural de reabilitação; deixar explícito que **monitoramento de internados** é cenário sintético/experimental separado, não comprovado pelo REHAB26.
6. **Alertas**: regras determinísticas, severidade experimental, estado de revisão humana, timestamp, evidência, histórico SQLite e exportação JSON/CSV.
7. **LLM**: sumarização somente com fatos estruturados; falha da LLM não bloqueia alertas; saída não diagnóstica.
8. **UI**: abas Vídeo, Áudio, Anomalias, Alertas; processamento em worker sem bloquear thread Tkinter.

## Azure — histórico da decisão condicional (superado pela autorização de substituição)

Os itens abaixo registram a situação anterior à decisão vigente no início deste
arquivo. Não são gates do calendário atual. Azure permanece contingência desativada;
retomá-lo exige decisão explícita, sem assinatura, cobrança ou implantação automática.
- `PENDENTE_FIAP` em 14/10/2026. Aguardar resposta da FIAP sem paralisar módulos offline.
- Atualização 23/10/2026: coordenação confirmou indisponibilidade de Azure for Students. Responsável possui conta Microsoft, sem assinatura Azure; contingência requer conta gratuita convencional elegível e recursos Speech/Language F0 verificados.
- Continuidade além do período inicial pode exigir upgrade para Pay-As-You-Go; não autorizar upgrade/cobrança automaticamente. Orçamentos alertam, mas não bloqueiam gastos. Roteiro: docs/AZURE_F0_SETUP.md.
- Se F0 indisponível, registrar custo estimado e pedir decisão; **não contratar S0 automaticamente**.
- Sem Azure até marco de contingência: manter mocks, documentação e testes offline, mas **não declarar requisito de integração real atendido**.

## Não objetivos
Diagnóstico, triagem clínica autônoma, prescrição, validação regulatória, integração hospitalar, inferência de fadiga/doença a partir de voz, transmissão de dados pessoais, nuvem para hospedar app.

## Métricas
Vídeo: precisão/recall/F1 por repetição, matriz de confusão, falhas por ângulo de câmera e cobertura. Áudio: WER e acerto de termos rotulados. Vitais: precision/recall sobre anomalias sintéticas injetadas, latência de alerta; demonstrar diferenças entre dados reais sem rótulo e sintéticos rotulados. Registrar versão, semente, divisão e proveniência.

## Atualização da coordenação e teste cloud — 06/11/2026
Usuário esclareceu que a coordenação autorizou qualquer LLM nesta parte do projeto;
Llama/Qwen eram exemplos, não restrição. Autorizou testes gpt-oss:120b-cloud ou
alternativa adequada no plano OllamaPro. Incremento atual limitado à comparação de
A03/A05/A08manual: textos fictícios sem áudio/voz/vídeo/dados pessoais; modelo já
disponível, sem compra de créditos/alteração de plano/fallback automático.
Preservar Whisper/regras locais e protocolos/avaliações anteriores. Uso cloud fica
explícito, sem rotular fonte como Qwen local. LLM nunca decide alertas. Adoção
definitiva e expansão dependem da avaliação e próxima decisão; não automática.

## Adoção textual — 10/11/2026

Decisão explícita do usuário: seguir com gpt-oss:120b-cloud para análise textual
opcional na UI, promptv2/contratov3 já avaliados. Apenas transcrições fictícias do
corpus conhecido; opção desativada por padrão e confirmação antes de cada execução.
GPT-OSS é a opção implementada de nuvem; Qwen local permanece preservado como
alternativa, sem fallback automático. Whisper local/regras e revisão independente
da LLM continuam. Sem compra de créditos, ativação de cobrança ou troca de plano.
Guia OPTIONAL_GPT_OSS_UI_2026-11-10 e specs/optional_text_ui_v1. Esta atualização
substitui a condição anterior de decisão de adoção pendente, não o histórico.


## 2026-11-12 — Autorização ElevenLabs e tarefas restantes

Em12/11/2026, usuário relatou autorização recebida na aula de11/11 para usar vozes sintéticasElevenLabs no projeto, incluindo amostraA02_exhales já local. PlanejarA2experimentalcomáudios sintéticos, controles e evidências observáveis. Uso do recurso autorizado não implica detector já implementado ou comprovação de condição médica; não afirmar aceite integralA2apenas por gerar áudio. Seguir aprovações por tarefa e preservar termos/origem do provedor.

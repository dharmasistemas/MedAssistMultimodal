# Dia14 — tarefa4 complementada: CPU/v2 — 06/11/2026

## Protocolo e execução

Runner novo scripts/evaluate_day14_text_cpu_v2.py, sem alterar runner/resultados v1.
Dez entradas: A03/A04/A05 development, A08/A12 evaluation, manual e Whisper separados.
Cinco gravações do mesmo locutor; A08/A12 têm mesmo roteiro, não dez casos independentes.
Referências/hashes de áudio/manual/ASR e código congelado verificados antes da execução.
CPU num_gpu0, contexto4096, socket180s, temperatura0/768tokens; prompt v2 e modelo/digest
anteriores. Config/hashes de runner e entradas gravados antes da primeira chamada.
Sem retry/repair/fallback/cloud/download ou alterações durante o lote.

## Resultado

10/10 respostas concluídas, sem timeout/erro CUDA/indisponibilidade neste lote.
4/10 análises válidas;6/10 rejeitadas por evidência. Tempo total282,955s (~4min43s).
Primeira chamada128,727s, dos quais98,732s de carga; demais12,334–24,508s.
As condições/carga diferem do diagnóstico anterior: não alegar latência estável.
Opções reais conferidas em todos os registros; métricas reconstruídas dos10resultados
sem nova inferência e coincidentes com o runner.

| Caso | Manual | Whisper | Motivo/conteúdo |
|---|---|---|---|
|A03|válida128,73s|válida20,97s|positive, referência provisória neutral|
|A04|válida24,51s|válida24,27s|neutral, referência provisória mixed|
|A05|inválida13,20s|inválida12,33s|falta de ar aparece duas vezes; citação ambígua|
|A08|inválida15,21s|inválida13,61s|expressão com sentir não é cópia literal de senti; ASR também altera separação|
|A12|inválida15,34s|inválida14,78s|expressão com sentir não é cópia literal de senti|

| Grupo | Válidas/tentativas | Sentimento correto entre válidas | Expressões exatas TP/FP/FN | Contexto TP/FP/FN |
|---|---|---|---|---|
|development manual|2/3|0/2|0/6/4|6/0/0|
|development Whisper|2/3|0/2|0/5/4|6/0/0|
|evaluation manual|0/2|não mensurável|0/0/4|4/0/0|
|evaluation Whisper|0/2|não mensurável|0/0/4|4/0/0|

Sentimento operacional correto0/10tentativas, distinto de0/4análises válidas e de
qualidade não mensurável entre0válidas de evaluation. Não contar rótulo bruto de
resposta rejeitada como análise válida; não confundir falha com abstenção unknown.
Não houve abstenção válida. Rótulos de sentimento são provisórios/ambíguos, não
consenso clínico. Não foram relabelados após ver saídas.

Expressões: comparação exata do protocolo; frases maiores contendo dor/tontura
não equivalem às expressões de referência. F1operacional0 nos quatro grupos; precisão
não definida em evaluation, onde não há predições aceitas. O resultado não significa
que o modelo desconheça os sintomas, mas falhou na tarefa/contrato medidos.
Contextos determinísticos coincidem10/10entradas,20menções contando as duas variantes;
mesmo corpus conhecido, sem generalização/validação clínica ou decisão de alertas.

## Decisão técnica desta entrega

CPU resolve o caminho de execução neste lote, mas Qwen v2 ainda tem qualidade
insuficiente para entregar sentimento/expressões como confiáveis. Preservar validação
estrita; falha da LLM deve manter regras e evidência de indisponibilidade/invalidade.
Não reduzir critérios ou alterar prompt/referências na mesma avaliação. Novos ajustes
exigem outra versão e avaliação; não bloqueiam registrar estes resultados negativos.
O teste CPU de uma única entrada não previa a taxa de rejeição aqui observada.

## Permissão TTS e limites de escopo

Resposta do suporte Dark Planner de06/11 informada pelo usuário registrada em
permissions/dark_planner_support_2026-11-06.json e no rastreador, como permissão de
uso comunicada em resposta à consulta acadêmica. Não mantemos o estado sem resposta.
Não equiparar a frase livres de direitos autorais a domínio público verificado ou
inventar termos específicos não fornecidos. Sete TTS não processados neste lote;
planejar expansão separada, sem alterar corpus depois de medir resultados.
Os12áudios não estão integralmente avaliados; humano5/12 foi o escopo deste protocolo.

## Como conferir e próximo passo

Guia não exige validar cálculo ou diagnosticar sintomas. Confira na pasta local
`data/interim/audio/day14_text_evaluation_cpu_v2/` os10arquivos e summary.json:
A03/A04 têm analysis preenchido; A05/A08/A12 têm analysis=null e erro explícito,
mas mentions permanece preenchido. As respostas brutas estão preservadas.
Recibo público com hashes e resumo, código/testes anteriores intactos.
Regressão613testes/341subcasos; nenhuma chamada nova durante a conferência.

Tarefa4 executada/complementada, sem aceite semântico do Qwen. Próximo incremento
**tarefa5: fechamento, limites, decisão de integração e impacto no calendário**,
sob aprovação conforme AGENTS.md. Eventos/SQLite/revisão/UI não implementados nesta
entrega. Entrega17/11 e janelas de integração/avaliação mantidas sob risco.

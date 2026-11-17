# Fechamento do dia 10 — 02/11/2026

Cinco tarefas entregues por autorização. Usuário verificou os guias e esclareceu
as métricas. Nenhuma declaração de revisão de guia equivale a validação clínica.
Tarefa 5 fecha decisão/contrato; não altera código ou reexecuta o experimento.

## Entregas

| Tarefa | Resultado | Evidência |
|---|---|---|
| 1 | Protocolo, parâmetros, fonte e critérios anteriores à execução | docs/DAY_10_TASK_01.md; specs/day10_video_experiment_v1.md; day10_protocol_v1.json |
| 2 | Qualidade angular imutável, sem cascata ou ponte entre gaps | domain/temporal_quality.py; 33 casos sintéticos |
| 3 | Segmentação de baixa/alta/retorno, fronteiras, gaps e EOF | domain/temporal_segmentation.py; 28 casos sintéticos |
| 4 | Avaliador temporal e uma execução NPY development completa | domain/temporal_evaluation.py; 11 casos; DAY_10_TASK_04_2026-11-02.json/.md |
| 5 | Decisão de continuidade, contrato de integração e fechamento | docs/DAY_10_TASK_05.md; specs/video_integration_contract.md |

## Resultado real preservado

15016 frames, uma fonte NPY world 3D development, cam1. 110 referências elegíveis,
nenhuma removida por qualidade. 34 ciclos pareados (TP), zero FP e 76 FN: precisão
100%, recall 30,91%, F1 47,22%. O pareamento usa IoU inclusiva ≥0,5 um-para-um.
Não é avaliação de desvios/correção clínica nem novo teste independente.

Cobertura braço–tronco 48,84% antes/48,08% após máscara adicional; 114 frames
rejeitados extras. 19/34 pares com ambos limites em ±15 frames; erros dos demais
limites não foram escondidos. Gravação inteira insuficientemente coberta.
Nenhum ajuste posterior, expansão de fonte ou ablação foi executado. Não concluir
que o filtro causou a precisão observada ou que outro vídeo terá o mesmo resultado.

## Decisão e impacto

Encerrar a investigação de vídeo desta janela. Preservar componentes e resultados
como baseline experimental para fluxo técnico; não promover proxies de desvio a
alertas clínicos automáticos. A futura apresentação precisa dizer “ciclos detectados”,
qualidade, fonte e limites, sem prometer contagem completa de sessão.

Detectar desvios com qualidade suficiente permanece requisito pendente. Avisos de
qualidade/segmentação não o substituem; eventual redução exige decisão explícita
e alinhamento com coordenação quando afetar os critérios do curso. Não declarar
release pronto por terminar as tarefas do dia.

Contrato proposto compatível com Session/MultimodalEvent/registro transacional:
evidência versionada, identidade correta, IDs/instantes estáveis, confidence=None,
revisão inicial pendente e separação entre tempo de vídeo e horário de processamento.
Adaptador real de vídeo para SQLite/UI e revisão auditada **não implementados**.

## Validação

Última regressão executada na tarefa 4: **316 testes e 341 subcasos passaram** em
3,31 s. A tarefa 5 é documental; não repetir testes sem alteração funcional.
Manifestos de planejamento, execução e v1 anterior permanecem como registros
imutáveis, assim como seleção e revisão humana. Verificações finais de hashes,
artefatos, documentação e baseline constam no complemento abaixo.

## Pendências e próximo incremento

- Detecção confiável dos desvios e cobertura de orientações/novas fontes.
- Alinhamento integral, causa da diferença de 133 frames, unidade 2D e calibração.
- Processadores vitais/prescrições, áudio real, motor/revisão, interface e integração.
- Preparo/coleta consentida do corpus de áudio ainda não comprovados nesta etapa.

Próximo incremento previsto: **dia 11, 03/11, vitais sintéticos e primeiro processador
funcional integrado**, preservando fontes/identidades. Sem início automático.
Risco de entrega em 17/11 continua alto; não consumir a janela de integração com
novas tentativas de ajuste de vídeo sem revisão explícita do planejamento.

Decisão (referência do acervo local, não distribuída) ·
[Contrato proposto](../specs/video_integration_contract.md) ·
Próximo dia (referência do acervo local, não distribuída).

## Complemento das verificações finais
Hashes de protocolo, execução, v1 anterior, artefatos e CSV humano conferidos e
preservados. Links e UTF-8 verificados. Baseline passou; manifesto 17/17 em
preparation, com três bloqueios reais mantidos. Scanner aprovado (215 arquivos,
zero valores locais comparados); diff --check sem erro de conteúdo. Suíte completa
não repetida nesta entrega documental. SHA-256 do relatório original da execução:
989fdfdaf74bb1906828b0e4176530d288b24623bc30a5295fafeede10fc91c3.

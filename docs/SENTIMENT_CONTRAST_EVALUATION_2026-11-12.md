# A5 — resultado das seis chamadas GPT-OSS — 12/11/2026

## Resultado real

Usuário autorizou explicitamente: “Pode executar as chamadas ao GPT-OSS”. Executadas exatamente seis chamadas, uma por texto aprovado, com plano congelado, gpt-oss:120b-cloud, promptv2/contratov3, temperatura0, thinklow,1536tokens máximos e timeoutsocket180s. Todas retornaram conteúdo válido e término stop; sem retry, reparo, fallback, modelo alternativo ou ajuste do prompt. Fonte real ollama_cloud; provider_injected=false.

| Entrada | Referência aprovada | Retorno | Chamada(s) | Ocorrências encontradas/esperadas |
|---|---|---|---|---|
| S01 | positive | positive | 0.823 | 1/1 |
| S02 | positive | positive | 0.736 | 1/1 |
| S03 | negative | negative | 0.778 | 1/1 |
| S04 | negative | negative | 0.676 | 1/1 |
| S05 | mixed | mixed | 1.127 | 1/1 |
| S06 | neutral | neutral | 0.868 | 2/2 |

Sentimento:6/6coincidentes entre válidas e entre tentativas. Por classe: positive2/2,negative2/2,mixed1/1,neutral1/1. Unknown não foi testado como referência; nenhuma abstenção/falha/entrada não tentada. Matriz de confusão diagonal no JSON.

Termos por ocorrência:7TP,0FP,0FN,precisão/recall/F1=100% neste conjunto. Termos únicos por entrada:6TP,0FP,0FN. “Dor no peito” não foi contada também como “dor”; as duas menções de tontura emS06foram preservadas. Extração de termo não determina contexto clínico ou alerta.

Tempo somado das seis chamadas:5,009s; não é tempo total do processo nem garantia de desempenho. APIreportou5176tokens de entrada, dos quais4064emcache (incluídos nos5176),1076de saída. Saldo/custo efetivamente debitado não foi consultado ou estimado; não houve compra de créditos/alteração de plano. Aliasretornado gpt-oss:120b é aceito pelo providercongelado.

## Citações para sua conferência

A validação formal confirmou citações literais únicas na entrada; isso não substitui revisão de sentido. Na leitura técnica, todos os trechos contêm apoio ao sentimento retornado. A proposta abaixo é conferência do agente, não aprovação humana atribuída a você. Os JSONs continuam com semantic_evidence_review=pending_human_review. Confirme se os trechos sustentam os rótulos; não é necessário repetir a aprovação dos textos de entrada.

### S01 — positive

> Mesmo com dor no ombro, fiquei contente com a atenção recebida e confiante na continuidade das sessões.

**Conferência proposta:** Avaliação positiva explícita da atenção e da continuidade; a menção de dor não determina sentimento negativo.

### S02 — positive

> O atendimento de hoje foi acolhedor e a explicação do exercício me deixou satisfeita.

**Conferência proposta:** Acolhimento e satisfação são avaliações positivas explícitas; ausência de tontura é informação factual separada.

### S03 — negative

> Fiquei decepcionado com a consulta porque minhas dúvidas não foram esclarecidas. Hoje não senti dor.

**Conferência proposta:** Decepção explícita com a consulta; ausência de dor não torna o sentimento positivo.

### S04 — negative

> A demora para iniciar a sessão me irritou, e saí insatisfeito com a organização do atendimento. Durante a espera, senti falta de ar.

**Conferência proposta:** Irritação e insatisfação explícitas com a organização; relato de falta de ar não é o fundamento do rótulo.

### S05 — mixed

> Gostei da forma como o profissional explicou o exercício, mas fiquei aborrecida com a falta de privacidade na sala. Relatei dor no peito no início da consulta.

**Conferência proposta:** Avaliações positiva (explicação) e negativa (privacidade) explícitas no mesmo narrador; não decorre de mudança de sintomas.

### S06 — neutral

> A consulta começou às nove horas. Fiz duas séries do exercício e informei que ontem tive tontura, mas hoje não tive tontura.

**Conferência proposta:** Relato factual sem avaliação positiva ou negativa explícita; ontem/hoje e negação não tornam o texto misto.

## Verificação e arquivos

Saída imutável/exclusiva: `data/interim/audio/sentiment_contrast_gpt_oss_v1/`, com run_config.json,S01–S06.json e summary.json. Configuração contém plano e versãoOllama anteriores às chamadas. Respostas finais preservadas; nenhum raciocínio interno armazenado. Não apagar, alterar ou reexecutar a saída para tentar resultado melhor.

Revalidadas as seis respostas finais com o validador existente e reconstruídas as métricas de cada entrada e o resumo; correspondem integralmente aos arquivos salvos. Plano, referências, recibo de aprovação, entradas, prompt, contrato, código e manifesto local fixado mantiveram os hashes antes/depois. Nenhuma chamada extra foi feita nessa conferência.

Comando já executado:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B scripts/evaluate_sentiment_contrast.py --execute --allow-cloud --plan configs/sentiment_contrast_evaluation_v1.json
```

Não repetir. Última regressão da preparação1.026testes/341subcasos aprovada; não repetida nesta execução, pois nenhum código mudou. Apenas resultados/documentação/recibo novos. Nenhuma sessãoSQLite, candidato, revisão de alerta, áudioWhisper/TTSou mudança deUIcriada por este experimento textual.

## Alcance para A5

Há agora demonstração de quatro classes de sentimento, além da avaliação anterior toda neutra. É evidência funcional favorável no pequeno conjunto escrito para contraste, conhecido e com linguagem explícita; não demonstra generalização clínica/populacional, robustez a errosASR ou todas as classes (unknownausente). Não somar este lote e o corpus anterior como se fossem amostras clínicas independentes. Resultado anterior negativo e omissão de termo na avaliação anterior permanecem no histórico.

A avaliação não transforma sentimento positivo/negativo em urgência ou decisão de alerta. A5tem avaliação contrastante real concluída e conferência semântica humana ainda pendente. Próxima tarefa proposta após sua revisão: implementar o detector acústico experimental de pausasA2com testesoffline, usando protocolo já preparado; seus três áudios/checklist serão reaproveitados na avaliação posterior, com anotação temporal ainda a completar.


## Conferência semântica aprovada — 13/11/2026

O usuário conferiu e aprovou as citações deS01–S06. Aprovação registrada separadamente em reports/SENTIMENT_CONTRAST_SEMANTIC_APPROVAL_2026-11-13.json, com hashes das respostas/resumo originais. A pendência humana descrita acima está resolvida; campos pending_human_review nas saídas congeladas preservam o estado no instante da execução, não o estado atual de aprovação. Nenhum arquivo bruto, modelo, métrica ou revisão de alerta alterado. Não equivale a validação clínica.

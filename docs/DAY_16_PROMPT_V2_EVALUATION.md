# Dia 16 — avaliação real do prompt v2 — 07/11/2026

## Resultado

As dez chamadas autorizadas retornaram análises válidas, contra zero no experimento
anterior. O mesmo contrato v3, validador, referências, modelo e parâmetros foram
mantidos. Não houve retry, reparo de resposta, troca de modelo ou nova transcrição.
Somente os textos fictícios manual/Whisper congelados foram enviados, sem áudio.

| Entrada | Válida | Ocorrências encontradas | Omissões | Tempo (s) |
|---|---|---|---|---|
| A03_manual | Sim | 2/2 | 0 | 0.991 |
| A03_whisper | Sim | 2/2 | 0 | 1.575 |
| A04_manual | Sim | 1/2 | 1 | 0.768 |
| A04_whisper | Sim | 2/2 | 0 | 0.839 |
| A05_manual | Sim | 2/2 | 0 | 0.946 |
| A05_whisper | Sim | 2/2 | 0 | 0.825 |
| A08_manual | Sim | 2/2 | 0 | 0.742 |
| A08_whisper | Sim | 2/2 | 0 | 1.232 |
| A12_manual | Sim | 2/2 | 0 | 0.786 |
| A12_whisper | Sim | 2/2 | 0 | 1.456 |

| Métrica | Manual | Whisper |
|---|---|---|
| Análises válidas | 5/5 | 5/5 |
| Ocorrências: TP / FP / FN | 9 / 0 / 1 | 10 / 0 / 0 |
| Precisão / recall / F1 | 100% / 90% / 94,74% | 100% / 100% / 100% |
| Termos únicos: TP / FP / FN | 8 / 0 / 0 | 8 / 0 / 0 |
| Sentimento coincidente com referência | 5/5 | 5/5 |

No conjunto das dez entradas: 19 TP, zero FP e 1 FN; precisão 100%, recall 95%,
F1 97,44%. A04 manual omitiu a segunda ocorrência de **tontura**, em “Hoje não estou
com tontura, mas quero registrar o que aconteceu ontem.” A ocorrência histórica
foi extraída. Isso é uma omissão semântica, apesar de a resposta atender ao contrato.
As regras determinísticas continuam separadas da LLM; nenhuma decisão de alerta
ou revisão humana foi criada por esse experimento.

## Execução e comparação

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B scripts/evaluate_text_v3_prompt_v2.py --execute --allow-cloud --plan configs/day16_text_evaluation_v3_prompt_v2.json
```

Comando já executado. A saída exclusiva existente não deve ser apagada ou
sobrescrita para repetir o lote. Qualquer nova rodada exige novo experimento.

Tempo somado das chamadas: **10,159 s**, contra 10,023 s anteriormente. Tokens
informados pela API: 8600 de entrada, dos quais 7376 em cache (incluídos nos 8600),
e 2311 de saída. O prompt com exemplos aumentou o consumo. Valor efetivamente
debitado e saldo do plano não foram verificados; não houve compra de créditos
ou alteração de plano. Dez respostas encerradas com `stop`, sem timeout ou
truncamento. O transporte não registra status HTTP em respostas bem-sucedidas.
O nome retornado foi gpt-oss:120b, alias aceito de gpt-oss:120b-cloud.

## Verificações e evidências

- Métricas de cada resposta reconstruídas a partir do conteúdo final e referências,
  com leitura UTF-8, sem chamar novamente o modelo; grupos e totais conferidos.
- Hashes de todas as dependências do novo plano reconferidos após as inferências.
- Regressão offline: **801 testes e 341 subcasos em 9,35 s**.
- Dados completos: `data/interim/audio/day16_text_v3_prompt_v2_gpt_oss_cloud_v1/`.
- Recibo com hashes: `reports/DAY_16_PROMPT_V2_EVALUATION_2026-11-07.json`.
- Experimento negativo anterior preservado em `day16_text_v3_gpt_oss_cloud_v1`.

## Como conferir e limites

Compare esta tabela com `summary.json`. Em `A04_manual.json`, confira `provider.content`,
`result.analysis.terms` e `metrics.term_occurrences`; a segunda tontura está ausente.

O resultado permite prosseguir com a interface exibindo sucesso e falhas reais,
mas não torna a LLM definitivamente adotada ou clinicamente validada. O corpus
é pequeno e conhecido; todas as referências de sentimento são neutral. Os exemplos
positivos/negativos do prompt não são testes reais de discriminação de classes.
Não há prova de generalização ou de que transcrição Whisper seja melhor que manual.
A análise textual dos sete TTS e a integração deste adapter no fluxo persistido
continuam pendentes; nenhum código de produção foi alterado nesta avaliação.

Recomenda-se retomar a tarefa 3 do dia 16: definir a apresentação Tkinter e seus
estados, mantendo a omissão registrada e uma avaliação posterior com variedade de
sentimentos e termos. Não iniciar outra rodada de ajuste para eliminar um único
erro observado. Próxima tarefa depende de aprovação por tarefa do AGENTS.md.

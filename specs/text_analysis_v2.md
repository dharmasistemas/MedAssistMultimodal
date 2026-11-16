# Análise textual local v2 — citações localizadas pelo código

06/11/2026. Revisão autorizada após resposta A03 v1 com posições incorretas.
O protocolo v1, seu adapter, referências, recibos e resultados permanecem intactos.
Seleção explícita: `providers.qwen_text_v2.QwenTextAnalyzerV2`. O runner v1 continua
usando v1; não há troca automática nem fallback entre contratos.

O modelo fornece JSON estrito:

```json
{"sentiment":"neutral","sentiment_evidence":[{"quote":"Não senti dor."}],"key_phrases":[{"quote":"dor"}]}
```

Cada item contém somente `quote`, literal não vazia, até 300 caracteres. O código
procura todas as ocorrências exatas, inclusive sobrepostas. Uma única ocorrência
é obrigatória: ausência ou repetição rejeita toda a análise. Não escolher a primeira
ocorrência, normalizar acentos/maiúsculas/espaços nem aceitar posições enviadas pelo
modelo. Para repetição, o prompt pede uma citação mais longa e única; não há retry.
Duplicatas dentro da mesma lista são rejeitadas; uma citação pode fundamentar tanto
sentimento quanto expressão, em listas distintas.

O adapter cria TextEvidence com índices Python [start,end) calculados localmente,
mantendo TextAnalyzer/TextAnalysis e hash do texto original. Não altera o rótulo
semântico retornado. Citação localizada não prova que sentimento/expressão estão
corretos. `unknown` com listas vazias é válido; outros sentimentos exigem evidência.

Preservados do v1: entrada pt-BR até 4000 caracteres; 8 itens por lista; resposta
até 16000 caracteres; rejeição de JSON inválido/chaves extras/duplicadas/não finitos;
modelo qwen2.5:7b-instruct, temperatura 0, 768 tokens, socket 60 s, loopback fixo,
sem proxy/redirect/cloud/pull/retry. Modelo diferente e truncamento são rejeitados.
Regras determinísticas independentes continuam disponíveis após falha. A LLM não
decide alertas, diagnóstico, prescrição ou urgência.

Esta entrega tem validação offline. Uma nova chamada real requer resultado separado
identificado como v2; não converter retroativamente respostas v1 para contar acertos.
As referências existentes continuam provisórias; nenhuma nova qualidade semântica
ou recuperação do cronograma é declarada com testes simulados.

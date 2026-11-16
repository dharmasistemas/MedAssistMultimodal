# Análise textual local v1 — protocolo do dia 14

06/11/2026, tarefas 1–3. Definido antes de executar o corpus com Qwen. Sem geração
real nestas tarefas. Modelo fixo qwen2.5:7b-instruct, endpoint HTTP loopback
127.0.0.1:11434, sem cloud, pull ou fallback de modelo.

## Papel dos componentes

TextAnalyzer preservado; origem ollama_qwen adicionada sem quebrar mocks. Qwen
produz sentimento textual e expressões literais, nunca diagnóstico, prescrição,
severidade ou decisão de alerta. Regras puras separadas detectam menções/contexto
e continuam disponíveis quando o provider falha. Menção não equivale a alerta.

Entrada pt-BR, 1–4000 caracteres, texto original sem normalizar offsets. Prompt
separa conteúdo não confiável das instruções. Não obedecer comandos no relato.
Resposta JSON estrita, sem markdown/chaves desconhecidas ou duplicadas:

```json
{"sentiment":"neutral","sentiment_evidence":[{"start":0,"end":5,"quote":"texto"}],"key_phrases":[]}
```

Sentimento: positive/neutral/negative/mixed/unknown; evidências e expressões são
listas com até 8 itens. Cada item tem start/end inteiros, intervalo [start,end)
em caracteres Python do texto original e quote idêntico ao trecho, até 300 caracteres.
Sentimento não unknown exige evidência; unknown pode abster-se. Expressões vazias
são válidas. Validar duplicatas/intervalos/limites. Não completar/corrigir JSON
automaticamente. Armazenar hash do texto, modelo e fonte; citação literal não prova
correção semântica. Não inferir sentimento vocal/emoção a partir de texto.

Transporte OllamaProvider existente reutilizado, temperature=0, max_tokens=768,
timeout de socket 60 s, sem retry/correção/fallback automáticos. Modelo retornado
deve coincidir e finish_reason length é rejeitado. Timeout não promete interrupção
do processamento no servidor ou cancelamento forte do worker da futura UI.

## Regras experimentais locais context-terms-v1

Vocabulário inicial: dor, dor no peito (termo mais longo prioritário), falta de ar,
tontura. Busca literal case-insensitive com bordas de palavra, preservando offsets.
Sem expandir para qualquer doença ou sintoma não configurado.

Contextos: affirmed_current, negated_current, affirmed_historical,
affirmed_earlier_in_session, conditional, third_party, unknown. Evidência por
ocorrência contém termo, [start,end), trecho e contexto de sentença. Regras de
contexto limitadas à sentença/prefixo, marcadores explícitos, precedência:
incerteza → terceira pessoa → condicional → negação → histórico → início da sessão
→ afirmação atual. Dentro da sentença, adversativas mas/porém reiniciam o prefixo.
Não resolver correferência, negação dupla complexa, ironia ou fala indireta geral.
Ausência de termo retorna lista vazia, não paciente saudável. Não define urgência.

## Avaliação futura (tarefa 4)

Humanos development A03/A04/A05 primeiro e evaluation A08/A12 depois, referência
manual e texto Whisper separados. Sem corrigir ASR antes da análise. A03 contém dor
e falta de ar negadas; A04 tontura histórica e atual negada; A05 falta de ar
condicional e negada; A08/A12 falta de ar e tontura afirmadas. Anotações confirmadas
em arquivo separado antes da execução, não fornecidas à LLM como resposta esperada.

Rótulos de sentimento dos roteiros são intenção textual provisória: neutral em A03,
mixed em A04, neutral em A05, negative em A08/A12. Ambiguidade entre descrição factual
e valência deve ser reportada; não chamar de ground truth clínico. Permitir unknown
e medir abstenção separadamente. Expressões devem ter referência humana definida
antes de avaliar precisão/recall, não escolhida a partir da saída do modelo.

Medir sentimento/exatidão das evidências, expressões/contexto, erros de schema,
timeout/latência e diferença entre entrada manual/ASR, denominadores explícitos.
Sem limiar de aceite clínico validado. Mesmo locutor e corpus conhecido: não teste
independente. Os sete TTS permanecem pendentes da resposta de permissões; mocks
offline nas tarefas 2–3 não são execução real do Qwen ou avaliação do corpus.

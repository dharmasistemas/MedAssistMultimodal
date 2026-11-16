# Contrato de análise textual v3 — termos e evidências separados

**Data:** 06/11/2026. **Estado:** especificado; ainda não implementado nem executado.
Aplica-se a texto PT-BR simulado, com o mesmo contrato para provedores locais ou
cloud. LLM opcional, sem diagnóstico, prescrição, urgência ou decisão de alertas.
Schema: [text_analysis_v3.schema.json](text_analysis_v3.schema.json).

## Problema corrigido e preservação histórica

O v2 pede citações únicas, mas sua métrica exige expressões curtas exatas. Em
`Se eu sentir falta de ar... Neste momento, não estou com falta de ar.`, o termo
aparece duas vezes: citar só `falta de ar` é ambíguo; citar uma frase inteira deixa
de coincidir com a referência curta. O v3 separa identificação e localização.

V1/v2, referências e resultados anteriores permanecem intactos. Não converter
respostas antigas em novos acertos ou comparar F1 de tarefas diferentes como se
fosse a mesma medida. Esta revisão foi motivada por resultados já observados: os
cinco casos são corpus de desenvolvimento conhecido, incluindo os que antes eram
evaluation. Não os apresentar como novo teste independente.

## Entrada e saída

Entrada: texto original inalterado, idioma pt-BR, 1–4000 caracteres e vocabulário
fixo fornecido no prompt: `dor`, `dor no peito`, `falta de ar`, `tontura`.
Não extrair expressões livres nesta tarefa. Termos ausentes não devem ser inventados.
Máximo de resposta: 16000 caracteres; até 8 termos/ocorrências e 8 evidências de
sentimento; cada citação até 300 caracteres. Orçamento de tokens deve comportar
prompt, entrada e saída, definido por experimento antes da execução.

Exemplo válido para a entrada abaixo:

```text
Se eu sentir falta de ar, vou avisar. Agora não estou com falta de ar.
```

```json
{
  "sentiment": "neutral",
  "sentiment_evidence": [
    {"quote": "Se eu sentir falta de ar, vou avisar."}
  ],
  "terms": [
    {"term": "falta de ar", "quote": "Se eu sentir falta de ar, vou avisar."},
    {"term": "falta de ar", "quote": "Agora não estou com falta de ar."}
  ]
}
```

`term` é identificador canônico exatamente igual a um item do vocabulário. `quote`
é evidência literal de uma ocorrência, não a expressão usada na métrica de termos.
Não devolver start/end, contexto clínico, explicação, severidade ou campos extras.
É permitido usar a mesma citação em sentimento e termos ou para termos diferentes.
Repetir o mesmo termo em ocorrências diferentes é necessário; não colapsar negação
e condição em uma única menção.

## Localização e validação determinísticas obrigatórias

1. Validar JSON estrito: sem markdown, chaves extras/duplicadas ou números não
   finitos. O schema é parte da validação, não prova de evidência ou semântica.
2. A citação deve existir exatamente no texto e ocorrer uma só vez, considerando
   também correspondências sobrepostas. Não normalizar acento, caixa, espaços,
   pontuação ou Unicode para aceitar a citação. `parei` não corrige `Parei`.
3. Para cada item de terms, procurar o vocabulário na citação com bordas de palavra,
   sem distinguir caixa, preservando os índices originais. Entre termos que se
   sobrepõem, escolher o mais longo: `dor no peito` suprime `dor` nessa ocorrência.
   Não fazer stemming, tradução ou sinônimos implícitos. O termo declarado precisa
   ter exatamente uma ocorrência elegível na citação. Uma citação com duas
   ocorrências elegíveis do mesmo termo é ambígua; o modelo deve citar trecho menor
   que ainda seja único no texto. Se não conseguir, deve omitir o item.
4. Código calcula quote_start/quote_end e term_start/term_end em caracteres Python
   [início,fim). Evidência interna inclui quote, term, texto literal do termo e hash
   da entrada. Não confundir os dois intervalos. Nenhum índice é contado pela LLM.
5. Duplicata é a mesma combinação (term,term_start,term_end), mesmo com citações
   diferentes. Rejeitar duplicatas; permitir os dois itens do exemplo, pois apontam
   para ocorrências diferentes. Sentiment_evidence não admite citação duplicada.
6. Sentimento diferente de unknown exige ao menos uma evidência literal. Ausência
   de evidência não vira unknown automaticamente. Unknown pode ter listas vazias.
7. Qualquer violação invalida toda a análise do provider, sem retry/repair ou aceite
   parcial neste protocolo. Contextos/regras locais continuam disponíveis em saída
   separada; invalidade não é ausência de sintoma, unknown ou paciente saudável.

Termo canônico identifica menção, não afirmação atual. Contextos experimentalmente
calculados continuam no componente determinístico existente; a LLM não os decide.
Uma citação literal pode ser semanticamente inadequada: localização não certifica
interpretação. Se o texto superar 8 ocorrências elegíveis, a futura implementação
deve sinalizar entrada fora da capacidade deste protocolo antes da chamada; não
aceitar truncamento silencioso como cobertura completa.

## Sentimento: política linguística v3

Sentimento textual não é condição clínica, emoção vocal nem intensidade da dor.
Classificar linguagem avaliativa explícita do narrador, considerando negação e
escopo. Relatos factuais de sintomas, sua ausência, ação de parar, condição ou
histórico não bastam por si para inferir valência. Relato de terceiros não atribui
automaticamente emoção ao narrador.

|Rótulo|Critério de anotação|Exemplo didático novo|
|---|---|---|
|positive|Avaliação positiva explícita do narrador|Estou satisfeito com a sessão.|
|negative|Avaliação negativa explícita do narrador|Estou frustrado com a sessão.|
|mixed|Avaliações positiva e negativa explícitas, ambas presentes|Estou satisfeito com o atendimento, mas frustrado com a espera.|
|neutral|Relato compreensível sem avaliação positiva/negativa explícita|Hoje não senti dor.|
|unknown|Sentido/escopo insuficiente para aplicar os critérios|Não sei explicar o que quero dizer.|

Essas frases são exemplos editoriais, não resultados de modelo. Citar o trecho que
fundamenta a classificação. Unknown é abstenção, não erro de transporte; ausência
de sintoma não implica positive, presença de sintoma não implica negative e mudança
histórico→atual não implica mixed. Ambiguidade real precisa ser anotada como tal
antes da execução, sem permitir qualquer rótulo após observar a resposta.

**Os rótulos provisórios v1 não foram reescritos.** A04=mixed e A08/A12=negative
foram baseados em intenção do roteiro e não são automaticamente referências para
esta nova tarefa linguística. A futura anotação v3 deve ser feita a partir do texto
e desta política, com justificativa, responsável, data e estado de revisão, antes
de qualquer nova chamada. Enquanto essa anotação não for revista/aceita, sentimento
é exploratório, sem nova taxa de acerto publicada como validada. Novas pontuações
não substituem nem reabilitam os resultados antigos.

## Métricas e referências alinhadas

- **Validade:** análises válidas/tentativas, com erros de schema, evidência,
  transporte, timeout e truncamento separados. Informar latência, tokens e consumo
  disponível sem inventar valor efetivamente debitado. Falha não conta como unknown.
- **Termos por ocorrência (principal):** comparar multiconjunto de
  (term,term_start,term_end) com referências específicas da entrada. TP/FP/FN,
  precisão/recall/F1; citar uma frase maior não altera o termo pontuado. Uma omissão
  de ocorrência repetida conta como FN. Não avaliar o tamanho da citação como se
  fosse identidade do termo.
- **Termos únicos (secundária):** comparar conjuntos de term, com denominador e
  rótulo próprios; não substituir a métrica de ocorrências nem esconder omissões.
- **Sentimento:** exatidão entre válidas e operacional entre tentativas, cobertura
  e unknown separados, somente após referências v3 revistas. Reportar desacordos
  e itens de referência não pontuáveis; nunca contar rótulo bruto de análise inválida.
- **Contexto:** medir separadamente o componente determinístico; não atribuir seus
  acertos ao modelo cloud/local. Termo/contexto e estado de revisão de alerta são
  conceitos diferentes.

As referências de termo/contexto v1 podem ser insumo da anotação v3, mas não bastam
para os novos índices: fixar cada ocorrência no texto manual e no Whisper realmente
enviados, separadamente, com seus hashes. Não copiar offsets manual→ASR, corrigir
transcrição silenciosamente ou colapsar repetições. Conferir longest-match na nova
anotação. Métricas com zero denominador retornam null; se houve FN, F1 operacional
zero permanece distinto de ausência de predições aceitas.

## Próximo incremento e congelamento

Antes de novas chamadas: implementar tipos/validador/prompt/métricas v3 e testes
offline; criar referências de ocorrência e anotação linguística v3 para revisão;
fixar schema/prompt/config/modelo/hashes/ordem e versão do avaliador em novo recibo.
Não reutilizar TextAnalysis v2 sem adaptação explícita: ele ainda não representa
os dois intervalos nem source cloud. Runners v1/v2 continuam históricos.

Casos offline mínimos: duas ocorrências de falta de ar com contextos diferentes;
duas citações diferentes para a mesma ocorrência (rejeitar); citação repetida no
texto; termo repetido dentro de citação única; dor no peito versus dor; caixa do
termo versus caixa literal da citação; fim exclusivo e Unicode; termo inventado;
literalidade/schema/listas/limites/unknown; provider indisponível preservando regras.

Nenhum modelo novo é adotado por este contrato. Backend/think/tokens/timeout serão
explícitos no próximo experimento e não alterados durante o lote. Texto fictício
somente em cloud autorizada, sem novos créditos/planos/fallback automáticos. LLM
nunca determina alertas. Tarefa5 do dia14 continua pendente de entrega específica.

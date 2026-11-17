# Whisper — visão consolidada dos 12 áudios

07/11/2026. Consolidação dos resultados de 05–06/11, sem novas inferências ou alteração de mídia/referências. O relatório anterior focava apenas a expansão dos sete TTS; os cinco humanos já estavam no relatório do dia 13. Os dois grupos agora aparecem juntos por arquivo.

|Áudio|Origem|Erros / palavras|WER|Diferença medida|
|---|---|---|---|---|
|A01|TTS|0/17|0,00%|Sem erro de palavras|
|A02|TTS|1/20|5,00%|senti → sente|
|A03|Voz humana|0/21|0,00%|Sem erro de palavras|
|A04|Voz humana|0/18|0,00%|Sem erro de palavras|
|A05|Voz humana|0/18|0,00%|Sem erro de palavras|
|A06|TTS|1/20|5,00%|senti → sente|
|A07|TTS|0/16|0,00%|Sem erro de palavras|
|A08|Voz humana|1/20|5,00%|e → de|
|A09|TTS|1/16|6,25%|inserção de o|
|A10|TTS|0/18|0,00%|Sem erro de palavras|
|A11|TTS|2/16|12,50%|inserção de eu; inserção de o|
|A12|Voz humana|0/20|0,00%|Sem erro de palavras|

Totais preservados: voz humana 1/97 = 1,03%; TTS 5/123 = 4,07%; conjunto descritivo 6/220 = 2,73%. Não é média simples dos percentuais por arquivo. A contagem compara palavras após a normalização definida; não é contagem de arquivos com erro.

## Manter ou substituir os TTS?

Recomendação: manter os sete TTS no corpus atual. A diferença observada não isola o efeito da origem da voz: roteiros, vozes, formatos e condições diferem, há poucos exemplos e A02/A06 repetem o mesmo conteúdo e erro. Não concluir que qualquer voz humana é superior ao TTS. Três dos sete TTS tiveram WER zero.

Substituir somente os casos que deram erro depois de medir mudaria o conjunto de avaliação para obter pontuação melhor. Os erros atuais são evidências úteis para verificar como o fluxo trata uma transcrição imperfeita. Se houver uma nova coleta justificada, criar outra versão/experimento, preservar os originais e comparar gravações do mesmo roteiro sob condições definidas. Não foi autorizada ou executada nova coleta nesta entrega.

WER mede fidelidade de palavras; não avalia sozinho se a LLM interpretou corretamente o relato ou se uma regra de alerta funcionou. Isso não torna erros irrelevantes: trocar senti por sente muda a formulação do relato; perder uma negação, trocar lado corporal ou atribuir fala de terceiro ao narrador são exemplos de efeitos que precisam de testes específicos no fluxo. A relevância não pode ser deduzida só do percentual de WER. Nenhuma consequência clínica dos erros deste lote foi validada.

Próxima avaliação deve comparar referência manual e ASR, mantendo as diferenças, e verificar termos/ocorrências/contextos separadamente. A inserção de Eu em A11 e do artigo em A09 está registrada como erro de transcrição, sem alterar a referência para aceitá-la. A análise textual v3 ainda não foi executada; não afirmar que ela já tolerou esses erros.

O melhor uso do tempo agora é avançar na avaliação textual e na integração planejadas, com erros explícitos e revisão humana. Não é necessário regravar para apagar os erros desta avaliação. Nova gravação passa a fazer sentido se houver áudio incompreensível/arquivo inválido, correção do roteiro solicitada ou um experimento comparativo específico — não apenas porque um grupo teve WER maior.

Fontes locais: `data/interim/audio/day13_evaluation_v1/evaluation.json` e `data/interim/audio/day14_tts_whisper_v1/evaluation.json`. Resultados e rótulos anteriores preservados; nenhum código, modelo ou configuração alterado.

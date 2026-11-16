# Resultados e limitações

Consolidação dos experimentos locais até 16/11/2026. Sem validação clínica ou avaliação independente de pacientes.

| Frente | Resultado no recorte conhecido |
| --- | --- |
| Cotovelo RGB | Dez trechos: quatro analisáveis, 1 TP/1 FP/2 TN e seis abstenções; detectado 1/3 dos positivos totais |
| Whisper | 12 áudios, WER 6/220 = 2,73% |
| GPT-OSS, prompt revisado | Dez entradas válidas, 19 TP/0 FP/1 FN por ocorrência; F1 97,44% |
| Sentimento contrastante | Seis textos, seis rótulos coincidentes, sete termos recuperados; unknown não avaliado |
| Vitais | 18 cenários/216 amostras sintéticas; 13 TP, zero FP/FN nas referências conhecidas |
| Prescrições com plano | Oito casos: um compatível, quatro divergentes e três indeterminados |
| Piloto de pausas | Concordância qualitativa 2/3; temporal 0 TP/1 FP/0 FN, sem positivos humanos para calcular recall |

Lotes e corpus não são independentes nem representam pacientes diferentes. Termo não comprova sintoma afirmado. Sentimento não é diagnóstico. Vídeo tem qualidade/cobertura insuficientes. Alterações vocais médicas e movimentação durante internação não foram demonstradas.

O relatório acadêmico em aprovação documenta metodologia, fontes por experimento e trabalhos futuros. Fontes independentes não são apresentadas como um único atendimento correlacionado.

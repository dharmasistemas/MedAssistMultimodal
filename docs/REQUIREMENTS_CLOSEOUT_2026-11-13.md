# Fechamento dos requisitos — 13/11/2026

Esta consolidação é a referência atual de aderência. Preserva a matriz de 11/11 (referência do acervo local, não distribuída) e seus registros históricos. Fonte: enunciado original (referência do acervo local, não distribuída), páginas físicas 3–4. As aprovações do usuário sobre guias e UI não constituem aceite da banca nem validação clínica.

## Resultado do fechamento

O fluxo técnico da POC está implementado nos recortes avaliados: entrada, processamento, evidência, consulta, candidatos quando a regra sinaliza, revisão humana e exportação. Isso não significa cumprimento integral de todos os requisitos. Vídeo tem qualidade/cobertura insuficientes; alterações vocais indicativas de condições médicas e movimentação do paciente fictício internado (N3) não foram demonstradas. Não há percentual global de atendimento: os requisitos têm alvos diferentes.

As modalidades serão demonstradas separadamente. Participante REHAB26, locutores e paciente fictício não são a mesma pessoa. A síntese reúne resultados com proveniência, sem inferir relação clínica entre fontes independentes. As substituições OpenCV/MediaPipe e Whisper/LLM foram autorizadas pela coordenação conforme relato do usuário; autorização de tecnologia não dispensa avaliar o requisito.

## Matriz consolidada

“Atendido no recorte” significa função demonstrada no conjunto indicado, sem generalização clínica. “Parcial” indica parte funcional demonstrada e exigência ainda incompleta. “Não demonstrado” indica ausência de evidência suficiente do alvo solicitado.

| ID | Requisito | Estado atual e evidência | Limite / pendência real |
|---|---|---|---|
| V1 | Processar vídeo clínico | **Atendido no recorte:** MP4 de fisioterapia, OpenCV/MediaPipe, poses/ângulos, UI e evidências. [Vídeo](ELBOW_RGB_UI_2026-11-12.md) | Trechos fornecidos de uma gravação; não alegar análise confiável de toda a sessão. |
| V2 | Detectar movimento fora do padrão | **Parcial:** detector experimental de flexão de cotovelo, avaliado em dez trechos RGB conhecidos. | Só 4/10 analisáveis; 1 TP, 1 FP, 2 TN e 6 abstenções, incluindo dois positivos. Precisão 50% nos analisáveis; detectou 1/3 positivos de referência considerando todos os trechos. Não cobre todos os erros de Ex1. |
| V3 | Relatar desvios/falhas automaticamente | **Parcial:** relatório aponta o desvio experimental, intervalo, regra, evidência e revisão. | Exportação implementada não compensa a qualidade limitada de V2; baixa visibilidade é limitação técnica, não falha clínica do exercício. |
| A1 | Processar áudio de consultas | **Atendido no recorte simulado:** 12 gravações, sete TTS e cinco humanas. Corpus (referência do acervo local, não distribuída) | Não são consultas reais nem 12 pacientes. |
| A2 | Detectar alterações vocais indicativas de condições médicas | **Não demonstrado no alvo médico; recorte técnico implementado:** descritores e detector de pausas, três arquivos, UI/revisão/exportação. [Piloto](ACOUSTIC_PILOT_UI_2026-11-13.md), [temporal](ACOUSTIC_TEMPORAL_EVALUATION_2026-11-13.md) | Todos sem sinal global; concordância qualitativa 2/3. Comparação temporal: 0 TP, 1 FP, 0 FN; nenhuma referência positiva, recall não calculável. Não detecta doença, fadiga ou dificuldade respiratória comprovadas. |
| A3 | Transcrição/análise de áudio, originalmente Azure Speech | **Atendido com substituição autorizada no recorte:** Whisper local real em 12/12; WER 6/220 = 2,73%. | WER mede transcrição, não condição vocal ou segurança clínica. |
| A4 | Termos críticos, originalmente Azure Text Analytics | **Atendido com substituição autorizada no corpus:** GPT-OSS opcional na UI; rodada anterior 19/20 ocorrências; novo conjunto contrastante 7/7. [Prompt v2](DAY_16_PROMPT_V2_EVALUATION.md), [contraste](SENTIMENT_CONTRAST_EVALUATION_2026-11-12.md) | Conjuntos diferentes; não somar como casos independentes. Regras locais de contexto decidem candidatos; LLM não decide alertas. |
| A5 | Sentimentos, originalmente Azure Text Analytics | **Atendido no recorte textual:** seis textos fictícios, quatro classes, 6/6 coincidentes; citações aprovadas pelo usuário em 13/11. | Textos explícitos, sem avaliação clínica/generalização; unknown não testado. Não são seis novos áudios ou transcrições Whisper. |
| N1 | Anomalias em FC, pressão e oxigenação | **Atendido no recorte sintético:** 18 cenários/216 amostras, 13 TP, zero FP/FN nas referências conhecidas. [Avaliação](../reports/DAY_11_CLOSEOUT_2026-11-03.md) | Sem avaliação clínica independente. BIDMC não executado; dataset específico não é obrigatório no enunciado. |
| N2 | Alterações inesperadas de prescrição | **Atendido no recorte sintético com plano declarado:** oito casos, 1 compatível, 4 divergentes, 3 indeterminados; quatro candidatos; UI conferida. [Prescrições](PRESCRIPTION_EXPECTATION_UI_2026-11-12.md) | Não julga segurança terapêutica. Sem expectativa aplicável ou unidade comparável, abstém-se. |
| N3 | Padrões de movimentação do paciente fictício internado | **Não demonstrado neste cenário:** não há evidência de um fluxo independente de movimentação durante internação. | Correção de interpretação do usuário em 13/11: manter “internação”. Vídeo de fisioterapia é V1–V3, não substitui N3. Vitais e prescrições sintéticos também não comprovam análise de movimentação. |
| N4 | Alertas automáticos para equipe médica | **Fluxo local atendido no recorte; cobertura parcial:** regras → candidato → evidência → revisão auditada → histórico/exportação. Fluxo (referência do acervo local, não distribuída), exportação (referência do acervo local, não distribuída) | Nem todo evento é alerta. Vídeo/A2 limitam cobertura; piloto acústico real não gerou candidatos. Sem notificação externa implementada; o PDF não exige email. Revisão humana não valida clinicamente a regra. |
| D1 | Código completo em Git | **Pendente de fechamento de entrega:** código local disponível. | Conferir conteúdo versionável, dependências, execução, dados/segredos excluídos e acesso à versão final. Não há comprovação de publicação final nesta tarefa. |
| D2 | Relatório técnico | **Parcial:** rascunho 0.2 (referência do acervo local, não distribuída) existente. | Atualizar implementação, resultados positivos/negativos, limites, fontes técnicas e adaptações; preservar dados acadêmicos e comentários do usuário. |
| D3 | Vídeo de até 15 minutos publicado | **Pendente:** ensaio anterior realizado pelo usuário. | Revisar roteiro com modalidades independentes; gravar fluxo final, anomalia/resposta e limites; conferir duração, permissões e link público/não listado. |

## O que foi encerrado em 12–13/11

- Vídeo: implementação e avaliação delimitadas entregues, erros e abstenções preservados. Intervalos são entradas fornecidas; detecção de intervalos incorretos na gravação completa não foi demonstrada.
- Prescrições: expectativa independente integrada, avaliada e conferida na UI.
- Sentimento: referências e citações aprovadas; execução real concluída, sem nova rodada necessária para este fechamento.
- Acústica: coleta/escuta, integração, conferência visual e referência temporal encerradas. Três listas humanas vazias revisadas são referências válidas, não preenchimento pendente. O falso positivo temporal de AP02 não é candidato global; AP03 permanece discordante na avaliação qualitativa. Não alterar anotações/limiares para melhorar o resultado.

As lacunas de V2/V3, N3 independente e A2 devem constar no relatório e na demonstração. O planejamento abaixo prioriza a entrega verificável com essas limitações; não promete atendimento integral nem aceite acadêmico. Nenhum novo dataset, modelo, ajuste de limiar ou regravação é iniciado por esta consolidação.

## Cronograma restante e próximo incremento

| Data | Trabalho | Conferência de saída |
|---|---|---|
| 13/11 | Consolidação atual (13.4) | Matriz, limites e calendário para revisão do usuário. |
| 14/11 | Simplificar UI em incrementos | Primeiro: reorganizar a entrada e navegação por modalidade, com origem visível, ação principal clara e detalhes técnicos recolhidos. Preservar funções, integridade, histórico, confirmação cloud e revisão auditada. Inspeção visual antes do incremento seguinte. |
| 15/11 | Avaliação integrada e correções; congelamento condicionado | Percursos positivo/negativo/insuficiente/falha, independência da LLM, revisão e exportação; congelar somente versão efetivamente verificada. |
| 16/11 | Atualizar relatório e roteiro; gravar | Documentação coerente com esta matriz, exemplos incluindo falhas, vídeo até 15 minutos. |
| 17/11 | Conferir e entregar | Código/relatório/link acessíveis, permissões e versão final conferidos. |

Para o ensaio, usar UUIDs dos guias, não posições variáveis na lista. Casos úteis: vídeo D9-04 (TP), D9-02 (FP) e caso de abstenção; prescrições E01/E02/E03; vitais sem/com ocorrência; áudio com transcrição e LLM opcional; acústica AP02/AP03 para explicitar limites. Não é necessário executar tudo no vídeo final: selecionar roteiro dentro da duração, mantendo as falhas relevantes no relatório.

## Verificação desta consolidação

Mudança exclusivamente documental. Nenhum código, regra, prompt, áudio, referência humana ou SQLite alterado; nenhuma decodificação, ASR ou chamada LLM. Regressão existente: 1.156 testes/341 subcasos antes do último refinamento de apresentação; depois, 38 testes direcionados aprovados. Esses resultados são históricos, não uma nova execução nem validação clínica.

Verificados UTF-8, links locais desta consolidação e diferenças de whitespace. Recibo com hashes das fontes de resultado e documentos em REQUIREMENTS_CLOSEOUT_2026-11-13.json (referência do acervo local, não distribuída). Próxima implementação exige aprovação explícita por tarefa conforme AGENTS.md (referência do acervo local, não distribuída), seção “Execução passo a passo com aprovação do usuário”.


## Correções e decisões do usuário — 13/11/2026

- **N3:** desconsiderada a proposta anterior de substituir internação por consulta. O cenário é o paciente fictício internado; a análise de fisioterapia permanece separada em V1–V3. Não foi implementado novo detector para N3 nesta revisão.
- **D1:** após os ajustes finais de funcionalidades e UI, planejar backup integral em `_backup/` e só depois limpeza para entrega enxuta. Não executar agora. Antes da operação, definir destino novo, escopo, manifesto, validação da cópia e lista exata de remoções com dependências/testes. Não percorrer conteúdos privados existentes nem incluir recursivamente o destino no próprio backup. Compatibilizar a autorização específica de criação do backup com a regra de área privada do AGENTS antes da execução. Preservar fora da distribuição enxuta a evidência necessária à rastreabilidade acadêmica. Arquivo intermediário não é automaticamente descartável: alguns são dependências de integridade/histórico e devem ser identificados. Remoções seguem aprovação da lista exata e condições de segurança do AGENTS; nenhuma exclusão realizada ou implicitamente aprovada por este plano. Atualizar documentação e verificar a execução da distribuição limpa.
- **D2:** nova revisão do relatório técnico somente após concluir ajustes finais funcionais. Não gerar revisão agora. Incluir seção de trabalhos futuros com robustez do vídeo, N3 de internação, avaliação acústica adequada, mais casos independentes e avaliação clínica quando aplicável. Não apresentar trabalhos futuros como requisitos já atendidos.
- **14/11 antecipado:** primeira tarefa passa a ser protótipo visual não funcional para comentários/aprovação, antes de alterar a UI real. Priorizar simplicidade e demonstração clara, mantendo limitações explícitas.

As decisões atuais substituem a interpretação anterior de N3 e a sequência documental anterior; os recibos congelados registram versões históricas, não o hash desta revisão. Atualização em UI_PROPOSAL_2026-11-13.md (referência do acervo local, não distribuída).

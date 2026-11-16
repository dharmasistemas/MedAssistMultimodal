# A2 — protocolo experimental de pausas — v1 — 12/11/2026

## Alvo e limites fixados antes de medir as novas amostras

Detectar **padrão de pausas internas frequentes / baixa energia**, sem identificar cansaço, dispneia, origem da pausa ou som de respiração. A autorização acadêmica do uso de vozes sintéticas foi relatada pelo usuário; o experimento verifica um comportamento simulado, não condição médica. A2completo permanece não demonstrado até a avaliação e não vira validado clinicamente pela simulação.

Não usar transcrição, prompt de geração, nome do arquivo, rótulo de condição ou saídaLLM como entrada da regra. ASR/LLM opcionais e separados; detecção acústica não deve depender de chamadas de modelo. Não mudar o corpus12, prompts/experimentos anteriores ou alterar o MP3 para forçar resultado positivo.

## Pré-processamento e parâmetros propostos

Perfil proposto `internal-pauses-v1`, fixo para uma rodada após aprovação deste protocolo; números são heurísticas de engenharia, não limites médicos:

- Decodificação local determinística com backend já disponível,mono16000Hz,float, sem normalização de ganho/remoção de ruído/silêncios/interpolação. Preservar hash e original.
- Reutilizar describe_audio/energy-descriptors-v1: janelas20ms,RMS de baixa energia estritamente<0,01, intervalos contínuos>=0,20s. Nenhum pacote ou modelo novo.
- Duração suportada5–60s inclusiva; pico normalizado>=0,05 e RMSglobal>=0,01. Pouco sinal, silêncio completo, amplitude fora[-1,1], valores não finitos ou metadados inconsistentes não podem virar “sem padrão”. Entradas inválidas/rejeitadas e insuficiência técnica devem ser separadas.
- Cortar SOMENTE do denominador os intervalos de baixa energia que tocam início0ou fimduração, usando os intervalos do descritor; não editar áudio nem renumerar timestamps. Intervalos internos menores que0,20s não são descritos por esse perfil e não serão inventados. Exigir intervalo central restante>=3s; caso contrário, evidência insuficiente.
- Considerar pausa longa cada intervalo descrito estritamente interno com duração>=0,60s. Contar cada intervalo contínuo uma vez; não fragmentar em janelas para aumentar a contagem. Soma das durações dessas pausas / duração do intervalo central = fração de pausas longas.
- **Sinal experimental** se houver pelo menos3pausas longas E fração>=15%, ambos inclusivos. **Sem sinal do perfil** se entrada suficiente e ao menos um critério não ocorrer. **Evidência insuficiente** para requisitos técnicos não atendidos. Duração inválida/arquivo corrompido/ausente/alterado são falhas explícitas, sem candidato clínico presumido.
- Guardar contagem,durações,intervalos originais,denominador,fração,limiares,hash,versão e motivo. Comparações temporais usarão índices inteiros de amostra quando possível; fronteiras exatas0,60/0,20serão testadas sem depender de erro de arredondamentofloat.

Controle por energia não é detector de fala(VAD) ou respiração: expiração pode ter energia alta e NÃO ser contada como pausa; ruído pode mascarar intervalos, e gravação baixa pode gerar falsos sinais. Esses resultados devem ser mostrados, sem mudar parâmetros depois de ouvir/medir o positivo. Não prometer que a amostraexhalesdisparará a regra.

## Amostras e controles

Inventário inicial em [acoustic_pilot_inventory_v1.json](acoustic_pilot_inventory_v1.json), apenas metadados e hashes. Um candidato ElevenLabs disponível; dois arquivos DarkPlanner apenas exploratórios, pois modelo/voz/comportamento não foram confirmados. Não comparar fornecedores diferentes como efeito causal isolado de cansaço ou das tags.

Conjunto mínimo proposto de três gravações do MESMOtextoA02,mesma voz/modelo/fornecedor/configuração:

| ID | Condição de geração | Arquivo sugerido | Referência atual |
|---|---|---|---|
| AP01 | Contínua, sem tags | A02_elevenlabs_continuous_take01.mp3 | Ainda não coletada |
| AP02 | Entrega com pausas/expiração simulada | A02_elevenlabs_exhales_take01.mp3 | Arquivo presente; escuta/anotação pendentes |
| AP03 | Pausas por pontuação, sem tag respiratória | A02_elevenlabs_punctuation_take01.mp3 | Ainda não coletada |

O AP03é controle de causa: se contiver o mesmo padrão acústico, também PODEsinalizar. Isso NÃOdeve ser contado automaticamente como falso positivo do alvo “pausas”, mas demonstra a falta de especificidade médica. Se a referência de escuta não tiver pausas frequentes e a regra sinalizar, registrar falso positivo. Não rotularAP01negativo ouAP02positivo apenas pelo prompt; referência depende do áudio realmente produzido.

Os MP3DarkPlanner não são controles pareados deAP02. Após escuta, o teste com tags pronunciadas pode ser exemplo de falha de geração, fora do conjunto comparativo; não inventar a correspondência pelo nome01/02.

## Referência humana e escuta antes de pontuar

Registrar metadados de voz/modelo/settings e texto realmente falado. Ouvir as três condições e preencher checklist sem olhar a saída do futuro detector: palavras preservadas, tags pronunciadas, pausas/interrupções perceptíveis, expiração audível, ruído/defeitos e observações. Depois anotar início/fim aproximados dos intervalos longos no Audacity, com gravação original; uma forma de onda bruta pode auxiliar, sem usar a classificação automática como groundtruth. Aprovar referências antes de calcular acurácia. Os tempos podem ser estimados até0,1s; incerteza deve ficar registrada.

Referência de classe: pausas internas frequentes percebidas / não frequentes / incerto. Nunca “paciente cansado/saudável”. Para intervalos de referência anotados como>=0,60s, comparar um-para-um com sobreposição temporal(IoU>=0,5), reportandoTP/FP/FN; não deslocar referências para caber na saída. Separar discordância de percepção humana da contagem técnica definida. Caso incerto não entra silenciosamente no denominador: reportar à parte. Com três arquivos, sempre publicar tabela individual e denominadores; não generalizar.

Na avaliação de arquivo, comparar rótulos de escuta com os três estados da regra, incluindo insuficiência/falha. Registrar latência e unidades. Os sons de expiração serão observações humanas; nenhum acerto de identificação automática de respiração será publicado com esse detector.

## Plano de implementação posterior

1. Regra pura tipada e testesoffline: positivo/negativo/bordas3pausas/15%/0,60s/baixa energia, exclusão das bordas, silêncio,baixo sinal,ruído,clipping e falha de decodificação. Mocks explicitamente rotulados.
2. Decoder/descritores independentes do Whisper quando possível, sem carregar modelo apenas para medir energia. Se compor comASR, manter estados por etapa e falhas independentes; preservar evidênciasv1.
3. Nova evidência/sessão para o piloto, fonteTTSreal identificada. Somente sinal do perfil produz candidato técnico para revisão, sem severidade/diagnóstico. Sem revisão automática; preservar estado e hashes.
4. Avaliação local com configuração/hashes anteriores e saída exclusiva; uma rodada, sem afinar parâmetros para obrigarAP02a disparar. Preservar quaisquer falsos positivos/negativos.
5. UI apresenta “Padrão experimental de pausas frequentes no áudio simulado”, contagem/tempos/motivo e limitações. Exportação/revisão tratam sinal diferente de texto crítico/sentimento. Não alterar candidatos existentes com novos resultados.

Nesta tarefa somente protocolo/inventário/checklist foram preparados. Referências de sentimentoA5foram aprovadas pelo usuário, mas isso não autoriza chamadascloud. Próximo dia13: preparar/avaliarA5sob autorização e implementarA2após protocolo aprovado; avaliaçãoA2depende das amostras e escuta. Nenhum código ou modelo novo, nenhum áudio processado porASR/descritor nesta preparação.

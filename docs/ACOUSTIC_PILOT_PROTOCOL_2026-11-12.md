# A2 — protocolo e preparação dos áudios — 12/11/2026

## Entrega desta tarefa

[Protocolo técnico](../specs/acoustic_pause_pilot_v1.md), [inventário](../specs/acoustic_pilot_inventory_v1.json) e [checklist de escuta](../specs/acoustic_pilot_listen_review_v1.csv) preparados. A regra futura buscará pausas frequentes, não diagnóstico de cansaço ou dificuldade respiratória. Foi registrada a aprovação explícita dos seis textos de sentimentoA5; não houve chamadaGPTOSS.

Encontrados três MP3na pasta elevenlabs_tests. A02ElevenLabs:10,45s de duração nos metadados,mono44100Hz. Os testesDarkPlanner têm12,02s e7,65s. Só metadados de contêiner/hashes foram lidos; não fizemos escuta, decodificação de waveform, transcrição ou medição de pausas. Modelo/voz confirmados pelo usuário: Eleven v4; Fernanda - Formal, Polite and Direct; ID7iqXtOF3wl3pomwXFY7G. Outras configurações e escuta permanecem pendentes.

## O que fazer para preparar a avaliação

1. Confirmar modelo e nome da voz usados no A02ElevenLabs e manter configurações iguais nos controles. IDtécnico,se disponível, ajuda; não é necessário regravar o original para registrar informação.
2. Gerar na MESMAplataforma/modelo/voz uma versão contínua e uma com pausas apenas de pontuação, usando textos abaixo. Não substituir áudios antigos. Salvar em data/interim/audio/elevenlabs_tests com nomes sugeridos. Se já existir versão equivalente, informar para aproveitá-la após conferência de metadados.
3. Ouvir os três e preencher checklist: palavras preservadas? Tags faladas? Expiração audível? Pausas perceptíveis? Ruído/defeitos? Descrever o que ouviu; não é necessário chamar alguém de cansado. Deixar dúvidas como incerto, não sim.
4. Quando as amostras estiverem prontas, faremos anotação temporal e revisão de referências antes da avaliação. Não precisa medir com precisão todas as pausas agora. O detector não foi executado e não deve ser usado para fabricar a própria referência.

### Controle contínuo — AP01

Salvar como `A02_elevenlabs_continuous_take01.mp3`:

```text
Durante o exercício, senti dor no ombro direito. A dor começou quando levantei o braço e continuou depois que parei.
```

### Controle de pontuação — AP03

Salvar como `A02_elevenlabs_punctuation_take01.mp3`:

```text
Durante o exercício... senti dor no ombro direito. A dor começou... quando levantei o braço... e continuou depois que parei.
```

AP02é o arquivo já disponível `A02_elevenlabs_exhales_take01.mp3`; não precisa gerar de novo. Estes textos não prometem pausas de duração fixa: anotaremos o áudio realmente produzido. Não é necessário usar tags novas ou contratar recurso/plano.

## O que conferir no protocolo

O perfil proposto reaproveita energia em janelas20ms; sinaliza se houver pelo menos3intervalos internos de baixa energia>=0,60s E se somarem>=15%do intervalo central. São parâmetros técnicos propostos, fixados antes da análise, não limites clínicos. Pausas no início/fim não contam; silêncio/baixo sinal não são resultado normal. O fato de haver uma expiração não garante sinal: respiração pode ter energia, e a gravação pode ter poucas pausas.

O controle de pontuação pode sinalizar se produzir o mesmo padrão; isso demonstra justamente por que não atribuímos causa médica automaticamente. Mostrar um padrão detectável é uma demonstração experimental parcial deA2, não prova de doença.

A aprovação desta tarefa permite seguir ao incremento seguinte quando solicitado; não autoriza inferênciacloud, geraçãoTTSautomática ou instalação. Nenhum código/UI/banco/áudio alterado. Verificações desta preparação: metadados/hash dos trêsMP3, links/UTF8/checklist e referênciasA5aprovadas pontuáveis no validador existente. Sem repetir suíteunitária, pois só documentos/dados de referência mudaram.


## Preenchimento do checklist — esclarecimento de 12/11/2026

O separador foi alterado pelo usuário para ponto e vírgula; manter esse formato (`delimiter=';'`) nas leituras futuras. Conferência estrutural:13colunas e3linhas, sem modificar oCSV. Cada linha corresponde a um áudioAP01/AP02/AP03.

| Pergunta do item3 | Coluna | Como responder |
|---|---|---|
| As palavras foram preservadas? | words_preserved_yes_no_uncertain | yes se o conteúdo verbal corresponde ao texto; pausas/expiração não são palavras extras. no se houver troca/omissão/adição; descreva emnotes |
| As tags foram faladas? | tags_spoken_yes_no_uncertain | yes se a voz pronunciar a instrução, como “exhales”, em vez de executá-la; no se isso não ocorrer. Nos controles semtags, no e observação “sem tags no prompt” |
| Há expiração audível? | exhalation_audible_yes_no_uncertain | yes para sopro/soltura de ar audível; não basta existir silêncio. Se não distinguir, uncertain |
| Há pausas perceptíveis/repetidas? | internal_pauses_frequent_yes_no_uncertain | yes para várias interrupções perceptíveis dentro da fala; uma pausa habitual entre duas frases não basta. Escuta humana, sem precisar medir tempos ou aplicar limiar do detector agora |
| Há ruído ou defeitos? | noise_or_artifacts | Texto livre: “Não observei”, “Estalo no início”, “Chiado leve”; não inferir que expiração intencional seja defeito |
| O que você ouviu de relevante? | notes | Complementos, palavras trocadas, localização aproximada, dúvida ou condição sem tags |

Padronização sugerida nas quatro colunas yes_no_uncertain: `yes`(sim),`no`(não),`uncertain`(incerto). “no” é observação negativa confirmada; vazio é não preenchido; uncertain é dúvida após ouvir. Não deduzir resposta pelo prompt ou pelo nome doarquivo.

Outras colunas: case_id/file identificam amostra e caminho; voice_name/voice_id/model registram geração; settings descreve configurações efetivamente usadas, como “Padrão, velocidade1.0” apenas se confirmado. Se não souber, escrever “Não registrado”, sem inventar. review_status permanece pending enquanto não ouvir/conferir; depois usar reviewed para indicar revisão DEESCUTA, não validação clínica nem revisão dos candidatos naUI. A anotação temporal e os rótulos finais do experimento ainda serão preparados/conferidos separadamente.

Não foi necessário alterar oCSV; preservar separador e preenchimentos do usuário. Textos em campos que contenham ponto e vírgula precisam permanecer entre aspas duplas; o editor de planilhas costuma cuidar disso ao salvar.


## Checklist e configurações recebidos — 12/11/2026

Usuário preencheu os três áudios como reviewed;CSVponto e vírgula preservado integralmente. Configurações na imagem: Fernanda,Elevenv4,idiomaautomático,MP344,1kHz128kbps; estabilidade emposiçãointermediária,similaridade tendendoalta,intensidadeclonagem próximamínimo. Não há números dos sliders visíveis; não inventarpercentuais. Efeitosáudio recolhidos,sem ajuste verificável. A imagem é evidência fornecida, não leitura de uma conta autenticada.

| Caso | Palavras preservadas | Tags pronunciadas | Expiração audível | Pausas frequentes | Ruído/defeitos |
|---|---|---|---|---|---|
| AP01 | yes | no | no | no | no |
| AP02 | yes | no | yes | no | no |
| AP03 | yes | no | yes | yes | no |

Manter a referência de pausas derivada da escuta: AP01/AP02nãofrequentes,AP03frequentes. A atuaçãoexhalesnão foi rotulada positiva automaticamente; o controle de pontuação pode ter expiração/pausas mesmo sem tag. Isso confirma a necessidade de separar fenômeno acústico de causa médica, sem demonstrar acerto/falha do detector ainda inexistente. Não regravar para tornar o alvo positivo.

Inventário atualizado com5MP3(3pareadosElevenLabs,2exploratóriosDarkPlanner),metadados/hash e configurações. [Referências qualitativas de escuta](../specs/acoustic_pilot_listen_references_v1.json) preservam os rótulos fornecidos; anotação temporal permanece pendente, sem intervalos inventados. Não é necessário preencher o mesmo checklist novamente. Quando formos avaliar intervalos, precisaremos revisar sua localização temporal; isso não foi concluído apenas pelas respostas yes/no. Nenhuma escuta pelo agente,inferência ou extração de características nesta atualização.

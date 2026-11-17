# Roteiro consolidado de demonstração — MedAssistMultimodal

15/11/2026. Interface CustomTkinter aprovada pelo usuário. Versão para ensaio; a avaliação integrada, a gravação e a publicação ainda não foram executadas nesta tarefa. Este documento substitui o roteiro 0.1 como orientação vigente, preservando o histórico.

## História e mensagem da apresentação

Um profissional explora três capacidades da POC: observar um exercício de fisioterapia, interpretar um relato simulado em áudio/texto e conferir anomalias em dados estruturados. Depois localiza a evidência, registra uma revisão e exporta os resultados.

Fala de abertura: “O MedAssistMultimodal é uma prova de conceito acadêmica de apoio à revisão profissional. Vou apresentar vídeo, áudio e dados estruturados em exemplos independentes. O participante do dataset, os locutores e o paciente fictício não são a mesma pessoa. O sistema não diagnostica nem prescreve.”

PAT-001 identifica apenas o contexto sintético do aplicativo. Não usar a personagem do roteiro antigo para atribuir o vídeo e as vozes à mesma paciente. O percurso é multimodal por reunir capacidades e resultados com proveniência; não demonstra fusão clínica, correlação causal ou sincronização entre essas fontes.

## Preparação antes de gravar

- Usar a interface padrão CustomTkinter, maximizada, já aprovada. Deixar caminhos, UUIDs e detalhes técnicos recolhidos durante a narrativa; abri-los quando ajudarem a demonstrar evidência.
- Base de consulta de referência: `data/interim/audio/desktop_workspaces_v1/0779a007-3dba-443f-885f-5d79aa274ed4/audio.sqlite3`. Não editar essa base para encenar pendências. A preparação de uma cópia exclusiva com os resultados necessários e a escolha de um candidato ainda pendente fazem parte da próxima avaliação integrada. Não supor que Criar cópia de trabalho clona todo o histórico atual.
- Conferir áudio do computador, player, legibilidade e seleção de resultados. Não mostrar credenciais nem diretórios pessoais desnecessários.
- Separar execução nova de consulta histórica: entrada à esquerda define o próximo processamento; resultado selecionado à direita é uma execução salva. Dizer explicitamente qual está sendo mostrado.
- Preferir uma execução nova curta local e consultar os demais resultados já salvos. Selecionar qual execução será feita ao vivo depois de medir sua duração na avaliação integrada. Por enquanto, não prometer duração do processamento.
- GPT-OSS é opcional. Para uma nova chamada, confirmar explicitamente na UI o envio apenas da transcrição fictícia autorizada. Não enviar o áudio/vídeo, não executar chamadas extras para repetir tomadas. Consultar resultado salvo dispensa nova inferência, mas deve ser anunciado.
- Confirmar previamente se a permissão de cada mídia cobre sua exibição no vídeo publicado; autorização acadêmica de tecnologia não equivale automaticamente a direito de redistribuir mídia. Não incluir o dataset no Git. Se necessário, limitar a exposição às saídas e à evidência permitida.
- Anotar os UUIDs das execuções escolhidas no ensaio, sem usar posições como “primeira” ou “quarta” linha. Novas execuções podem ter outros IDs.

Comando de consulta, a partir da raiz e com o ambiente ativado:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m medassistmultimodal.desktop_multimodal --database data/interim/audio/desktop_workspaces_v1/0779a007-3dba-443f-885f-5d79aa274ed4/audio.sqlite3
```

## Sequência principal — 12 minutos, com margem até 15

Os tempos abaixo são orçamento narrativo, não duração medida de inferência. Há três minutos de margem; não preencher toda essa margem com processamento silencioso.

| Tempo | Cena | Ações na interface | Mensagem principal |
| --- | --- | --- | --- |
| 0:00–0:45 | Objetivo | Apresentar as quatro abas e a mensagem de fontes independentes. | POC de apoio à revisão, sem diagnóstico ou prescrição. |
| 0:45–1:15 | Contexto | Área de trabalho → conferir Base/PAT-001 → Consultar; recolher o painel. | SQLite preserva execuções e evidências. Histórico é consulta, não processamento. |
| 1:15–3:15 | Vídeo | Aba Vídeo → Consultar vídeos nesta base → selecionar D9-04 salvo → clicar numa linha da tabela de frames. Abrir brevemente Evidência técnica. | OpenCV lê frames; MediaPipe estima pose; regras experimentais calculam ângulos e sinalizam um desvio. |
| 3:15–5:45 | Áudio e texto | Selecionar entrada do corpus; ▶ para ouvir brevemente, ■ para parar. Mostrar transcrição e regras de contexto de uma execução correspondente; mostrar GPT-OSS identificado numa execução salva. | Whisper transcreve localmente; GPT-OSS oferece análise textual opcional. As regras determinam candidatos. |
| 5:45–7:00 | Vitais | Anomalias → consultar V02 salvo, ou executar esse cenário na cópia preparada se escolhido como execução ao vivo. Abrir Dados, critérios e evidência. | Uma sequência sintética ultrapassa o limiar com persistência; exibir valores, unidade e período. |
| 7:00–8:15 | Prescrições | Selecionar E02 divergente. Comparar rapidamente com E01 compatível e E03 indeterminada, sem abrir todos os detalhes. | O plano declarado é a expectativa; diferença não é recomendação terapêutica. Sem base comparável, o sistema se abstém. |
| 8:15–9:30 | Revisão humana | Revisar resultado → Revisão humana → selecionar candidato pendente preparado → ler evidência → preencher revisor/motivo → Registrar como revisado → confirmar. | Revisão auditada com autoria declarada, motivo e horário; eventos técnicos não são todos alertas. |
| 9:30–10:45 | Relatório | Revisão e relatório → Relatório e exportação → Carregar resultados → selecionar resultados das modalidades → Gerar prévia → Exportar TXT e JSON. | Fontes permanecem separadas; exportar não decide nem aprova itens pendentes. |
| 10:45–12:00 | Resultados e limites | Mostrar o resumo final; se necessário, usar um slide ou trecho do relatório. | Cobertura e qualidade limitadas; A2 médico e movimentação na internação não demonstrados. Trabalhos futuros explícitos. |

Em caso de espera longa, usar um resultado salvo e anunciar “esta execução foi processada anteriormente”. Cortes de edição devem ser identificados. Não apresentar erro, recusa de integridade ou indisponibilidade como sucesso. A recuperação funcional detalhada será conferida na avaliação integrada; não é necessário dramatizar todas as falhas no vídeo.

## Detalhamento das cenas

### Vídeo: mostrar capacidade e limite juntos

Selecionar D9-04, frames inclusivos 897–1056. Clicar no frame 897 ou em outra linha para mostrar a atualização da imagem, tempo relativo e ângulos. A imagem é RGB original; não dizer que contém landmarks desenhados. Pose e ângulos são resultados computados, consultáveis na evidência.

Fala: “Neste trecho conhecido, o detector experimental sinalizou flexão de cotovelo. Isso é um candidato para revisão, não um diagnóstico nem uma avaliação completa do exercício.”

Mostrar o limite imediatamente: dez trechos RGB conhecidos foram avaliados, quatro analisáveis, um verdadeiro positivo, um falso positivo, dois verdadeiros negativos e seis abstenções. O detector encontrou um dos três positivos de referência no total. Não chamar D9-04 de prova de desempenho geral. D9-02 é um falso positivo documentado; pode ser citado sem trocar de tela se o tempo estiver curto. Não substituir as métricas RGB pelas métricas dos NPY.

### Áudio: transcrição, contexto e LLM identificados

A02 é uma opção para ouvir e demonstrar o relato de dor; se sua transcrição trouxer “sente” em vez de “senti”, conservar e explicar a diferença. A03 possui um exemplo salvo com GPT-OSS para mostrar a análise opcional. Ao trocar de A02 para A03, anunciar a mudança de exemplo e conferir a mídia do resultado; escolher A03 do início ao fim também é aceitável para reduzir trocas.

Fala: “Whisper transforma o áudio em texto. As regras procuram termos e seu contexto. A análise opcional com GPT-OSS acrescenta interpretação textual identificada, mas não decide alertas.” Mostrar somente termos e sentimento realmente presentes no resultado selecionado. Não atribuir ao áudio A03 os resultados do conjunto contrastante de seis textos: são avaliações diferentes.

Se for executar áudio ao vivo, usar Processar áudio na cópia preparada; GPT-OSS começa desmarcado. Marcá-lo exige a confirmação da execução. Se a nuvem falhar, apresentar o estado real e as etapas concluídas; consultar o exemplo salvo identificado, sem mudar silenciosamente de modelo.

Piloto de pausas: reservar a explicação curta para o fechamento. AP03 teve discordância qualitativa e não produziu sinal global. Expiração sintetizada não comprova detecção de fadiga/doença. Se houver tempo, abrir Pausas de áudio e consultar AP03; essa cena é opcional, não condição para concluir o percurso principal.

### Anomalias: evidência concreta das regras

V02: FC de 120 bpm em cinco amostras consecutivas; perfil experimental com limite superior 110 bpm e persistência mínima de três amostras. Conferir os valores exibidos; são escolhas sintéticas de software, não limites clínicos validados. Não afirmar que a série ocorreu durante o vídeo nem decorreu da dor.

E02: antes 10 mg, esperado pelo plano 15 mg, observado 20 mg. Esperado não é sinônimo do valor anterior. O aplicativo aponta a divergência e sua origem. E01 demonstra compatibilidade e E03 demonstra resultado indeterminado. Não usar o antigo P06 como prova de mudança inesperada: seu diff histórico, sem expectativa, não demonstra sozinho esse requisito.

Fala: “Estas análises usam regras locais, sem LLM. A divergência exige conferência profissional; o sistema não recomenda corrigir a dose.” A movimentação durante internação é uma exigência independente ainda não demonstrada; o vídeo de fisioterapia não a substitui.

### Revisão: uma decisão demonstrativa, não esvaziar a lista

Usar um candidato de V02 ou E02 ainda pendente na cópia preparada. O mesmo revisor pode ser usado em diferentes itens; o motivo deve ser específico. Exemplo de revisor: `Revisor-demo`. Motivo para E02: “Conferi a divergência do cenário sintético E02: plano 15 mg e observado 20 mg; demonstração acadêmica, sem julgamento terapêutico.”

Depois de confirmar, conferir estado e histórico. Não resetar um item revisado para repetir a tomada e não revisar todos os resumos apenas para zerar pendências. Se todos os candidatos escolhidos já estiverem revisados, mostrar o histórico existente e anunciar essa condição; preparar outra execução na cópia antes de gravar a ação de revisão.

### Relatório: seleção verificável

Selecionar D9-04, o áudio realmente mostrado, V02 e E02 pelas identidades/conteúdo, não pelo número da linha. Gerar a prévia depois da revisão; alterações de seleção/contexto ou revisão invalidam a prévia e exigem nova geração. Exportar TXT/JSON e abrir um deles brevemente para mostrar origem e revisão, sem exibir caminhos privados.

Fala: “O relatório reúne resultados de origens independentes, preservando evidências e estados. Não é uma conclusão clínica unificada.” Se ocorrer “integridade não confirmada”, interromper a exportação e investigar na avaliação; não trocar aleatoriamente sessões até a mensagem desaparecer nem apresentar arquivo antigo como se fosse o novo.

## Referências operacionais para o ensaio

Estes sete IDs foram confirmados por consulta SQLite somente leitura em 15/11. Existência não é nova validação de conteúdo, integridade, revisão ou disponibilidade dos providers. A próxima avaliação integrada conferirá esses aspectos e os IDs da cópia de demonstração.

| Exemplo | Sessão na base de referência |
| --- | --- |
| D9-04 — vídeo positivo experimental | `4e08454a-67d1-58fd-b14b-9ae1cdcca8cf` |
| A03 — áudio com análise textual salva | `a236b3f2-14f5-4ab6-9a92-61107cfb23eb` |
| V02 — vitais | `db11026c-682d-5f28-8763-38576e82f705` |
| E01 — compatível | `187f9411-71e3-5ab1-a321-1c52317d855b` |
| E02 — divergente | `187b7c74-d929-5fb2-82fd-f1f103716fae` |
| E03 — indeterminada | `0db7fafc-fee0-5baa-ab59-1b59bec1b939` |
| AP03 — piloto de pausas | `d173dea7-0d98-5988-910b-8c8a7e260c3e` |

Área de trabalho e Histórico de sessões alternam entre painéis no tema atual; recolher o painel depois da seleção para ganhar espaço. Os rótulos dos seletores podem não mostrar o código do cenário: conferir o resultado e usar Histórico de sessões com o UUID quando necessário.

## Encerramento sugerido

“O protótipo demonstra processamento de vídeo e áudio, análise textual opcional, regras de anomalias, revisão humana e exportação rastreável. Os dados apresentados têm origens independentes. A análise de movimento tem cobertura e precisão limitadas; alterações vocais médicas e monitoramento de movimentação durante internação não foram demonstrados. A evolução exige mais exemplos independentes, referências adequadas e avaliação profissional. A decisão assistencial continua com o profissional.”

Tecnologias a citar durante as respectivas cenas: Python 3.12, OpenCV/MediaPipe, Whisper local, GPT-OSS via Ollama como opção textual, regras determinísticas, SQLite e CustomTkinter/ttk. Não apresentar tecnologias planejadas ou contingentes como executadas. Substituições autorizadas pela coordenação conforme registros do projeto.

## Como revisar esta entrega

1. Ler o percurso de 12 minutos e confirmar se a ordem comunica as capacidades com clareza.
2. Conferir as falas de origem independente, anomalias, revisão e limites.
3. Escolher preferência entre A03 contínuo ou A02 seguido de A03; o roteiro admite ambos sem misturar resultados.
4. Aprovar o roteiro ou apontar ajustes antes da avaliação integrada. Não é necessário executar modelos, revisar alertas ou gravar o vídeo para aprovar este documento.

Próxima tarefa, sob aprovação: avaliação integrada na interface final, preparação controlada dos casos de demonstração, medição de tempos e correção de bloqueios. Não houve nova inferência, revisão, exportação, backup, limpeza, congelamento ou revisão do relatório acadêmico nesta consolidação.

Fontes locais: [matriz de fechamento](REQUIREMENTS_CLOSEOUT_2026-11-13.md), [vídeo](ELBOW_RGB_UI_2026-11-12.md), áudio (referência do acervo local, não distribuída), anomalias (referência do acervo local, não distribuída), [revisão/exportação](UI_SIMPLIFICATION_REVIEW_2026-11-14.md), [aparência final](UI_CUSTOMTKINTER_INCREMENT_02_2026-11-15.md), roteiro histórico (referência do acervo local, não distribuída).


## Preparação autorizada em 15/11

Base enxuta com oito sessões disponível em `data/interim/audio/desktop_workspaces_v1/484768d2-58c9-467e-9816-2fa664fa24fc/audio.sqlite3`. Guia [Horários e base para ensaio](REHEARSAL_DATABASE_AND_TIMES_2026-11-15.md). A existência desta base não significa que tempos do ensaio e fluxo final já foram avaliados. Revisões anteriores foram preservadas.

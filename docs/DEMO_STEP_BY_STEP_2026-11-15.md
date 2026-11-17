# Demonstração — passo a passo com falas e notas

15/11/2026. Revisão da proposta enviada pelo usuário. Foco no uso do aplicativo; detalhes técnicos completos ficam no relatório. Referência operacional para ensaio; nenhuma nova execução de modelo ou gravação de revisão foi realizada nesta elaboração.

## Organização e ajustes da proposta

A divisão em abertura, demonstração e encerramento é adequada. Os orçamentos de 1min30 + 12min + 1min30 totalizam exatamente o limite de 15 minutos, sem margem. Mantenha-os como máximos; procure finalizar a montagem em até 14min30, incluindo transições, título e créditos. Os tempos abaixo são planejamento, ainda não medidos.

Correções de conteúdo incorporadas:

- Foram selecionados dez trechos conhecidos de uma gravação para avaliação; não são dez partes que cobrem integralmente o vídeo.
- No cotovelo, a regra sinaliza ângulos **abaixo de 150°**, não uma exigência de que o movimento correto fique abaixo de 150°. A decisão é do trecho, com critério de proporção e cobertura; o frame isolado é evidência.
- Vitais e prescrições são **cenários sintéticos deste projeto**, independentes do dataset de vídeo. Não apresentar outro projeto ou um dataset anterior como fonte desses exemplos.
- V02 contém FC de **120 bpm**, acima do **limite superior experimental de 110 bpm**. Não é limite mínimo nem recomendação clínica.
- Revisado é uma conferência declarada e auditada. Nesta demonstração acadêmica, não anunciar que ocorreu validação clínica.
- Voz disponível publicamente no catálogo não significa domínio público ou ausência de direitos. Dizer apenas que foram usadas vozes sintéticas da ElevenLabs com as permissões registradas.
- Usar o ID completo de A03 confirmado na base de ensaio; não depender do prefixo 0cdc8664 nem da posição na tabela.

## Preparação — fora da gravação

**Nota 1:** Abrir a base enxuta descrita em [Horários e base de ensaio](REHEARSAL_DATABASE_AND_TIMES_2026-11-15.md):

`data/interim/audio/desktop_workspaces_v1/484768d2-58c9-467e-9816-2fa664fa24fc/audio.sqlite3`

Área de trabalho → conferir Base e PAT-001 → Consultar → recolher o painel. Histórico de sessões é um painel alternativo; abrir um recolhe o outro.

**Nota 2:** A base tem A03 salvo, mas não A02. O processamento de A02 será uma execução nova, feita no ensaio/gravação pelo usuário. A entrada A02 continua disponível no catálogo do projeto. Anotar o ID do resultado produzido para a seleção final do relatório. Se preferir tudo pré-processado, processar A02 antes e avisar que será consultada uma execução salva.

**Nota 3:** D9-04 já está revisado na base preparada. Mostrar seu histórico; não tentar registrar nova decisão nem resetar seu estado. A demonstração de uma revisão nova ficará no candidato de E02, pendente quando conferido para este roteiro. Revalidar esse estado antes da tomada; se já foi revisado nos testes, mostrar o histórico ou preparar nova execução sintética, preservando a anterior.

**Nota 4:** Testar som e tempo do Whisper antes da gravação. Durante espera longa, fazer corte identificado, dizendo “após concluir o processamento”. Não mostrar um resultado antigo como se tivesse acabado de ser produzido. Consultar A03 salvo não envia nova transcrição à nuvem.

## Parte 1 — objetivo e tecnologias — até 1min30

**Fala 1:** “O MedAssistMultimodal é uma prova de conceito acadêmica para apoiar o profissional na consulta de informações e na revisão de ocorrências.”

**Fala 2:** “Vou demonstrar análise de vídeo, áudio e texto, detecção de anomalias e geração de relatórios. Os exemplos têm origens independentes: o participante do vídeo, os locutores e o paciente fictício não são a mesma pessoa.”

**Fala 3:** “Foram usados OpenCV e MediaPipe no vídeo, Whisper para transcrição e GPT-OSS via Ollama como análise textual opcional. Vitais e prescrições usam regras locais. A interface usa CustomTkinter e os registros são armazenados em SQLite.”

**Fala 4:** “O sistema não diagnostica nem prescreve. Seus resultados experimentais precisam de interpretação profissional.”

**Nota:** Mostrar a janela e as quatro abas, sem abrir código ou apresentar uma lista extensa de dependências.

## Parte 2 — demonstração — até 12 minutos

### 2.1 Avaliação do vídeo — aproximadamente 2min30

**Fala 1:** “Foi selecionada uma gravação de exercício de fisioterapia do dataset REHAB26. Ela foi processada com OpenCV e MediaPipe.”

**Fala 2:** “Dez trechos conhecidos foram selecionados para avaliar o comportamento do detector. Vou consultar o trecho D9-04, já processado.”

**Nota 1:** Aba Vídeo → Consultar vídeos nesta base → selecionar a sessão `4e08454a-67d1-58fd-b14b-9ae1cdcca8cf`. Conferir frames 897–1056. Rolar a tabela e clicar na linha do frame **1015**; não há botão Ver frame.

**Fala 3:** “Neste trecho, o aplicativo sinalizou flexão de cotovelo fora da referência experimental. O frame 1015 apresenta o menor ângulo calculado, aproximadamente 135,8 graus, abaixo da referência de 150 graus.”

**Nota 2:** Abrir Evidência técnica para mostrar o resultado e o frame de evidência; recolher em seguida. Se mencionar o critério completo: cobertura mínima de 80% e pelo menos 20% dos frames válidos abaixo de 150°. Neste trecho: 160 frames válidos e 42 abaixo da referência, ou 26,25%. Não explicar esses detalhes se prejudicarem o ritmo; o relatório os documenta.

**Fala 4:** “Esse é um sinal experimental do trecho, não uma conclusão clínica sobre o exercício inteiro. A avaliação também encontrou falso positivo e trechos sem dados suficientes para análise.”

**Nota 3:** Clicar Revisar resultado. Em Revisão e relatório → Revisão humana, selecionar o item **Candidato — Flexão de cotovelo**, em vez de um resumo ou ciclo. Mostrar evidência e histórico já existente.

**Fala 5:** “Aqui é possível consultar a evidência e o registro de revisão. Revisado significa uma conferência registrada, não certificação clínica. Vou demonstrar uma nova decisão no exemplo de prescrição.”

**Nota 4:** Deixar a exportação para o bloco final, evitando repetir esse percurso em todas as modalidades.

### 2.2 Avaliação do áudio/texto — aproximadamente 3min30

**Fala 1:** “Foram preparados relatos fictícios de atendimentos de fisioterapia. Parte das gravações usa minha voz e parte usa vozes sintéticas da ElevenLabs, com as permissões registradas.”

**Fala 2:** “Vou mostrar A02 com transcrição local e A03 com análise textual opcional já salva.”

**Nota 1:** Aba Áudio e texto → entrada Relato e transcrição → Áudio de demonstração A02 → ▶ para ouvir → ■ para parar. Ouvir não gera a transcrição. A entrada selecionada à esquerda pode ser diferente do resultado histórico à direita; conferir o arquivo no resultado.

**Fala 3:** “Este é o áudio A02. Ao clicar em Processar áudio, o Whisper realiza a transcrição localmente.”

**Nota 2:** Manter Incluir análise textual com GPT-OSS desmarcado → Processar áudio → confirmar a operação na cópia de trabalho → aguardar. Se necessário, usar corte de espera identificado. Ao concluir, conferir o novo resultado e sua mídia A02. Anotar o ID; não escolher apenas o último item pela posição.

**Fala 4:** “A transcrição aparece no resultado, junto aos termos e contextos encontrados pelas regras. Uma menção à dor pode gerar um candidato para conferência, mas não equivale a diagnóstico.”

**Nota 3:** Mostrar o texto efetivamente gerado. Se aparecer “sente” em vez de “senti”, dizer que houve essa diferença de transcrição, sem editar a evidência. A02 pode produzir duas menções e um resumo; não chamar isso de três problemas clínicos. A revisão segue o mesmo fluxo já mostrado; não precisa abrir e gravar todos os itens.

**Fala 5:** “Agora vou consultar A03, uma execução anterior com GPT-OSS. Não estou fazendo uma nova chamada ao modelo nesta consulta.”

**Nota 4:** Histórico de sessões → selecionar `a236b3f2-14f5-4ab6-9a92-61107cfb23eb` → aba Áudio e texto. Conferir mídia `A03_S01_take01.m4a`. Para ouvir A03, selecionar também A03 na entrada antes de usar ▶; trocar a entrada não muda automaticamente a execução histórica.

**Fala 6:** “Neste exemplo, o relato nega dor e falta de ar. O resultado textual identifica termos e sentimento, mas a presença das palavras não significa que os sintomas estejam afirmados.”

**Nota 5:** Mostrar a seção de análise textual opcional do resultado salvo e as regras de contexto. Na evidência consultada, o sentimento é neutro e os trechos incluem as negações. Não afirmar que a LLM sozinha decide a classificação dos candidatos.

**Fala 7:** “Essa análise textual é opcional e identificada. Uma execução nova exige confirmação do envio da transcrição fictícia; a LLM não decide alertas.”

**Fala 8:** “Descritores e pausas de áudio são recursos técnicos experimentais. Não demonstramos detecção de doença ou cansaço pela voz.”

### 2.3 Detecção de anomalias — aproximadamente 4 minutos

**Fala 1:** “Para esta capacidade foram usados cenários sintéticos de vitais e prescrições, separados do vídeo e dos áudios. Vou apresentar uma ocorrência de frequência cardíaca e uma divergência em relação a um plano de prescrição fictício.”

**Fala 2:** “Essas análises usam regras locais, sem LLM. Os limites são referências experimentais e não orientações de tratamento.”

**Nota 1:** Aba Anomalias → Dados a analisar: Vitais → Cenário V02 → Analisar cenário → confirmar. Conferir que o resultado apresentado é o da execução recém-criada. Se necessário, localizá-lo pelo ID e horário de registro. A ação gera um registro novo; consultar um resultado salvo é outra operação.

**Fala 3:** “V02 apresenta cinco amostras consecutivas de frequência cardíaca de 120 batimentos por minuto, acima do limite superior experimental de 110. A regra exige persistência de pelo menos três amostras para gerar a ocorrência.”

**Nota 2:** Mostrar a ocorrência, valores e período. Se necessário, abrir Dados, critérios e evidência e recolher depois.

**Fala 4:** “O horário do registro mostra quando a execução foi gravada no aplicativo. O horário nominal continua sendo o do cenário sintético. Essa série não foi medida durante o exercício do vídeo.”

**Nota 3:** Trocar para Prescrições e consultar E02 salvo: `187b7c74-d929-5fb2-82fd-f1f103716fae`. Pode usar Histórico de sessões para localizar esse ID e voltar a Anomalias. Não é necessário clicar Analisar cenário para consultar E02 já salvo.

**Fala 5:** “Em E02, a dose anterior era 10 miligramas, o plano sintético previa 15 e a versão observada registra 20. O aplicativo aponta a divergência entre esperado e observado. Ele não recomenda corrigir a dose nem avalia a segurança terapêutica.”

**Nota 4:** Mostrar esperado/observado. Se houver tempo, citar E01 compatível e E03 indeterminada, sem executar novos cenários. Não confundir esperado pelo plano com valor da versão anterior.

**Fala 6:** “Vou registrar uma conferência demonstrativa deste candidato.”

**Nota 5:** Revisar resultado → Revisão humana → selecionar **Candidato — Divergência do plano de prescrição**. Conferir estado pendente. Identificação do revisor: `Revisor-demo`. Motivo: `Conferi o cenário sintético E02: plano 15 mg e observado 20 mg; demonstração acadêmica, sem julgamento terapêutico.` → Registrar como revisado → confirmar → conferir o histórico. Não escolher uma simples alteração ou resumo no lugar do candidato. Se o item já estiver revisado, mostrar o histórico ou preparar outra execução antes de gravar; não resetar.

**Fala 7:** “A decisão fica registrada com autoria declarada, motivo e horário, mantendo a evidência original. Os outros itens podem continuar pendentes. O monitoramento de movimentação durante internação não foi demonstrado nesta POC.”

### 2.4 Relatórios — aproximadamente 2 minutos

**Fala 1:** “Agora vou reunir os resultados apresentados em um relatório, preservando as origens e os estados de revisão.”

**Nota 1:** Revisão e relatório → Relatório e exportação → Carregar resultados. Selecionar pelas linhas o vídeo D9-04, o novo A02 ou A03 efetivamente mostrado, o novo V02 e E02. Se quiser incluir os dois áudios, selecionar ambos. Identificar por conteúdo/ID/horário, não pelos números variáveis das linhas. Não incluir sessões que não foram apresentadas apenas para preencher o relatório.

**Nota 2:** Gerar prévia → mostrar separação dos dados sintéticos e do vídeo de dataset → Exportar TXT e JSON → escolher destino → conferir mensagem e abrir o TXT gerado. Após mudar seleção ou registrar revisão, gerar a prévia novamente.

**Fala 2:** “O relatório reúne resultados de origens independentes, preservando evidências e estados. Não é uma conclusão clínica unificada. Exportar também não aprova automaticamente os itens pendentes.”

**Nota 3:** Se surgir recusa de integridade ou prévia desatualizada, não apresentar um arquivo antigo como novo. Registrar o problema e corrigir no ensaio; essas falhas não devem ser ocultadas por troca aleatória de sessões.

## Parte 3 — encerramento — até 1min30

**Fala 1:** “A demonstração percorreu consulta e processamento por modalidade, identificação de ocorrências, revisão auditada e exportação.”

**Fala 2:** “O vídeo usa um conjunto pequeno de trechos, com falsos positivos e abstenções. Alterações vocais indicativas de condições médicas e movimentação durante internação não foram demonstradas. Esses limites estão documentados no relatório.”

**Fala 3:** “Como trabalhos futuros, ficam a ampliação da avaliação com exemplos independentes, maior robustez das regras de movimento e avaliação acústica e clínica adequada.”

**Fala 4:** “O objetivo é organizar resultados e evidências para apoiar o profissional. A interpretação e qualquer decisão assistencial permanecem com ele.”

**Nota:** Não é necessário ler todas as métricas em voz alta. Uma síntese dos limites é suficiente, com os resultados completos no relatório. Conferir a duração do vídeo montado, incluindo títulos e créditos, antes da publicação.

## Conferência desta elaboração

Critério e frame de vídeo conferidos na evidência salva de D9-04: frame 1015, mínimo 135,789°, 42/160 frames abaixo de 150°, status experimental deviation. Conferidos A03/mídia/negações/análise salva, estado já revisado dos três eventos de D9-04 e estado pendente dos eventos de E02 no momento da consulta. Esses estados podem mudar após novos testes.

Fonte dos limites de vitais: `specs/synthetic_vitals_v1.md`; regra de cotovelo: `src/medassistmultimodal/domain/elbow_deviation.py`. Guias operacionais: [roteiro consolidado](DEMO_SCRIPT_2026-11-15.md), [base enxuta](REHEARSAL_DATABASE_AND_TIMES_2026-11-15.md), [fechamento dos requisitos](REQUIREMENTS_CLOSEOUT_2026-11-13.md).

Documento para revisão/ensaio. Não declara concluída a avaliação integrada final nem inicia chamadas cloud, revisão clínica, exclusões ou congelamento.

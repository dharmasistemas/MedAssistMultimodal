# Dia 13 — A2: avaliação local e integração na UI — 13/11/2026

**Atualização:** usuário realizou a conferência visual e entregou as três listas temporais vazias revisadas. A pendência temporal foi encerrada; veja o [fechamento temporal](ACOUSTIC_TEMPORAL_EVALUATION_2026-11-13.md). O restante preserva as instruções e o estado anterior à entrega da referência.

## Resultado e limites

Três MP3 reais decodificados localmente com hashes e perfil fixado antes da execução. Nenhuma execução Whisper/ASR, GPT-OSS/LLM, geração de voz, instalação ou mudança de limiar. Nova cópia de trabalho, sem alterar a base anterior ou suas revisões. A análise é de energia/pausas, não de condição médica ou identificação de respiração.

| Caso | Referência de escuta fornecida | Resultado da regra | Pausas internas >=0,60s | Comparação por arquivo | Sessão na nova base |
|---|---|---|---|---|---|
| AP01 | Sem pausas frequentes | Sem sinal | 0 | Concorda | c19f5fa4-d547-5d3b-9e61-b899ee3144f4 |
| AP02 | Sem pausas frequentes | Sem sinal | 1 | Concorda | 322c64d9-f8a2-5e8d-8cfd-87f932adbb94 |
| AP03 | Pausas frequentes | Sem sinal | 0 | Diverge | d173dea7-0d98-5988-910b-8c8a7e260c3e |

**Concordância qualitativa: 2/3.** Contra os rótulos de escuta:2negativos concordantes e1positivo não sinalizado(AP03); nenhum sinal positivo ou candidato real de pausa foi gerado. Isso não demonstra detector satisfatório de fala entrecortada; a hipótese técnica é mais restrita que a percepção de pausas frequentes anotada no checklist.

Os descritores calculados (não anotações humanas) foram:

- AP01: um intervalo de baixa energia de0,56s; nenhum >=0,60s; duração total7,706s.
- AP02: um intervalo interno de0,82s, fração central8,02%; outros intervalos são menores que0,60s ou borda. Não atinge3pausas e15%; duração total10,449s.
- AP03: quatro intervalos de0,54s,0,56s,0,30s e0,40s; nenhum >=0,60s; duração total9,874s. É a explicação numérica do resultado do perfil, sem atribuir causa médica.

Não foram alterados os parâmetros para obrigarAP03ouAP02a sinalizar, nem regravados/selecionados novos takes. Todos os resultados foram preservados. Expiração audível permanece observação humana emAP02/AP03, não acerto de detector de respiração.

## O que já está integrado

Modo **Pausas de áudio**, casos AP01–AP03, no controle de cenário existente. Processa somente esses arquivos previamente inventariados e autorizados; validar paciente fictício, hashes e origem antes de decodificar. Horário da sessão é de processamento, separado do tempo relativo no áudio; não inventar data clínica/captura.

AbaÁudio apresenta resultado/motivo, contagem, fração, critérios e intervalos. Pausas longas usadas na regra e todos os intervalos de baixa energia são mostrados separadamente, para não sugerir que zero pausas longas significa áudio sem interrupções. Mostra ASR/LLMnãoexecutados e origemTTS. Cada execução tem resumo e, somente no sinal positivo, candidato pendente; os três áudios reais geraram apenas resumo (nenhum candidato). O percurso positivo/revisão foi testado com ondas sintéticas, rotuladasmock.

Novo envelope acoustic-pause-evidence-v1, fonte simulated-acoustic-pauses-v1, identidade fictícia e confiança nula. Leitor reconstrói o resultado dos descritores e valida bytes/hash/identidade/grupo completo de eventos. Não decodifica mídia ao consultar histórico. Retentativa reutiliza bytes/IDs, sem nova decodificação. Revisão auditada e exportação TXT/JSON usam os serviços existentes. Documentos antigos não recebem campos extras ou novas classificações retroativamente.

## Como conferir sem reprocessar

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m medassistmultimodal.desktop_multimodal --database data/interim/audio/desktop_workspaces_v1/0779a007-3dba-443f-885f-5d79aa274ed4/audio.sqlite3
```

1. Clique Consultar paraPAT-001 e escolha uma das sessões da tabela. A abaÁudio mostrará o resultado acústico, sem exigir o botão de processamentoWhisper.
2. ConfiraAP03: zero pausas longas, mas quatro intervalos de baixa energia visíveis. Essa distinção explica por que o perfil não coincide com sua percepção de pausas frequentes.
3. ConfiraAP02: uma pausa longa e fração8,02%; abaixo dos critérios. Não é ausência de expiração, cansaço ou doença.
4. Alertas e revisão mostra somente o resumo nas três sessões reais. Não inventar candidato para a demo; os candidatos de dor/vitais/prescrições/vídeo continuam separados e disponíveis nas sessões anteriores herdadas.
5. Em Síntese e exportação, escolha as três sessões, gere síntese e exporteTXT/JSON. Nenhuma análise é repetida nessa consulta/exportação.
6. Opcionalmente, para NOVA análise local, selecione Pausas de áudio e AP01/AP02/AP03 no controle de cenários e Registrar cenário. A confirmação informa processamento acústico semASR/LLM; uma nova sessão é criada. Não é necessário repetir os três resultados entregues.

Relatório já exportado: `data/interim/multimodal/reports_v1/017afc96-5761-41d9-851f-d7ebfd6d464d/summary.txt` e `summary.json`.

## Referência temporal: pendência humana explícita

Usuário informou que não possui tempos anotados. Portanto **precisão/recall de intervalos não foram calculados** e estão nulos nos resultados. O checklist existente foi preservado e já permite a comparação por arquivo acima. Não preencher intervalos humanos a partir da saída do detector.

Página para anotar ouvindo os arquivos originais: temporal_review.html (referência do acervo local, não distribuída). Abra em um navegador local, sem servidor. Não contém tempos/previsões do detector: apenas players de áudio e ferramentas de marcação.

1. Para cadaAP, ouça e pause. Marque início/fim de pausa interna de pelo menos0,60s pelos botões ou digitando segundos. Se não identificar nenhuma, mantenha lista vazia.
2. Confira a lista e marque Ouvi e conferi esta lista. Não marcar expiração com som automaticamente como silêncio. Os limites do anotador são do protocolo; pausas mais curtas não entram nessa métrica específica.
3. Salvar referência temporal emJSON baixa acoustic_temporal_reference_v1.json. Salve em `data/interim/audio/acoustic_pilot_v1/` e informe o caminho; depois conferiremos/importaremos as anotações antes de pontuar os intervalos. A página não envia dados à rede e não altera arquivos originais.

Não precisa preencher o checklist novamente. Se a escuta dos intervalos longos não acompanhar o rótulo qualitativo anterior, registrar a distinção entre duas tarefas, sem reescrever rótulos para melhorar métricas. Sem tempos humanos revisados, esta parte da tarefa permanece pendente e não pode ser declarada concluída.

## Verificação e arquivos

Runner já executado uma vez: scripts/evaluate_acoustic_pilot.py --execute. Diretório exclusivo data/interim/audio/acoustic_pilot_v1 contémconfigantesdaexecução,workspace,AP01–AP03,summary,ui_checks e página de referência. Não apagar/repetir resultados para ajustar desempenho. Fonte/código fixado e trêsMP3preservados porhashantes/depois. Saída prévia preservada;0ASR,0LLM,0revisõesautomáticas;3sessões/3eventosnovos pendentes.

Regressão completa: **1.156 testes e341subcasos em46,37s**, incluindo11casos novos. Testes direcionados38aprovados em16,18s; após esclarecimento final da apresentação,38aprovados em18,79s. Testes usam decoders injetados/ondas fictícias em diretórios temporários. ConferênciaTkreal consultou3sessões e exportou pelaUI; conferência posterior confirmou os intervalos curtos deAP03sem nova decodificação ou escrita na base. Inspeção visual humana pendente.

Scanner528arquivos/zeroachados/zerovaloreslocaiscomparados, sintaxe/UTF8/diff--check conferidos. Três relatórios históricos tiveram texto reconstruído idêntico. Principais arquivos: application/register_acoustics.py,infrastructure/desktop_acoustics.py,structured_workspace.py,desktop_vitals.py,desktop_multimodal.py,desktop_text.py,desktop_summary.py,tests/unit/test_acoustic_ui.py e wrapperTkcompartilhado. Nenhum esquemaSQLnovo ou pacote instalado.

**EstadoA2:** integração técnica e comparação qualitativa entregues; resultadoAP03discordante e métrica temporal aguardando referência. Não declarar atendimento médico integral. Próximo trabalho: sua conferência daUI/anotação temporal; depois completar pontuação possível e consolidar matriz antes da simplificação global, com aprovação por tarefa doAGENTS. Não iniciar nova otimização automaticamente.

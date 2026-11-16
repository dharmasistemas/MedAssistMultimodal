# Interface desktop v1 — contrato de apresentação

07/11/2026 — dia 16, tarefa 3. **Especificação; interface ainda não implementada.**
Tecnologia prevista: Tkinter/ttk. Complementa [handoff de áudio](audio_ui_handoff.md)
e [processamento de áudio](audio_processing_v1.md), preservando seus contratos.

## Objetivo e limites do primeiro incremento

Permitir consultar sessões já persistidas, entender a origem de cada resultado,
abrir evidência verificada e acompanhar a revisão de eventos. A primeira tela
implementada na tarefa 4 será de consulta. Processamento e revisão gravável ficam
para a tarefa 5, com aprovação própria. Abrir o aplicativo não inicia modelos,
downloads, chamadas cloud, criação de pacientes ou alteração de eventos.

A avaliação do prompt v2 obteve dez análises válidas, com uma ocorrência omitida.
Isso não equivale à adoção definitiva do provider nem à sua integração automática
no ProcessAudio. A interface deve apresentar exatamente o provider registrado.

## Organização visual

Janela com título **MedAssistMultimodal**, redimensionável, tamanho inicial sugerido
1100 × 750 e mínimo 900 × 600. Usar painéis ajustáveis, barras de rolagem, foco por
teclado e rótulos textuais além de cores. Não depender apenas de verde/vermelho.

Cabeçalho: nome, indicação “POC acadêmica — apoio à revisão profissional” e contexto
da base aberta. Seleção de base é explícita; não localizar e alterar automaticamente
bancos de experimentos. Bases históricas congeladas permanecem em consulta.
Uma base de trabalho gravável futura deve ser identificada como tal.

| Área | Apresentação inicial | Capacidade posterior, fora da tarefa 4 |
|---|---|---|
| Histórico | Sessões, sujeito, data, origem; selecionar uma sessão | Filtros adicionais e outras modalidades |
| Áudio | Detalhes verificados, etapas, texto, menções e evidência | Novo processamento e acompanhamento do worker |
| Vídeo | “Integração com a interface pendente” e limites conhecidos | Resultados experimentais com frame e visibilidade |
| Anomalias | “Integração com a interface pendente” | Vitais/prescrições com unidade, origem e regra |
| Alertas e revisão | Eventos de áudio como itens para revisão, sem severidade inventada | Gravar decisão explícita e consultar auditoria |

As abas futuras não têm botões que aparentem executar funções indisponíveis.
A lista de eventos de áudio não deve ser chamada de motor de alertas multimodais.
Uma sessão sem eventos de áudio pode existir: informar isso sem declarar a sessão
vazia, excluir eventos de outras modalidades ou atribuir falha ao ASR.

### Disposição da aba Áudio

1. Identificação: sessão, execução, paciente fictício/sujeito, horário da sessão e
   do processamento, com fuso indicado. Guardar UTC; apresentar horário local com
   deslocamento explícito, sem substituir o valor original na evidência.
2. Resumo: estado global e integridade, origem humana/TTS, referência de mídia e
   permissão declarada. PAT-001 é paciente fictício, não identidade do locutor.
3. Etapas: ASR, descritores acústicos, regras e LLM, cada uma com estado e fonte.
4. Transcrição original somente leitura; segmentos quando disponíveis.
5. Menções das regras: termo, trecho literal, contexto, classificação e revisão.
6. Análise LLM separada: sentimento textual e citações, termos e citações, modelo,
   contrato/prompt quando registrados, fonte local/cloud/mock e estado.
7. Detalhe do item: referência, hash, confidence e histórico de revisão disponíveis.

Descritores acústicos mostram unidade e caráter técnico experimental; sentimento
é avaliação linguística explícita, não emoção vocal ou estado clínico. Ausência
de campo/medida é “Não disponível”, sem fabricar zero, versão ou confiança. Uma
transcrição contendo instruções é exibida como texto, nunca executada.

## Modelo de estado proposto

Estado da tela não substitui os estados persistidos. Futuro modelo independente
dos widgets, tipado e testável sem Tkinter, com os seguintes componentes:

| Componente | Campos/valores previstos | Regra |
|---|---|---|
| Contexto | base_ref, access_mode=read_only/workspace, selected_session_id, selected_event_id | Nenhuma seleção implícita para revisão |
| Consulta | idle / loading / ready / empty / error | empty só após consulta bem-sucedida sem registros |
| Integridade | not_checked / verified / missing / invalid / unsupported | verified apenas após leitura e conferência do serviço |
| Execução da tela | idle / validating / processing / saving / finished / error | Estados transitórios, não gravados como estado clínico |
| Resultado global | completed / degraded / failed / rejected / unavailable | unavailable é ausência de resultado consultável na UI |
| Etapas | estados originais de input/asr/acoustics/rules/llm | Não converter disabled, unknown ou falha em sucesso vazio |
| Revisão | pending_review / reviewed / dismissed | Metadado atual do SQLite, independente do resultado global |
| Operação de revisão | idle / editing / submitting / saved / conflict / error | Só existe na implementação futura da tarefa 5 |
| Erro de apresentação | código, mensagem curta, contexto seguro | Não exibir traceback, credenciais ou caminhos pessoais |
| Concorrência | request_id e seleção associada | Resposta antiga não substitui a seleção atual |

Estados de integridade e erros de apresentação são classificações propostas para
a UI, não novos enums persistidos. Se o serviço atual não distinguir um erro,
mostrar erro genérico seguro; não deduzir a causa por texto arbitrário de exceção.

| Situação | Texto de apresentação | Revisão gravável futura |
|---|---|---|
| Nenhuma sessão selecionada | “Selecione uma sessão” | Bloqueada |
| Consulta em andamento | “Carregando histórico/evidência…” | Bloqueada |
| Base sem sessões | “Nenhuma sessão encontrada nesta base” | Bloqueada |
| Falha ao consultar | “Não foi possível consultar o histórico” | Bloqueada; não mostrar lista vazia como sucesso |
| Evidência ausente/alterada | “Evidência indisponível ou integridade não confirmada” | Bloqueada; metadados identificados como não verificados |
| ASR indisponível/sem fala | “Processamento falhou — consulte a etapa ASR” | Somente revisão técnica de evento persistido, com escopo explícito |
| LLM desativada | “Análise textual opcional desativada” | Regras válidas continuam disponíveis |
| LLM timeout/inválida | “Resultado parcial — análise textual indisponível/inválida” | Regras válidas continuam disponíveis |
| LLM unknown válida | “Análise concluída — sentimento indeterminado” | Sem interpretar como falha ou neutral |
| Regras sem menções | “Nenhuma menção configurada encontrada” | Não afirmar ausência de problema de saúde |
| Evento revisado/descartado | Estado atual e histórico | Sem reabertura ou nova primeira revisão |

Ao mudar de seleção, limpar o detalhe anterior ou marcá-lo explicitamente como
carregando. Em falha, nunca manter o resultado anterior sob o cabeçalho da nova
sessão. Repetir consulta é permitido; não repetir inferência para recuperar detalhe.

## Mapeamento dos dados existentes

| Dado | Fonte e responsabilidade futura |
|---|---|
| Lista de sessões | Serviço sobre `SQLiteSessionRepository.list_for_patient` com paciente explícito; widgets sem SQL |
| Sessão/eventos/estado atual | `query_audio_session`, que confere hash, ponteiro, identidade e grupo completo |
| Transcrição, etapas e proveniência | Documento de evidência conferido por serviço de apresentação usando `AudioEvidenceStore`; não ler diretamente dos widgets |
| Histórico de revisão | `event_review_history`; consulta não executa revisão |
| Nova execução | `ProcessAudio` → preparação → `register_audio_sqlite`, somente no incremento de worker |
| Revisão explícita | `EventReviewRequest` → `review_event_sqlite`, somente na tarefa 5 |

**Lacuna identificada:** `query_audio_session` retorna sessão e eventos com itens
de evidência, não o documento completo com transcrição e todos os estados. A tarefa
4 precisará de um serviço/adaptador de leitura que componha esse detalhe após
conferência, sem mudar as fontes congeladas. Não preencher dados ausentes usando
um arquivo arbitrário do corpus ou uma referência manual. Aceitar apenas schema
de evidência suportado; inconsistência impede apresentar o conteúdo como verificado.

O histórico inicial usa filtro explícito por paciente fictício (ex.: PAT-001),
sem presumir que o repositório já tenha listagem geral. Consulta por participante
de dataset, se adicionada depois, usa o método e identidade próprios.

O estado de revisão atual vem do SQLite; o pending_review no JSON original
permanece histórico imutável. Filtrar por áudio sem ocultar a existência de outras
modalidades. Metadados de provider ausentes não são inferidos do nome do arquivo.
Uma etapa mock deixa isso visível mesmo se outras etapas forem reais. TTS é origem
do áudio e não significa que o Whisper executado seja mock.

## Revisão humana — interação futura

Mostrar o item e evidência verificada antes de habilitar a decisão. Rótulos:
“Registrar como revisado” e “Descartar item”, sem “aprovar diagnóstico”. Exigir
evento selecionado, estado pending_review, base de trabalho gravável, referência
opaca do revisor e motivo. Revisor é declarado, sem autenticação implementada.

Antes de enviar, mostrar evento, decisão, motivo e revisor em confirmação explícita.
Gerar review_id e horário UTC para a solicitação; retentativa da mesma operação
reutiliza ambos. Duplo clique não cria duas operações. Em conflito, recarregar
estado e histórico; não mudar expected_status ou reabrir silenciosamente.

Sucesso só aparece após confirmação da transação; então consultar novamente evento
e histórico. Falha de atualização da tela após commit não autoriza nova decisão:
reconciliar pela consulta/recibo. A revisão não altera a evidência nem certifica
validade clínica. Simulação técnica só é permitida em evento mock, sempre visível.
Não revisar automaticamente todos os itens ao abrir sessão, selecionar aba ou fechar.

## Processamento e concorrência — interação futura

O thread principal cria/atualiza widgets. Trabalho lento usa worker com mensagens
de dados e fila; atualização da tela pelo agendamento Tkinter. Conexão SQLite é
aberta e usada no thread proprietário; não compartilhar conexão criada na UI com
worker. A inicialização nativa/OpenMP precede imports de bibliotecas acústicas.

Uma execução por vez inicialmente, com feedback por etapa sem percentual fictício.
Nenhum botão de cancelamento promete parar uma chamada remota já iniciada. Ao
fechar durante trabalho, explicar a operação em curso e aguardar/concluir de forma
controlada; não declarar rollback ou cancelamento sem confirmação. Política concreta
de encerramento será testada na tarefa 5. Nova inferência usa novo run_id; retentativa
de persistência reutiliza bytes preparados, sem reexecutar modelos.

LLM começa desativada. Adoção cloud e integração do adapter ainda requerem decisão
explícita: autorização do experimento não habilita envio pela UI. Quando integrado,
o fluxo deverá informar que o texto fictício sai da máquina e registrar escolha e
escopo por execução; não enviar áudio, voz, vídeo ou dados pessoais. Falha não
aciona outro modelo ou retry automático.

## Critérios verificáveis para os próximos incrementos

| Cenário de aceite | Resultado esperado | Incremento |
|---|---|---|
| Abrir aplicativo sem configuração de LLM | Janela/histórico disponíveis, zero inferência | 4 |
| Base inexistente ou inacessível | Erro explícito, sem criar base vazia no lugar | 4 |
| Base válida vazia / sessão sem áudio | Mensagens diferentes e verdadeiras | 4 |
| Sessão com evidência íntegra | Texto, etapas e proveniência correspondem aos registros | 4 |
| Evidência ausente/alterada ou schema desconhecido | Conteúdo não apresentado como verificado, revisão bloqueada | 4 |
| ASR real com timeout LLM simulado | Mostrar proveniência por etapa e degraded | 4 |
| Consulta de evento já revisado | Estado SQLite atual e histórico, JSON original intacto | 4 |
| Carregamento responde fora de ordem | Não substituir a seleção atual por detalhe antigo | 4/5 conforme uso de worker |
| Revisar sem motivo/revisor, sem evidência ou em base histórica | Não enviar operação | 5 |
| Revisão válida, replay e conflito | Auditoria atômica; sem duplicação ou reset | 5 |
| Processamento lento, falha e fechamento | UI responsiva; estado final verdadeiro | 5 |
| Abrir tela e selecionar sessão | Nenhuma revisão ou chamada cloud implícita | 4 e 5 |

Testar apresentação/estados com fixtures offline e serviços injetados; inspeção
manual da janela real na tarefa 4, incluindo acentos e rolagem. As fixtures devem
explicitar mock. Não modificar bancos/evidências congelados para testar gravação.
Não criar novos testes de código nesta tarefa documental.

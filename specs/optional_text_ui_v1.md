# GPT-OSS opcional no áudio — contrato UI v1

10/11/2026. Usuário aprovou GPT-OSS para a próxima implementação.

A entrada desktop_multimodal passa a TextAudioApp, extensão de VideoApp. Na aba
Áudio há checkbox desmarcado por padrão. A escolha aplica-se à próxima execução
de áudio pelo comando existente Processar localmente. Marcar não faz requisição.
Ao processar com a opção marcada, uma confirmação informa modelo, envio apenas de
transcrição fictícia e nova execução. Cancelar não executa ASR nem nuvem.

Whisper permanece local; recursos acústicos e regras ficam independentes. Envia-se
somente o campo text ao proxy Ollama127.0.0.1:11434 para gpt-oss:120b-cloud. Não há
áudio, imagem, identidade de paciente ou evidência JSON no payload da LLM.
Somente o corpus simulado conhecido pode ser processado por esse controle.
Sem troca de plano, compra de créditos, fallback ou retry automático de provider.

Reutilizar contrato text-analysis-v3 e prompt text-v3-prompt-v2 avaliado. Um bridge
explícito encaminha o prompt revisado a partir do processador congelado. O prompt
original, suas experiências e os validators não são modificados. Parâmetros:
temperatura0,thinklow,1536tokensmáximos,timeout de socket60s. Timeout não comprova
cancelamento imediato do processamento remoto; UI não promete cancelamento.

A evidência audio-processing-evidence-v1 mantém seus campos e acrescenta em llm:
prompt_revision,prompt_sha256,runtime,final_content (somente sucesso),response_metadata.
Não registra thinking/raciocínio interno. Resposta inválida/erro mantém código
sanitizado e nenhum resultado falso. Validação v3 exige JSON/citações literais;
resposta válida pode ser semanticamente incompleta. Não é validação clínica.
A leitura TextHistoryReader reconfere o resultado contra a resposta final, input,
fonte/modelo e perfil conhecido. Evidência antiga continua com seu contrato anterior.

Processamento completo/parcial, transcrição e regras usam persistência/auditoria
existentes, sem schema SQLite novo. Não são criados alertas por termos da LLM.
Eventos continuam resumo e menções das regras. Retentativa de gravação reutiliza
bytes/IDs e não repete ASR/LLM. Não sobrescrever sessões anteriores/revisões.
A ativação posterior não modifica sessões existentes; exige nova execução nesta
versão. Análise avulsa de uma transcrição histórica sem novo ASR não foi implementada.

UI mostra fonte/modelo, sentimento textual e citações, termos e limites; etapa LLM
mostra sucesso/timeout/indisponível/inválida/capacidade. Desativada não equivale a
falha nem a neutral/unknown. Estado da opção da próxima execução não substitui o
estado persistido da sessão consultada. Operações seguem no worker; checkbox fica
desabilitado durante trabalho. Histórico, vídeo, revisão e cópias são preservados.

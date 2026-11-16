# Síntese factual e exportação de sessões — v1

10/11/2026. Nova aba Síntese e exportação, preservando as quatro abas existentes.
Selecionar explicitamente1–20sessões da base consultada; nenhuma seleção padrão.
Catálogo combina histórico do paciente fictício selecionado e dataset independente.
Não permite incluir sessão de outro paciente por UUID, fonte desconhecida ou detalhe
não verificado. Sessões sem modalidade opcional não têm dado inventado.

SummaryService usa TextHistoryReader e contratos existentes, sem modelo/ASR/pose,
sem escrita no SQLite ou revisão automática. Verifica PRAGMA data_version e hash
do banco antes/depois da coleta para recusar snapshot misto por escrita concorrente.
Regras/candidatos e resultados LLM são apresentados separadamente. Preserva
negação, falha/ausência, unidades/valores e origem/mock. Não classifica gravidade,
não diagnostica, não recomenda conduta e não infere relações entre modalidades.

ReportSnapshot imutável contém JSON selected-session-summary-v1, report_id,
generated_atUTC, referência da base, seleção, grupos patient_sessions/dataset_sessions,
contagens de eventos/revisão, detalhes com evidências/hashes/histórico e texto.
Grupos separados não significam associação do participante a PAT-001. Tempos
registrados e relativos mantêm seu significado original; sem alinhamento novo.

Texto legível determinístico preserva dados principais, etapas/LLM/citações,
intervalos vitais/cobertura, mudanças de prescrição, ciclos/qualidade RGB e revisão.
Eventos técnicos não equivalem à quantidade de alertas clínicos. JSON contém os
detalhes completos e referências locais, sem pixels/bytes de áudio ou vídeo.

Exportar reconfere as sessões selecionadas e compara com o snapshot. Evidência
inválida ou mudanças nos resultados/revisões exigem nova síntese. Mudança de
seleção/base/paciente invalida a apresentação atual. Contexto/resposta atrasados
não substituem a seleção atual. Operações em worker, widgets no thread Tk.

Saída exclusiva: data/interim/multimodal/reports_v1/<report_id>/summary.txt,
summary.json,manifest.json. TXT UTF-8; JSON canônico. Manifesto de hashes é escrito
por último como marcador de conclusão. Reenvio idêntico retorna os mesmos arquivos;
pasta incompleta/divergente é preservada e recusada, sem sobrescrita/limpeza.
Falha durante escrita pode deixar pasta parcial: recuperação explícita, sem afirmar
conclusão ou uma transação atômica de múltiplos arquivos. A síntese em memória não
altera evidência antiga; arquivos exportados são snapshots e não atualizam sozinhos.

Exportação não é pacote portátil ou autorização de divulgação de mídia. Síntese
atual não substitui o relatório técnico acadêmico nem prova correlação clínica.

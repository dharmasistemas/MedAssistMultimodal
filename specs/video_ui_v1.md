# Vídeo RGB na interface — contrato v1

08/11/2026. Incremento autorizado após o fechamento do dia 17.

- Entrada estável: `python -m medassistmultimodal.desktop_multimodal`.
- Aba Vídeo em VideoApp, extensão da UI anterior. Histórico próprio de sessões
  `dataset_participant`, dataset rehab26-v1, referência opaca do manifesto day07.
  patient_id é nulo; não aparece no histórico PAT-001.
- Vídeo/modelo locais já adquiridos, com hash antes/depois da extração. Sem URL,
  câmera, download, novo participante ou nova ligação a identidade sintética.
- Intervalo inclusivo configurável dentro dos frames 0–449. Padrão 20–99, 80 frames.
  Limite explícito para demonstração curta; não é análise da gravação inteira.
- OpenCV decodifica sequencialmente; MediaPipe Tasks Full/CPU extrai pose world 3D.
  Medidas e filtros/segmentação reutilizam o domínio existente, sem mudar limiares.
  Ausência de pose é ausência, nunca uma pose de zeros.
- `rgb-video-evidence-v1`: run, sujeito, âncora UTC de processamento, fonte/modelo e
  hashes, versões, intervalo/fps, frames angulares originais, timeline utilizável,
  perfis, ciclos candidatos e intervalos compactos de qualidade. Não guarda pixels.
- Qualidade técnica não é classificação clínica. Ciclos detectados não são total
  verdadeiro. Tempo de frame é relativo; horário de captura desconhecido.
- Evidência exclusiva em workspace; sessão/eventos/auditoria pelo UOW existente.
  source rehab26-rgb-video-v1, processor rgb-temporal-v1, confiança nula. Todos os
  eventos novos começam pendentes; resumo, ciclo e qualidade são itens distintos.
- IDs determinísticos no mesmo run/hash/item. Retentativa em memória reutiliza
  evidência/IDs, sem extrator. Arquivo órfão após falha preservado; não há transação
  única entre arquivo e banco. Cache perde-se ao encerrar o aplicativo.
- Leitura reconfere hash, identidade, grupo completo e metadados dos eventos.
  Recalcula somente filtros/segmentação determinísticos dos ângulos persistidos
  para validar consistência, sem decodificar vídeo, extrair pose ou modificar dados.
- Revisão usa EventReviewRequest e auditoria existentes. Autoria declarada, motivo,
  confirmação, replay e conflito. Sem reabertura/reset. Não é autenticação ou aceite
  clínico. Simulação técnica só em mocks explícitos.
- Visualização: frame RGB original solicitado por índice, reduzido para caber no
  painel; sem overlay e sem player contínuo nesta versão. Não afirmar que imagem e
  ângulos NPY estão sincronizados. A análise atual usa RGB novo, não NPY.
- Exportação individual pelo botão Exportar sessão, reconferida, JSON exclusivo
  na cópia de trabalho. Export de paciente do dia 17 continua só para paciente;
  sessão de dataset é exportada separadamente.
- Trabalho de arquivos/SQLite/providers em worker; somente widgets/PhotoImage no
  thread Tk. Fechamento aguarda operação ativa, sem alegar cancelamento.

Sem avaliação de precisão/recall RGB neste incremento. Desempenho NPY anterior não
é validação do RGB. Cobertura deste trecho não generaliza para a gravação inteira.

## Atualização de interação — 09/11/2026

A imagem ocupa a coluna esquerda inteira; informações e tabela ficam à direita.
Seleção de linha da tabela solicita o frame RGB correspondente (inclusive por
teclado); não há campo ou botão de visualização separados. Captura original de
preview até720×960, redução proporcional na UI. Seleção mais recente prevalece
quando há leitura ativa; troca de contexto invalida retornos. Frames no cabeçalho
continuam definindo uma nova análise. Evidência/persistência não mudam.

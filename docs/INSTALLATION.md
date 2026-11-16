# Instalação e uso

Python 3.12 com Tk/Tcl. A reprodução principal considera Windows. O player não foi verificado em outros sistemas.

| Arquivo | Uso |
| --- | --- |
| requirements.txt | Interface e demonstração sintética |
| requirements-ui.txt | CustomTkinter |
| requirements-dev.txt | Suíte offline, UI e NumPy para fixtures NPY |
| requirements-video.txt | MediaPipe, OpenCV, Pillow e NumPy |
| requirements-audio.txt | faster-whisper, CTranslate2 e PyAV |

Use ambiente próprio. Não instale dependências dentro de ambientes de outros projetos. Os arquivos registram o ambiente do desenvolvimento; recursos opcionais podem ser instalados separadamente.

## Demonstração sem arquivos privados

1. Instale requirements.txt e configure PYTHONPATH para src, conforme README.
2. Execute `python -B -m medassistmultimodal.prepare_demo` ou `scripts/start_app.ps1 -Demo`.
3. A base contém vitais V01/V02 e prescrições E01/E02/E03. Regras reais executam sobre dados artificiais, sem observações clínicas.
4. Consulte PAT-001 na UI. Em Anomalias, escolha um resultado ou execute um cenário. Registro real e horário nominal são distintos.
5. Em Revisão e relatório, selecione candidato, informe autoria/motivo e confirme. Resumos e qualidade não são automaticamente alertas.
6. Carregue resultados, selecione sessões, gere prévia e exporte TXT/JSON. Mudar seleção/revisão invalida a prévia.

Cada preparação cria uma base nova. Arquivos sintéticos idênticos podem ser reutilizados; divergentes são rejeitados sem sobrescrita. Não há LLM, ASR, vídeo ou downloads nessa inicialização.

## Bases e recursos locais

Use --database ou Selecionar base. Bases de trabalho guardam workspace.json ao lado do SQLite. Evidências externas são obrigatórias para integridade; copiar só o banco não produz pacote autônomo. Criar cópia de trabalho duplica todo o banco, sem filtrar/excluir sessões. Descartar com motivo é decisão auditada, não exclusão.

Whisper requer modelo e manifesto locais. GPT-OSS requer conta Ollama configurada e confirmação por execução de transcrição fictícia conhecida; começa desativado. Vídeo requer mídia, modelo Pose Landmarker e manifestos. Ausência desses ativos impede o fluxo correspondente e não deve ser apresentada como sucesso.

Consulte [dados e modelos](DATA_AND_MODELS.md). Testes de software não substituem avaliação clínica.

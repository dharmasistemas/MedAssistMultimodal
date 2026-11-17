# Dia 14/11 — incremento 5: Revisão e relatório

## Situação

A tentativa anterior ficou incompleta: correção de empilhamento não aplicada porque a revisão automática de permissão falhou por limite de uso, sem julgamento de risco. Ao retomar, confirmou-se que os dados eram carregados, mas tabelas reaproveitadas ficavam encobertas pelos contêineres novos. Corrigido com ordem de empilhamento explícita, incluindo detalhes técnicos de áudio/anomalias. Capturas finais da janela conferidas com listas visíveis. Não considerar o recibo visual anterior como prova de layout final correto.

## Entrega

Revisão humana: seletor de resultados por modalidade/origem/horário; lista de itens sem UUID como rótulo principal; distinção entre candidato, contexto, alteração, qualidade, ciclo técnico e resumo. Não contar todos os eventos como alertas. Item selecionado mostra estado, evidência resumida e histórico com autoria, horário e motivo. Evidência completa e retentativa ficam recolhidas.

Revisor e motivo são obrigatórios; o motivo é limpo ao trocar de item, e o revisor pode continuar sendo o mesmo. Confirmação antes de gravar; itens revisados/descartados ficam bloqueados para nova decisão. A retentativa reenvia a mesma solicitação, sem duplicar auditoria. Após gravar, a tela relê o estado e permanece na revisão. Nenhuma aprovação de guia/UI registra revisão clínica automaticamente.

Relatório e exportação: clique nas linhas para incluir/retirar até20resultados, gerar prévia resumida e exportar TXT/JSON completos. Dataset separado do paciente fictício; sem relação causal/sincronização clínica demonstradas. Conteúdo integral exportável disponível sob demanda. A prévia tem apresentação diferente do TXT completo, mas parte dos mesmos dados verificados; exportações e contratos históricos permanecem preservados. Nenhuma LLM gera essa prévia.

Seleção, contexto ou início de revisão invalidam a prévia. Exportar ainda reconfere integridade/estado contra a base e recusa snapshot obsoleto. Os resultados podem ser exportados com itens pendentes, explicitamente identificados; exportar não aprova alertas.

## Como conferir

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m medassistmultimodal.desktop_multimodal --database data/interim/audio/desktop_workspaces_v1/0779a007-3dba-443f-885f-5d79aa274ed4/audio.sqlite3
```

1. Em Revisão e relatório → Revisão humana, clicar Carregar resultados desta base. Se a base não estiver consultada, usar Área de trabalho → Consultar antes.
2. Para localizar precisamente E02, usar Histórico de sessões e selecionar UUID `187b7c74-d929-5fb2-82fd-f1f103716fae`; depois clicar Revisar resultado na aba de origem. Também é possível selecionar pelo catálogo da nova aba, conferindo o conteúdo esperado/observado. A lista deve mostrar resumo, alteração e candidato, em vez de tratá-los como três alertas clínicos. Selecionar o candidato: esperado15/observado20 e estado/histórico à direita. Os rótulos do seletor usam modalidade/identidade/horário; números variam conforme o catálogo.
3. Conferir motivo/revisor e abrir Evidência completa. Não é necessário registrar nova decisão para aprovar a aparência. Se desejar exercer o fluxo, fazê-lo conscientemente na cópia de trabalho e confirmar a decisão específica; o histórico deve ser relido após gravar.
4. Usar Revisar resultado nas abas de origem: deve abrir diretamente Revisão humana, mesmo que a última seção visitada fosse Relatório e exportação.
5. Em Relatório e exportação, Carregar resultados; clicar em uma ou mais linhas, Gerar prévia, conferir fontes separadas. Para repetir a checagem realizada, selecionar as sessões abaixo.
6. Abrir Conteúdo integral para exportação; Exportar TXT e JSON continua criando os arquivos completos e manifesto na área de relatórios, sem mudar o banco. Alterar seleção exige gerar nova prévia.

Casos de conferência readonly usados:

| Modalidade | UUID |
|---|---|
| Áudio A03/GPT-OSS já salvo | a236b3f2-14f5-4ab6-9a92-61107cfb23eb |
| Vídeo D9-04 | 4e08454a-67d1-58fd-b14b-9ae1cdcca8cf |
| Vitais V02 | db11026c-682d-5f28-8763-38576e82f705 |
| Prescrição E02 | 187b7c74-d929-5fb2-82fd-f1f103716fae |

Não escolher por posição fixa na lista. O catálogo contém37resultados na base conferida; a prévia usada reúne3sessões do paciente fictício e1de dataset independente. Nenhuma nova revisão, exportação na base do projeto ou inferência foi realizada na inspeção automática; exportação e decisões foram testadas apenas em bases temporárias. HashSQLite antes/depois idêntico.

## Verificação e arquivos

45testes direcionados aprovados em28,88s: categorização, fontes independentes, navegação normal/vídeo, seleção por clique, campos/recusa/confirmação, revisão/replay sem duplicar, bloqueio de reabertura, autoria/motivo no histórico, snapshot desatualizado e contexto/tamanho de janela. O teste de empilhamento complementa a inspeção visual; estar mapeado não garante que um widget esteja descoberto.

Implementação em desktop_review_layout.py e integração em desktop_simplified.py. Botões Revisar resultado das outras três apresentações agora abrem diretamente a seção humana. Correção de empilhamento nos detalhes de áudio/anomalias. Casos de uso, providers, regras, schemas e formato de exportação preservados.

Recibo visual final: reports/UI_REVIEW_FINAL_READONLY_CHECK_2026-11-14.json. Recibo técnico de fechamento: reports/UI_SIMPLIFICATION_REVIEW_2026-11-14.json. Não houve backup/limpeza nem nova revisão do relatório técnico acadêmico. Próximo passo é conferência humana desta aba; ajustes eventualmente identificados pertencem à mesma tarefa.


## Fechamento técnico da retomada

Correção de visibilidade aplicada e capturas finais conferidas. Testes direcionados:45aprovados28,88s. Uma rodada da regressão ficou sem terminar; foi interrompido apenas o processo confirmado desta tarefa. Reforçada a coleta dos ciclos de widgets/variáveis na thread proprietária do runtimeTk, antes de testes posteriores com workers. Não se atribui causa definitiva à demora somente por isso.

**Regressão final:1.198testes e341subcasos aprovados em69,35s, sem skips.** Comando: `python -B -m pytest tests/unit -q -rs -p no:cacheprovider --tb=short -o faulthandler_timeout=45`. SintaxePython/UTF-8 e `git diff --check` conferidos. Tarefa tecnicamente concluída; inspeção/aprovação visual do usuário ainda pendente.

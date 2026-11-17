# Horários e base enxuta para ensaio — 15/11/2026

## Entrega

Vitais e Prescrições agora exibem o instante real do primeiro registro da sessão, obtido de `audit_records.created_at` da operação `register_multimodal_session`. A auditoria já guardava esse instante UTC; a interface o converte para o fuso local. Não foi necessário migrar schema ou modificar evidências/IDs. Horário de processamento e instante de persistência são conceitos distintos: este ajuste apresenta **Registro no aplicativo**, não inventa um horário de início/fim do processamento.

A aba Anomalias mostra separadamente Registro no aplicativo e Horário nominal do cenário. Histórico, seletores de resultados e revisão/exportação usam a data de registro para essas modalidades; o horário nominal continua preservado nos documentos. A exportação também inclui o registro separado quando disponível. Ausência da auditoria é indicada no resumo; o histórico usa o horário nominal como alternativa, sem atribuir um horário atual inventado. Repetir uma gravação pendente conserva o primeiro registro. Executar um cenário novamente cria uma sessão nova com outra data de registro.

Áudio/vídeo mantêm sua semântica anterior. O relógio depende da data/hora configurada no Windows. Nenhuma gravação histórica foi alterada para parecer recente.

## Base pronta

`data/interim/audio/desktop_workspaces_v1/484768d2-58c9-467e-9816-2fa664fa24fc/audio.sqlite3`

Contém **8 sessões, 19 eventos e 12 registros de auditoria**:

| Exemplo | Uso |
| --- | --- |
| D9-04 | Vídeo com verdadeiro positivo experimental |
| D9-02 | Vídeo com falso positivo documentado |
| A03 | Áudio/transcrição e análise textual GPT-OSS já salva |
| V02 | Ocorrência sintética de vitais |
| E01 | Prescrição compatível |
| E02 | Prescrição divergente |
| E03 | Prescrição indeterminada |
| AP03 | Piloto acústico com limite/discordância documentado |

Os IDs e estados de revisão foram preservados. Nenhuma revisão foi apagada ou resetada. Para gravar uma revisão nova, primeiro conferir se o candidato está pendente; se não estiver, executar o cenário na base de ensaio e revisar o novo candidato. Isso acrescenta uma execução de demonstração, sem alterar as amostras copiadas. Não foram criadas execuções novas por inferência nesta preparação.

A base original permanece disponível e seu hash foi conferido antes/depois da preparação. Nenhuma exclusão, limpeza, backup na área privada ou alteração de mídia foi realizada.

**Dependências:** a base enxuta aponta para os JSON de evidência originais dentro do projeto. Esses arquivos, as mídias e os assets necessários continuam obrigatórios. É uma seleção de histórico para uso no mesmo projeto, não um pacote autônomo transportável. O manifesto ao lado da nova base lista referências/hashes; a limpeza futura deverá preservar ou empacotar essas dependências sem quebrar a integridade. `Criar cópia de trabalho` continua copiando integralmente a base selecionada; não foi adicionado botão de filtragem ou exclusão.

## Como abrir e conferir

No terminal do ambiente medassistmultimodal, a partir da raiz:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m medassistmultimodal.desktop_multimodal --database data/interim/audio/desktop_workspaces_v1/484768d2-58c9-467e-9816-2fa664fa24fc/audio.sqlite3
```

1. Área de trabalho → conferir Base e PAT-001 → Consultar. O histórico do paciente mostra seis sessões; os dois vídeos são independentes do paciente e aparecem no catálogo de vídeo e no relatório, totalizando oito resultados.
2. Em Anomalias, consultar V02 e E02: conferir Registro no aplicativo e Horário nominal do cenário. As amostras antigas terão o instante em que foram registradas originalmente, e não a data desta cópia.
3. Se desejar testar um registro novo, selecionar V02 → Analisar cenário → confirmar. O novo resultado deve apresentar o horário atual de registro, preservando o horário nominal. Essa ação aumenta o total da base de ensaio.
4. Em Revisão e relatório, carregar os resultados, selecionar as amostras desejadas e gerar prévia. Oito detalhes e a síntese conjunta foram validados sem nova inferência. Conferir o estado dos candidatos antes de ensaiar a decisão humana.
5. Para repetir o ensaio sem acumular testes nesta base preparada, Criar cópia de trabalho gera outra cópia integral do estado selecionado; registrar seu caminho. Não apagar evidências ou registros manualmente.

## Verificação

- Regressão: 1.204 testes e 341 subcasos aprovados em 65,40 s.
- Cinco casos novos: horário real vs nominal em vitais/prescrições/plano; retentativa sem alterar instante; seleção de base com auditoria preservada e origem inalterada; ausência de auditoria sem inventar data; recusas de seleção vazia/ausente.
- Leitura verificada das oito sessões e igualdade dos detalhes com a origem; foreign_keys/integrity_check aprovados; síntese das oito sessões construída sem chamada de modelo.
- Recibo: `reports/REHEARSAL_DATABASE_2026-11-15.json`. Inventário e classificação em MIGRATION_AUDIT.

Arquivos principais: `infrastructure/desktop_vitals.py` (consulta da auditoria), `desktop_anomaly_layout.py`, `desktop_multimodal.py`, `desktop_audio_layout.py`, `desktop_review_layout.py`, `desktop_summary.py`, `infrastructure/desktop_summary.py` (apresentação/catálogo) e `infrastructure/rehearsal.py` (preparação seletiva). Todos sob `src/medassistmultimodal/`.

Esta entrega não executa a avaliação integrada final nem congela a versão. Aguardar conferência do usuário antes da próxima tarefa.

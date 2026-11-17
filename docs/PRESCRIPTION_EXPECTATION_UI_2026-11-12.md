# Prescrições: alterações esperadas e divergentes — 12/11/2026

## Entrega

N2 agora possui comparação explícita entre um plano sintético de mudanças esperadas e a versão observada. Não recomenda tratamento nem decide se a dose é clinicamente correta. A exigência “inesperada” é demonstrada como divergência de contexto declarado; sem esse contexto, classificar como indeterminado, não presumir erro.

Plano separado contém paciente/conjunto fictícios, hash canônico da versão-base, versão-alvo, instante nominal da declaração e lista completa dos itens esperados. O plano é contexto de entrada, não rótulo de saída do teste. Nos cenários, foi construído da versão-base e de uma alteração pretendida literal, independentemente de mudanças posteriores feitas no documento observado. Os rótulos de avaliação ficam separados.

Classificações:

- **Compatível:** estado observado coincide exatamente com o plano aplicável.
- **Divergente:** presença/ausência ou valor de campo não coincide; registrar esperado e observado, com candidato pendente de revisão.
- **Indeterminado:** plano ausente, de outra identidade/base/versão, declarado fora do intervalo nominal ou comparação que exige interpretar unidade diferente. Não converter mg/g nem recomendar valores. Entrada malformada é rejeitada, não indeterminada silenciosamente.

A comparação preserva números como texto decimal exato normalizado;15.000 equivale a15, mas não arredonda uma diferença decimal pequena. A política de unidades é conservadora: mesmo equivalência aparente, como1000mg/1g, não é inferida. Se houver unidade incompatível, a avaliação toda fica indeterminada, sem declarar coincidência parcial como segura.

O envelope prescription-evidence-v2 preserva snapshots/diff existentes e acrescenta plano, resultado e candidatos. Apenas divergent gera expectation_candidates/0. Sem SQL novo. Fonte/identidade são sintéticas; is_mock=False indica execução real de regra sobre dados fictícios, nunca paciente real. Todos os novos eventos começam pendentes, confiança nula.

## Como conferir pela UI sem criar novas sessões

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m medassistmultimodal.desktop_multimodal --database data/interim/audio/desktop_workspaces_v1/a62bde4e-4ce6-4c3d-bfaf-e867474659ce/audio.sqlite3
```

1. Consulte PAT-001 nessa base. Ela é uma nova cópia da base do vídeo, preservando áudio/vitais/prescrições/vídeos já existentes.
2. Selecione a sessão E02 identificada abaixo. Em Anomalias → Prescrições, deve aparecer **Divergência do plano sintético**, com dose esperada15 e observada20. São valores fictícios, não instrução terapêutica.
3. Veja os snapshots antes/depois e, em Alertas e revisão, diferencie **Divergência do plano sintético** do resumo e da mudança de campo. A consulta não exige registrar revisão. Se revisar, use autoria declarada e motivo específico.
4. Consulte E01: compatível com o plano, sem candidato de divergência. Depois E03, E04 ou E05: indeterminado, com motivo explícito, sem candidato. Não interpretar como ausência de problema.
5. Em Síntese e exportação, carregue sessões dessa base, selecione as desejadas, gere e exporte TXT/JSON. Há também relatório já exportado na localização abaixo.
6. Opcionalmente, para nova execução sintética, escolha Prescrições no controle Cenário sintético e um código E01–E08. Registrar cenário cria outra sessão na cópia de trabalho; não é necessário repetir para conferir esta entrega. P01–P17 continuam disponíveis como comparações antigas, sem avaliação de expectativa.

| Caso | Resultado | Motivo técnico | Sessão |
|---|---|---|---|
| E01 | compatible | matches_declared_plan | 187f9411-71e3-5ab1-a321-1c52317d855b |
| E02 | divergent | differs_from_declared_plan | 187b7c74-d929-5fb2-82fd-f1f103716fae |
| E03 | indeterminate | plan_missing | 0db7fafc-fee0-5baa-ab59-1b59bec1b939 |
| E04 | indeterminate | unit_change_not_interpreted | e13f0462-bca6-5b39-a13d-599b3cb8abcf |
| E05 | indeterminate | base_mismatch | 75b047e3-0b5d-523e-943b-8961c5ff2bb5 |
| E06 | divergent | differs_from_declared_plan | 3f7d737c-9d7c-5a23-89bc-b44a3c5244ae |
| E07 | divergent | differs_from_declared_plan | 15d857e2-82ac-5141-a2be-1d8579bbe39f |
| E08 | divergent | differs_from_declared_plan | fea0e7d0-13dd-57f2-8dca-0f1cb02cf366 |

E01:plano15mg/observado15mg; E02:plano15mg/observado20mg; E03:sem plano; E04:unidade alterada; E05:hash-base obsoleto; E06:inclusão planejada ausente; E07:inclusão não planejada; E08:remoção não planejada.

## Verificação realizada

Oito cenários conhecidos, oito resultados coincidentes com referências:1compatível,4divergentes,3indeterminados.21eventos novos,4candidatos, todos pendentes. Retentativas idempotentes não duplicaram eventos. Não é validação clínica, teste independente ou estimativa de desempenho em prescrições reais.

O runner `scripts/verify_prescription_expectation.py --execute` já foi executado e usa diretório exclusivo `data/interim/prescriptions/expectation_ui_v1/`: config/hashes/referências anteriores à execução, workspace novo, entrada hash por caso, detalhes das oito sessões, ui_checks e summary final. Não apagar saídas para repetir. A declaração temporal do plano é parte do cenário fictício, não alegação de documento clínico emitido previamente no mundo real.

Conferência funcional Tk consultou as oito sessões e os candidatos; fonte, código dependente e banco preservados nas consultas/exportação. Nenhuma revisão automática ou nova inferência. Inspeção visual humana ainda pendente. Relatório completo:

`data/interim/multimodal/reports_v1/a84b0593-af7f-45ac-bb9e-0370cbe6ee58/summary.txt` e `summary.json`.

### Testes

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m pytest tests/unit -q -rs -p no:cacheprovider --tb=short
```

Regressão: **1013testes e341subcasos em41,41s**,36casos novos, sem skips. Direcionados:82aprovados em15,43s. Cobertos plano ausente/errado/obsoleto/futuro/malformado, duplicatas, valores decimais, mudança de unidade, inclusão/remoção, evidência adulterada/grupo incompleto, revisão/replay/conflito, legado e widgets. Primeira execução direcionada teve8falhas de fixture por usar leitor de exportação incompleto; corrigido para o leitor padrão da aplicação e reexecutado com sucesso. Nenhum dado real afetado.

Scanner485arquivos/zeroachados/zerovaloreslocaiscomparados. Os textos de três relatórios históricos foram reconstruídos e permaneceram idênticos, sem alterar snapshots ou recibos antigos. Código antigo de comparação e schemasv1 preservados.

## Arquivos e próximo passo

Contrato: [prescription_expectation_v1](../specs/prescription_expectation_v1.md). Novos módulos de domínio, apresentação, preparação e fixtures; adaptados leitor, workspace, UI e síntese. Testes e runner próprios; sem pacote, modelo, nuvem ou mídia nova.

Próxima tarefa proposta: preparar seis textos fictícios contrastantes e referências de sentimento para A5. Primeiro revisão das referências, depois chamadas GPT-OSS sob aprovação específica. A2 continua aguardando resposta da coordenação, sem novo aceite presumido. Aguardar conferência/aprovação por tarefa conforme AGENTS.md.

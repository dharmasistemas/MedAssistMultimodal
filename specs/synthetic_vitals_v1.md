# Contrato de sinais vitais sintéticos — v1

03/11/2026 — dia 11, tarefa 1. Especificação anterior ao gerador e processador.
**Não implementado nesta tarefa.** Parâmetros abaixo são escolhas artificiais para
verificar software; não definem normalidade, urgência ou conduta médica.

## Origem, identidade e formato

JSON UTF-8 estrito, schema_version `synthetic-vitals-v1`. Origem interna, sem dados
pessoais reais, BIDMC ou REHAB26. Identidade `synthetic_patient`, `patient_id=PAT-001`,
`source_kind=synthetic`, dataset_id/participant_ref nulos. Gerador versionado,
seed inteira 20261103 e configuração preservados no manifesto com SHA-256 do JSON.
Não inferir simultaneidade com qualquer vídeo ou áudio por compartilhar PAT-001.

Uma série contém series_id, scenario_id, identidade/origem, generator_version,
seed, started_at, interval_seconds=1, samples e referências sintéticas separadas.
IDs textuais da série/cenário são estáveis; sessão/eventos usam UUID conforme domínio.
Âncora nominal fictícia: `2026-11-03T12:00:00+00:00`, explicitamente sintética.
Cada amostra contém sample_index inteiro >=0, timestamp UTC consciente de fuso e
quatro canais: heart_rate (bpm), spo2 (%), systolic e diastolic (mmHg).
Cada canal contém value (número ou null), unit e quality (`valid`, `missing`,
`invalid`). Não aceitar bool como número, NaN/Infinity no JSON ou unidade implícita.

Índices começam em zero e são contíguos. Timestamp = âncora + índice segundos,
estritamente crescente. Lacuna temporal não é interpolada: representar posição
com canal ausente ou rejeitar envelope com índice/tempo inconsistente.
Canal missing exige null; valid exige número finito; invalid preserva valor JSON
representável e motivo explícito, sem entrar em regras de limiar. Texto recebido
como valor inválido fica no registro de rejeição do importador, fora do canal tipado.

SpO2 fora de [0,100], FC <=0 ou pressão <=0 são inválidas por domínio/formato,
sem pretender que valores positivos sejam clinicamente plausíveis. Pressão exige
par sistólica/diastólica válido e sistólica > diastólica; se um falhar, ambas
ficam indisponíveis para regra de pressão. Outros canais continuam analisáveis.
Envelope inválido (identidade, unidade, ordem, duplicata, tempo) rejeita a série
antes de persistir. Valor/canal inválido gera qualidade técnica local, sem zerar.

## Perfil experimental `synthetic-vitals-rules-v1`

| Canal | Limite inferior | Limite superior | Persistência |
|---|---:|---:|---|
| FC | 50 bpm | 110 bpm | 3 amostras consecutivas válidas |
| SpO2 | 94% | — | 3 amostras consecutivas válidas |
| Sistólica | 90 mmHg | 140 mmHg | 3 pares consecutivos válidos |
| Diastólica | 60 mmHg | 90 mmHg | 3 pares consecutivos válidos |

Comparação estrita: abaixo de inferior ou acima de superior; igualdade não dispara.
Cada canal/direção tem regra própria. Não há soma de evidências entre canais ou
modelo estatístico/LLM. Baseline artificial: 75 bpm, 98%, 120/80 mmHg.

Para cada regra, manter sequência máxima de violações consecutivas na mesma
direção. Ao atingir 3, produzir UMA ocorrência, iniciada na primeira violação,
confirmada na terceira. Extensões atualizam o intervalo no resultado final, sem
um evento por amostra. Igualdade/retorno encerra sequência na última violação;
missing/invalid interrompe e reinicia contagem. Não unir através de gaps.
Troca direta de direção encerra uma sequência e inicia outra. Ao fim do arquivo,
sequência >=3 produz ocorrência com término `end_of_series`; <3 não produz.
Nenhum streaming ou atualização de evento persistido é prometido neste incremento.

Intervalos inclusivos; duração nominal = quantidade de amostras * 1 s (exposição
da grade), distinta de timestamp final - inicial. Latência de confirmação nominal
= timestamp da terceira - primeira = 2 s; não é tempo de execução do computador.
Qualidade missing/invalid é compactada por canal/motivo em intervalos consecutivos,
separada de ocorrência de limiar e sem severidade clínica. Ausência não é normalidade.

## Cenários fixados antes da geração

Cada cenário é série independente de 12 amostras (0–11); demais valores usam baseline.
As referências ficam separadas da entrada do processador; testes as confrontam depois.

| ID | Alteração artificial | Resultado esperado de limiar |
|---|---|---|
| V01 | Somente baseline | Nenhuma ocorrência |
| V02 | FC=120 nos índices 3–7 | FC alta 3–7, confirmação 5 |
| V03 | FC=45 em 3–7 | FC baixa 3–7, confirmação 5 |
| V04 | SpO2=92 em 3–7 | SpO2 baixa 3–7, confirmação 5 |
| V05 | Pressão=150/95 em 3–7 | Duas ocorrências altas, uma por canal, 3–7 |
| V06 | Pressão=85/55 em 3–7 | Duas ocorrências baixas, uma por canal, 3–7 |
| V07 | 50/110 bpm alternados; SpO2=94; pressão=90/60 em 0–5 e 140/90 em 6–11 | Nenhuma; igualdade em todos os limites |
| V08 | FC=120 em 3–4 | Nenhuma; duas violações insuficientes |
| V09 | FC=120 em 3–5 | Uma FC alta 3–5, confirmação 5 |
| V10 | FC=120 em 1–3 e 5–7 | Duas FC altas, separadas pelo retorno em 4 |
| V11 | FC=120 em 1–2 e 4–5; FC ausente em 3 | Nenhuma; gap interrompe sequência e gera qualidade |
| V12 | Todos os canais ausentes | Nenhuma de limiar; qualidade/ausência total explícita |
| V13 | SpO2=101 em 2; FC=0 em 4; pressão=70/80 em 6 | Qualidade inválida; nenhuma de limiar |
| V14 | FC=120 em 1–5 e SpO2=92 em 2–6 | Duas ocorrências independentes sobrepostas |
| V15 | FC=120 em 9–11 | Uma FC alta 9–11, confirmação 11, término EOF |
| V16 | FC=120 em 10–11 | Nenhuma; EOF não completa persistência |
| V17 | FC=120 em 1–2 e 4–5; FC inválida em 3 | Nenhuma; inválido interrompe sequência |
| V18 | Sistólica ausente em 3, diastólica=95 em 1–5 | Sem ocorrência: par indisponível em 3 interrompe; FC/SpO2 preservadas |

V18: sistólica baseline nos demais índices; as duas sequências diastólicas têm
apenas duas amostras cada (1–2, 4–5). Referências de qualidade identificam o par.

Casos adicionais unitários sem série persistível: bool, NaN/infinitos em memória,
unidade errada/ausente, timestamp sem fuso, ordem invertida, índice duplicado,
identidade de dataset misturada, canal valid com null, missing com número e série
vazia. Série vazia é rejeitada, não apresentada como avaliação negativa normal.
Amostra finita imediatamente além de cada limite dispara se repetida três vezes;
no limite não dispara. Cobrir também reversão direta FC alta→baixa e canal isolado
inválido enquanto outro mantém episódio detectável. Sem download ou provider.

Seed será usada apenas para variação reproduzível de baseline dentro de faixas
artificiais seguras para o perfil: FC 72–78, SpO2 97–99, pressão 118–122/78–82,
inteiros, aplicada antes das substituições de cada cenário. V01 usa essa variação;
V07 e índices explicitamente substituídos permanecem exatos. Não prometer bytes
idênticos apenas pela seed: registrar versão, algoritmo e hash do artefato gerado.

## Resultado, evidência e integração futura

Processador puro recebe série validada + perfil, nunca rótulos de referência.
Resultado: versão/perfil, origem/hash, cobertura por canal (válidos/total),
intervalos de qualidade e ocorrências com rule_id, canal/direção, limites/unidades,
first/last/confirmed_index, timestamps nominais, valores observados e término.
Confiança clínica não é estimada; severity não será inferida como urgência médica.

Persistir artefato JSON imutável com hash antes do banco. Referência sintética de
comparação e entrada devem ter hashes próprios. evidence_ref aponta arquivo/hash
mais fragmento de ocorrência ou resumo de qualidade. Tipos, valores e intervalos
ficam no artefato; MultimodalEvent atual não possui colunas de tipo/severidade/payload.

| Campo existente | Adaptação prevista |
|---|---|
| Session.subject | synthetic_patient / PAT-001; sem dataset_id/participant_ref |
| Session.started_at | Âncora nominal explicitamente fictícia da série |
| source_kind / source | synthetic / identificador versionado de vitais sintéticos |
| timestamp | Horário nominal de confirmação; qualidade usa início do intervalo; resumo usa âncora |
| confidence | None, sem converter cobertura em probabilidade |
| processor / is_mock | vitals-rules-v1 / False para execução efetiva sobre dados sintéticos |
| review_status | pending_review; revisão humana não executada automaticamente |
| evidence_ref | Artefato durável + SHA-256 + item estável |
| IDs | UUID estável derivado de run_id explícito, hashes/config e chave da ocorrência |

Dado sintético não equivale a processador mock. Persistir resumo mesmo sem ocorrência
para distinguir execução negativa de ausência de execução; ausência total tem resumo
de qualidade, nunca texto de normalidade. Não criar um evento para cada sample.

Retentativa reutiliza run_id, IDs, instantes e bytes da evidência. Mesmo ID/conteúdo
diferente é conflito. Usar validate_for_session e RegisterMultimodalSession para
sessão/eventos/auditoria atômicos. Arquivo + SQLite não são transação única: gravar
e validar evidência antes; falha no banco deixa artefato recuperável e não destrutivo,
retentativa valida hash. Arquivo ausente/divergente impede persistência completa.
Workflow de revisão e UI continuam pendentes; status auditado completed significa
persistência concluída, não aprovação clínica.

## Verificações previstas e limites

Tarefa 2: gerar os 18 cenários/manifesto, conferir determinismo, unidades, referências
independentes e proteção Git. Tarefa 3: regras, validação e testes acima. Tarefa 4:
SQLite/CLI, duplicação, conflito, rollback e evidência ausente. Tarefa 5: fluxo completo,
métricas por regra, qualidade/cobertura e latência nominal separada da computacional.
Precisão/recall sintéticos medem conformidade à injeção e ao perfil, sem provar eficácia
clínica. BIDMC fica para avaliação independente posterior com sinais disponíveis.
Nenhuma orientação de tratamento, classificação diagnóstica ou chamada ao Qwen.
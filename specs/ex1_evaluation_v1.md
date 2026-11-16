# Dia 8 — protocolo de avaliação Ex1 v1

Definido em 31/10/2026 antes da execução de avaliação reservada. Usuário autorizou
as seis tarefas em conjunto. Sem novos downloads, instalação ou ajuste de limiares.

## Unidades e referências

Unidade: repetição anotada, extremos inclusivos. Pareamento pela referência opaca do
participante, orientação e número de repetição. Cam1 somente; orientação da pessoa
não é uma câmera diferente. Avaliação condicionada a intervalos de referência,
não avalia segmentação automática. Grupo development v1: três participantes, 334
repetições; evaluation v1: dois participantes, 222. Nenhuma troca de grupos.

Positivo por regra: código específico presente no erro principal OU nos adicionais.
`bent_elbow_proxy` versus `ERR_BENT_ARM`; `low_elevation_proxy` versus
`ERR_LOW_ABDUCTION`. Ausência desse código é negativo para essa regra, inclusive
quando existe outro erro. Nunca usar correctness_score como rótulo de todos os
desvios. O proxy de elevação não comprova o plano frontal e pode falhar nessa tarefa.

## Métricas

Matriz TP/FP/TN/FN apenas para analisáveis; precisão TP/(TP+FP), recall TP/(TP+FN),
F1 2TP/(2TP+FP+FN). Denominador zero retorna null. Abstenções separadas por classe;
cobertura total e por classe; detecção efetiva TP/todos os positivos elegíveis,
incluindo abstenções no denominador. Agregar globalmente, por participante e por
orientação. Não tratar repetições correlacionadas como sujeitos independentes nem
apresentar intervalos de confiança clínicos. Sem métrica global correto/incorreto.

## RGB development e investigação temporal

Na única gravação RGB disponível, selecionar a primeira repetição temporal de cada
combinação orientação/correctness_score, sem consultar resultado de regras. Seleção
fixa para ampliar casos e views, não amostra aleatória nem estimativa populacional.
Decodificar sequencialmente toda a gravação para verificar contagem real. Inferir
pose somente nos intervalos selecionados, com detector novo por intervalo; evita
transportar tracking entre saltos. Resultados não são idênticos a inferência contínua.
Comparar regras com anotações específicas; exportar checklist local de início/meio/fim
para revisão visual humana ainda pendente. Diferença RGB/NPY deve ser investigada sem
inferir causa apenas pelo tamanho. Nenhum offset será ajustado para melhorar métricas.

## Congelamento e avaliação reservada

Manifesto `data/manifests/day08_evaluation_freeze.json` fixa hashes da configuração,
geometria, regras e protocolo antes da abertura dos NPY reservados. Verificação
obrigatória em cada execução; divergência exige nova versão/protocolo, nunca ajuste
retroativo pelos resultados de evaluation. Analisar NPY 3D dos cinco participantes,
com relatórios development/evaluation separados. RGB reservado não está adquirido:
as métricas de evaluation referem-se aos NPY distribuídos, não ao novo pipeline RGB.
Nenhum NPY 2D reinterpretado, diagnóstico ou revisão clínica automática.

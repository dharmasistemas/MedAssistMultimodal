# Dia 10 — protocolo exploratório de qualidade e segmentação v1

Definido em 02/11/2026, tarefa 1 de 5. **Especificação, sem implementação ou nova
execução.** O usuário escolheu priorizar o fluxo integrado com os dados atuais;
mais exemplos só serão propostos para perguntas específicas, não para repetir toda
a análise. Preservar regras, configuração e resultados clínicos experimentais v1.

## Papel da saída de vídeo

Na futura integração, apresentar fonte, frames/tempos, medidas, qualidade e revisão
humana. Manter os proxies v1 disponíveis como comparação experimental, sem promovê-los
a alertas clínicos automáticos nem declarar correto um exercício sem sinalização.
Esta política de planejamento não altera hoje executáveis, enums ou configurações
v1. O requisito de detectar desvios continua insuficiente; qualidade técnica e
contagem de repetições não o substituem. Nenhuma redução formal de escopo é presumida.

## Experimento mínimo e dados fixos

Uma intervenção de qualidade: marcar descontinuidades angulares; um baseline temporal:
repouso/elevação/retorno. Não implementar agora normalização por tronco, filtros
adaptativos, mudança dos limiares de desvio ou múltiplos detectores concorrentes.

Fonte principal para execução da tarefa 4: **NPY world 3D completo Ex1/cam1 do
participante P-0236ac1b114742088a082d0b6163bae1**, já disponível (15016 frames).
Referência: todas as 110 repetições anotadas dessa gravação, sem seleção por resultado
ou recorte dos intervalos antes de segmentar. Nenhum participante evaluation.
NPY distribuído não representa avaliação do novo extrator RGB.

Os 12 casos development já selecionados e suas timelines servem somente para
inspeção/regressão diagnóstica de qualidade. As dez timelines RGB não devem ser
concatenadas como vídeo contínuo nem usadas para alegar segmentação da gravação.
O MP4 existente permanece para contexto visual. Sem nova inferência RGB completa,
novos arquivos de mídia ou downloads neste experimento inicial.

Os dados são de desenvolvimento já examinados. Não chamar este experimento de
teste cego/independente. Artefatos, configuração e seleção serão fixados por hashes
antes da execução real; futura mudança exige nova versão, motivo e relatório próprio.

## Contrato de entrada e saída proposto

Entrada: série ordenada com índice original, ângulos por medida ou ausência/motivo,
visibilidade e tempo nominal. Índices devem ser consecutivos; ausência explícita
permanece como frame indisponível. Índice duplicado, fora de ordem, saltado sem
registro de ausência ou FPS incompatível é erro de contrato, sem renumerar a série.
Perfil atual: 30 FPS, world 3D, sem referência vertical de tronco.

Saída de qualidade por medida/frame: valor original, estado/motivo original,
marcação técnica adicional e valor utilizável ou None. Não substituir o dado bruto,
alterar coordenadas ou apresentar geometria sem filtro como medida aceita.
São contratos planejados, não nova API já entregue.

## Qualidade: parâmetros e semântica exatos

| Parâmetro | Valor inicial | Papel e justificativa |
|---|---|---|
| FPS aceito | 30 | Perfil do dado existente; não prometer equivalência em outro FPS |
| Visibilidade mínima | 0,5 inclusive | Preservar o corte v1 dos pontos necessários; não é garantia de pose correta |
| Salto angular máximo entre frames | 30° inclusive | Limite técnico exploratório: sinalizar variação superior a um sexto do domínio angular em um frame; não é limite fisiológico validado |
| Medidas inspecionadas | Cotovelo e braço–tronco, independentemente | Uma falha de cotovelo não rejeita automaticamente uma medida diferente |
| Tratamento de um salto acima do limite | Marcar os dois extremos como suspeitos para aquela medida | Não assumir qual extremo está correto |
| Preenchimento/suavização | Nenhum | Não apagar lacunas ou fabricar continuidade |

Comparar apenas pares consecutivos **originalmente válidos pelo filtro v1**.
Se faltar medida entre dois frames, não comparar através da lacuna. Identificar
todos os pares antes de aplicar a máscara adicional: não repetir filtragem em
cascata nem usar “último aceito” como referência móvel. Igualdade a 30° é aceita;
valor superior marca os dois extremos. O primeiro frame não tem predecessor.

Conservar flags/motivos quando o mesmo frame participa de vários pares. Após
marcação, seu valor utilizável é None; o valor original continua auditável.
Razões de ausência/visibilidade anteriores permanecem distintas do salto suspeito.
O corte pode rejeitar movimento válido ou deixar passar pose errada; não certifica
qualidade clínica. Foi escolhido após observar desenvolvimento e antes da nova
execução, não como valor validado pela amostra. Não ajustar para maximizar resultado.

## Segmentação: estados e parâmetros

Entrada: somente série utilizável braço–tronco após qualidade. Nunca ler anotação
first_frame/last_frame no segmentador; ela só participa do avaliador posterior.
Não reutilizar o corte de 80° da classificação de baixa elevação como rótulo clínico.

| Parâmetro | Valor inicial | Justificativa operacional |
|---|---|---|
| Faixa baixa | Ângulo ≤ 30° | Referência inicial grosseira de braço próximo ao tronco |
| Faixa alta | Ângulo ≥ 60° | Separação de 30° para histerese, não execução correta |
| Confirmação de faixa | 3 frames consecutivos | Persistência nominal de 0,1 s, evita confirmação por um único frame |
| Duração mínima | 15 frames inclusivos (0,5 s) | Rejeitar ciclos instantâneos do estimador |
| Duração máxima | 450 frames inclusivos (15 s) | Limitar espera do estado e o experimento; não limite clínico de exercício |
| Lacunas toleradas dentro de tentativa | Zero | Interromper sem inventar passagem por frames indisponíveis |

Estados: aguardar baixa, pronto e ativo; manter uma tentativa de subida quando
necessário. Inicializar aguardando baixa. Após três frames baixos, ficar pronto.
O primeiro frame estritamente acima de 30° inicia uma tentativa e fixa início
candidato. Ativar somente depois de três frames consecutivos ≥ 60°; reiniciar
essa contagem quando sair da faixa alta. Retorno à baixa antes da ativação cancela
a tentativa e exige novamente a confirmação de baixa.

Ativo: três frames consecutivos ≤ 30° confirmam retorno. Fim do segmento = primeiro
frame dessa sequência baixa, embora a confirmação seja posterior. Duração =
fim − início + 1; emitir apenas se 15–450 frames inclusive. Após completar, ficar
pronto (a baixa já foi confirmada), sem reutilizar frames de subida da repetição anterior.

Permitir no máximo dois frames adicionais de espera para confirmar uma sequência
baixa iniciada dentro do limite de duração: limite de espera = início + 450 − 1 + 2.
Essa margem não aumenta a duração máxima aceita do segmento. Ao atingir o limite
de espera sem fechamento válido, cancelar a tentativa. Não cancelar antes apenas
porque a confirmação de três frames termina depois do frame final elegível.

Qualquer ausência/suspeita interrompe a tentativa/segmento e volta a aguardar baixa,
com todas as contagens zeradas; registrar interrupção técnica, não emitir repetição
completa. Ao cancelar por retorno antes de ativação, o frame baixo atual pode contar
como primeiro da nova confirmação baixa. Ao cancelar por duração ou fechar um ciclo
curto rejeitado, voltar a aguardar baixa e contar o frame atual como primeiro somente
se ele for válido e baixo. No fim de arquivo, uma tentativa
incompleta é registrada como tal, sem ser contada como repetição completa.
Movimento que nunca alcança a faixa alta ou nunca retorna não é ciclo completo.
Sem correção automática de frames, interpolação, suavização ou agrupamento de gaps.

## Correspondência temporal e métricas

Referências elegíveis: intervalos anotados inclusivos inteiramente dentro da série.
Referência fora dos limites é registrada à parte, nunca truncada silenciosamente.
Conferir que a fonte prevista contém 110 intervalos; divergência interrompe a análise.

IoU temporal = frames da interseção / frames da união, usando extremos inclusivos.
Gerar pares com IoU ≥ 0,5; ordenar por IoU decrescente, menor erro absoluto de início,
início da referência e início da previsão. Percorrer nessa ordem aceitando somente
pares ainda livres. Cada referência/previsão é usada no máximo uma vez. Método
determinístico simples, sem alegar pareamento ótimo global.

Par aceito = TP; previsão completa não pareada = FP; referência elegível não pareada
= FN, **inclusive se houver baixa qualidade**. Não retirar referências difíceis do
denominador para melhorar recall. Sem TN de detecção temporal, pois não há universo
definido de todas as não repetições.

Reportar precisão TP/(TP+FP), recall TP/(TP+FN), F1 2TP/(2TP+FP+FN), contagens de
previstos/referências/interrupções, cobertura original e após máscara (total e por
orientação nos intervalos de referência), frames rejeitados por motivo e perda de
cobertura. Denominador zero = None. Para pares aceitos, erro assinado e absoluto
de início/fim em frames e segundos; mediana, média e máximo absoluto. Tolerância
descritiva adicional ±15 frames (0,5 s) por limite, sem alterar pareamento após ver
resultados. Esse critério é de localização para inspeção, não aceitabilidade clínica.

## Aceite técnico versus resultado experimental

Aceite dos componentes: casos sintéticos conhecidos passam integralmente, incluindo
igualdades de limiar, salto em cada direção, ausência, sem cascata, aquecimento,
retorno incompleto, duração mínima/máxima, EOF, índices e pareamento um-para-um.
Verificar que valores/fontes v1 e CSV humano não mudaram. Falha nesses contratos
é defeito a corrigir antes da execução real, não licença para ajustar parâmetros.

Não há meta clínica justificável de precisão/recall ou taxa de rejeição para liberar
esses detectores como confiáveis. Portanto, o ensaio real **é exploratório**: nenhum
F1 observado sozinho promove o componente a detector clínico validado. Um relatório
real com métricas ruins continua sendo resultado do experimento, não aceite da
qualidade de detecção. Rejeitar tudo ou prever zero não conta como solução.

Se faltar uma repetição completa ou toda evidência válida for rejeitada, registrar
falha de viabilidade do baseline; não relaxar thresholds em ciclo. Nos demais casos,
reportar perdas/cobertura/erros integralmente e decidir com usuário o que pode ser
mostrado como experimental. Sem nova busca de exemplos favoráveis para “passar”.

## Parada e continuidade

Uma configuração e uma execução development planejada na tarefa 4; correções de
defeitos de contrato são permitidas, versionadas, sem otimizar pela métrica real.
Outra hipótese/parâmetro exige proposta explícita e não estende automaticamente
o dia 10. Fechar decisão em 02/11; preservar vitais/integração de 03/11 e áudio real.
Ausência de solução de vídeo deve permanecer como requisito pendente, com decisão
de escopo formal quando necessária. Novos dados só mediante pergunta concreta,
volume/licença e autorização; não iniciar expansão nesta tarefa.

Configuração planejada: [day10_video_experiment_v1.json](../configs/day10_video_experiment_v1.json).
Nenhum módulo consumidor ou componente desse protocolo foi implementado na tarefa 1.

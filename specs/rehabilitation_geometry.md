# Dia 4 / tarefa 1 — Convenções geométricas experimentais v1

Definidas em 26/10/2026; dia 4 planejado para 27/10. Usuário autorizou tarefas 1–3
em conjunto. Esta convenção orienta medidas futuras; somente primitivas genéricas
e fixtures estão implementadas nas tarefas 2/3, não o extrator de medidas da tarefa 4.

## Coordenadas e unidades

Ponto/vetor tem duas ou três coordenadas numéricas finitas, todas na mesma base,
escala e unidade. Ângulos não orientados, em graus, intervalo [0,180]. Não indicam
sentido horário, lado anatômico, plano de movimento ou probabilidade clínica.
Vértice explícito: angle_at_points(A,B,C) mede o ângulo entre A-B e C-B em B.

2D: usar plano da imagem com x para a direita e y para baixo; unidades em pixels
ou coordenadas com a mesma escala nos dois eixos. Se x/y vierem normalizados por
largura/altura diferentes, corrigir a proporção antes do cálculo. Escala uniforme
preserva ângulos; escalas diferentes entre eixos não têm essa garantia.

3D: usar coordenadas compatíveis na mesma base, por exemplo world landmarks em
metros depois de validar os arquivos reais. Não misturar x/y em pixels com z
relativo do MediaPipe como se fossem três coordenadas euclidianas equivalentes.
A transformação e o alinhamento com o mundo físico ainda precisam ser verificados.

Visibilidade é metadado de qualidade, não uma quarta coordenada geométrica.
Não aceitar uma tupla (x,y,z,visibility) diretamente nas funções de ângulo.
A seleção/conversão de coordenadas ficará nas camadas de leitura/medidas futuras.

## Medidas previstas para a tarefa 4

Índices conforme joint_names.txt inspecionado: ombro esquerdo 11, direito 12;
cotovelo direito 14; punho direito 16; quadril esquerdo 23, direito 24.

| Medida experimental | Definição proposta | Convenção |
|---|---|---|
| Cotovelo direito | Ângulo ombro direito–cotovelo direito–punho direito, vértice no cotovelo | 180 graus para braço alinhado/estendido; 90 para ângulo reto; não converter automaticamente em amplitude clínica de flexão |
| Braço–tronco direito | Ângulo quadril direito–ombro direito–cotovelo direito, vértice no ombro | 0 para braço na direção do quadril; 90 perpendicular; 180 na direção oposta |
| Inclinação do tronco | Vetor do ponto médio dos quadris ao ponto médio dos ombros versus referência vertical para cima | 0 alinhado à referência; 90 perpendicular; valor não orientado |

O ângulo braço–tronco é uma referência grosseira de elevação, não abdução
glenoumeral isolada. Em 3D, elevar o braço lateralmente ou à frente pode produzir
o mesmo ângulo. Não usar seu nome/valor para afirmar que o plano de abdução foi
validado. Movimento de escápula, rotação do tronco e câmera influenciam a interpretação.

Em 2D a vertical de imagem proposta é (0,-1), sem compensação automática da câmera.
Ela é uma referência visual, não gravidade medida. Em 3D, exigir vetor vertical
calibrado/fornecido explicitamente na mesma base; não presumir eixo de gravidade.
Para uma referência visual 3D não calibrada, informar essa limitação no resultado.

A postura sintética de tronco usada na tarefa 3 já fornece a direção do centro
hips→shoulders. O cálculo dos pontos médios e associação de índices ainda é tarefa 4.

## Geometria inválida e precisão

Primitivas rejeitam NaN, infinitos, booleanos, tipos incompatíveis, dimensões mistas,
vetores nulos e pontos coincidentes que tornem uma direção indefinida. Ângulo zero
é válido para direções iguais, não é substituto para falha ou ponto ausente.
Diferenças de coordenadas que excedam a representação float são rejeitadas.

Normalização por escala máxima evita overflow/underflow do comprimento de vetores.
Cálculo usa a relação de meio ângulo com atan2 e normas da soma/diferença das
direções unitárias. Não há arredondamento antes do resultado; testes usam tolerâncias
numéricas explícitas. Não impor tolerância de distância em metros ou pixels sem
conhecer unidade e qualidade da entrada: vetores exatamente nulos são recusados
agora; limiar de qualidade/visibilidade é tarefa 5.

Primitivas retornam float ou levantam GeometryError. Ainda não existe resultado
“não analisável” com motivo estruturado: esse tratamento é da tarefa 5. Não há
interpolação, suavização, preenchimento com zero ou recuperação silenciosa.

## Alcance

Somente geometria e dados artificiais. Sem regras de correto/incorreto, alertas,
confidence inventada, diagnóstico, parâmetros ajustados com participantes de avaliação
ou processamento de vídeo/NPY. Os grupos Ex1 v1 permanecem inalterados.

## Estado após tarefas 4–6 — 26/10/2026

domain/rehabilitation.py implementa as três medidas e qualidade independente por
resultado. A API exige CoordinateSpace e min_visibility; WORLD_3D exige vertical
explícita para o tronco. Retorna Measurement com valor ou motivo de não analisável.
As descrições prospectivas acima registram a convenção inicial; implementação e
limites atuais: [guia](../docs/DAY_04_TASKS_04_06.md).

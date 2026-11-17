# REHAB26 — Validação técnica preliminar (14/10/2026)

## Inspeção dos metadados — 26/10/2026

Relatório real (referência do acervo local, não distribuída): 1.665 linhas,
832 corretas/833 incorretas, delimitador ponto e vírgula e chave composta esclarecidos.
Intervalos comuns às três câmeras; nomes presentes na fonte não reproduzidos aqui.
Parser de produção e validação de NPY/vídeo permanecem pendentes.
Os pontos de inspeção pendentes abaixo preservam o histórico anterior à aquisição.

## Atualização de aquisição — 26/10/2026

Quatro metadados adquiridos e verificados por MD5 publicado e SHA-256 local:
relatório (referência do acervo local, não distribuída) e
manifesto (referência do acervo local, não distribuída).
Parsing e interpretação ainda pendentes; NPY/vídeos não adquiridos.
A seção abaixo preserva o diagnóstico documental de 14/10.

## Status honesto — registro de 14/10/2026
**PASSOU na validação documental/metadados; validação dos bytes e parsing local PENDENTE.** A página oficial do Zenodo foi consultada em 14/10/2026. A sessão de geração destes documentos não conseguiu baixar os arquivos para abrir os CSV/NPY; portanto **não afirmar que os dados já foram executados ou que o parser foi testado**. O Codex deve realizar a validação de arquivos na máquina do usuário antes de implementar regras.

## Evidências confirmadas pelo repositório
- DOI 10.5281/zenodo.23018128; publicação 28/09/2026, versão v1.
- 45 gravações RGB (3 exercícios, 5 participantes, 3 câmeras); 1.665 repetições; 832 corretas/833 incorretas; segmentação em frames e erros por repetição.
- MediaPipe Pose 0.10.20 Full, 33 landmarks, arquivos 2D e 3D `.npy` `(frames,33,4)` float64, indexados por frame 30 FPS.
- `Segmentation.csv`, `Segmentation.txt`, `Error_types.csv`, `joint_names.txt`, `jointSequences-mediapipe.zip`, `videos.zip` disponíveis no registro.
- Exercícios Ex1 abdução do braço direito, Ex6 agachamento, Ex7 extensão do ombro; câmeras 0°,45°,90°.
- Licença: somente pesquisa acadêmica/não comercial; permissão comercial exige contato com os autores.

## Riscos e pontos de atenção
1. Só **5 participantes**: resultados não generalizam para população clínica; diferentes câmeras e repetições do mesmo sujeito são correlacionadas.
2. Landmarks pré-computados foram produzidos pelo próprio MediaPipe; comparar o nosso MediaPipe no mesmo vídeo não constitui validação independente de ground truth articular.
3. Classificação de execução correta/incorreta por fisioterapeuta é referência de qualidade, mas não equivale a diagnóstico nem a indicação terapêutica universal.
4. Regras geométricas dependem da orientação de câmera e da visibilidade; não usar limiar angular único para todas as views sem análise.
5. Arquivos grandes (~9,1 GB); download seletivo e controle de disco.
6. A documentação descreve `Segmentation.csv` com segmentação por frames; **nomes exatos das colunas e codificação de erros ainda não foram inspecionados**.

## Gate de validação no Codex — antes de modelagem
- [ ] Obter quatro arquivos pequenos por download manual ou script autorizado; verificar MD5 publicados: `Error_types.csv` 2f89da48c2c26b4868a59deaa4fb3ed9; `joint_names.txt` 2d6999cedf3775d3e9dded2e87b8d035; `Segmentation.csv` 3d1cf6b552f60ef03eb8f5db977c139f; `Segmentation.txt` 502475f709390d96b599da65fa45ffd3.
- [ ] Registrar cabeçalhos, delimitador, encoding, contagens, rótulos e intervalos frame inicial/final; não assumir se fim é inclusivo.
- [ ] Verificar se 1.665 linhas/repetições e contagem de classes correspondem ao descrito; distinguir linhas por câmera de repetições únicas.
- [ ] Inspecionar `Ex1`, códigos de erros e orientação/câmera para seleção do baseline.
- [ ] Após aprovação de download (~686 MB), validar zip, nomes, shape/dtype e visibilidade de NPY Ex1; testar alinhamento frame/segmento e lacunas de frames.
- [ ] Após aprovação do vídeo (~8,4 GB), testar pelo menos um MP4 Ex1 de uma câmera com OpenCV e reproduzir landmarks com MediaPipe; comparar índice e timestamp.
- [ ] Definir split por participante/gravação e relatório de cobertura por view, erro e classe.
- [ ] Produzir `reports/rehab26_validation.json` e `reports/rehab26_validation.md` com evidências e limitações.

## Fontes
https://zenodo.org/records/23018128
https://doi.org/10.5281/zenodo.23018128

## Parser implementado — 26/10/2026

Tarefa 4 (referência do acervo local, não distribuída): parser de metadados executado nos quatro arquivos
reais, com contagens coincidentes com a inspeção e hashes reconferidos.
Evidência (referência do acervo local, não distribuída).
Atualiza as pendências históricas de parsing acima; NPY/vídeos continuam ausentes
e alinhamento com mídia não foi validado.

## Aquisição de landmarks — 28/10/2026

Dia 5 / tarefa 2 (referência do acervo local, não distribuída): ZIP e dez NPY Ex1/cam1 2D/3D adquiridos e
verificados por hashes/CRC; NumPy instalado. As pendências históricas de aquisição
acima foram superadas para esse subconjunto. Inspeção de arrays/alinhamento ainda
pendente; nenhum vídeo adquirido. Manifesto (referência do acervo local, não distribuída).

## Inspeção dos NPY — 28/10/2026

Relatório real (referência do acervo local, não distribuída): dez arquivos
float64 (frames,33,4), 78.333 posições por representação, pares 2D/3D com mesmo
número de frames/visibilidade e 76 posições totalmente zeradas. Sem NaN/infinitos.
Unidade 2D divergente entre descrição em pixels e faixas semelhantes a normalizadas:
pendente de confirmação, bloquear conversão geométrica implícita. 3D compatível com
world descrito, sem calibração física. Loader/alinhamento segmentação/vídeo pendentes.

## Loader implementado — 28/10/2026

Dia 5 / tarefa 4 (referência do acervo local, não distribuída): leitura read-only com validação v1, hashes
esperados na conferência real, índices preservados e frames zero sinalizados.
Evidência (referência do acervo local, não distribuída).
Unidade 2D continua pendente, sem conversão geométrica implícita. Alinhamento dos
segmentos é tarefa 5; nenhum vídeo ou métrica de movimento validado.

## Cobertura da segmentação nos NPY — 28/10/2026

Relatório (referência do acervo local, não distribuída): 556/556 repetições
Ex1/cam1 cabem nos arrays e têm dados estruturalmente presentes; 55.455 posições
anotadas por representação. Os 76 frames zerados ficam fora dos segmentos.
Sem truncamento ou remoção de linhas. Isso atualiza a pendência de cobertura por
índice neste subconjunto, não comprova sincronização visual RGB nem resolve unidade 2D.

## Pipeline RGB inicial — 31/10/2026
Relatório (referência do acervo local, não distribuída): 80 frames reais 20–99,
1080×1920, 30 FPS, 80 poses. Tasks 1.2.0 Full/CPU difere da API/versão usada para
os NPY distribuídos. Diferenças médias absolutas cotovelo 2,2633° e braço–tronco
1,9352° em 80 pares válidos; não são erro contra referência clínica independente.
Contagem declarada RGB 15149 e NPY 15016; não concluir alinhamento até o fim.
Unidade dos NPY 2D antigos não resolvida. Warning interno MediaPipe NORM_RECT sem
IMAGE_DIMENSIONS observado, sem exceção; não declarar calibração visual validada.
Teste de imagem preta confirmou no_pose no runtime real.

## Avaliação inicial — dia 8, 31/10/2026
Fechamento (referência do acervo local, não distribuída): 22 repetições RGB development,
1860 frames inferidos e 15149 decodificados; nenhum positivo específico dos dois
proxies nessa seleção. 334 NPY development/222 evaluation avaliados separadamente.
Configuração congelada antes do holdout. Qualidade insuficiente: cobertura reservada
50%, precisão do cotovelo 15,15%, elevação sem detecção dos positivos analisáveis.
Diferença RGB/NPY de 133 frames confirmada; causa e revisão visual não resolvidas.
Nenhuma prova de alinhamento visual completo ou desempenho clínico generalizável.

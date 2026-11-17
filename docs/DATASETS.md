# Datasets — inventário, governança e aquisição

## REHAB26-ViewAngles (principal para vídeo)
- Página oficial: https://zenodo.org/records/23018128 ; DOI https://doi.org/10.5281/zenodo.23018128
- Autores: Janosova, Budikova, Sedmidubsky (2026). Uso **acadêmico/não comercial apenas**; comercial requer contato `info@visioncraft.ai`. Não redistribuir vídeos no Git.
- 45 gravações (3 exercícios x 5 participantes x 3 câmeras), 1.665 repetições; 832 corretas/833 incorretas; 30 FPS; três câmeras sincronizadas; orientação 0–90° + 45°; Ex1 abdução do braço direito, Ex6 agachamento, Ex7 extensão do ombro.
- Arquivos: `Segmentation.csv` (~83,3 KB), `Segmentation.txt` (~2 KB), `Error_types.csv` (934 B), `joint_names.txt` (511 B), `jointSequences-mediapipe.zip` (~686 MB), `videos.zip` (~8,4 GB). Total ~9,1 GB.
- NPY: shape `(frames,33,4)`, `float64`; canais `(x,y,z,visibility)`; descrição da fonte diz 2D x/y em pixels e z relativo, mas a inspeção de 28/10 encontrou faixas semelhantes a normalizadas: unidade 2D ainda não confirmada; 3D documentado em metros, origem centro dos quadris; algumas sequências terminam antes do vídeo.
- **Aquisição progressiva**: baixar quatro arquivos pequenos primeiro; validar cabeçalhos/códigos; depois zip de landmarks; vídeo integral somente quando necessário e autorizado pelo usuário.
- Salvar externamente a `data/raw/rehab26/`, com `.gitignore`; gerar `data/manifests/rehab26_manifest.json` com origem, DOI, versão, hashes, licença, data e subconjunto.
- Não misturar views da mesma repetição entre treino e teste. Divisão por **participante ou gravação**; baseline de regras não precisa treinamento. Evitar vazamento entre 3 câmeras sincronizadas.

## UI-PRMD (referência cinemática complementar)
https://pmc.ncbi.nlm.nih.gov/articles/PMC5773117/ ; verificar arquivo, esquema e condições específicas de cada distribuição antes de uso; dados de sensores, não substitui vídeos RGB.

## Áudio
- Primário: 12+ gravações de **consultas simuladas** PT-BR, consentidas, sem dados pessoais reais; scripts e transcrições de referência; casos neutros, termos de atenção e ruído controlado. Registrar autorização e limites de divulgação.
- Complementar: Mozilla Common Voice PT, https://commonvoice.mozilla.org/pt/datasets ; confirmar versão, termos atuais e seleção de pt-BR; não presumir rotulagem clínica nem redistribuição livre.

## Sinais vitais
- BIDMC PPG and Respiration: https://physionet.org/content/bidmc/1.0.0/ ; séries reais para avaliação independente; verificar sinais efetivamente disponíveis por arquivo, unidade e licença no download. Não presumir pressão arterial contínua no BIDMC.
- Dados sintéticos: séries de FC, SpO2, pressão, episódios anômalos injetados e prescrições com ground truth, geradas por script com seed fixa.

## Regras transversais
Dados reais do BIDMC/REHAB26 nunca vinculados ficticiamente à mesma identidade. Sem uploads públicos de arquivos sensíveis/restritos. Documentar consentimento, licença, versões, hash, splits, transformações, limites e vieses. Não incluir zip de dataset no repositório.

## Estado local — 28/10/2026

Dez NPY Ex1/cam1 2D/3D adquiridos e inspecionados, com hashes conferidos.
Relatório (referência do acervo local, não distribuída): formato confirmado,
76 posições de frame totalmente zeradas e divergência de unidade 2D documentada.
Nenhum vídeo RGB adquirido; alinhamento com segmentação permanece para tarefa 5.

## Atualização — dia 7, 31/10/2026
Um vídeo Ex1/cam1 development adquirido por HTTP Range 206, 195639329 bytes, CRC
ZIP e SHA local verificados. Nenhum ZIP completo de vídeos adquirido/verificado;
parcial integral inicial preservado e não usado. [Manifesto](../data/manifests/day07_rgb_assets.json).
Primeira repetição (frames 20–99) processada por OpenCV/MediaPipe CPU, 80 poses.
Vídeo declara 15149 frames versus 15016 no NPY correspondente; sincronização visual
independente e validação da gravação inteira permanecem pendentes.
Modelo Full float16 v1 oficial: 9398198 bytes, URL/hash no manifesto; fora do Git.


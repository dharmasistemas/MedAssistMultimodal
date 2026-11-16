# Dados, modelos e permissões

## Conteúdo do código

Geradores e casos sintéticos de vitais/prescrições, contratos, testes e pequenos metadados/textos fictícios necessários às avaliações congeladas. prepare_demo gera dados e uma base sem consultar históricos ou baixar arquivos.

## Arquivos locais

Mídias, modelos binários, SQLite, evidências operacionais, autorizações pessoais e gravação da apresentação permanecem locais. Backups privados ficam fora da distribuição. Não inserir credenciais, dados identificáveis ou conteúdo restrito no Git.

## Vídeo

Fonte: [REHAB26-ViewAngles, Zenodo v1](https://zenodo.org/records/23018128), DOI 10.5281/zenodo.23018128. Uso acadêmico/não comercial e atribuição conforme página da fonte. O projeto avaliou uma gravação Ex1/cam1, não todo o dataset.

O fluxo espera assets descritos em data/manifests/day07_rgb_assets.json e modelo Pose Landmarker adquirido separadamente. Manifestos registram caminhos, hashes e proveniência, não contêm mídia/modelo. A presença de metadados não confirma arquivos binários no clone. O participante do dataset não é PAT-001.

## Áudio e Whisper

O corpus principal tem 12 relatos fictícios: cinco com voz do autor e sete TTS. O piloto de pausas tem três arquivos adicionais. O código não inclui as vozes nem concede direitos sobre elas.

A reprodução exata requer arquivos/permissões, catálogo data/interim/audio/simulated_v1/collection_status.json e evidências locais. Whisper small convertido para CTranslate2 deve corresponder a data/manifests/day13_whisper_assets.json. Não inventar hashes nem substituir arquivos para contornar verificações. Consultar os manifestos para a origem e os locais esperados dos modelos.

Históricos do autor continuam consultáveis enquanto suas evidências forem preservadas. O clone não os recria. Os arquivos necessários para execução real podem ser obtidos apenas de fontes autorizadas; o aplicativo não os baixa automaticamente.

## LLM opcional

GPT-OSS gpt-oss:120b-cloud via Ollama, prompt v2/contrato v3. Desligado por padrão, com confirmação por execução. Somente transcrições fictícias conhecidas nesse fluxo. A LLM não decide alertas. Chaves ficam fora do código e do Git.

Referências: [MediaPipe Pose](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Ollama cloud](https://docs.ollama.com/cloud).

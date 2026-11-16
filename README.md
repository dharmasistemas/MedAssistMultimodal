# MedAssistMultimodal

POC acadêmica FIAP Tech Challenge Fase 4 para apoio à revisão profissional de dados multimodais. Python 3.12, aplicação desktop e SQLite.

Repositório: https://github.com/dharmasistemas/MedAssistMultimodal

## Capacidades

- **Vídeo:** OpenCV/MediaPipe, pose, ângulos, frames e sinal experimental de flexão de cotovelo.
- **Áudio e texto:** player local, Whisper e GPT-OSS opcional via Ollama, com confirmação de envio da transcrição fictícia por execução.
- **Anomalias:** regras locais de vitais e comparação de prescrições sintéticas com plano declarado.
- **Revisão e relatório:** evidência, autoria/motivo, auditoria e exportação TXT/JSON.

O sistema não diagnostica nem prescreve. As modalidades têm fontes independentes. O vídeo tem falsos positivos e abstenções; alterações vocais médicas e movimentação durante internação não foram demonstradas. A LLM não decide alertas.

## Início rápido

Windows, Python 3.12 com Tk/Tcl. O ambiente usado no desenvolvimento chama-se medassistmultimodal; você pode criar outro ambiente local.

```powershell
git clone https://github.com/dharmasistemas/MedAssistMultimodal.git
cd MedAssistMultimodal
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m medassistmultimodal.prepare_demo
```

O último comando imprime o campo `database` de uma **nova base sintética** com V01, V02, E01, E02 e E03. Copie o caminho:

```powershell
python -B -m medassistmultimodal.desktop_multimodal --database CAMINHO_EXIBIDO_NO_CAMPO_DATABASE
```

Alternativa PowerShell:

```powershell
.\scripts\start_app.ps1 -Demo
```

Essa opção cria a base e abre o aplicativo. Não baixa modelos, chama serviços ou gera áudio/vídeo. Em Anomalias, consulte ou execute os cenários; depois use Revisão e relatório. Bases anteriores permanecem preservadas.

Para uma base local existente, use `scripts/start_app.ps1 -Database CAMINHO_DA_BASE`.

## Recursos opcionais

```powershell
python -m pip install -r requirements-video.txt
python -m pip install -r requirements-audio.txt
```

Esses comandos instalam dependências, não mídias/modelos. Os fluxos reais exigem arquivos autorizados e manifestos locais. Vídeos, vozes, modelos, bancos e evidências operacionais não acompanham o clone. Ver [dados e modelos](docs/DATA_AND_MODELS.md). Não é necessário .env para a demonstração sintética.

CustomTkinter é a aparência padrão. `--ui simplified` usa a simplificada nativa e `--ui classic` a clássica preservada. Os modos nativos podem executar sem CustomTkinter instalado.

## Testes offline

```powershell
python -m pip install -r requirements-dev.txt
python -B -m pytest tests/unit -q -p no:cacheprovider
```

Os testes usam fixtures temporárias/providers injetados, sem inferência real ou chamadas pagas. Pequenos JSON históricos necessários aos testes de planos congelados são preservados. Não são mídias ou credenciais e não devem ser removidos como simples temporários.

## Documentação

- [Instalação e uso](docs/INSTALLATION.md).
- [Dados, modelos e permissões](docs/DATA_AND_MODELS.md).
- [Resultados e limitações](docs/RESULTS.md).
- [Situação dos entregáveis](docs/DELIVERY.md).

O relatório técnico está em revisão do autor e o vídeo será indicado por link no YouTube. O audiovisual fica fora do repositório. A instalação em ambiente completamente novo deve ser conferida antes de declarar a distribuição final congelada.

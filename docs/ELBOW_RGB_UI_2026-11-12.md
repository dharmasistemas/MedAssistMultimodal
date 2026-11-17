# Cotovelo: avaliação RGB e integração na UI — 12/11/2026

## Entrega e alcance

Modo explícito de análise de cotovelo para os dez trechos D9 conhecidos da gravação REHAB26 local, sem rótulos de referência no detector. O seletor da aba Vídeo mostra IDs neutros; escolher um define os frames exatos. Campos alterados não podem iniciar execução com intervalo divergente do caso. Modo manual preservado para ciclos nos frames0–449, sem detecção de desvio.

O processamento usa OpenCV/MediaPipe real emCPU e o detector integrado anteriormente, sem mudar os limiares. Cada caso tem sessão própria, evidência v2 e identidade de dataset separada de PAT-001. Intervalos vêm da seleção conhecida, não são descobertos automaticamente. Um sinal positivo cria candidato pendente de revisão; negativo não certifica movimento correto e baixa cobertura produz evidência insuficiente.

A UI exibe resultado, limiar, fração, cobertura original e frame de evidência. A tabela de ciclos continua mostrando ângulos após filtro temporal; sua cobertura pode diferir da regra de cotovelo, que usa medidas originais conforme perfilv1. Candidato é identificado como “Desvio experimental: cotovelo” na aba Alertas e revisão. Exportação de sessão e síntese TXT/JSON incluem o resultado; sem revisão automática.

## Como conferir sem reprocessar

Abra a aplicação com a nova cópia de trabalho indicada no resultado abaixo:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m medassistmultimodal.desktop_multimodal --database data/interim/audio/desktop_workspaces_v1/1a943131-cc8a-47e9-8ed5-92a0b138e47f/audio.sqlite3
```

1. Clique Consultar e, na aba Vídeo, Consultar vídeos nesta base. Selecione a sessão D9-04 indicada nos resultados. Deve aparecer sinal experimental de flexão, com cobertura/fração/regra.
2. Clique em uma linha da tabela, inclusive frames897–1056. A imagem RGB deve carregar sem precisar executar pose novamente; navegue pela tabela e confira rolagem/escala.
3. Na aba Alertas e revisão, diferencie o candidato de cotovelo dos resumos/ciclos/avisos técnicos. Consultar não exige marcar como revisado; se registrar revisão, use motivo específico e sua autoria declarada.
4. Consulte também D9-02 (falso positivo frente à referência), D9-01 (sem sinal) e D9-10 (evidência insuficiente), sem apresentar a ausência de sinal como normalidade.
5. Na aba Síntese e exportação, carregue e selecione sessões da nova base, gere síntese e exporte. Alternativamente, Exportar sessão na aba Vídeo gera JSON individual.

Para NOVA inferência (opcional, não necessária para a conferência), selecione D9-04 no novo seletor, confira897–1056 e clique Analisar RGB local. A execução cria outra sessão. A rodada entregue já processa todos os dez casos; não apagar saídas nem repetir para esconder erros.

## Execução e preservação

Runner: `python -B scripts/evaluate_elbow_rgb.py --execute`. Já executado nesta entrega; diretório exclusivo `data/interim/rehab26/elbow_rgb_v1/`, com config anterior à inferência, workspace novo e arquivos por caso. `summary.json` é marcador de conclusão. Entrada e arquivos dependentes verificados por SHA antes/depois; referências conhecidas usadas apenas pelo avaliador. Sem download, nuvem ou ajuste de modelo. Frames não contínuos entre casos usam detector novo por trecho, como na UI.

O script de conferência `scripts/verify_elbow_rgb_ui.py` consulta a sessão salva e carrega um frame real, sem nova pose ou revisão. Testes Tk automatizados são funcionais; inspeção visual final pertence ao usuário.

## Limitações

É seleção development intencional, conhecida e já inspecionada; não é teste independente nem estimativa populacional. Os outros dois casos NPY semRGB não viraram negativos e permanecem excluídos por falta de mídia. Resultados de ciclos não medem detecção de desvio. O perfil não detecta todos os erros de Ex1. A adaptação de N3 para consulta permanece decisão do usuário, sem atribuir ao PDF redação diferente. Warnings internos do MediaPipe sobre feedback e NORM_RECT reapareceram; execução sem exceção não comprova calibração.

Arquivos principais: infrastructure/desktop_video.py, desktop_video.py, scripts/evaluate_elbow_rgb.py, scripts/verify_elbow_rgb_ui.py, tests/unit/test_elbow_rgb_ui.py e wrapper Tk em test_desktop_workflow.py. SchemaSQL/domínio/parâmetros congelados preservados. Evidências/bancos anteriores não reescritos; recibos antigos preservam hashes de versões anteriores do código.

## Verificação offline

```powershell
python -B -m pytest tests/unit -q -rs -p no:cacheprovider --tb=short
```

977testes e341subcasos aprovados em58,80s;34testes direcionados de UI/workflow em19,07s e46testes detector/vídeo em7,68s. Nove casos novos em relação à versão anterior completa. Nenhum desses testes é validação médica.


## Localização para conferência

Base nova: `data/interim/audio/desktop_workspaces_v1/1a943131-cc8a-47e9-8ed5-92a0b138e47f/audio.sqlite3`.

Sessão positiva D9-04: `4e08454a-67d1-58fd-b14b-9ae1cdcca8cf`, frames897–1056.

Esta sessão tem candidato real de desvio pendente; não foi revisada automaticamente.


## Resultado real da rodada completa

Dez extraçõesRGB reais,916frames submetidos ao MediaPipe, sem retentativa/ajuste de parâmetro ou exclusão posterior. Quatro de dez trechos analisáveis (40%);1TP,1FP,2TN e0FN entre analisáveis; seis abstenções, das quais duas com referência positiva. Precisão nos analisáveis50%; recall condicionado aos analisáveis100%, **sem incluir duas abstenções positivas**, portanto não interpretar como sensibilidade global. Detectado1dos3positivos de referência:33,33% no conjunto completo. Não é benchmark independente.

| Caso | Resultado contra referência de cotovelo | Cobertura original | Sessão na base nova |
|---|---|---|---|
| D9-01 | Sem sinal (negativo de referência) | 100.0% | a6cce852-573b-5165-9339-d641a2f6bf33 |
| D9-02 | Falso positivo | 100.0% | 2d6355b0-d125-522e-b056-9319e2469fce |
| D9-03 | Sem sinal (negativo de referência) | 100.0% | 7394a7ef-998d-5df2-920f-857a1f0172e0 |
| D9-04 | Sinal correto | 100.0% | 4e08454a-67d1-58fd-b14b-9ae1cdcca8cf |
| D9-05 | Abstenção em negativo | 69.8% | 22a0edd9-ae68-5d41-a2b3-f3f581ea4e70 |
| D9-06 | Abstenção em negativo | 76.1% | 89487df1-c4fc-5e8c-8f72-20bc983a16e2 |
| D9-07 | Abstenção em positivo | 65.8% | e7be178b-ba70-5528-9a39-cb2d6559aa0f |
| D9-08 | Abstenção em negativo | 0.0% | c7c13bce-15b5-53e5-9e6d-7297740486e6 |
| D9-09 | Abstenção em negativo | 0.0% | 18569fad-283d-5074-a17d-d43de7856d30 |
| D9-10 | Abstenção em positivo | 0.0% | 5230f8a1-cc8f-5026-81a5-e952322b37f4 |

D9-03 é negativo específico de cotovelo, embora tenha rótulo de baixa abdução: não é exercício correto por esse motivo. D9-02 falso positivo preservado. Nos dois sinais, frações foram21,35% (D9-02) e26,25% (D9-04), frente ao limiar20%; sem mudar o limiar depois. Não afirmar equivalência com valores NPY ou rodadas anteriores de pose. A análise parcial não recupera casos de baixa visibilidade.

Nova síntese completa: `data/interim/multimodal/reports_v1/6fd0867b-ea9c-4475-9c18-2b5214af4acd/summary.txt` e `summary.json`. Casos D9-11/12 permanecem semRGB e não entraram no denominador10. Originais, configuração, código dependente, vídeo e modelo preservados/conferidos durante a rodada.38eventos novos, todos pendentes; dois são candidatos de cotovelo, os demais resumos/ciclos/qualidade. Nenhuma revisão automática.

Conferência Tk real: sessãoD9-04,160linhas,1candidato,frame897 exibido,exportação igual à releitura,hash da nova base inalterado pela consulta. Não é inspeção visual humana. Scanner476arquivos/zeroachados/zerovaloreslocaiscomparados; sintaxe e diff--check aprovados.

**Decisão:** integração funcional concluída; qualidade de cobertura/detecção continua limitada. Não executar nova otimização nesta janela. Solicitar conferência visual do usuário; próximo incremento proposto: expectativa explícita de alterações de prescrição (N2), sob aprovação por tarefa.

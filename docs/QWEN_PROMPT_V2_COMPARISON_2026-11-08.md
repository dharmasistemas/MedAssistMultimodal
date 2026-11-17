# Dois testes Qwen com o prompt revisado — 08/11/2026

## Protocolo autorizado

O usuário pediu duas chamadas Qwen antes da decisão de adoção. Foram escolhidas
A03_whisper e A05_whisper do corpus conhecido, com referências v3 aprovadas.
O prompt é exatamente o mesmo `text-v3-prompt-v2` usado no último GPT-OSS.
Entradas, referências, validação e métricas foram mantidas; o GPT-OSS não foi
chamado novamente. O comparador usa as respostas já preservadas do experimento.

Qwen local `qwen2.5:7b-instruct`, digest conferido, contexto 4096, temperatura 0,
orçamento máximo de saída 1536 e timeout de socket 180 s. A opção num_gpu não foi
enviada: seleção automática do Ollama, sem forçar CPU. Não se alterou configuração
global ou o perfil CPU antigo. Não houve pull, retry, fallback, cloud ou compra.

O prompt tem 3084 bytes UTF-8; bytes não são contagem de tokens. Este probe usa o
limite de entrada do domínio e um contexto explícito, sem a estimativa conservadora
de bytes do perfil CPU antigo, que rejeitaria antecipadamente esse caso. Não houve
pré-tokenização. Na resposta concluída A05, a API informou 905 tokens de entrada,
61 de saída e término stop; nenhum truncamento foi observado nessa resposta.

## Resultados

| Entrada | Qwen local, seleção automática | GPT-OSS cloud anterior, mesmo texto/prompt |
|---|---|---|
| A03 Whisper | Timeout em 180,026 s; sem análise | Válida em 1,575 s; 2/2 ocorrências |
| A05 Whisper | Válida em 41,502 s; 1/2 ocorrências | Válida em 0,825 s; 2/2 ocorrências |

Qwen: uma análise válida de duas tentativas, total 221,528 s. A05 retornou neutral
com evidência válida e a ocorrência negada de falta de ar. Omitiu a ocorrência
condicional em “Se eu sentir falta de ar, vou contar ao profissional.”. Isso é
omissão semântica; a resposta aceita não está completa. A03 indisponível não deve
ser descrita como interpretação errada, neutral ou abstenção unknown.

GPT-OSS anterior: duas análises válidas no mesmo subconjunto, quatro ocorrências
encontradas, total aproximado 2,400 s. Reuso de resultados históricos: zero chamadas
cloud nesta rodada. Os dois rótulos esperados são neutral; não testa outras classes.

A05 Qwen informou cerca de 28,257 s de carga, 4,989 s de avaliação do prompt e
8,226 s de geração. Após A03, api/ps não listava o modelo. Após A05, listava contexto
4096 e 2313546628 bytes de VRAM alocados. Uma observação durante a segunda chamada
também mostrou VRAM alocada; o teste não foi configurado como CPU-only. Esses dados
não provam a causa do timeout ou uma distribuição exata de tempo entre CPU/GPU.
Não foram usados logs novos para atribuir uma causa CUDA à chamada de hoje.

## Interpretação e decisão

O prompt comum elimina uma diferença importante dos testes anteriores. Ainda assim,
não é um benchmark controlado entre modelos: execução local/cloud, política de
raciocínio suportada, carga de modelo e ambientes diferem. Duas entradas conhecidas
não estabelecem generalização ou superioridade universal.

Nesta máquina e neste teste limitado, o GPT-OSS tem evidência mais favorável de
latência e extração. Recomenda-se considerá-lo para a opção textual, preservando
Qwen local como alternativa explícita; a decisão final continua do usuário.
A preferência de avaliação textual **opcional na UI** foi registrada, mas não foi
ativada nem integrada nesta tarefa. A LLM não decide alertas e a ausência/falha
de análise textual não remove resultados válidos das regras.

## Evidências e verificações

- Runner: `scripts/probe_qwen_prompt_v2.py`, execução somente com `--execute`.
- Saída exclusiva: `data/interim/audio/qwen_prompt_v2_auto_probe_2026-11-08_v1/`.
- `config.json` foi gravado antes das chamadas, com hashes de fontes/modelo/ref
  e dos dois resultados GPT-OSS usados na comparação; reconferidos ao final.
- Respostas: `A03_whisper.json`, `A05_whisper.json`; agregado em `summary.json`.
- Dois testes offline novos conferem payload, prompt, seleção automática e bloqueios.
- O diretório existente não deve ser excluído ou sobrescrito para repetir a rodada.

O timeout do cliente não é confirmação de cancelamento imediato do runner. A segunda
chamada foi feita uma vez, conforme o plano; não se presume que o primeiro trabalho
tenha sido encerrado normalmente. Isso limita a interpretação de latência.

Fontes oficiais de apoio: [API chat Ollama](https://docs.ollama.com/api/chat) e
[observação CPU/GPU no Ollama](https://docs.ollama.com/faq#how-can-i-tell-if-my-model-was-loaded-onto-the-gpu).

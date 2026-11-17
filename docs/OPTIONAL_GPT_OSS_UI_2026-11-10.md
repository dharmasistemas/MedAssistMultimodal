# Análise textual opcional com GPT-OSS — 10/11/2026

## Entrega

A decisão do usuário por GPT-OSS foi registrada no AGENTS e no escopo. A aba Áudio
agora permite ativar análise textual por gpt-oss:120b-cloud do Ollama. Opção desligada
por padrão; nova confirmação antes de processar. Nenhuma ativação só por abrir a UI.
As regras locais continuam decidindo candidatos de revisão; LLM apenas extrai
termos/citações e classifica o sentimento textual. Não produz diagnóstico ou prescrição.

## Como conferir sem nova chamada

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m medassistmultimodal.desktop_multimodal --database data/interim/audio/desktop_workspaces_v1/e78e5b27-bd4d-4a62-95c7-231c918cb262/audio.sqlite3
```

1. Na aba Áudio, confirme que a opção GPT-OSS está desmarcada. Isso descreve a
   próxima execução; não muda o resultado das sessões anteriores.
2. Selecione a sessão `a236b3f2-14f5-4ab6-9a92-61107cfb23eb` no histórico.
3. Confira Whisper real, regras concluídas e LLM concluída com fonte ollama_cloud,
   modelo gpt-oss:120b-cloud e prompt text-v3-prompt-v2.
4. Leia a transcrição A03. O resultado LLM é Neutro, com citação literal, dor e
   falta de ar extraídas. As regras classificam ambas como negated_current;
   encontrar um termo não significa afirmar presença do sintoma.
5. Confira os três eventos em Alertas e revisão: resumo e duas menções das regras.
   Todos os novos eventos desta execução foram deixados pendentes. Não é necessário
   registrar revisão para apenas inspecionar a apresentação.
6. Feche e abra com o mesmo comando: evidência, texto e estados permanecem.

A cópia inclui sessões e revisões anteriores preservadas. Não interpretar todo
item herdado como uma nova análise GPT-OSS.

## Como executar uma nova análise quando desejar

1. Consulte a cópia de trabalho para PAT-001, escolha o áudio simulado conhecido
   no controle superior e confira o horário da nova sessão.
2. Na aba Áudio, marque Análise textual opcional: GPT-OSS120B(Ollamacloud).
3. Clique Processar localmente. A confirmação explica que Whisper executa local e
   somente a transcrição fictícia será enviada à nuvem pela conta Ollama conectada.
4. Confirme e aguarde. Depois selecione a nova sessão no histórico.
5. Desmarque para processar somente Whisper/regras, sem nuvem. Fechar e reabrir
   também retorna a opção ao estado desligado.

Esta versão integra LLM a uma **nova execução de áudio**; não acrescenta análise
à sessão antiga nem reaproveita ASR histórico. Não repetir processamento só para
tentar gravar: se a persistência falhar, use Repetir gravação pendente, que conserva
bytes/IDs em memória e não chama providers. O cache de recuperação dura só durante
a instância atual. Evidência órfã permanece para recuperação explícita.

## Estados e limitações

- Desativada: nenhuma chamada LLM e o processamento local continua normalmente.
- Concluída: resposta aceita pelo contrato, com citações e modelo/fonte explícitos;
  não prova completude ou correção clínica.
- Timeout/indisponível/resposta inválida: estado global parcial, preservando ASR,
  descritores e regras válidas. Não existe retry/fallback automático de LLM.
- Entrada fora da capacidade: LLM não é chamada; limites4000caracteres/8ocorrências;
  regras disponíveis não são removidas por ultrapassar a capacidade da LLM.

O modelo retorna sentimento da linguagem textual, não emoção detectada na voz.
Não há promessa de generalização; avaliação anterior tinha apenas referências
neutras. Os sete TTS ainda não têm avaliação textual completa. A UI não substitui
avaliação independente nem autoriza uso com dados clínicos reais.

## Conferência real limitada

Uma execução A03: Whisper local real e **uma chamada GPT-OSS**, sem retries.
Status completed, LLM succeeded em0,9058s; neutral, duas ocorrências com evidência
válida. Regras: duas negadas. Três eventos pendentes, originais preservados por hash.
Retorno de modelo gpt-oss:120b, alias validado do solicitado gpt-oss:120b-cloud.
Parâmetros:promptv2/contratov3,temperatura0,thinklow,1536saída máxima,timeout60s.
Métricas da API preservadas no envelope; não foi consultado saldo/custo debitado.
Nenhuma compra, mudança de plano, instalação, upload de áudio ou revisão automática.

O verificador terminou o processamento/persistência, mas inicialmente tentou abrir
a sessão antes de recarregar a lista do histórico. Corrigida a recarga no script;
a sessão já persistida foi conferida em processo novo, sem repetir ASR/GPT-OSS.
O config inicial conserva o hash do script anterior à correção; o recibo final
identifica o código final. Não sobrescrever resultados para repetir o experimento.

Artefatos: `data/interim/audio/text_ui_gpt_oss_v1/` contém config, workspace, export e
summary. `scripts/verify_text_ui.py` é verificação de uma execução, não rotina para
reexecutar automaticamente. A conferência visual final cabe ao usuário.

## Código e verificação

Novos desktop_text (UI/infrastructure), bridge de prompt explícito, leitor validado
e metadados adicionais de llm. ProcessAudio, prompts/adapter congelados, schema,
registradores e regras originais preservados. Entrada desktop_multimodal adaptada.

```powershell
python -B -m pytest tests/unit -q -rs -p no:cacheprovider
```

Próxima tarefa proposta: síntese legível e exportação pela UI, antes do ensaio e
simplificação. Aguarda nova aprovação conforme AGENTS.md.

Regressão completa: **927 testes e 341 subcasos em 34,32 s**, incluindo 10 casos novos, sem skips. Após rótulos finais em português:33testes direcionados em10,79s. Scanner:458arquivos/zero achados/zero valores locais comparados.

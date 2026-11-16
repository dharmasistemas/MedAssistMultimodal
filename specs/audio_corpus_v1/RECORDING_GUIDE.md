# Gravação do corpus simulado PT-BR v1

## Passos de coleta

1. Leia o modelo de autorização e registre os usos aceitos ANTES de gravar. Use
   referência opaca S01 para locutor; não colocar nome, CPF, telefone ou dados reais
   nos roteiros, nomes dos arquivos ou manifesto público. A voz continua potencialmente
   identificável; código opaco não a torna anônima.
2. Escolha local tranquilo e microfone disponível. Use o mesmo dispositivo e distância
   confortável em todas as leituras. Não instalar aplicativo ou serviço pago por causa
   deste guia. Registrar o aplicativo/formato usado no controle local.
3. Grave A01–A12, um arquivo por caso. Leia somente o texto do TXT correspondente,
   sem falar o ID. Voz natural, sem simular dificuldade respiratória, dor ou doença.
   Deixe aproximadamente um segundo de silêncio no início e no fim, sem cortar palavras.
   Faça pausa natural onde há pontuação. Duração é observada depois, não inventada.
4. Para A06 e A12, use ruído ambiente leve e seguro, sem voz de terceiros, música ou
   televisão. Não aumentar volume para prejudicar audição e não buscar mascarar toda
   a fala. Registrar tipo/posição da fonte; sem medição, SNR é desconhecido. Se não
   conseguir ruído controlado, grave limpo e marque a condição real; não alegar ruído.
5. Preferir WAV PCM, mono, 16 bits; 16 kHz é alvo de entrada normalizada. Se o gravador
   produzir 44,1/48 kHz, estéreo ou M4A, preservar o original sem renomear sua extensão.
   Conversão local validada fica para a implementação de áudio; não precisa instalar
   conversor agora. O manifesto registra o caminho real após aquisição, não pressupõe WAV.
6. Salve originais em `data/raw/audio/simulated_v1/`, por exemplo `A01.wav` ou
   `A01.m4a` conforme o formato verdadeiro. Não sobrescrever tentativas: `A01_take02`.
   Selecionar uma tomada explicitamente para avaliação e registrar qual foi usada.
7. Escute cada tomada. Se trocar uma palavra, repetir ou hesitar, registre exatamente
   o que disse em TXT local sob `data/interim/audio/simulated_v1/references/`. O roteiro
   público é prompt, não referência definitiva. Não “corrigir” a fala para coincidir
   com o texto nem usar transcrição automática como ground truth sem escuta independente.
8. Preencha `data/interim/audio/simulated_v1/collection_status.json`: speaker_ref,
   consent_ref local, data real com fuso, caminho da referência verificada e notas.
   Campos técnicos/hash ainda não medidos ficam null para a inspeção técnica futura.
   human_verified só vira true após escuta. Não inventar timestamps de gravação.
9. Avise ao Codex os caminhos locais/formatos e os usos autorizados, sem enviar dados
   pessoais pelo chat. A inspeção técnica posterior verificará duração, canais, clipping,
   silêncio, hashes e arquivos selecionados antes de executar modelos.

Mídia, registros pessoais de autorização e referências derivadas da gravação ficam
fora do Git. Estrutura pública contém apenas textos fictícios e planejamento.
Um relato com sintomas nesta lista é exercício de leitura, não orientação médica.

## Referências e avaliação futura

O manifesto mantém estados pending e campos não comprovados null. Após coleta,
criar manifesto de aquisição local com hashes e metadados reais, referência manual
verificada e usos permitidos. Preservar versão do roteiro e registrar desvios de fala.
A saída do Whisper vai para outro artefato, nunca substitui referência humana.
Nenhum modelo foi baixado ou executado nesta tarefa.

WER futura: (substituições + exclusões + inserções) / palavras da referência.
Fixar normalização antes de comparar: Unicode NFC, minúsculas, remover pontuação,
colapsar espaços; preservar negação, palavras e acentos. Registrar também números
por caso e agregado ponderado pelo total de palavras, sem contar prompt como áudio.
Alinhamento/normalização serão implementados/testados na trilha de áudio. Referência
vazia exige tratamento explícito; não dividir por zero ou dizer WER perfeita.

Para texto, comparar expressões e seus contextos (afirmado atual, negado, histórico,
condicional, terceira pessoa e correção), mantendo evidência no trecho transcrito.
Os rótulos pretendidos de sentimento devem ser revisados antes de avaliar a saída;
ambiguidade será registrada em vez de forçar acerto. Sentimento textual não determina
alerta e não é emoção acústica. Extrações da LLM não prescrevem nem decidem alertas.

A01–A06 são development; A07–A12 evaluation. A02/A06 e A08/A12 são pares dependentes,
tratados como grupos, não quatro exemplos independentes. Todo o conteúdo é conhecido
neste projeto: divisão serve para evitar ajuste nos casos finais, não prova avaliação
cega. Registrar qualquer consulta/ajuste; mesma voz em ambas não testa novo locutor.
Comparação limpo/ruído tem apenas um par por divisão, sem conclusão estatística geral.
Nenhum limiar clínico ou meta de WER foi validado aqui.
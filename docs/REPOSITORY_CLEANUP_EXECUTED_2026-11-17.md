# Limpeza autorizada — execução de 17/11/2026

O usuário aprovou a lista exata de 86 caminhos (referência do acervo local, não distribuída). Todos os hashes continuavam correspondentes à proposta.

## Procedimento executado

1. Inventário com exclusão das áreas privadas e links/junctions.
2. Regressão anterior à remoção: 1.216 testes e 341 subcasos em 78,52 s.
3. Checkpoint Git **c580e7f5c865518788474a581a54804df9acfb4c**. Textos e metadados verificados por hash no commit. Binários não foram versionados: as86 cópias completas foram preservadas e verificadas em uma área local ignorada, identificada no recibo.
4. Validação absoluta dos86 alvos dentro do workspace, rejeição de links e caminhos privados e nova checagem de cada hash.
5. Remoção individual dos86 arquivos, sem exclusão recursiva de diretórios e sem uso de limpeza automática do Git.
6. Atualização de11 links em quatro documentos que apontavam aos guias removidos.

Bases, mídias de trabalho, modelos, evidências necessárias ao aplicativo, código reutilizável, UI clássica, lições e comentários do autor permanecem preservados. O ZIP de backup informado pelo usuário não foi aberto. Nenhum push ou download foi executado.

## Verificação posterior

A primeira rodada pós-limpeza apresentou um timeout de um teste de UI e avisos de descarte de variáveis Tk no thread de worker. Não foi identificada dependência de arquivo removido. A fixture passou a coletar ciclos de objetos Tk no thread principal entre testes; manteve-se o prazo original de quatro segundos do worker. Rodada direcionada:35 testes em26,61 s. A primeira rodada e seus avisos permanecem no recibo/XML, sem ocultação.

Resultado final da regressão completa: **1.216 testes e 341 subcasos aprovados em 64,80 s**, sem falhas.

## Rastreabilidade

- Recibo dos86 arquivos removidos e hashes (referência do acervo local, não distribuída).
- Checkpoint e cópias verificadas (referência do acervo local, não distribuída).
- Links atualizados (referência do acervo local, não distribuída).
- Dados usados nas figuras do relatório (referência do acervo local, não distribuída).

Esse recibo substitui os links operacionais para guias removidos. Registros históricos que apenas citam nomes de arquivos preservam seu sentido histórico; não são instruções de execução atual.

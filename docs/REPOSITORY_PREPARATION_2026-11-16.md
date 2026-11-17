# Preparação do repositório — 16/11/2026

## Resultado concreto

Destino: https://github.com/dharmasistemas/MedAssistMultimodal

Foi preparada uma cópia enxuta e independente em **`dist/repository-preview-20261116-204058`**, com **341 arquivos / 1639366 bytes**. Ela tem um repositório Git próprio, branch main, origin configurado e commit local **`a3af6b787f1f96675df62b1beffe928317329463`**. Nenhum push foi executado. A seleção explícita não inclui backups, vídeos, vozes, modelos binários, bancos, evidências operacionais nem slides de apresentação.

O Git original da raiz conserva seu histórico e alterações preexistentes. Não foi resetado ou substituído. A cópia de publicação não leva esse histórico antigo: contém somente o código/contratos/testes/documentação selecionados. A pasta dist é ignorada pelo Git da raiz.

## O que mudou

- README atual, com instalação e execução da interface final.
- Guias INSTALLATION, DATA_AND_MODELS, RESULTS e DELIVERY.
- `prepare_demo.py` gera dados sintéticos e uma base nova com V01/V02/E01/E02/E03, sem mídia, ASR, LLM ou rede; dados existentes divergentes são rejeitados, nunca sobrescritos.
- `scripts/start_app.ps1 -Demo` prepara essa base e abre a UI. `-Database` abre uma base existente.
- Prescrições P01–P17 podem usar um manifesto sintético gerado. O fallback para o recibo antigo permanece para instalações anteriores.
- Requisitos de UI/dev e manifesto de release atualizados; mensagens obsoletas do diagnóstico legado corrigidas.
- `.gitignore` ampliado para mídias, modelos e diretórios de preparação. `.gitattributes` mantém os bytes exatos necessários aos planos congelados, inclusive após checkout Windows.

Código de domínio, providers, UI clássica e testes foram preservados. Pequenos JSON históricos de textos fictícios/metadados permanecem na seleção porque a regressão de planos congelados depende deles. Excluir tudo que pareça intermediário quebraria esses testes e parte da rastreabilidade.

## Verificações concluídas

| Verificação | Resultado |
| --- | --- |
| Regressão completa na cópia enxuta | **1.216 testes e 341 subcasos**, 66,80 s, zero falhas |
| Planos congelados e bootstrap após checkout | **36 testes**, 4,79 s |
| Ajuste final do diagnóstico legado | **2 testes**, 0,19 s |
| Checkout Git | 341 arquivos com hashes idênticos ao manifesto |
| Bootstrap sem histórico privado | Cinco sessões sintéticas criadas no checkout; nenhuma inferência/modelo |
| UI no checkout | Cinco sessões consultadas, E02 visível, sem erros de callback e banco inalterado pela consulta |
| Scanner sobre a seleção completa | Zero achados nos padrões conferidos; nenhum binário de mídia/modelo/banco |

A primeira rodada encontrou uma exigência antiga de documentos de baseline no manifesto de release; foi atualizada antes da rodada aprovada. Também foi corrigida a normalização de fim de linha do Git, e os blobs/checkout finais foram conferidos por hash. Essas correções não alteraram resultados experimentais históricos.

O checkout foi testado usando o Conda existente. **Não houve nova instalação de dependências em ambiente vazio**, download pesado ou execução real dos fluxos de mídia na cópia. Isso permanece uma distinção importante: início rápido sintético verificável não equivale a reprodução automática das avaliações reais sem seus ativos autorizados.

## Limpeza local proposta

Lista exata: 86 arquivos candidatos (referência do acervo local, não distribuída), total de 2414320 bytes, com hashes/cabeçalhos no manifesto JSON. São guias diários não necessários ao snapshot, protótipos/temporários e recibos antigos sem dependência identificada na seleção. As fontes citadas pelo relatório, comentários do autor, lições, governança, dados e evidências locais permanecem preservadas.

**Nenhum arquivo foi excluído.** Conforme AGENTS.md, regra3: “Remoção somente após aprovação expressa do usuário para lista exata, com Git limpo/commit de segurança e testes de regressão”. O ZIP informado pelo usuário foi considerado como informação de backup, sem abertura ou inspeção. A raiz ainda contém alterações preexistentes; a etapa de exclusão terá de satisfazer a condição de checkpoint de segurança e reconferir cada hash antes de remover arquivos individualmente. Referências de índices históricos devem ser ajustadas nessa etapa.

## Como conferir agora

1. Abra o README da pasta de publicação acima. Confira os quatro guias operacionais e os avisos sobre dados externos.
2. Execute `scripts/start_app.ps1 -Demo` dessa pasta no ambiente do projeto. Isso cria somente uma nova base sintética nessa cópia.
3. Consulte Vitais/Prescrições, revisão e prévia/exportação. Não precisa executar Whisper, GPT-OSS ou vídeo para conferir a preparação.
4. Revise a lista exata de limpeza. O próximo passo proposto é executar somente essa lista após aprovação e segurança Git.
5. Publicação deve usar o repositório da cópia enxuta, não um envio indiscriminado da raiz. O push ainda não foi autorizado/executado nesta preparação; o conteúdo está disponível para conferência local.

O relatório final segue em revisão do autor. Seu cabeçalho recebeu somente a URL de repositório informada, sem afirmar publicação ou commit final de entrega. O vídeo continua externo e seu link permanece pendente.

## Manifestos

- `reports/REPOSITORY_PUBLICATION_MANIFEST_2026-11-16.json`: lista exata publicável e hashes.
- `reports/REPOSITORY_GIT_PREPARATION_2026-11-16.json`: commit local e estado da cópia.
- `reports/REPOSITORY_CHECKOUT_CHECK_2026-11-16.json`: checkout e UI sem histórico privado.
- `reports/REPOSITORY_PUBLICATION_SCAN_2026-11-16.json`: scanner limitado aos padrões indicados, não garantia absoluta de segurança.
- `reports/REPOSITORY_PREVIEW_TESTS_FINAL_2026-11-16.xml`: resultado formal da regressão.
- `reports/REPOSITORY_CLEANUP_CANDIDATES_2026-11-16.json`: proposta não executada de exclusões.


## Atualização de17/11/2026

Usuário aprovou a lista e os86arquivos foram removidos individualmente após checkpoint e conferência de hashes. O texto anterior registra a situação da proposta em16/11. Resultado e verificações atuais no [recibo da limpeza](REPOSITORY_CLEANUP_EXECUTED_2026-11-17.md).

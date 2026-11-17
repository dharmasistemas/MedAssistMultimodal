# Janela transparente ao trocar de monitor — 16/11/2026

## Diagnóstico reproduzido

A biblioteca CustomTkinter reduz o atributo `-alpha` para 0,15 ao detectar mudança de escala/DPI no Windows. Ela atualiza o layout e, ao terminar, restaura alpha para 1. Um erro nessa atualização pode interromper a restauração.

Na aplicação, a adaptação de botões ttk para CTk preservava a posição com `pack(before=...)`. O controle usado como referência podia ser outro botão antigo, ocultado na sequência. CustomTkinter guarda essas opções e as reaplica quando o DPI muda. A simulação na janela real reproduziu `TclError: window ... isn't packed` no reposicionamento de CTkButton. Isso interrompia o ciclo entre reduzir e restaurar a opacidade. A reprodução explica o sintoma, embora não tenha sido possível testar fisicamente o segundo monitor do usuário: somente um monitor ficou visível ao processo de teste.

## Correção

- Após inserir os botões na ordem correta, reconfigurar pack com opções estáveis, sem referências temporárias before/after. Isso preserva a ordem atual e permite reescala.
- A janela principal passa a ser OpaqueCTk, uma subclasse local que mantém alpha=1 nas tentativas de alterar opacidade. Consultas ao atributo e outras opções de janela continuam normais. É proteção adicional, não substituição da correção do layout.
- Manter DPI automático, fontes, tema e modo clássico. Não editar a biblioteca instalada nem alterar configurações de escala do Windows.

Arquivos: `src/medassistmultimodal/desktop_custom.py`, `desktop_multimodal.py`, `tests/unit/test_monitor_opacity.py` e `tests/unit/test_desktop_custom.py`.

## Como conferir no ensaio

1. Fechar a janela antiga pelo botão de fechar, aguardando o encerramento normal se estiver processando. Uma instância já aberta não carrega a correção.
2. Reabrir com o comando habitual da UI CustomTkinter e a base de ensaio.
3. Restaurar a janela se necessário, arrastar da tela 1 para a tela 2 e maximizar novamente. Pode usar Win+Shift+Seta para mover a janela entre monitores.
4. Aguardar alguns segundos, alternar as quatro abas e conferir opacidade, tamanho dos controles e rolagem.
5. Repetir o movimento de volta. Não é necessário processar arquivos, chamar GPT-OSS ou mudar os dados para conferir esta correção.

Não é necessário igualar as escalas das duas telas. A simulação corrigida alternou 100%, 150% e 125% sem erro de callback e com alpha=1. A conferência física das duas telas pelo usuário permanece necessária. O reparo não declara concluída a avaliação integrada final.

Recibos: `reports/MONITOR_OPACITY_CHECK_2026-11-16.json` e inventário próprio. Nenhuma alteração de banco, mídia, modelo ou pacote instalado.

Fontes primárias: [rotina de DPI do CustomTkinter](https://github.com/TomSchimansky/CustomTkinter/blob/master/customtkinter/windows/widgets/scaling/scaling_tracker.py), [escala automática](https://customtkinter.tomschimansky.com/tutorial/scaling/). O diagnóstico principal foi conferido também no código da versão instalada e na reprodução local.

## Testes desta correção

Primeira rodada direcionada:43 aprovados em28,71s. Após corrigir a causa de pack, a janela real passou pela reescala100/150/125% sem erros. A regressão completa atingiu100% sem falhas exibidas, mas houve reinicialização do runtime antes do resumo de encerramento: essa rodada não é declarada aprovada. A conferência física dos monitores permanece pendente.

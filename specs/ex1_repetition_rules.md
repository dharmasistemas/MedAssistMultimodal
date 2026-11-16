# Ex1 — regras experimentais v1

31/10/2026. Entrada: intervalos inclusivos anotados, cam1, world 3D documentado
no dataset. Não é segmentação automática. Sem transformação implícita dos NPY 2D.
3D estimado não é ground truth cinemático nem calibração física. Não inferir gravidade;
tronco indisponível. Não há validação de plano frontal nem compensação da câmera.

Configuração: configs/ex1_rules_v1.json; versão e SHA-256 no relatório.
Visibilidade mínima .5 inclusive; cobertura por medida .8 inclusive do total esperado,
incluindo frames ausentes. Não interpolar, suavizar ou remover índices.
Cotovelo: desvio se fração de frames válidos com ângulo <150° for >=.2.
Elevação: desvio se máximo braço–tronco <80°. Igualdade não dispara limiar angular.
Esses valores são escolhas experimentais iniciais, sem referência clínica universal,
fixados antes da execução de desenvolvimento e sem otimização pelos rótulos.
Elevação baixa é proxy de amplitude; não equivale a ERR_LOW_ABDUCTION confirmado.
Cotovelo flexionado é proxy geométrico, sem diagnóstico. Não implementados:
ERR_ARM_FORWARD, ERR_ELEVATED_SHOULDER, ERR_HEAD_TO_SIDE. Por isso, ausência dos dois
desvios não significa repetição correta. overall_correctness e confidence = null.

Resultado por regra: deviation/no_deviation/not_analyzable, cobertura, frame e tempo
nominal (índice/30), evidence_ref, configuração, pending_review. Evidência de flexão:
menor ângulo; elevação: pico. Regras não são eventos persistidos nem alertas clínicos.
Amostras locais retêm medidas por frame; relatório público contém resumo sem nomes.
Falha de arquivo/NPY gera erro explícito do loader; dados insuficientes geram abstenção.
Cam diferente de 1 é indisponível neste perfil; orientação é estratificação registrada,
sem alegar que 3D elimina os efeitos de view. Avaliação futura deve reportar cobertura
por participante/orientação e comparar cada proxy com rótulo específico, nunca usar
os dois proxies como classificador binário de todos os erros do Ex1.

Grupo: três participantes de desenvolvimento, 334 repetições; grupos v1 preservados.
Parâmetros v1 congelados para avaliação futura; qualquer mudança deve criar nova versão
antes de abrir avaliação, sem ajuste retroativo pelo resultado daquele grupo.

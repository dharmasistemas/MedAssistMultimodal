"""Factual Portuguese presentation shared by the UI and exported summary."""
REASONS={'plan_missing':'Plano de mudanças esperadas ausente.',
    'identity_mismatch':'Plano e versões pertencem a identidades/conjuntos diferentes.',
    'base_mismatch':'O plano não corresponde ao hash da versão anterior.',
    'version_mismatch':'Plano incompatível com a versão de destino.',
    'plan_time_incompatible':'Declaração do plano fora do intervalo entre as versões.',
    'unit_change_not_interpreted':'Mudança de unidade; equivalência não interpretada.',
    'differs_from_declared_plan':'Estado observado diverge do plano sintético declarado.',
    'matches_declared_plan':'Estado observado corresponde ao plano sintético declarado.'}


def expectation_lines(document):
    if 'expectation' not in document:return ['Expectativa: não avaliada nesta comparação histórica.']
    result=document['expectation']
    titles={'compatible':'Compatível com o plano sintético',
        'divergent':'Divergência do plano sintético — requer revisão',
        'indeterminate':'Expectativa indeterminada'}
    lines=[titles[result['status']],REASONS[result['reason']],
        'Não determina erro terapêutico nem recomenda tratamento.']
    plan=document['expectation_plan']
    if plan is not None:
        lines.append(f"Plano declarado em {plan['declared_at']} | Versão prevista: {plan['target_version']}")
    for item in result['differences']:
        lines.append(f"• {item['item_id']} | {item['field']} | Esperado: {item['expected']} | Observado: {item['observed']}")
    return lines

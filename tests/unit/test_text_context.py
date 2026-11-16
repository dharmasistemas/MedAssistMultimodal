import pytest
from medassistmultimodal.domain.text_context import detect_term_contexts
from medassistmultimodal.application.analyze_report_text import analyze_report_text


@pytest.mark.parametrize('text,contexts',[
    ('Senti dor.', ['affirmed_current']),
    ('Não senti dor e não tive falta de ar.', ['negated_current','negated_current']),
    ('Ontem senti tontura. Hoje não estou com tontura.', ['affirmed_historical','negated_current']),
    ('Se eu sentir falta de ar, vou contar. Não tenho falta de ar.', ['conditional','negated_current']),
    ('Meu irmão sentiu dor no peito. Eu não senti dor no peito.', ['third_party','negated_current']),
    ('No começo senti dor. Depois não senti mais dor.', ['affirmed_earlier_in_session','negated_current']),
    ('Talvez seja dor.', ['unknown']),
    ('Não senti dor, mas senti tontura.', ['negated_current','affirmed_current']),
    ('Sem dor nem tontura.', ['negated_current','negated_current']),
    ('DOR NO PEITO e falta de ar.', ['affirmed_current','affirmed_current']),
    ('adoro exercício sem problemas.', []),
    ('Fiz o exercício e terminei.', [])])
def test_literal_mentions_context_and_offsets(text,contexts):
    result=detect_term_contexts(text)
    assert [m.context for m in result]==contexts
    assert all(text[m.start:m.end]==m.quote for m in result)
    assert result==detect_term_contexts(text)


def test_longest_term_and_repeated_occurrences_preserved():
    r=detect_term_contexts('dor no peito e dor no peito')
    assert len(r)==2 and all(m.term=='dor no peito' for m in r)


@pytest.mark.parametrize('text',[None,'','a'*4001])
def test_invalid_input(text):
    with pytest.raises(ValueError):detect_term_contexts(text)


def test_no_provider_still_yields_rules():
    r=analyze_report_text('Senti tontura.')
    assert len(r.mentions)==1 and r.analysis is None and r.provider_error=='provider_not_configured'

"""Experimental deterministic mention contexts; no diagnosis, urgency or alerts."""
from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class TermMention:
    term: str
    start: int
    end: int
    quote: str
    context: str
    sentence: str
    rule_version: str = 'context-terms-v1'


def detect_term_contexts(text: str) -> tuple[TermMention,...]:
    if not isinstance(text,str) or not text.strip() or len(text)>4000:
        raise ValueError('Nonempty text up to 4000 characters required')
    results=[]
    for sentence in re.finditer(r'[^.!?\n]+',text):
        segment=sentence.group()
        for match in re.finditer(r'\b(dor no peito|falta de ar|tontura|dor)\b',segment,re.I):
            prefix=segment[:match.start()].lower()
            prefix=re.split(r'\b(?:mas|porém)\b',prefix)[-1]
            if re.search(r'\b(?:talvez|não sei|pode ser|será)\b',prefix):context='unknown'
            elif re.search(r'\b(?:meu irmão|minha irmã|minha mãe|meu pai|ele|ela)\b',prefix):context='third_party'
            elif re.search(r'\bse\b',prefix):context='conditional'
            elif re.search(r'\b(?:não|nunca|sem|nem)\b',prefix):context='negated_current'
            elif re.search(r'\b(?:ontem|antigamente|semana passada)\b',prefix):context='affirmed_historical'
            elif re.search(r'\b(?:no começo|no início|antes)\b',prefix):context='affirmed_earlier_in_session'
            else:context='affirmed_current'
            start=sentence.start()+match.start();end=sentence.start()+match.end()
            results.append(TermMention(match.group().lower(),start,end,text[start:end],context,segment.strip()))
    return tuple(results)

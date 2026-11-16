"""Métricas binárias por regra com abstenção explícita; sem dependências externas."""
from dataclasses import dataclass
from collections.abc import Iterable


@dataclass(frozen=True)
class RuleObservation:
    participant_ref: str
    orientation: int
    positive: bool
    status: str

    def __post_init__(self):
        if not isinstance(self.participant_ref,str) or not self.participant_ref.strip():
            raise ValueError('Referência obrigatória')
        if type(self.orientation) is not int or not 0<=self.orientation<=90:
            raise ValueError('Orientação inválida')
        if type(self.positive) is not bool or self.status not in {'deviation','no_deviation','not_analyzable'}:
            raise ValueError('Rótulo/status inválido')


def binary_metrics(observations: Iterable[RuleObservation]) -> dict:
    rows=tuple(observations)
    if any(not isinstance(r,RuleObservation) for r in rows):raise ValueError('Observações tipadas obrigatórias')
    tp=fp=tn=fn=ap=an=0
    for row in rows:
        if row.status=='not_analyzable':
            if row.positive:ap+=1
            else:an+=1
        elif row.status=='deviation':
            if row.positive:tp+=1
            else:fp+=1
        elif row.positive:fn+=1
        else:tn+=1
    def ratio(n,d):return n/d if d else None
    return {'eligible':len(rows),'analyzable':tp+fp+tn+fn,
        'tp':tp,'fp':fp,'tn':tn,'fn':fn,'abstained_positive':ap,'abstained_negative':an,
        'precision':ratio(tp,tp+fp),'recall_analyzable':ratio(tp,tp+fn),
        'f1_analyzable':ratio(2*tp,2*tp+fp+fn),
        'coverage':ratio(tp+fp+tn+fn,len(rows)),
        'positive_coverage':ratio(tp+fn,tp+fn+ap),'negative_coverage':ratio(tn+fp,tn+fp+an),
        'effective_positive_detection':ratio(tp,tp+fn+ap)}


def stratified_metrics(rows: Iterable[RuleObservation]) -> dict:
    rows=tuple(rows)
    return {'overall':binary_metrics(rows),
        'by_participant':{p:binary_metrics(r for r in rows if r.participant_ref==p) for p in sorted({r.participant_ref for r in rows})},
        'by_orientation':{str(o):binary_metrics(r for r in rows if r.orientation==o) for o in sorted({r.orientation for r in rows})}}

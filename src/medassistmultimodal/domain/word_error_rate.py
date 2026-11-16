"""Word alignment metrics, separate from transcription and clinical interpretation."""
from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True, slots=True)
class WordEdit:
    operation: str
    reference: str | None
    hypothesis: str | None


@dataclass(frozen=True, slots=True)
class WordErrorRate:
    normalization: str
    reference_words: int
    hypothesis_words: int
    substitutions: int
    deletions: int
    insertions: int
    wer: float | None
    alignment: tuple[WordEdit, ...]


def normalized_words(text: str) -> tuple[str, ...]:
    if not isinstance(text,str):raise ValueError('Text required')
    text=unicodedata.normalize('NFC',text).lower()
    # Punctuation separates tokens; accents and negation are preserved.
    text=''.join(' ' if unicodedata.category(c).startswith('P') else c for c in text)
    return tuple(text.split())


def word_error_rate(reference: str,hypothesis: str) -> WordErrorRate:
    ref,hyp=normalized_words(reference),normalized_words(hypothesis)
    costs=[[0]*(len(hyp)+1) for _ in range(len(ref)+1)]
    for i in range(len(ref)+1):costs[i][0]=i
    for j in range(len(hyp)+1):costs[0][j]=j
    for i,a in enumerate(ref,1):
        for j,b in enumerate(hyp,1):
            costs[i][j]=min(costs[i-1][j-1]+(a!=b),costs[i-1][j]+1,costs[i][j-1]+1)
    i,j=len(ref),len(hyp);edits=[]
    # Stable minimum-edit tie priority: match, substitution, deletion, insertion.
    while i or j:
        if i and j and ref[i-1]==hyp[j-1] and costs[i][j]==costs[i-1][j-1]:
            edits.append(WordEdit('match',ref[i-1],hyp[j-1]));i-=1;j-=1
        elif i and j and costs[i][j]==costs[i-1][j-1]+1:
            edits.append(WordEdit('substitution',ref[i-1],hyp[j-1]));i-=1;j-=1
        elif i and costs[i][j]==costs[i-1][j]+1:
            edits.append(WordEdit('deletion',ref[i-1],None));i-=1
        else:
            edits.append(WordEdit('insertion',None,hyp[j-1]));j-=1
    edits.reverse()
    s=sum(e.operation=='substitution' for e in edits)
    d=sum(e.operation=='deletion' for e in edits)
    ins=sum(e.operation=='insertion' for e in edits)
    return WordErrorRate('nfc-lower-punctuation-as-space-whitespace-v1',len(ref),len(hyp),s,d,ins,
                         (s+d+ins)/len(ref) if ref else None,tuple(edits))

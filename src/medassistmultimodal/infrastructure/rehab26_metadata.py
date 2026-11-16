"""Leitura estrita dos metadados v1; não abre vídeo/NPY nem exporta sujeitos."""
import csv
from dataclasses import dataclass, field
import io
from pathlib import Path
import re

SEGMENT_COLUMNS = ('video_id','exercise_id','exercise_subtype','person','repetition_number',
                   'first_frame','last_frame','person_orientation','correctness_score',
                   'error_description','additional_errors')
ERROR_COLUMNS = ('exercise_id','exercise_name','error_code','error_description')
EXERCISES = {1:'Arm abduction',6:'Squat',7:'Shoulder extension'}
ORIENTATIONS = frozenset((*range(0,91,10),45))


class MetadataValidationError(ValueError):
    """Mensagem inclui contexto/linha, sem reproduzir nomes da fonte."""


@dataclass(frozen=True, slots=True)
class ErrorDefinition:
    exercise_id: int
    exercise_name: str
    code: str
    description: str


@dataclass(frozen=True, slots=True)
class Repetition:
    video_id: str = field(repr=False)
    exercise_id: int
    exercise_subtype: str | None
    person: str = field(repr=False)
    repetition_number: int
    first_frame: int
    last_frame: int
    person_orientation: int
    correctness_score: int
    error_code: str | None
    additional_errors: tuple[str, ...]

    @property
    def key(self) -> tuple[str,int,int]:
        return self.video_id,self.person_orientation,self.repetition_number

    @property
    def frame_count(self) -> int:
        return self.last_frame-self.first_frame+1


@dataclass(frozen=True, slots=True)
class Rehab26Metadata:
    repetitions: tuple[Repetition, ...] = field(repr=False)
    errors: tuple[ErrorDefinition, ...]
    joints: tuple[str, ...]
    semantics_text: str = field(repr=False)


def _rows(text: str, columns: tuple[str,...], label: str):
    try:
        reader=csv.reader(io.StringIO(text,newline=''),delimiter=';',strict=True)
        if tuple(next(reader,())) != columns:
            raise MetadataValidationError(f'{label}: cabeçalho inválido')
        count=0
        for row in reader:
            if len(row)!=len(columns):
                raise MetadataValidationError(f'{label}: linha {reader.line_num}: quantidade de campos inválida')
            count+=1
            yield reader.line_num,dict(zip(columns,row))
        if not count: raise MetadataValidationError(f'{label}: sem registros')
    except csv.Error as error:
        raise MetadataValidationError(f'{label}: CSV malformado') from error


def _integer(value: str, label: str) -> int:
    if not re.fullmatch(r'[0-9]+',value):
        raise MetadataValidationError(f'{label}: inteiro não negativo esperado')
    try: return int(value)
    except ValueError: raise MetadataValidationError(f'{label}: inteiro inválido') from None


def _text(value: str, label: str) -> str:
    if not value or value!=value.strip():
        raise MetadataValidationError(f'{label}: texto obrigatório sem espaços externos')
    return value


def parse_errors(text: str) -> tuple[ErrorDefinition,...]:
    result=[];seen=set()
    for line,row in _rows(text,ERROR_COLUMNS,'Error_types'):
        label=f'Error_types linha {line}'
        exercise=_integer(row['exercise_id'],label)
        if exercise not in EXERCISES or row['exercise_name']!=EXERCISES[exercise]:
            raise MetadataValidationError(f'{label}: exercício/nome incompatível')
        code=_text(row['error_code'],label)
        if not re.fullmatch(r'ERR_[A-Z_]+',code):raise MetadataValidationError(f'{label}: código inválido')
        if (exercise,code) in seen:raise MetadataValidationError(f'{label}: definição duplicada')
        seen.add((exercise,code))
        result.append(ErrorDefinition(exercise,row['exercise_name'],code,_text(row['error_description'],label)))
    return tuple(result)


def parse_segmentation(text: str, errors: tuple[ErrorDefinition,...]) -> tuple[Repetition,...]:
    lookup={(error.exercise_id,error.code) for error in errors}
    result=[];seen=set();groups={}
    for line,row in _rows(text,SEGMENT_COLUMNS,'Segmentation'):
        label=f'Segmentation linha {line}'
        numbers={name:_integer(row[name],label) for name in
                 ('exercise_id','repetition_number','first_frame','last_frame','person_orientation','correctness_score')}
        exercise=numbers['exercise_id']
        person=_text(row['person'],label);video=_text(row['video_id'],label)
        if exercise not in EXERCISES or video!=f'ex{exercise}_{person}':
            raise MetadataValidationError(f'{label}: exercício/gravação incompatível')
        if row['exercise_subtype']!=('' if exercise==6 else 'right'):
            raise MetadataValidationError(f'{label}: subtipo inválido')
        if numbers['repetition_number']<1 or numbers['first_frame']>numbers['last_frame']:
            raise MetadataValidationError(f'{label}: repetição/intervalo inválido')
        if numbers['person_orientation'] not in ORIENTATIONS or numbers['correctness_score'] not in (1,5):
            raise MetadataValidationError(f'{label}: orientação/rótulo inválido')
        primary=row['error_description'] or None
        additional=tuple(row['additional_errors'].split(',')) if row['additional_errors'] else ()
        if len(set(additional))!=len(additional):raise MetadataValidationError(f'{label}: erro adicional duplicado')
        codes=((primary,) if primary else ())+additional
        if any((exercise,code) not in lookup for code in codes):
            raise MetadataValidationError(f'{label}: código desconhecido para exercício')
        if (numbers['correctness_score']==1 and codes) or (numbers['correctness_score']==5 and primary is None):
            raise MetadataValidationError(f'{label}: rótulo e erros inconsistentes')
        value=Repetition(video_id=video,person=person,exercise_subtype=row['exercise_subtype'] or None,
                         error_code=primary,additional_errors=additional,**numbers)
        if value.key in seen:raise MetadataValidationError(f'{label}: chave composta duplicada')
        seen.add(value.key);result.append(value);groups.setdefault(video,[]).append(value)
    for values in groups.values():
        ordered=sorted(values,key=lambda value:value.first_frame)
        if any(a.last_frame>=b.first_frame for a,b in zip(ordered,ordered[1:])):
            raise MetadataValidationError('Segmentation: intervalos sobrepostos na gravação')
    return tuple(result)


def parse_joints(text: str) -> tuple[str,...]:
    result=[]
    for line,raw in enumerate(text.splitlines(),start=1):
        match=re.fullmatch(r'([0-9]+): ([a-z][a-z0-9_]*)',raw)
        if match is None or int(match[1])!=line-1:
            raise MetadataValidationError(f'joint_names linha {line}: índice/nome inválido')
        result.append(match[2])
    if len(result)!=33 or len(set(result))!=33:
        raise MetadataValidationError('joint_names: esperados 33 índices/nomes distintos')
    return tuple(result)


def load_metadata(directory: Path) -> Rehab26Metadata:
    directory=Path(directory)
    if '..' in directory.parts or any(part.casefold() in {'_backup','.git'} for part in directory.parts):
        raise MetadataValidationError('Diretório não permitido')
    absolute=directory.absolute()
    for part in reversed((absolute,*absolute.parents)):
        if part.is_symlink() or part.is_junction():raise MetadataValidationError('Links não permitidos')
    def read(name):
        path=absolute/name
        if path.is_symlink() or path.is_junction():raise MetadataValidationError('Links não permitidos')
        try:
            with path.open('rb') as stream:data=stream.read(1048577)
            if len(data)>1048576:raise MetadataValidationError('Metadado excede limite de 1 MiB')
            return data.decode('utf-8')
        except (OSError,UnicodeError):
            raise MetadataValidationError(f'{name}: arquivo indisponível ou UTF-8 inválido') from None
    errors=parse_errors(read('Error_types.csv'))
    repetitions=parse_segmentation(read('Segmentation.csv'),errors)
    joints=parse_joints(read('joint_names.txt'))
    semantics=read('Segmentation.txt')
    if not semantics.strip():raise MetadataValidationError('Segmentation.txt vazio')
    return Rehab26Metadata(repetitions,errors,joints,semantics)

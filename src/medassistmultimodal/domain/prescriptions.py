"""Comparison of complete fictional documents; never recommends treatment."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import re
import unicodedata

FIELDS = ('product_code', 'dose_value', 'dose_unit', 'frequency_per_day',
          'route', 'duration_days', 'instructions')
SNAPSHOT_FIELDS = {'schema_version','subject_kind','patient_id','source_kind','source',
                   'dataset_id','participant_ref','synthetic','prescription_set_id',
                   'version','issued_at','complete','items'}


@dataclass(frozen=True, slots=True)
class PrescriptionItem:
    item_id: str
    product_code: str
    dose_value: str
    dose_unit: str
    frequency_per_day: int
    route: str
    duration_days: int
    instructions: str


@dataclass(frozen=True, slots=True)
class PrescriptionSnapshot:
    patient_id: str
    prescription_set_id: str
    version: int
    issued_at: str
    items: tuple[PrescriptionItem, ...]


@dataclass(frozen=True, slots=True)
class FieldChange:
    field: str
    before: str | int
    after: str | int


@dataclass(frozen=True, slots=True)
class PrescriptionChange:
    item_id: str
    kind: str
    before: PrescriptionItem | None
    after: PrescriptionItem | None
    field_changes: tuple[FieldChange, ...]
    unit_change_note: str | None = None


@dataclass(frozen=True, slots=True)
class PrescriptionComparison:
    processor: str
    subject_kind: str
    patient_id: str
    source_kind: str
    source: str
    prescription_set_id: str
    before: PrescriptionSnapshot
    after: PrescriptionSnapshot
    input_pair_sha256: str
    before_canonical_sha256: str
    after_canonical_sha256: str
    status: str
    included_count: int
    removed_count: int
    modified_count: int
    changes: tuple[PrescriptionChange, ...]
    clinical_validation: bool = False


def _object(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError('Missing, extra or invalid object fields')


def _text(value, empty=False):
    if not isinstance(value,str) or value != value.strip() or (not empty and not value):
        raise ValueError('Invalid text')
    return unicodedata.normalize('NFC',value)


def _positive_integer(value):
    if type(value) is not int or value <= 0:
        raise ValueError('Positive integer required, not bool')
    return value


def _timestamp(value):
    if not isinstance(value,str):
        raise ValueError('UTC timestamp required')
    try:
        dt=datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('Invalid timestamp') from exc
    if dt.utcoffset()!=timedelta(0):
        raise ValueError('Explicit UTC required')
    return dt.astimezone(timezone.utc).isoformat()


def _dose(value):
    if not isinstance(value,str) or re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',value) is None:
        raise ValueError('Dose must be unsigned decimal text')
    number=Decimal(value)
    if number <= 0:
        raise ValueError('Dose must be positive')
    # No Decimal.normalize(): it can round under the ambient Decimal context.
    result=format(number,'f')
    if '.' in result:
        result=result.rstrip('0').rstrip('.')
    return result


def _snapshot(value):
    _object(value,SNAPSHOT_FIELDS)
    expected={'schema_version':'synthetic-prescriptions-v1','subject_kind':'synthetic_patient',
              'source_kind':'synthetic','source':'synthetic-prescriptions-fixture-v1'}
    if any(value[k]!=v for k,v in expected.items()):
        raise ValueError('Unsupported schema or origin')
    if value['synthetic'] is not True or value['complete'] is not True:
        raise ValueError('Only complete synthetic snapshots accepted')
    if value['dataset_id'] is not None or value['participant_ref'] is not None:
        raise ValueError('Dataset identity forbidden')
    patient=_text(value['patient_id'])
    if re.fullmatch(r'PAT-[0-9]{3}',patient) is None:
        raise ValueError('Synthetic patient required')
    if not isinstance(value['items'],list):
        raise ValueError('Complete items list required')
    items=[]
    for item in value['items']:
        _object(item,('item_id',*FIELDS))
        unit=_text(item['dose_unit']); route=_text(item['route'])
        if unit not in ('mg','g','mL','unit') or route not in ('oral','topical'):
            raise ValueError('Unsupported unit or route')
        items.append(PrescriptionItem(_text(item['item_id']),_text(item['product_code']),
            _dose(item['dose_value']),unit,_positive_integer(item['frequency_per_day']),
            route,_positive_integer(item['duration_days']),_text(item['instructions'],empty=True)))
    if len({item.item_id for item in items})!=len(items):
        raise ValueError('Duplicate item_id')
    return PrescriptionSnapshot(patient,_text(value['prescription_set_id']),
        _positive_integer(value['version']),_timestamp(value['issued_at']),
        tuple(sorted(items,key=lambda item:item.item_id)))


def _sha(snapshot):
    from dataclasses import asdict
    canonical={**asdict(snapshot),'schema_version':'synthetic-prescriptions-v1',
        'subject_kind':'synthetic_patient','source_kind':'synthetic',
        'source':'synthetic-prescriptions-fixture-v1','synthetic':True,
        'complete':True,'dataset_id':None,'participant_ref':None}
    data=json.dumps(canonical,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def compare_prescriptions(input_bytes: bytes) -> PrescriptionComparison:
    """Parse strict JSON and compare without IO, clocks, providers or reference labels."""
    if not isinstance(input_bytes,bytes):
        raise ValueError('Original JSON bytes required')
    def reject(value):
        raise ValueError('Nonfinite JSON forbidden')
    def pairs(entries):
        result={}
        for key,value in entries:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    try:
        payload=json.loads(input_bytes.decode('utf-8'),parse_constant=reject,object_pairs_hook=pairs)
    except (UnicodeError,json.JSONDecodeError) as exc:
        raise ValueError('Invalid UTF-8 JSON') from exc
    _object(payload,('before','after'))
    before,after=(_snapshot(payload[k]) for k in ('before','after'))
    if before.patient_id!=after.patient_id or before.prescription_set_id!=after.prescription_set_id:
        raise ValueError('Snapshots belong to different patient or set')
    if after.version < before.version:
        raise ValueError('Version reversed')
    if after.version==before.version:
        if before!=after:raise ValueError('Same-version content conflict')
    elif datetime.fromisoformat(after.issued_at)<=datetime.fromisoformat(before.issued_at):
        raise ValueError('New version must have later timestamp')
    old={x.item_id:x for x in before.items}; new={x.item_id:x for x in after.items}
    changes=[]
    for identifier in sorted(old.keys()|new.keys()):
        a,b=old.get(identifier),new.get(identifier)
        if a is None:changes.append(PrescriptionChange(identifier,'included',None,b,()))
        elif b is None:changes.append(PrescriptionChange(identifier,'removed',a,None,()))
        elif a!=b:
            fields=tuple(FieldChange(f,getattr(a,f),getattr(b,f)) for f in FIELDS if getattr(a,f)!=getattr(b,f))
            note='Unit representation changed; no clinical equivalence or dose increase inferred.' if a.dose_unit!=b.dose_unit else None
            changes.append(PrescriptionChange(identifier,'modified',a,b,fields,note))
    return PrescriptionComparison('prescription-diff-v1','synthetic_patient',after.patient_id,
        'synthetic','synthetic-prescriptions-fixture-v1',after.prescription_set_id,before,after,
        hashlib.sha256(input_bytes).hexdigest(),_sha(before),_sha(after),
        'changed' if changes else 'unchanged',sum(c.kind=='included' for c in changes),
        sum(c.kind=='removed' for c in changes),sum(c.kind=='modified' for c in changes),tuple(changes))

"""Pinned pilot inputs and read-only reconstruction of standalone acoustic evidence."""
from dataclasses import asdict,replace
import hashlib
from pathlib import Path

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.application.register_acoustics import restore_acoustics
from medassistmultimodal.application.register_vitals import strict_json
from medassistmultimodal.domain.events import ReviewStatus
from medassistmultimodal.providers.whisper_local import checked_path

INVENTORY='specs/acoustic_pilot_inventory_v1.json'
RECEIPT='reports/ACOUSTIC_PILOT_LISTEN_REVIEW_2026-11-12.json'


def acoustic_source(root,case):
    try:
        receipt=strict_json(checked_path(RECEIPT,root).read_bytes())
        raw=checked_path(INVENTORY,root).read_bytes();hashes=receipt['files_sha256']
        expected=hashes.get(INVENTORY,hashes.get(INVENTORY.replace('/','\\')))
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError()
        item=next(x for x in strict_json(raw)['files'] if x.get('case_id')==case)
        if item['listen_review_status']!='reviewed_by_project_user':raise ValueError()
        return dict(case_id=case,audio_ref=item['path'],sha256=item['sha256'],origin_kind='tts',
            voice_name=item['voice_name'],voice_id=item['voice_id'],tts_model=item['model'],
            settings=item['generation_settings'],permission_declared=True,permission_ref=RECEIPT,
            inventory_sha256=expected)
    except (ValueError,KeyError,TypeError,OSError,StopIteration) as exc:raise HistoryError('scenario_unavailable') from exc


def read_acoustics(root,session,events):
    if not events:return [],[]
    references={e.evidence_ref.split('#')[0] for e in events}
    if len(references)!=1:raise ValueError('One acoustic document per session required')
    reference=references.pop();path=checked_path(reference,root)
    if not path.is_relative_to(Path(root)/'data/interim/audio/desktop_workspaces_v1'):raise ValueError('Invalid acoustic area')
    try:raw=path.read_bytes()
    except FileNotFoundError as exc:raise HistoryError('evidence_missing') from exc
    doc=strict_json(raw);restored=restore_acoustics(doc,reference)
    if restored.evidence!=raw or restored.session!=session:raise ValueError('Acoustic reconstruction differs')
    expected={e.event_id:e for e in restored.events}
    if set(expected)!={e.event_id for e in events}:raise ValueError('Incomplete acoustic event group')
    rows=[]
    for event in events:
        if replace(event,review_status=ReviewStatus.PENDING_REVIEW)!=expected[event.event_id]:raise ValueError('Acoustic event mismatch')
        fragment=event.evidence_ref.split('&item=/')[1]
        item=doc['summary'] if fragment=='summary' else doc['candidates'][0]
        meta=asdict(event);meta.update(event_id=str(event.event_id),session_id=str(event.session_id),timestamp=event.timestamp.isoformat())
        rows.append(dict(event=meta,evidence_item=item,modality='acoustics'))
    return rows,[dict(reference=reference,sha256=restored.evidence_sha256,evidence=doc)]

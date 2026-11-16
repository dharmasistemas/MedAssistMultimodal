"""Create a selected, auditable work database; never delete or rewrite the source."""
from contextlib import closing
import hashlib
import json
import sqlite3
from uuid import uuid4, UUID
from .desktop_workspace import WORKSPACES
from .sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.providers.whisper_local import checked_path


def create_rehearsal(root, source, session_ids):
    root = __import__('pathlib').Path(root).resolve()
    source = checked_path(str(source), root)
    selected = {str(UUID(str(sid))) for sid in session_ids}
    if not selected: raise ValueError('Select at least one session')
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as origin:
        origin.row_factory = sqlite3.Row
        origin.execute('BEGIN')
        sessions = [dict(r) for r in origin.execute('SELECT * FROM multimodal_sessions') if r['session_id'] in selected]
        if len(sessions) != len(selected): raise ValueError('Missing selected session')
        events = [dict(r) for r in origin.execute('SELECT * FROM multimodal_events') if r['session_id'] in selected]
        event_ids = {r['event_id'] for r in events}
        audits = []
        for row in origin.execute('SELECT * FROM audit_records'):
            record = json.loads(row['payload'])
            sids = {s['session_id'] for s in record.get('sources',[]) if s.get('session_id')}
            eids = {e['event_id'] for e in record.get('events',[]) if e.get('event_id')}
            if sids & selected or eids & event_ids:
                if not sids <= selected or not eids <= event_ids:
                    raise ValueError('Audit spans unselected sessions; select the whole group')
                audits.append(dict(row))
        patients = {s['patient_id'] for s in sessions if s['patient_id']}
        contexts = [dict(r) for r in origin.execute('SELECT * FROM synthetic_patient_contexts') if r['patient_id'] in patients]
        dependencies = {}
        for event in events:
            ref = event['evidence_ref'].split('#')[0]
            raw = checked_path(ref,root).read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            if '#sha256='+sha+'&' not in event['evidence_ref']: raise ValueError('Evidence hash mismatch')
            dependencies[ref] = sha
        workspace_id = str(uuid4())
        directory = root/WORKSPACES/workspace_id
        directory.mkdir(parents=True,exist_ok=False)
        destination = directory/'audio.sqlite3'
        with closing(sqlite3.connect(destination)) as target:
            target.execute('PRAGMA foreign_keys=ON');initialize_multimodal_schema(target)
            for table, rows in [('synthetic_patient_contexts',contexts),('multimodal_sessions',sessions),('multimodal_events',events),('audit_records',audits)]:
                for row in rows:
                    columns = ','.join(row)
                    target.execute(f"INSERT INTO {table} ({columns}) VALUES ({','.join('?' for _ in row)})",tuple(row.values()))
            target.commit()
            if target.execute('PRAGMA foreign_key_check').fetchall(): raise ValueError('Foreign key mismatch')
            if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Database integrity failed')
        (directory/'workspace.json').write_text(json.dumps(dict(version='desktop-workspace-v1',workspace_id=workspace_id)),encoding='utf-8')
        manifest = dict(source=source.relative_to(root).as_posix(),source_sha256=before,
            database=destination.relative_to(root).as_posix(),sessions=sorted(selected),events=len(events),audit_records=len(audits),
            evidence_dependencies=dependencies,independent_bundle=False,
            note='Evidence references remain unchanged; retain referenced files and original media/assets. Review states and nominal/audit times preserved.')
        (directory/'rehearsal_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=before: raise ValueError('Source changed during preparation')
    return manifest

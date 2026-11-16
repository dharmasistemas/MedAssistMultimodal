"""Prepare a new synthetic UI workspace without media, models or network calls."""
from contextlib import closing
from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from medassistmultimodal.application.patient_context import Patient, PatientContext
from medassistmultimodal.application.register_vitals import encode_json
from medassistmultimodal.demo.synthetic_vitals import build_scenarios, json_bytes, SEED
from medassistmultimodal.demo.prescription_fixtures import build_prescription_cases
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from medassistmultimodal.infrastructure.structured_workspace import StructuredWorkspace
from medassistmultimodal.infrastructure.desktop_workspace import WORKSPACES
from medassistmultimodal.providers.whisper_local import checked_path


def _write_verified(path, raw):
    """Create once, or accept identical bytes. Never overwrite existing content."""
    if path.exists():
        if not path.is_file() or path.read_bytes() != raw:
            raise ValueError(f'Existing generated input differs: {path.name}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def prepare_demo(root):
    root = Path(root).absolute()
    series, references = build_scenarios(SEED)
    bundles = {
        'vitals_v1': {f"{s['scenario_id']}.json": json_bytes(s) for s in series},
        'prescriptions_v1': {f'{key}_input.json': encode_json(value)
                             for key, value in build_prescription_cases()[0].items()},
    }
    bundles['vitals_v1']['references.json'] = json_bytes(references)
    # Preflight every existing path before writing inputs or creating a workspace.
    planned = []
    for name, payloads in bundles.items():
        manifest = encode_json(dict(schema_version='portable-synthetic-inputs-v1',
            files={key: dict(sha256=hashlib.sha256(raw).hexdigest()) for key, raw in payloads.items()}))
        for key, raw in {**payloads, 'manifest.json': manifest}.items():
            path = checked_path(f'data/synthetic/{name}/{key}', root)
            if path.exists() and (not path.is_file() or path.read_bytes() != raw):
                # Existing development vital manifests contain additional provenance.
                if name == 'vitals_v1' and key == 'manifest.json':
                    actual = json.loads(path.read_bytes())
                    expected = json.loads(manifest)
                    if any(actual['files'].get(k, {}).get('sha256') != v['sha256']
                           for k, v in expected['files'].items()):
                        raise ValueError('Existing vital manifest differs')
                    continue
                raise ValueError(f'Existing generated input differs: {path.name}')
            planned.append((path, raw))
    for path, raw in planned:
        _write_verified(path, raw)
    identifier = str(uuid4())
    directory = checked_path(f'{WORKSPACES}/{identifier}', root)
    directory.mkdir(parents=True, exist_ok=False)
    database = directory/'audio.sqlite3'
    with database.open('xb'):
        pass
    with closing(sqlite3.connect(database)) as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        initialize_multimodal_schema(connection)
        context = PatientContext(Patient('PAT-001', 'Pessoa fictícia PAT-001',
                                date(1970, 1, 1), 'not_specified', True), (), (), ())
        SQLitePatientRepository(connection).save(context)
        connection.commit()
    _write_verified(directory/'workspace.json', encode_json(dict(
        version='desktop-workspace-v1', workspace_id=identifier)))
    relative = database.relative_to(root).as_posix()
    service = StructuredWorkspace(root)
    sessions = {}
    for modality, case in [('vitals', 'V01'), ('vitals', 'V02'),
                           ('prescriptions', 'E01'), ('prescriptions', 'E02'), ('prescriptions', 'E03')]:
        outcome = service.register_scenario(relative, 'PAT-001', modality, case)
        if not outcome.persisted:
            raise ValueError(f'Could not persist {case}: {outcome.error_code}')
        sessions[case] = outcome.session_id
    result = dict(project='MedAssistMultimodal', database=relative, patient_id='PAT-001',
        source_kind='synthetic', clinical_validation=False, model_calls=0,
        sessions=sessions, note='Synthetic rules only; no video/audio or model results were generated.')
    _write_verified(directory/'demo_manifest.json', encode_json(result))
    return result


def main():
    root = Path(__file__).resolve().parents[2]
    print(json.dumps(prepare_demo(root), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

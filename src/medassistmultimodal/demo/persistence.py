"""CLI offline: gravação explícita, consulta read-only e exportação exclusiva."""
import argparse
from contextlib import closing
from dataclasses import asdict
from datetime import date, datetime
import json
from pathlib import Path
import sqlite3
import sys
from uuid import UUID, uuid5, NAMESPACE_URL

from .fixtures import build_demo_cases
from medassistmultimodal.application.patient_context import Patient, PatientContext
from medassistmultimodal.application.register_multimodal_session import RegisterMultimodalSession
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_multimodal_unit_of_work import SQLiteMultimodalUnitOfWork
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from medassistmultimodal.infrastructure.sqlite_session_repository import SQLiteSessionRepository
from medassistmultimodal.infrastructure.sqlite_event_repository import SQLiteEventRepository

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE = 'data/interim/demo/medassistmultimodal.sqlite3'


def _path(value: str, suffix: str) -> Path:
    # Rejeição lexical antes de consultar qualquer caminho protegido.
    candidate = Path(value)
    if any(part.casefold() in {'_backup', '.git'} for part in candidate.parts):
        raise ValueError('Caminho privado/técnico não permitido')
    if '..' in candidate.parts:
        raise ValueError('Use caminho sem ..')
    candidate = candidate if candidate.is_absolute() else ROOT / candidate
    allowed = ROOT / 'data' / 'interim' / 'demo'
    if not candidate.is_relative_to(allowed) or candidate.suffix.lower() != suffix:
        raise ValueError(f'Use arquivo {suffix} dentro de data/interim/demo/')
    for part in reversed((candidate, *candidate.parents)):
        if part.is_symlink() or part.is_junction():
            raise ValueError('Links/junctions não são permitidos')
    return candidate


def _json(value):
    if isinstance(value, UUID): return str(value)
    if isinstance(value, datetime): return value.isoformat(timespec='microseconds')
    raise TypeError(f'Tipo não serializável: {type(value).__name__}')


def _read(database: Path, session_id: UUID | None) -> dict:
    if not database.is_file():
        raise ValueError('Banco não existe; execute persist primeiro')
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        sessions = SQLiteSessionRepository(connection)
        events = SQLiteEventRepository(connection)
        if session_id is None:
            ids = [UUID(row[0]) for row in connection.execute(
                'SELECT session_id FROM multimodal_sessions ORDER BY started_at,session_id')]
        else:
            ids = [session_id]
        cases = []
        for identifier in ids:
            session = sessions.get_by_id(identifier)
            if session is not None:
                cases.append({'session': asdict(session),
                              'events': [asdict(event) for event in events.list_for_session(identifier)]})
        return {'project': 'MedAssistMultimodal', 'mode': 'persisted_metadata',
                'clinical_validation': False, 'cases': cases}


def _persist(database: Path, reuse: bool) -> None:
    if database.exists() and not reuse:
        raise ValueError('Banco já existe; use --reuse-db para reexecutar sem substituí-lo')
    database.parent.mkdir(parents=True, exist_ok=True)
    # Criação exclusiva: não converter corrida de criação em reuso silencioso.
    if not database.exists() or not reuse:
        with database.open('xb'): pass
    with closing(sqlite3.connect(database)) as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        initialize_multimodal_schema(connection)
        patients = SQLitePatientRepository(connection)
        unit_of_work = SQLiteMultimodalUnitOfWork(connection)
        use_case = RegisterMultimodalSession(unit_of_work)
        for case in build_demo_cases():
            patient_id = case.session.subject.patient_id
            context = PatientContext(Patient(patient_id, 'Pessoa fictícia ' + patient_id,
                                             date(1970, 1, 1), 'not_specified', True), (), (), ())
            # Cadastro explícito; não sobrescrever contexto existente divergente.
            existing = patients.get_by_id(patient_id)
            if existing is not None and existing != context:
                raise ValueError('Cadastro sintético existente diverge da fixture; não será sobrescrito')
            if existing is None:
                with connection:
                    patients.save(context)
            use_case.execute(case.session, case.events, correlation_id=uuid5(
                NAMESPACE_URL, 'medassistmultimodal:demo:v1:' + str(case.session.session_id)))


def main(argv) -> int:
    parser = argparse.ArgumentParser(description='Demonstração SQLite offline; somente metadados artificiais.')
    subparsers = parser.add_subparsers(dest='command', required=True)
    for name in ('persist', 'list', 'export'):
        sub = subparsers.add_parser(name)
        sub.add_argument('--database', default=DEFAULT_DATABASE)
        if name == 'persist': sub.add_argument('--reuse-db', action='store_true')
        else: sub.add_argument('--session-id', type=UUID)
        if name == 'export': sub.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        database = _path(args.database, '.sqlite3')
        if args.command == 'persist':
            _persist(database, args.reuse_db)
        payload = _read(database, getattr(args, 'session_id', None))
        text = json.dumps(payload, default=_json, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.command == 'export':
            output = _path(args.output, '.json')
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('x', encoding='utf-8') as stream:
                stream.write(text)
        print(text, end='')
        return 0
    except (ValueError, OSError, sqlite3.Error) as error:
        print(f'Erro: {error}', file=sys.stderr)
        return 2

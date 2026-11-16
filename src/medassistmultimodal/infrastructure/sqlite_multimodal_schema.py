"""Inicialização explícita e transacional do componente multimodal v1."""
import re
import sqlite3

from .sqlite_patient_repository import SQLitePatientRepository
from .sqlite_audit_repository import SQLiteAuditRepository

DDL = (
    """CREATE TABLE multimodal_schema_versions (
        component TEXT NOT NULL PRIMARY KEY CHECK(component = 'sessions_events'),
        version INTEGER NOT NULL CHECK(version >= 1))""",
    """CREATE TABLE multimodal_sessions (
        session_id TEXT NOT NULL PRIMARY KEY,
        subject_kind TEXT NOT NULL CHECK(subject_kind IN ('synthetic_patient','dataset_participant')),
        patient_id TEXT REFERENCES synthetic_patient_contexts(patient_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
        dataset_id TEXT, participant_ref TEXT, started_at TEXT NOT NULL,
        CHECK ((subject_kind = 'synthetic_patient' AND patient_id IS NOT NULL
                AND length(patient_id)=7 AND patient_id GLOB 'PAT-[0-9][0-9][0-9]'
                AND dataset_id IS NULL AND participant_ref IS NULL)
            OR (subject_kind = 'dataset_participant' AND patient_id IS NULL
                AND dataset_id IS NOT NULL AND length(trim(dataset_id))>0 AND dataset_id=trim(dataset_id)
                AND participant_ref IS NOT NULL AND length(trim(participant_ref))>0
                AND participant_ref=trim(participant_ref))))""",
    """CREATE TABLE multimodal_events (
        event_id TEXT NOT NULL PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES multimodal_sessions(session_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
        source_kind TEXT NOT NULL CHECK(source_kind IN ('synthetic','simulated','dataset')),
        source TEXT NOT NULL CHECK(length(trim(source))>0 AND source=trim(source)),
        timestamp TEXT NOT NULL,
        confidence REAL CHECK(confidence IS NULL OR confidence BETWEEN 0 AND 1),
        evidence_ref TEXT NOT NULL CHECK(length(trim(evidence_ref))>0 AND evidence_ref=trim(evidence_ref)),
        review_status TEXT NOT NULL DEFAULT 'pending_review'
            CHECK(review_status IN ('pending_review','reviewed','dismissed')),
        processor TEXT CHECK(processor IS NULL OR (length(trim(processor))>0 AND processor=trim(processor))),
        is_mock INTEGER NOT NULL CHECK(is_mock IN (0,1)),
        CHECK(is_mock=0 OR processor IS NOT NULL))""",
    "CREATE INDEX idx_multimodal_patient ON multimodal_sessions(patient_id,started_at,session_id)",
    "CREATE INDEX idx_multimodal_participant ON multimodal_sessions(dataset_id,participant_ref,started_at,session_id)",
    "CREATE INDEX idx_multimodal_events_session ON multimodal_events(session_id,timestamp,event_id)",
    """CREATE TRIGGER multimodal_session_identity_immutable
        BEFORE UPDATE OF session_id,subject_kind,patient_id,dataset_id,participant_ref ON multimodal_sessions
        WHEN NEW.session_id IS NOT OLD.session_id OR NEW.subject_kind IS NOT OLD.subject_kind
          OR NEW.patient_id IS NOT OLD.patient_id OR NEW.dataset_id IS NOT OLD.dataset_id
          OR NEW.participant_ref IS NOT OLD.participant_ref
        BEGIN SELECT RAISE(ABORT,'session identity is immutable'); END""",
)
DDL += tuple(
    f"""CREATE TRIGGER multimodal_event_source_{operation.lower()}
        BEFORE {operation} ON multimodal_events
        WHEN NOT EXISTS (SELECT 1 FROM multimodal_sessions s WHERE s.session_id=NEW.session_id
            AND ((s.subject_kind='dataset_participant' AND NEW.source_kind='dataset')
              OR (s.subject_kind='synthetic_patient' AND NEW.source_kind IN ('synthetic','simulated'))))
        BEGIN SELECT RAISE(ABORT,'event source incompatible with session'); END"""
    for operation in ('INSERT', 'UPDATE')
)


def require_foreign_keys(connection: sqlite3.Connection) -> None:
    if connection.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
        raise ValueError('Habilite PRAGMA foreign_keys=ON antes da transação')


def _objects(connection):
    return {row[0]: (row[1], row[2]) for row in connection.execute(
        "SELECT name,type,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"
    )}


def _normalized(sql):
    return re.sub(r'\s+', ' ', sql.strip())


def initialize_multimodal_schema(connection: sqlite3.Connection) -> None:
    """Não aceita transação ativa nem modifica schema desconhecido."""
    require_foreign_keys(connection)
    if connection.in_transaction:
        raise ValueError('Inicialização exige conexão sem transação ativa')
    with sqlite3.connect(':memory:') as reference:
        SQLitePatientRepository(reference).initialize()
        SQLiteAuditRepository(reference).initialize()
        baseline = _objects(reference)
        for statement in DDL:
            reference.execute(statement)
        expected = _objects(reference)
    # Validação e criação sob a mesma trava de escrita; não há executescript/commit implícito.
    connection.execute('BEGIN IMMEDIATE')
    try:
        actual = _objects(connection)
        for name, (kind, sql) in expected.items():
            if name in actual and (actual[name][0] != kind or _normalized(actual[name][1]) != _normalized(sql)):
                raise ValueError(f'Schema incompatível: {name}')
        component_names = set(expected) - set(baseline)
        present = component_names.intersection(actual)
        if present:
            if present != component_names:
                raise ValueError('Schema multimodal parcial ou sem versão')
            rows = connection.execute('SELECT component,version FROM multimodal_schema_versions').fetchall()
            if [tuple(row) for row in rows] != [('sessions_events', 1)]:
                raise ValueError('Versão multimodal não suportada')
            if not set(baseline).issubset(actual):
                raise ValueError('Schema baseline incompleto')
        else:
            SQLitePatientRepository(connection).initialize()
            SQLiteAuditRepository(connection).initialize()
            for statement in DDL:
                connection.execute(statement)
            connection.execute('INSERT INTO multimodal_schema_versions VALUES (?,?)', ('sessions_events', 1))
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def require_multimodal_version(connection: sqlite3.Connection) -> None:
    require_foreign_keys(connection)
    try:
        versions = connection.execute(
            'SELECT component,version FROM multimodal_schema_versions').fetchall()
    except sqlite3.DatabaseError as error:
        raise ValueError('Inicialize o schema multimodal antes de usar o repositório') from error
    if [tuple(row) for row in versions] != [('sessions_events', 1)]:
        raise ValueError('Versão multimodal não suportada')

"""Porta de auditoria reutilizada com SQLite local e SQL parametrizado."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict

from medassistmultimodal.application.audit import AuditRecord
from medassistmultimodal.application.redaction import redact_audit_events, redact_secrets


class SQLiteAuditRepository:
    """O chamador controla commit/rollback; correlation_id garante idempotência."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def initialize(self) -> None:
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS audit_records (
                audit_record_id INTEGER PRIMARY KEY,
                correlation_id TEXT NOT NULL UNIQUE,
                patient_id TEXT,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            )
        """)
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_patient ON audit_records(patient_id)"
        )

    def save(self, record: AuditRecord) -> int:
        # Redigir também objetos aninhados antes de qualquer persistência.
        safe = redact_audit_events((asdict(record),))[0]
        payload = json.dumps(safe, ensure_ascii=False, sort_keys=True, allow_nan=False)
        existing = self.connection.execute(
            "SELECT audit_record_id, payload FROM audit_records WHERE correlation_id = ?",
            (record.correlation_id,),
        ).fetchone()
        if existing is not None:
            if existing[1] != payload:
                raise ValueError("correlation_id já existe com conteúdo diferente")
            return int(existing[0])
        cursor = self.connection.execute(
            "INSERT INTO audit_records(correlation_id, patient_id, payload) VALUES (?, ?, ?)",
            (record.correlation_id, redact_secrets(record.patient_id), payload),
        )
        return int(cursor.lastrowid)

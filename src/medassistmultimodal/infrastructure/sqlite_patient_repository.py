"""Persiste somente contextos de pacientes sintéticos em SQLite."""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict
from datetime import date, datetime

from medassistmultimodal.application.patient_context import (
    Patient, PatientContext, Encounter, Exam, PendingExam,
)

PATIENT_ID_PATTERN = re.compile(r"^PAT-[0-9]{3}$")


def _patient_id(value: str) -> str:
    normalized = value.strip().upper()
    if not PATIENT_ID_PATTERN.fullmatch(normalized):
        raise ValueError("patient_id deve seguir o formato PAT-000")
    return normalized


class SQLitePatientRepository:
    """Preserva os mapeamentos de domínio; o chamador controla transações."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def initialize(self) -> None:
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS synthetic_patient_contexts (
                patient_id TEXT PRIMARY KEY,
                synthetic INTEGER NOT NULL CHECK (synthetic = 1),
                payload TEXT NOT NULL
            )
        """)

    def save(self, context: PatientContext) -> None:
        if not context.patient.synthetic:
            raise ValueError("Somente pacientes sintéticos são permitidos")
        patient_id = _patient_id(context.patient.patient_id)
        if patient_id != context.patient.patient_id:
            raise ValueError("Use patient_id canônico PAT-000 ao persistir")
        payload = json.dumps(asdict(context), ensure_ascii=False,
                             default=lambda value: value.isoformat(), allow_nan=False)
        self.connection.execute(
            "INSERT INTO synthetic_patient_contexts(patient_id, synthetic, payload) "
            "VALUES (?, 1, ?) ON CONFLICT(patient_id) DO UPDATE SET payload=excluded.payload",
            (patient_id, payload),
        )

    def get_by_id(self, patient_id: str) -> PatientContext | None:
        row = self.connection.execute(
            "SELECT payload FROM synthetic_patient_contexts WHERE patient_id = ?",
            (_patient_id(patient_id),),
        ).fetchone()
        if row is None:
            return None
        data = json.loads(row[0])
        patient = data["patient"]
        patient["birth_date"] = date.fromisoformat(patient["birth_date"])
        for encounter in data["encounters"]:
            encounter["occurred_at"] = datetime.fromisoformat(encounter["occurred_at"])
        for exam in data["exams"]:
            exam["collected_at"] = datetime.fromisoformat(exam["collected_at"])
        for pending in data["pending_exams"]:
            pending["requested_at"] = datetime.fromisoformat(pending["requested_at"])
            if pending["scheduled_for"] is not None:
                pending["scheduled_for"] = datetime.fromisoformat(pending["scheduled_for"])
        return PatientContext(
            patient=Patient(**patient),
            encounters=tuple(Encounter(**value) for value in data["encounters"]),
            exams=tuple(Exam(**value) for value in data["exams"]),
            pending_exams=tuple(PendingExam(**value) for value in data["pending_exams"]),
        )

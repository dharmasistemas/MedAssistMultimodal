"""
Valida a minimização do contexto enviado a providers remotos.

Os testes confirmam que identificadores e datas exatas são removidos,
preservando informações clínicas necessárias.
"""

import unittest
from datetime import date, datetime, timezone

from medassistmultimodal.application.patient_context import (
    Encounter,
    Exam,
    Patient,
    PatientContext,
    PendingExam,
)
from medassistmultimodal.application.privacy import (
    build_minimized_patient_text,
)


def create_patient_context() -> PatientContext:
    """Cria um prontuário sintético completo para os testes."""
    occurred_at = datetime(
        2026,
        8,
        20,
        12,
        0,
        tzinfo=timezone.utc,
    )

    return PatientContext(
        patient=Patient(
            patient_id="PAT-001",
            display_name="Paciente Sintético 001",
            birth_date=date(1980, 5, 14),
            biological_sex="female",
            synthetic=True,
        ),
        encounters=(
            Encounter(
                encounter_id="ENC-001",
                occurred_at=occurred_at,
                reason="Sessão simulada de reabilitação",
                clinical_notes="Movimento sintético registrado para teste.",
            ),
        ),
        exams=(
            Exam(
                exam_id="EXM-001",
                encounter_id="ENC-001",
                exam_type="Avaliação sintética de movimento",
                collected_at=occurred_at,
                result_text="Amplitude experimental registrada",
                reference_text="Referência sintética.",
                status="completed",
            ),
        ),
        pending_exams=(
            PendingExam(
                pending_exam_id="PEX-001",
                encounter_id="ENC-001",
                exam_type="Reavaliação sintética",
                requested_at=occurred_at,
                scheduled_for=occurred_at,
                status="scheduled",
            ),
        ),
    )


class PrivacyTests(unittest.TestCase):
    def test_removes_direct_identifiers_and_dates(self) -> None:
        text = build_minimized_patient_text(create_patient_context())
        for value in ("PAT-001", "Paciente Sintético 001", "1980-05-14",
                      "ENC-001", "EXM-001", "PEX-001", "2026-08-20"):
            with self.subTest(value=value):
                self.assertNotIn(value, text)

    def test_preserves_relevant_synthetic_information(self) -> None:
        context = create_patient_context()
        text = build_minimized_patient_text(context)
        for value in (context.patient.biological_sex, context.encounters[0].reason,
                      context.exams[0].exam_type, context.exams[0].result_text,
                      context.pending_exams[0].exam_type, "scheduled"):
            with self.subTest(value=value):
                self.assertIn(value, text)

    def test_minimization_does_not_mutate_internal_context(self) -> None:
        context = create_patient_context()
        build_minimized_patient_text(context)
        self.assertEqual(context, create_patient_context())
        self.assertEqual(context.patient.patient_id, "PAT-001")


if __name__ == "__main__":
    unittest.main()

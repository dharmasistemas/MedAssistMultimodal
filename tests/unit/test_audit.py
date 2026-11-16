"""
Valida o modelo de auditoria antes da persistência.

Os testes garantem UUID, decisão, operação e latência válidos.
"""

import unittest
from uuid import uuid4

from medassistmultimodal.application.audit import AuditRecord


def create_record() -> AuditRecord:
    """Cria um registro mínimo válido para os testes."""
    return AuditRecord(
        correlation_id=str(uuid4()),
        patient_id="PAT-001",
        operation="Registrar análise sintética de movimento",
        decision="human_validation",
        provider="fake",
        model="fake-model",
        sources=(),
        latency_ms=25.5,
        requires_human_validation=True,
        error_code=None,
        events=(),
    )


class AuditRecordTests(unittest.TestCase):
    def test_accepts_valid_record(self) -> None:
        """Aceita um registro com campos coerentes."""
        record = create_record()

        self.assertEqual(
            record.decision,
            "human_validation",
        )

    def test_rejects_invalid_correlation_id(self) -> None:
        """Exige um UUID válido."""
        with self.assertRaisesRegex(
            ValueError,
            "UUID válido",
        ):
            AuditRecord(
                correlation_id="invalid",
                patient_id="PAT-001",
                operation="Registrar análise sintética de movimento",
                decision="human_validation",
                provider="fake",
                model="fake-model",
                sources=(),
                latency_ms=10.0,
                requires_human_validation=True,
                error_code=None,
                events=(),
            )

    def test_rejects_unknown_decision(self) -> None:
        """Recusa decisões que não existem no contrato de auditoria."""
        with self.assertRaisesRegex(
            ValueError,
            "decision",
        ):
            AuditRecord(
                correlation_id=str(uuid4()),
                patient_id="PAT-001",
                operation="Registrar análise sintética de movimento",
                decision="unknown",
                provider=None,
                model=None,
                sources=(),
                latency_ms=None,
                requires_human_validation=False,
                error_code=None,
                events=(),
            )

    def test_rejects_empty_operation(self) -> None:
        """Impede auditoria sem a operação associada."""
        with self.assertRaisesRegex(
            ValueError,
            "operation",
        ):
            AuditRecord(
                correlation_id=str(uuid4()),
                patient_id="PAT-001",
                operation="   ",
                decision="blocked",
                provider=None,
                model=None,
                sources=(),
                latency_ms=None,
                requires_human_validation=True,
                error_code=None,
                events=(),
            )

    def test_rejects_negative_latency(self) -> None:
        """Impede persistência de latência negativa."""
        with self.assertRaisesRegex(
            ValueError,
            "latency",
        ):
            AuditRecord(
                correlation_id=str(uuid4()),
                patient_id="PAT-001",
                operation="Registrar análise sintética de movimento",
                decision="human_validation",
                provider="fake",
                model="fake-model",
                sources=(),
                latency_ms=-1.0,
                requires_human_validation=True,
                error_code=None,
                events=(),
            )


if __name__ == "__main__":
    unittest.main()
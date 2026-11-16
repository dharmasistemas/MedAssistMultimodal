"""
Minimiza dados do paciente antes de gerar textos opcionais de apresentação.

O contexto interno permanece completo. A versão minimizada remove nome,
datas exatas e identificadores de atendimentos e exames.
"""

from __future__ import annotations

from medassistmultimodal.application.patient_context import PatientContext


def build_minimized_patient_text(
    context: PatientContext,
) -> str:
    """Cria um resumo clínico sem identificadores ou datas exatas."""
    lines = [
        "Dados exclusivamente sintéticos e minimizados.",
        f"Biological sex: {context.patient.biological_sex}",
        "",
        "Relevant encounter information:",
    ]

    if context.encounters:
        for encounter in context.encounters:
            lines.extend(
                [
                    f"- Reason: {encounter.reason}",
                    f"  Notes: {encounter.clinical_notes}",
                ]
            )
    else:
        lines.append("- No encounters recorded.")

    lines.extend(
        [
            "",
            "Completed exams:",
        ]
    )

    if context.exams:
        for exam in context.exams:
            lines.extend(
                [
                    f"- Type: {exam.exam_type}",
                    f"  Result: {exam.result_text}",
                ]
            )
    else:
        lines.append("- No completed exams recorded.")

    lines.extend(
        [
            "",
            "Pending or scheduled exams:",
        ]
    )

    if context.pending_exams:
        for pending_exam in context.pending_exams:
            lines.extend(
                [
                    f"- Type: {pending_exam.exam_type}",
                    f"  Status: {pending_exam.status}",
                ]
            )
    else:
        lines.append("- No pending or scheduled exams.")

    return "\n".join(lines)

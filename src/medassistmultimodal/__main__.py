"""Verifica a base local sem serviços, downloads ou gravação de dados."""
import json
import sqlite3


def main() -> int:
    from medassistmultimodal.application.audit import AuditRecord
    from medassistmultimodal.application.patient_context import PatientContext
    from medassistmultimodal.application.privacy import build_minimized_patient_text
    from medassistmultimodal.infrastructure.sqlite_audit_repository import SQLiteAuditRepository
    from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
    with sqlite3.connect(":memory:") as connection:
        SQLiteAuditRepository(connection).initialize()
        SQLitePatientRepository(connection).initialize()
        connection.execute("SELECT 1").fetchone()
    print(json.dumps({
        "project": "MedAssistMultimodal",
        "status": "baseline_offline",
        "azure_status": "CONTINGENCIA_NAO_ATIVADA",
        "audio_target": "whisper_local; gpt-oss:120b-cloud opcional",
        "real_audio_adapters": "implementados; dependencias/modelos locais necessarios",
        "llm_required": False,
        "video_audio_alerts": "implementados nos recortes documentados; sem validacao clinica",
        "desktop_command": "python -B -m medassistmultimodal.desktop_multimodal",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

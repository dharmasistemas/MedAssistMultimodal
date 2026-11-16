"""Inspeção JSON das fixtures; não executa o pipeline multimodal."""
from dataclasses import asdict
from datetime import datetime
import json
from uuid import UUID

from .fixtures import build_demo_cases


def _json_value(value):
    if isinstance(value, (UUID, datetime)):
        return str(value) if isinstance(value, UUID) else value.isoformat()
    raise TypeError(f"Tipo não serializável: {type(value).__name__}")


def main(argv=()) -> int:
    if argv:
        from .persistence import main as persisted_main
        return persisted_main(argv)
    print(json.dumps({
        "project": "MedAssistMultimodal",
        "mode": "synthetic_fixture_only",
        "clinical_validation": False,
        "cases": [asdict(case) for case in build_demo_cases()],
    }, default=_json_value, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))

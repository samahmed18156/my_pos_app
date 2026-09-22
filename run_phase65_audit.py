from pathlib import Path
from services.final_production_audit import format_audit, run_final_audit

if __name__ == "__main__":
    result = run_final_audit(Path(__file__).resolve().parent)
    print(format_audit(result))
    raise SystemExit(0 if result["ok"] else 1)

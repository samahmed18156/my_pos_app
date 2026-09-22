from pathlib import Path
from services.gold_release_gate import run_gold_release_gate

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    issues = run_gold_release_gate(root)
    if issues:
        print("GOLD RELEASE GATE: FAIL")
        for issue in issues:
            print("-", issue)
        raise SystemExit(1)
    print("GOLD RELEASE GATE: PASS")

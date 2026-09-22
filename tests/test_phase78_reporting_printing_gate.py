from pathlib import Path
from services.report_printing_gate import validate_report_printing_gate

ROOT = Path(__file__).resolve().parents[1]


def test_phase78_reporting_printing_gate_passes_current_tree():
    assert validate_report_printing_gate(ROOT) == []


def test_phase78_detects_missing_reporting_file(tmp_path):
    issues = validate_report_printing_gate(tmp_path)
    assert any("Missing reporting/printing file" in x for x in issues)


def test_phase78_requires_jasper_runtime(tmp_path):
    for rel in (
        "jasper_reports/jasper_receipt.py",
        "jasper_reports/report_viewer.py",
        "services/receipt_printing.py",
        "receipt_printer.py",
        "history.py",
        "reports.py",
    ):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# test", encoding="utf-8")
    (tmp_path / "jasper_runtime").mkdir()
    issues = validate_report_printing_gate(tmp_path)
    assert any("Missing Jasper runtime JAR" in x for x in issues)

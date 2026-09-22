from pathlib import Path
from services.shop_smoke_gate import validate_shop_smoke_gate

ROOT = Path(__file__).resolve().parents[1]

def test_phase77_shop_smoke_gate_passes_current_tree():
    assert validate_shop_smoke_gate(ROOT) == []

def test_phase77_detects_missing_critical_workflow(tmp_path):
    (tmp_path / 'services').mkdir()
    issues = validate_shop_smoke_gate(tmp_path)
    assert any('Missing critical shop-readiness file' in x for x in issues)

def test_phase77_rejects_live_database(tmp_path):
    for rel in ('services/cashier_workflow.py', 'services/cashup_hardening.py',
                'services/sales_service.py', 'services/grn_service.py',
                'services/returns_service.py', 'services/receipt_printing.py',
                'services/day_end_procedure.py', 'services/upgrade_uninstall_safety.py',
                'tests/test_phase66_cashier_workflow.py', 'tests/test_phase67_cashup_hardening.py',
                'tests/test_phase68_receipt_printing.py', 'tests/test_phase69_document_numbering.py',
                'tests/test_phase70_day_end.py', 'tests/test_phase76_upgrade_uninstall_safety.py'):
        p=tmp_path/rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('', encoding='utf-8')
    (tmp_path/'pos_store.db').write_text('live', encoding='utf-8')
    issues=validate_shop_smoke_gate(tmp_path)
    assert any('live pos_store.db' in x for x in issues)

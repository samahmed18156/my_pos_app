# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

PROJECT = Path(SPECPATH).resolve().parents[1]
jasper_dir = PROJECT / "jasper_runtime"
version_file = PROJECT / "packaging" / "windows" / "BKPOS_version_info.txt"

hiddenimports = [
    "admin_portal", "admin_portal_backup", "advanced_reports", "app",
    "audit_log", "barcode_labels", "branches", "budget_expenses",
    "credit_note", "creditor_accounts", "creditor_payments", "creditors",
    "customer_accounts", "customer_pricing", "customers", "dashboard",
    "database", "debitors", "disaster_recovery", "document_viewer",
    "enhanced_cart", "financial_controls", "fix_branches", "health_check",
    "history", "install_direct_receipt_print", "invoice_selector", "invoices",
    "login", "management_upgrades", "menu_organization", "multi_branch",
    "payment", "permissions", "phase37_business_controls", "pos_six_upgrades",
    "product_master_wholesale", "production_upgrade", "professional_dashboard",
    "professional_grn", "professional_lookup", "professional_menu_cleanup",
    "professional_reports", "quotation", "receipt_printer", "reports", "returns",
    "sales_management", "sales_report", "security", "security_controls",
    "shortcut_hints", "smart_pos_controls", "stock", "store_settings",
    "supplier_aging", "supplier_credits", "supplier_ledger",
    "supplier_purchase_history", "supplier_statement", "touch_f3_lookup",
    "touch_optimization", "ui_feedback", "utility", "workflow_optimization",
    "core.config", "core.logger", "core.migrations", "core.permissions",
    "core.audit_log", "core.audit_viewer", "core.schema_manager",
]
hiddenimports += collect_submodules("services")
hiddenimports += collect_submodules("reportlab.graphics.barcode")

a = Analysis(
    [str(PROJECT / "app.py")],
    pathex=[str(PROJECT)],
    binaries=[],
    datas=[(str(jasper_dir), "jasper_runtime")] if jasper_dir.exists() else [],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "unittest"],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="BKPOS",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False,
    version=str(version_file) if version_file.exists() else None,
)
COLLECT(
    exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="BKPOS"
)

"""POS Health Check - safe diagnostics for the active POS installation."""
from core.logger import logger as _bkpos_logger
import os, sqlite3, sys, tkinter as tk
from tkinter import ttk, messagebox
from core.config import DB_PATH, BACKUP_DIR, APP_BASE_DIR
from services.recovery_hardening import full_database_health

from ui.window_polish import polish_window
REQUIRED_FILES = [
    'app.py','database.py','login.py','permissions.py','stock.py','debitors.py','creditors.py',
    'utility.py','reports.py','sales_report.py','returns.py','payment.py','receipt_printer.py',
    'invoices.py','invoice_selector.py','management_upgrades.py','product_master_wholesale.py',
    'customer_pricing.py','sales_management.py','smart_pos_controls.py','menu_organization.py',
    'advanced_reports.py','barcode_labels.py','customers.py','multi_branch.py','disaster_recovery.py',
    'audit_log.py','branches.py','admin_portal.py'
]
REQUIRED_TABLES = [
    'products','sales_history','sale_items','invoice_items','stock_movements','return_history',
    'return_items','debtors','creditors' if False else 'accounts','account_transactions',
    'grn_headers','grn_items','cashier_shifts','users','branches','sale_lifecycle'
]

class HealthCheckWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        polish_window(self)
        self.title('POS Health Check')
        self.geometry('760x650')
        self.minsize(680, 560)
        self.transient(parent)
        self.grab_set()
        self._build()
        self.run_checks()

    def _build(self):
        ttk.Label(self, text='POS HEALTH CHECK', font=('Segoe UI', 20, 'bold')).pack(pady=(18,4))
        ttk.Label(self, text='Checks the active installation without changing sales or stock data.', font=('Segoe UI', 10)).pack(pady=(0,12))
        frame = ttk.Frame(self, padding=12); frame.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(frame, columns=('status','details'), show='headings', height=20)
        self.tree.heading('status', text='Status'); self.tree.heading('details', text='Check')
        self.tree.column('status', width=90, anchor='center'); self.tree.column('details', width=560)
        self.tree.pack(side='left', fill='both', expand=True)
        sb=ttk.Scrollbar(frame, command=self.tree.yview); sb.pack(side='right', fill='y'); self.tree.configure(yscrollcommand=sb.set)
        self.summary = ttk.Label(self, text='', font=('Segoe UI', 11, 'bold')); self.summary.pack(pady=8)
        btns=ttk.Frame(self); btns.pack(pady=(0,16))
        ttk.Button(btns, text='Run Again', command=self.run_checks).pack(side='left', padx=5)
        ttk.Button(btns, text='Close', command=self.destroy).pack(side='left', padx=5)

    def add(self, ok, check, details):
        self.tree.insert('', 'end', values=('✓ PASS' if ok else '✗ CHECK', f'{check} — {details}'))
        return ok

    def run_checks(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        results=[]
        base=APP_BASE_DIR
        if getattr(sys, 'frozen', False):
            results.append(self.add(True, 'Main application', 'BKPOS executable is running'))
        else:
            results.append(self.add(os.path.exists(os.path.join(base,'app.py')), 'Main application', 'app.py found'))
            for f in REQUIRED_FILES[1:]:
                results.append(self.add(os.path.isfile(os.path.join(base,f)), f, 'module present' if os.path.isfile(os.path.join(base,f)) else 'missing'))
        db=DB_PATH
        db_ok=os.path.isfile(db)
        results.append(self.add(db_ok, 'Database file', 'pos_store.db found' if db_ok else 'pos_store.db missing'))
        if db_ok:
            try:
                report = full_database_health(db)
                if report["sqlite"].get("error"):
                    results.append(self.add(False, 'Database access', report["sqlite"]["error"]))
                else:
                    q = report["sqlite"].get("quick_check")
                    results.append(self.add(q == 'ok', 'Database integrity', q or 'not available'))
                    fk = report["sqlite"].get("foreign_key_check", [])
                    results.append(self.add(not fk, 'Foreign-key integrity', 'no violations' if not fk else f'{len(fk)} violation(s)'))
                    readiness = report.get("readiness", {})
                    missing = readiness.get("missing_tables", [])
                    results.append(self.add(not missing, 'Core database tables', 'all required tables present' if not missing else 'missing: ' + ', '.join(missing)))
                    cols = readiness.get("missing_columns", {})
                    results.append(self.add(not cols, 'Required database columns', 'all required columns present' if not cols else str(cols)))
                    checks = [
                        ('Orphan sale items', readiness.get('orphan_sale_items', 0)),
                        ('Orphan GRN items', readiness.get('orphan_grn_items', 0)),
                        ('Orphan stock movements', readiness.get('orphan_stock_movements', 0)),
                    ]
                    for label, count in checks:
                        results.append(self.add(count == 0, label, 'none found' if count == 0 else f'{count} orphan row(s)'))
                    neg = len(readiness.get('negative_global_stock', []))
                    results.append(self.add(neg == 0, 'Negative global stock', 'none found' if neg == 0 else f'{neg} product(s)'))
                    negb = len(readiness.get('negative_branch_stock', []))
                    results.append(self.add(negb == 0, 'Negative branch stock', 'none found' if negb == 0 else f'{negb} row(s)'))
            except Exception as e:
                results.append(self.add(False,'Database access',str(e)))
        backup_dir=BACKUP_DIR
        backups=[]
        if os.path.isdir(backup_dir): backups=[x for x in os.listdir(backup_dir) if x.lower().endswith(('.db','.zip'))]
        results.append(self.add(bool(backups),'Backup system','backup files found' if backups else 'no backup files found yet'))
        self.summary.config(text=f"RESULT: {'READY' if all(results) else 'REVIEW NEEDED'}   |   {sum(results)}/{len(results)} checks passed")

def install(app_cls):
    original = getattr(app_cls, 'create_menu_bar', None)
    if not original: return
    def create_menu_bar(self):
        original(self)
        try:
            mb=self.nametowidget(self['menu']) if self['menu'] else None
            if mb:
                # Find Utility menu and append a separator + health check command.
                for idx in range(mb.index('end') + 1 if mb.index('end') is not None else 0):
                    try:
                        if mb.entrycget(idx, 'label') == 'Utility':
                            submenu=mb.nametowidget(mb.entrycget(idx,'menu'))
                            submenu.add_separator(); submenu.add_command(label='POS Health Check', command=lambda: HealthCheckWindow(self))
                            break
                    except Exception as exc:
                        _bkpos_logger.warning("Suppressed exception in health_check.py", exc_info=exc)
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in health_check.py", exc_info=exc)
    app_cls.create_menu_bar=create_menu_bar

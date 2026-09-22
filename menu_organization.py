"""Logical POS menu organization.

Keeps the main window compact by grouping related tools:
- Stock: products, pricing, labels and branch stock
- Creditors: suppliers and GRN/purchasing
- Debtors: customer accounts, returns/refunds and reports
- Utility: shifts, audit and backup/admin tools
"""
import sqlite3
import tkinter as tk
from health_check import HealthCheckWindow
from tkinter import ttk, messagebox

from core.config import DB_PATH
DB_NAME = DB_PATH


def _return_report_schema():
    c = sqlite3.connect(DB_NAME)
    cur = c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS return_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        original_sale_id INTEGER NOT NULL,
        total_amount REAL NOT NULL DEFAULT 0,
        refund_type TEXT NOT NULL,
        cashier TEXT DEFAULT 'Unknown',
        reason TEXT DEFAULT ''
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS return_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        return_id INTEGER NOT NULL,
        sale_item_id INTEGER NOT NULL,
        barcode TEXT,
        description TEXT,
        qty REAL NOT NULL,
        price REAL NOT NULL,
        value REAL NOT NULL
    )""")
    c.commit(); c.close()


class ReturnRefundReportWindow(tk.Toplevel):
    """Focused returns/refunds report, placed under Debtors."""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Returns & Refunds Report")
        self.geometry("1120x650")
        self.minsize(980, 560)
        self.configure(bg="#eef2f7")
        _return_report_schema()
        self.build()
        self.refresh()

    def build(self):
        tk.Label(self, text="RETURNS & REFUNDS REPORT", font=("Arial", 18, "bold"),
                 bg="#2c5282", fg="white", pady=12).pack(fill="x")
        bar = tk.Frame(self, bg="#eef2f7", pady=10)
        bar.pack(fill="x", padx=12)
        today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
        tk.Label(bar, text="From (YYYY-MM-DD)", bg="#eef2f7").pack(side="left")
        self.frm = tk.Entry(bar, width=13); self.frm.insert(0, today); self.frm.pack(side="left", padx=5)
        tk.Label(bar, text="To", bg="#eef2f7").pack(side="left")
        self.to = tk.Entry(bar, width=13); self.to.insert(0, today); self.to.pack(side="left", padx=5)
        tk.Button(bar, text="RUN REPORT", font=("Arial", 10, "bold"), command=self.refresh).pack(side="left", padx=8)
        tk.Button(bar, text="VIEW IN JASPER VIEWER", command=self.view_in_jasperviewer).pack(side="left", padx=4)
        self.summary = tk.Label(self, text="", font=("Arial", 12, "bold"), bg="#eef2f7", anchor="w", justify="left")
        self.summary.pack(fill="x", padx=15, pady=(2, 8))

        cols = ("return", "date", "sale", "type", "amount", "cashier", "reason")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        headings = {"return":"Return #", "date":"Date", "sale":"Original Sale", "type":"Refund Type",
                    "amount":"Amount (R)", "cashier":"Cashier", "reason":"Reason"}
        widths = {"return":80, "date":145, "sale":105, "type":115, "amount":110, "cashier":120, "reason":300}
        for col in cols:
            self.tree.heading(col, text=headings[col]); self.tree.column(col, width=widths[col], anchor="e" if col == "amount" else "center")
        self.tree.pack(fill="both", expand=True, padx=15, pady=8)

    def view_in_jasperviewer(self):
        try:
            from jasper_reports.report_viewer import open_table_report
            rows=[self.tree.item(i,"values") for i in self.tree.get_children()]
            open_table_report("Returns & Refunds Report",["Return #","Date","Original Sale","Refund Type","Amount","Cashier","Reason"],rows,period=f"{self.frm.get()} to {self.to.get()}",parent=self)
        except Exception as exc: messagebox.showerror("JasperViewer",str(exc),parent=self)

    def refresh(self):
        try:
            from datetime import datetime
            a, b = self.frm.get().strip(), self.to.get().strip()
            datetime.strptime(a, "%Y-%m-%d"); datetime.strptime(b, "%Y-%m-%d")
            c = sqlite3.connect(DB_NAME)
            rows = c.execute("""SELECT id,timestamp,original_sale_id,refund_type,total_amount,cashier,reason
                               FROM return_history
                               WHERE date(timestamp) BETWEEN ? AND ? ORDER BY id DESC""", (a, b)).fetchall()
            total = sum(float(r[4] or 0) for r in rows)
            cash = sum(float(r[4] or 0) for r in rows if str(r[3]).lower() == "cash refund")
            credit = sum(float(r[4] or 0) for r in rows if str(r[3]).lower() == "credit note")
            items = c.execute("""SELECT COALESCE(SUM(ri.qty),0) FROM return_items ri
                                JOIN return_history rh ON rh.id=ri.return_id
                                WHERE date(rh.timestamp) BETWEEN ? AND ?""", (a, b)).fetchone()[0] or 0
            c.close()
            self.tree.delete(*self.tree.get_children())
            for r in rows:
                self.tree.insert("", "end", values=(r[0], r[1], r[2], r[3], f"R {float(r[4] or 0):,.2f}", r[5], r[6] or ""))
            self.summary.config(text=f"Returns: {len(rows)}   |   Items returned: {float(items):g}   |   Total: R {total:,.2f}   |   Cash Refunds: R {cash:,.2f}   |   Credit Notes: R {credit:,.2f}")
        except Exception as e:
            messagebox.showerror("Returns Report", f"Invalid date or report error:\n{e}", parent=self)


def install(app_cls):
    # Import lazily so the app can finish loading before optional windows are opened.
    from returns import ReturnsWindow
    from customer_pricing import open_customer_pricing
    from barcode_labels import BarcodeLabelWindow
    from multi_branch import BranchTransferWindow
    from management_upgrades import GRNWindow, ProductManagerWindow, ShiftWindow, SalesDashboard, BackupRestoreWindow
    from audit_log import AuditLogWindow
    from customers import CustomerManagerWindow
    from sales_management import SalesManagementWindow
    from business_intelligence import BusinessIntelligenceWindow
    from operational_control import OperationalControlWindow
    from enterprise_operations import EnterpriseOperationsWindow
    from customer_engagement import CustomerEngagementWindow
    from supplier_inventory_optimization import SupplierInventoryOptimizationWindow

    def create_menu_bar(self):
        mb = tk.Menu(self)

        # FILE
        file_menu = tk.Menu(mb, tearoff=0)
        file_menu.add_command(label="Log Out", command=self.log_out)
        file_menu.add_separator(); file_menu.add_command(label="Exit", command=self.quit)
        mb.add_cascade(label="File", menu=file_menu)

        # INVOICE
        inv = tk.Menu(mb, tearoff=0)
        inv.add_command(label="New Invoice    Ctrl+N", command=self.create_new_invoice)
        inv.add_command(label="Open Invoices  Ctrl+I", command=self.open_invoice_selector)
        inv.add_command(label="Sales & Invoice Management", command=lambda: SalesManagementWindow(self))
        inv.add_separator()
        inv.add_command(label="Close Current Invoice", command=self.close_current_invoice)
        inv.add_command(label="Close All Open Invoices", command=self.close_all_invoices)
        mb.add_cascade(label="Invoice", menu=inv)

        # STOCK — all product and pricing tools together
        if getattr(self, "is_admin", False) or self.can("can_access_stock"):
            stock = tk.Menu(mb, tearoff=0)
            stock.add_command(label="Price Lookup    Alt+L", command=lambda: __import__("professional_lookup").PriceLookupWindow(self))
            stock.add_command(label="Product Management", command=lambda: ProductManagerWindow(self))
            stock.add_separator()
            stock.add_command(label="Retail / Bulk / Wholesale Pricing", command=lambda: open_customer_pricing(self))
            stock.add_command(label="Barcode & Label Printing", command=lambda: BarcodeLabelWindow(self))
            stock.add_separator()
            stock.add_command(label="Branch Stock Transfers", command=lambda: BranchTransferWindow(self))
            mb.add_cascade(label="Stock", menu=stock)

        # CREDITORS — supplier purchasing naturally belongs here
        if getattr(self, "is_admin", False) or self.can("can_access_creditors"):
            cred = tk.Menu(mb, tearoff=0)
            cred.add_command(label="Creditors Maintenance", command=lambda: __import__("creditors").CreditorsWindow(self))
            cred.add_command(label="Goods Received Note (GRN)", command=lambda: GRNWindow(self))
            mb.add_cascade(label="Creditors", menu=cred)

        # DEBTORS — accounts, customers, returns/refunds and all reports
        if getattr(self, "is_admin", False) or self.can("can_access_debtors"):
            debt = tk.Menu(mb, tearoff=0)
            debt.add_command(label="Debtors Maintenance", command=lambda: __import__("debitors").DebitorsWindow(self))
            debt.add_command(label="Customer Management", command=lambda: CustomerManagerWindow(self))
            debt.add_separator()
            debt.add_command(label="Returns & Refunds    Ctrl+Shift+R", command=lambda: ReturnsWindow(self))
            if getattr(self, "is_admin", False) or self.can("can_view_reports"):
                debt.add_command(label="Returns & Refunds Report", command=lambda: __import__("professional_reports").ProfessionalReportWindow(self, "returns", "Returns & Credit Notes Report"))
                debt.add_separator()
                debt.add_command(label="Sales Report", command=self.open_sales_report)
                debt.add_command(label="Reports", command=self.open_reports)
                debt.add_command(label="Advanced Sales & Profit Reports", command=lambda: __import__("professional_reports").ProfessionalReportWindow(self, "advanced", "Advanced Sales & Profit Report"))
            mb.add_cascade(label="Debtors", menu=debt)
        elif getattr(self, "is_admin", False) or self.can("can_view_reports"):
            # Keep reports available to report-only users, but without creating a second returns menu.
            debt = tk.Menu(mb, tearoff=0)
            debt.add_command(label="Sales Report", command=self.open_sales_report)
            debt.add_command(label="Reports", command=self.open_reports)
            debt.add_command(label="Advanced Sales & Profit Reports", command=lambda: __import__("professional_reports").ProfessionalReportWindow(self, "advanced", "Advanced Sales & Profit Report"))
            mb.add_cascade(label="Reports", menu=debt)

        # UTILITY — operational/admin tools in one place
        if getattr(self, "is_admin", False) or self.can("can_access_utility"):
            util = tk.Menu(mb, tearoff=0)
            util.add_command(label="Utility Settings", command=lambda: __import__("utility").UtilityWindow(self))
            util.add_command(label="Professional Lookup & Statements", command=lambda: __import__("professional_lookup").LookupCenterWindow(self))
            util.add_command(label="Cashier Shift / End of Day", command=lambda: ShiftWindow(self))
            if getattr(self, "is_admin", False) or self.can("can_view_reports"):
                util.add_command(label="Sales Dashboard", command=lambda: SalesDashboard(self))
                util.add_command(label="Business Intelligence", command=lambda: BusinessIntelligenceWindow(self))
                util.add_command(label="Operational Control Center", command=lambda: OperationalControlWindow(self))
                util.add_command(label="Enterprise Operations & Resilience", command=lambda: EnterpriseOperationsWindow(self))
                util.add_command(label="Customer Engagement & Promotions", command=lambda: CustomerEngagementWindow(self))
                util.add_command(label="Purchasing & Inventory Optimization", command=lambda: SupplierInventoryOptimizationWindow(self))
            if getattr(self, "is_admin", False):
                util.add_separator(); util.add_command(label="Audit Log", command=lambda: AuditLogWindow(self))
                util.add_command(label="Backup & Disaster Recovery", command=lambda: BackupRestoreWindow(self))
                util.add_separator(); util.add_command(label="Manage Users", command=lambda: __import__("login").ManageUsersWindow(self))
            mb.add_cascade(label="Utility", menu=util)

        self.config(menu=mb)

    app_cls.create_menu_bar = create_menu_bar
    return app_cls


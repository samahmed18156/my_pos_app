"""Final single-workflow POS menu.

This module is intentionally installed last. It keeps the existing feature
modules and their database logic, but presents each business task in ONE
place only. Legacy/upgrade menu wrappers are therefore not shown.
"""
from core.logger import logger as _bkpos_logger
import tkinter as tk
from tkinter import messagebox


def _open_report(parent, kind, title):
    try:
        from professional_reports import ProfessionalReportWindow
        ProfessionalReportWindow(parent, kind, title)
    except Exception as exc:
        messagebox.showerror("Report", str(exc), parent=parent)


class ReportsCentreWindow(tk.Toplevel):
    """One entry point for all management/reporting views."""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Reports Centre")
        self.geometry("780x650")
        self.minsize(700, 560)
        self.configure(bg="#eef2f7")
        self.transient(parent)
        # Do not grab the application here: this centre opens report windows.
        # A persistent grab would prevent those report windows from receiving
        # mouse/keyboard close events reliably.
        self._build()

    def _close(self):
        try:
            self.grab_release()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in professional_menu_cleanup.py", exc_info=exc)
        try:
            self.destroy()
        finally:
            try:
                self.parent.focus_force()
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in professional_menu_cleanup.py", exc_info=exc)

    def _build(self):
        tk.Label(self, text="REPORTS CENTRE", font=("Arial", 20, "bold"),
                 bg="#243447", fg="white", pady=14).pack(fill="x")
        tk.Label(self,
                 text="All professional reports are accessed from this one centre.",
                 font=("Arial", 10), bg="#eef2f7", fg="#52606d").pack(pady=(12, 8))
        body = tk.Frame(self, bg="#eef2f7", padx=28, pady=10)
        body.pack(fill="both", expand=True)

        reports = [
            ("SALES REPORT", "Sales, VAT, payment and cashier summary", "sales", "Sales Report"),
            ("ADVANCED SALES & PROFIT", "Sales, cost, profit and margin analysis", "advanced", "Advanced Sales & Profit Report"),
            ("RETURNS & CREDIT NOTES", "Returns, refunds and credit-note activity", "returns", "Returns & Credit Notes Report"),
            ("FINANCIAL CONTROL", "Financial control and reconciliation report", "financial", "Financial Control Report"),
            ("STOCK RECONCILIATION", "Stock movements and SOH reconciliation", "stock", "Stock Reconciliation Report"),
            ("CASH-UP / RECONCILIATION", "Cash, card and cashier reconciliation", "cashup", "Cash-Up & Reconciliation Report"),
            ("INVOICE LIFECYCLE", "Invoice status, completed and voided invoices", "lifecycle", "Invoice Lifecycle Report"),
        ]
        for i, (name, desc, kind, title) in enumerate(reports):
            row, col = divmod(i, 2)
            f = tk.Frame(body, bg="white", bd=1, relief="solid", padx=12, pady=10)
            f.grid(row=row, column=col, sticky="nsew", padx=7, pady=7)
            body.grid_columnconfigure(col, weight=1)
            tk.Label(f, text=name, font=("Arial", 10, "bold"),
                     bg="white", fg="#243447", anchor="w").pack(fill="x")
            tk.Label(f, text=desc, font=("Arial", 9), bg="white",
                     fg="#667085", anchor="w", justify="left", wraplength=280).pack(fill="x", pady=(4, 8))
            tk.Button(f, text="OPEN REPORT", font=("Arial", 9, "bold"),
                      command=lambda k=kind, t=title: _open_report(self.parent, k, t)).pack(anchor="e")
        tk.Button(self, text="CLOSE", width=14, command=self._close).pack(pady=12)
        self.bind("<Escape>", lambda e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)


def install(app_cls):
    """Install the final menu after all legacy menu wrappers have loaded."""
    def create_menu_bar(self):
        mb = tk.Menu(self)

        # FILE — session controls only.
        file_menu = tk.Menu(mb, tearoff=0)
        file_menu.add_command(label="Log Out", command=self.log_out)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        mb.add_cascade(label="File", menu=file_menu)

        # INVOICE — organize the sales workflow into clear groups.
        inv = tk.Menu(mb, tearoff=0)
        sales_menu = tk.Menu(inv, tearoff=0)
        sales_menu.add_command(label="New Invoice    Ctrl+N", command=self.create_new_invoice)
        sales_menu.add_command(label="Open Invoices  Ctrl+I", command=self.open_invoice_selector)
        sales_menu.add_command(label="Sales & Invoice Management",
                               command=lambda: __import__("sales_management").SalesManagementWindow(self))
        sales_menu.add_command(label="Quotation    F9", command=self.open_quotation)
        inv.add_cascade(label="Sales & Invoices", menu=sales_menu)

        session_menu = tk.Menu(inv, tearoff=0)
        session_menu.add_command(label="Close Current Invoice", command=self.close_current_invoice)
        session_menu.add_command(label="Close All Open Invoices", command=self.close_all_invoices)
        inv.add_cascade(label="Open Invoice Sessions", menu=session_menu)
        mb.add_cascade(label="Invoice", menu=inv)

        # HISTORY — one central archive for finalized documents and reprints.
        try:
            from history import HistoryWindow
            mb.add_command(label="History", command=lambda: HistoryWindow(self))
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in professional_menu_cleanup.py", exc_info=exc)

        # STOCK — two simple groups instead of a long flat list.
        if getattr(self, "is_admin", False) or self.can("can_access_stock"):
            stock = tk.Menu(mb, tearoff=0)

            product_menu = tk.Menu(stock, tearoff=0)
            product_menu.add_command(label="Product Management",
                                     command=lambda: __import__("management_upgrades").ProductManagerWindow(self))
            product_menu.add_command(label="Price Lookup",
                                     command=lambda: __import__("professional_lookup").PriceLookupWindow(self))
            product_menu.add_command(label="Barcode & Label Printing",
                                     command=lambda: __import__("barcode_labels").BarcodeLabelWindow(self))
            stock.add_cascade(label="Products & Pricing", menu=product_menu)

            inventory_menu = tk.Menu(stock, tearoff=0)
            try:
                inventory_menu.add_command(
                    label="Stocktake / Physical Count",
                    command=lambda: __import__("stocktake", fromlist=["StocktakeWindow"]).StocktakeWindow(self)
                )
            except Exception as exc:
                _bkpos_logger.warning("Stocktake menu unavailable", exc_info=exc)
            inventory_menu.add_command(label="Branch Stock Transfers",
                                       command=lambda: __import__("multi_branch").BranchTransferWindow(self))
            stock.add_cascade(label="Inventory Operations", menu=inventory_menu)
            mb.add_cascade(label="Stock", menu=stock)

        # CREDITORS — supplier maintenance/accounting and purchasing are separated.
        if getattr(self, "is_admin", False) or self.can("can_access_creditors"):
            cred = tk.Menu(mb, tearoff=0)

            supplier_menu = tk.Menu(cred, tearoff=0)
            supplier_menu.add_command(label="Supplier Master",
                                      command=lambda: __import__("creditors").CreditorsWindow(self))
            supplier_menu.add_command(label="Supplier Accounts / Balances",
                                      command=lambda: __import__("creditor_accounts").SupplierAccountsWindow(self))
            supplier_menu.add_command(label="Supplier Payments",
                                      command=lambda: __import__("creditor_payments").SupplierPaymentsWindow(self))
            supplier_menu.add_command(label="Supplier Statements",
                                      command=lambda: __import__("supplier_statement").SupplierStatementWindow(self))
            supplier_menu.add_command(label="Supplier Aging",
                                      command=lambda: __import__("supplier_aging").SupplierAgingWindow(self))
            supplier_menu.add_command(label="Supplier Credits / Credit Notes",
                                      command=lambda: __import__("supplier_credits").SupplierCreditsWindow(self))
            cred.add_cascade(label="Supplier Accounts", menu=supplier_menu)

            purchasing_menu = tk.Menu(cred, tearoff=0)
            purchasing_menu.add_command(label="Purchase Orders",
                                        command=lambda: __import__("purchase_orders", fromlist=["PurchaseOrderWindow"]).PurchaseOrderWindow(self))
            purchasing_menu.add_command(label="GRN / Goods Received",
                                        command=lambda: __import__("management_upgrades").GRNWindow(self))
            purchasing_menu.add_command(label="Supplier Purchase History",
                                        command=lambda: __import__("supplier_purchase_history").SupplierPurchaseHistoryWindow(self))
            cred.add_cascade(label="Purchasing", menu=purchasing_menu)
            mb.add_cascade(label="Creditors", menu=cred)

        # DEBTORS — customer/account work and returns are separated.
        if getattr(self, "is_admin", False) or self.can("can_access_debtors"):
            debt = tk.Menu(mb, tearoff=0)

            customer_menu = tk.Menu(debt, tearoff=0)
            customer_menu.add_command(label="Customer Accounts / Balances",
                                      command=lambda: __import__("customer_accounts").CustomerAccountsWindow(self))
            customer_menu.add_command(label="Customer Aging",
                                      command=lambda: __import__("customer_accounts").CustomerAgingWindow(self))
            customer_menu.add_command(label="Customer & Pricing (Retail / Bulk / Wholesale)",
                                      command=lambda: __import__("customer_pricing").open_customer_pricing(self))
            customer_ops = tk.Menu(debt, tearoff=0)
            customer_ops.add_cascade(label="Customer Accounts", menu=customer_menu)
            customer_ops.add_command(label="Returns & Refunds    Ctrl+Shift+R",
                                     command=lambda: __import__("returns").ReturnsWindow(self))
            debt.add_cascade(label="Customer Operations", menu=customer_ops)
            mb.add_cascade(label="Debtors", menu=debt)

        # REPORTS — one report centre; individual report menus stay inside it.
        if getattr(self, "is_admin", False) or self.can("can_view_reports"):
            reports = tk.Menu(mb, tearoff=0)
            reports.add_command(label="Reports Centre", command=lambda: ReportsCentreWindow(self))
            mb.add_cascade(label="Reports", menu=reports)

        # UTILITY — advanced tools remain grouped under two clear headings.
        if getattr(self, "is_admin", False) or self.can("can_access_utility"):
            util = tk.Menu(mb, tearoff=0)
            util.add_command(label="Utility Settings",
                             command=lambda: UtilityWindow(self))
            util.add_command(label="Cashier Shift / End of Day",
                             command=lambda: __import__("management_upgrades").ShiftWindow(self))

            if getattr(self, "is_admin", False) or self.can("can_view_reports"):
                analysis = tk.Menu(util, tearoff=0)
                analysis.add_command(label="Management Dashboard & KPIs",
                                     command=lambda: __import__("smart_pos_controls").SmartManagementDashboard(self))
                analysis.add_command(label="Business Intelligence",
                                     command=lambda: __import__("professional_dashboard", fromlist=["BusinessIntelligenceWindow"]).BusinessIntelligenceWindow(self))
                analysis.add_command(label="Price Scenario Simulator",
                                     command=lambda: __import__("price_scenario_simulator", fromlist=["PriceScenarioSimulatorWindow"]).PriceScenarioSimulatorWindow(self))
                analysis.add_command(label="Financial & Stock Control Center",
                                     command=lambda: __import__("financial_controls").FinancialControlCenter(self))
                analysis.add_command(label="Budget & Expense Management",
                                     command=lambda: __import__("budget_expenses").Center(self))
                util.add_cascade(label="Management & Analysis", menu=analysis)

            if getattr(self, "is_admin", False):
                admin = tk.Menu(util, tearoff=0)
                admin.add_command(label="Audit Log",
                                  command=lambda: __import__("audit_log").AuditLogWindow(self))
                admin.add_command(label="Backup & Disaster Recovery",
                                  command=lambda: __import__("management_upgrades").BackupRestoreWindow(self))
                admin.add_command(label="POS Health Check",
                                  command=lambda: __import__("health_check").HealthCheckWindow(self))
                admin.add_command(label="Manage Users",
                                  command=lambda: __import__("login").ManageUsersWindow(self))
                util.add_cascade(label="Administration", menu=admin)

            mb.add_cascade(label="Utility", menu=util)

        self.config(menu=mb)

    app_cls.create_menu_bar = create_menu_bar
    return app_cls

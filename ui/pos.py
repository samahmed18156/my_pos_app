from core.logger import logger as _bkpos_logger
from store_settings import get_store_name, ensure_settings
ensure_settings()
import sqlite3
import time
import os
import webbrowser
import urllib.parse
import tkinter as tk
from tkinter import ttk, messagebox

from database import init_db
from professional_lookup import PriceLookupWindow
from debitors import DebitorsWindow
from creditors import CreditorsWindow
from creditor_payments import SupplierPaymentsWindow
from management_upgrades import GRNWindow
from utility import UtilityWindow
from multi_branch_operations import MultiBranchOperationsWindow
from executive_decision_support import ExecutiveDecisionSupportWindow
from reports import ReportsWindow
from sales_report import SalesReportWindow
from professional_reports import ProfessionalReportWindow
from returns import ReturnsWindow
from credit_note import CreditNoteWindow
from history import HistoryWindow
from quotation import open_quotation
from login import show_login_window, ManageUsersWindow

# UX UPGRADE - Import the new touch optimization features
from install_ux_upgrades import install_all_ux_features

# PROFESSIONAL DASHBOARD - Import the professional dashboard enhancement
from professional_dashboard import install_professional_dashboard
from ui.theme import PALETTE, configure_ttk, button as themed_button, entry_options
from ui.window_polish import polish_window


# ============================================================
# DATABASE
# ============================================================

from core.config import DB_PATH, _startup_database_safety
DB_NAME = DB_PATH

init_db()
_startup_database_safety()


# ============================================================
# COLORS
# ============================================================

UI_BG = PALETTE["bg"]
FRAME_BG = "#e8eef5"
WHITE = PALETTE["surface"]
BLUE_TEXT = PALETTE["primary"]
BLUE_BORDER = PALETTE["focus"]
PURPLE_LABEL = "#6d4cc2"
LOOKUP_BG = "#e8f4f5"
HEADER_COLOR = PALETTE["nav"]


# ============================================================
# F3 DATA LOOKUP
# ============================================================


from ui.windows import CustomerLookupWindow, F3SearchWindow, EditCartItemDialog, InvoiceSelectorWindow

class FamilySupermarketPOS(tk.Tk):

    def __init__(
        self,
        username,
        full_name,
        role,
        permissions=None
    ):

        super().__init__()

        self.title(
            f"BKPOS 10.0.0 - {get_store_name()}"
        )
        polish_window(self, self.title(), escape_close=False)

        # Give the complete POS enough vertical space so the invoice table,
        # product-entry area, status bar and totals panel do not get cramped.
        self.geometry(
            "1440x920"
        )
        self.minsize(1200, 800)

        self.configure(
            bg=UI_BG
        )
        # Do not set a wildcard Tk font here. Tk parses named fonts with spaces
        # as Tcl words, which can break classic Menu creation (e.g. "UI").
        configure_ttk(self)

        # ====================================================
        # USER / PERMISSIONS
        # ====================================================

        self.cashier_username = username
        self.cashier_name = full_name
        self.cashier_role = role

        self.logout_requested = False

        self.f3_window = None

        permissions = permissions or {}

        # Admin is ALWAYS unrestricted.
        self.is_admin = (
            str(role).lower() == "admin"
        )

        self.permissions = {}

        permission_names = [
            "can_edit_price",
            "can_edit_qty",
            "can_delete_items",
            "can_view_reports",
            "can_access_stock",
            "can_access_debtors",
            "can_access_creditors",
            "can_access_utility"
        ]

        for permission in permission_names:

            self.permissions[permission] = (
                True
                if self.is_admin
                else bool(
                    permissions.get(
                        permission,
                        False
                    )
                )
            )

        # ====================================================
        # MULTI INVOICE SYSTEM
        # ====================================================

        self.invoices = {}

        self.next_invoice_id = 1

        self.current_invoice_id = None



        # ====================================================
        # MENU
        # ====================================================

        self.create_menu_bar()

        # ====================================================
        # PROFESSIONAL MAIN POS SCREEN
        # ====================================================

        window_frame = tk.Frame(self, bg=WHITE)
        self.pos_screen = window_frame
        window_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ---------- Header / operator bar ----------
        header = tk.Frame(window_frame, bg=HEADER_COLOR, height=88)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Frame(header, bg=PALETTE["focus"], height=4).pack(side=tk.TOP, fill=tk.X)

        brand = tk.Frame(header, bg=HEADER_COLOR)
        brand.pack(side=tk.LEFT, padx=18, pady=10)
        tk.Label(brand, text=get_store_name(), font=("Segoe UI", 19, "bold"),
                 bg=HEADER_COLOR, fg=WHITE).pack(anchor="w")
        tk.Label(brand, text=f"Cashier: {self.cashier_name}  |  {self.cashier_role}",
                 font=("Segoe UI", 10, "bold"), bg=HEADER_COLOR, fg="#e6f0ff").pack(anchor="w", pady=(3,0))

        invoice_box = tk.Frame(header, bg=HEADER_COLOR)
        invoice_box.pack(side=tk.RIGHT, padx=18, pady=10)
        self.lbl_date = tk.Label(invoice_box, font=("Segoe UI", 10, "bold"),
                                 bg=HEADER_COLOR, fg="#e6f0ff")
        self.lbl_date.pack(anchor="e")
        self.lbl_current_invoice = tk.Label(invoice_box, text="Invoice 001",
                                            font=("Segoe UI", 18, "bold"),
                                            bg=HEADER_COLOR, fg=WHITE)
        self.lbl_current_invoice.pack(anchor="e")
        tk.Label(invoice_box, text="OPEN", font=("Segoe UI", 9, "bold"),
                 bg=HEADER_COLOR, fg="#c6f6d5").pack(anchor="e")
        self.update_date()

        # ---------- Quick actions ----------
        action_bar = tk.Frame(window_frame, bg=FRAME_BG, padx=10, pady=8)
        action_bar.pack(fill=tk.X)
        themed_button(action_bar, "＋ NEW INVOICE", self.create_new_invoice, kind="success", padx=16, pady=8).pack(side=tk.LEFT, padx=(0,6))
        themed_button(action_bar, "OPEN INVOICES", self.open_invoice_selector, kind="primary", padx=16, pady=8).pack(side=tk.LEFT, padx=6)
        tk.Label(action_bar, text="F3 Product Lookup   •   Ctrl+N New   •   Ctrl+I Open   •   F12 Payment",
                 font=("Segoe UI", 10, "bold"), bg=FRAME_BG, fg="#4a5568").pack(side=tk.RIGHT, padx=5)

        # ---------- Customer / invoice information ----------
        info = tk.Frame(window_frame, bg=WHITE, bd=1, relief=tk.SOLID, padx=10, pady=8)
        info.pack(fill=tk.X, padx=2, pady=(8,5))
        tk.Label(info, text="CUSTOMER / SALE", font=("Segoe UI", 9, "bold"),
                 bg=WHITE, fg=BLUE_TEXT).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0,6))

        tk.Label(info, text="Account / No.", font=("Segoe UI", 10, "bold"), bg=WHITE).grid(row=1,column=0,sticky="w")
        # The sale account is deliberately a controlled selection rather than a
        # free-text field. CASH is always available and active debtor accounts
        # are loaded from the customers table. This prevents invoices being
        # posted against an empty or misspelled account number.
        self.entry_num = ttk.Combobox(
            info, state="readonly", width=22,
            font=("Segoe UI", 12, "bold")
        )
        self.entry_num.grid(row=1,column=1,sticky="w",padx=(6,25))
        tk.Label(info, text="Customer Name", font=("Segoe UI", 10, "bold"), bg=WHITE).grid(row=1,column=2,sticky="w")
        self.entry_name = tk.Entry(info, **entry_options(font=("Segoe UI", 12), width=30))
        self.entry_name.insert(0, "Cash Sale")
        self.entry_name.grid(row=1,column=3,sticky="w",padx=(6,0))
        themed_button(info, "F3 CUSTOMER LOOKUP", self.open_customer_lookup, kind="primary", padx=14, pady=7).grid(row=1, column=4, padx=(10,0), sticky="w")

        # ---------- Invoice tabs ----------
        self.invoice_tabs_frame = tk.Frame(window_frame, bg=WHITE)
        self.invoice_tabs_frame.pack(fill=tk.X, padx=2, pady=(2,5))

        # ---------- Cart ----------
        cart_wrap = tk.Frame(window_frame, bg=WHITE, bd=1, relief=tk.SOLID)
        cart_wrap.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        tk.Label(cart_wrap, text="CURRENT INVOICE", font=("Segoe UI", 10, "bold"),
                 bg=WHITE, fg=BLUE_TEXT, padx=10, pady=6).pack(anchor="w")
        table_frame = tk.Frame(cart_wrap, bg=WHITE)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0,8))

        columns = ("code", "description", "qty", "price", "value")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", style="BK.Treeview")
        for col, title in [("code","Barcode / Code"),("description","Product Description"),
                           ("qty","Qty"),("price","Price"),("value","Value")]:
            self.tree.heading(col, text=title)
        self.tree.column("code", width=150, anchor="w")
        self.tree.column("description", width=500, anchor="w")
        self.tree.column("qty", width=80, anchor="center")
        self.tree.column("price", width=110, anchor="e")
        self.tree.column("value", width=125, anchor="e")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<Delete>", self.delete_selected_item)
        self.tree.bind("<BackSpace>", self.delete_selected_item)
        self.tree.bind("<Double-Button-3>", self.open_edit_cart_item)

        # ---------- Professional Product Entry ----------
        # Compact, invoice-style entry area: large and easy to use,
        # but intentionally not stretched across the whole window.
        entry_panel = tk.Frame(
            window_frame,
            bg=FRAME_BG,
            bd=1,
            relief=tk.SOLID,
            padx=10,
            pady=8
        )
        entry_panel.pack(fill=tk.X, padx=2, pady=(6,5))
        entry_panel.grid_columnconfigure(4, weight=1)

        tk.Label(
            entry_panel,
            text="ADD PRODUCT",
            font=("Segoe UI", 11, "bold"),
            bg=FRAME_BG,
            fg=BLUE_TEXT
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0,6))

        # The four input columns deliberately use compact fixed widths.
        # The fonts/heights stay large; only the horizontal width is limited.
        entry_specs = [
            ("Barcode / Code", 0, 14, "w"),
            ("Description", 1, 34, "w"),
            ("Qty", 2, 6, "center"),
            ("Price", 3, 10, "e"),
        ]

        for label, col, _width, _anchor in entry_specs:
            tk.Label(
                entry_panel,
                text=label,
                font=("Segoe UI", 10, "bold"),
                bg=FRAME_BG,
                fg="#374151"
            ).grid(
                row=1,
                column=col,
                sticky="w",
                padx=(0 if col == 0 else 6, 6),
                pady=(0,4)
            )

        self.code_entry = tk.Entry(
            entry_panel,
            **entry_options(font=("Segoe UI", 16, "bold"), width=14, bd=2)
        )
        self.code_entry.grid(row=2, column=0, sticky="ew", padx=(0,6), ipady=5)

        self.desc_display = tk.Entry(
            entry_panel,
            **entry_options(font=("Segoe UI", 15), width=34, state="readonly", readonlybackground="#f8fafc")
        )
        self.desc_display.grid(row=2, column=1, sticky="ew", padx=6, ipady=5)

        self.qty_entry = tk.Entry(
            entry_panel,
            **entry_options(font=("Segoe UI", 16, "bold"), width=6, justify="center")
        )
        self.qty_entry.insert(0, "1")
        self.qty_entry.grid(row=2, column=2, sticky="ew", padx=6, ipady=5)

        if self.can("can_edit_qty"):
            vcmd_qty = self.register(self._validate_qty_keystroke)
            self.qty_entry.config(
                validate="key",
                validatecommand=(vcmd_qty, "%P")
            )
        else:
            self.qty_entry.config(state="readonly")

        self.price_display = tk.Entry(
            entry_panel,
            **entry_options(font=("Segoe UI", 16, "bold"), width=10, justify="right")
        )
        self.price_display.insert(0, "0")
        self.price_display.grid(row=2, column=3, sticky="ew", padx=6, ipady=5)

        if not self.can("can_edit_price"):
            self.price_display.config(state="readonly")

        # Buttons are on their own full row, just like the invoice-style layout.
        button_row = tk.Frame(entry_panel, bg=FRAME_BG)
        button_row.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(8,0))

        themed_button(button_row, "ADD PRODUCT", self.add_current_item_to_cart, kind="success", font=("Segoe UI", 11, "bold"), padx=20, pady=8).pack(side=tk.LEFT, padx=(0,6))
        themed_button(button_row, "CLEAR", self.clear_product_input, kind="secondary", font=("Segoe UI", 11, "bold"), padx=24, pady=8).pack(side=tk.LEFT, padx=6)
        themed_button(button_row, "F3 PRODUCT LOOKUP", self.open_f3_lookup, kind="primary", font=("Segoe UI", 11, "bold"), padx=18, pady=8).pack(side=tk.LEFT, padx=6)

        tk.Label(
            button_row,
            text="ENTER to add  •  F3 to search",
            font=("Segoe UI", 9, "bold"),
            bg=FRAME_BG,
            fg="#718096"
        ).pack(side=tk.LEFT, padx=(12,0))

        self.code_entry.focus_set()

        self.code_entry.bind("<Return>", self.handle_exact_barcode_entry)
        self.price_display.bind("<Return>", self.confirm_price_and_focus_qty)
        self.qty_entry.bind("<Return>", self.add_current_item_to_cart)
        self.entry_num.bind("<<ComboboxSelected>>", self.on_sale_account_selected)
        self.entry_num.bind("<F3>", self.open_customer_lookup)
        self.entry_name.bind("<F3>", self.open_customer_lookup)
        self.bind("<F3>", self.open_f3_lookup)
        self.bind("<F12>", self.checkout)
        self.bind("<F9>", lambda e: open_quotation(self))
        self.bind("<Control-Shift-R>", lambda e: ReturnsWindow(self))
        self.bind("<Control-n>", lambda e: self.create_new_invoice())
        self.bind("<Control-i>", lambda e: self.open_invoice_selector())
        self.bind("<Control-l>", lambda e: self._focus_barcode())
        self.bind("<Escape>", lambda e: self._handle_escape())

        # Populate the account selector after all account-related widgets exist.
        self._refresh_sale_account_options("CASH")

        # ---------- Invoice totals: fixed at the right corner of Add Product ----------
        # Keep the totals visible on the same horizontal level as the product
        # entry fields. This prevents the totals panel from being pushed below
        # the screen on smaller displays.
        totals = tk.Frame(
            entry_panel,
            bg=PALETTE.get("total_bg", "#0f172a"),
            bd=0,
            relief=tk.FLAT,
            padx=12,
            pady=8
        )
        totals.grid(
            row=0,
            column=4,
            rowspan=4,
            sticky="nsew",
            padx=(16, 2),
            pady=0
        )
        entry_panel.grid_columnconfigure(4, minsize=245, weight=1)

        def total_row(r, label, attr, bold=False):
            tk.Label(
                totals,
                text=label,
                font=("Segoe UI", 11, "bold"),
                bg=PALETTE.get("total_bg", "#0f172a"),
                fg="#94a3b8" if not bold else "#ffffff",
                anchor="e"
            ).grid(row=r, column=0, sticky="e", padx=(2, 7), pady=3)

            lab = tk.Label(
                totals,
                text="0.00",
                font=("Segoe UI", 16 if not bold else 22, "bold"),
                bg="#1e293b",
                fg="#ffffff" if not bold else PALETTE.get("total_text", "#10b981"),
                width=11,
                anchor="e",
                bd=0,
                relief=tk.FLAT,
                padx=8
            )
            lab.grid(row=r, column=1, sticky="ew", padx=(0, 2), pady=3, ipady=3)
            setattr(self, attr, lab)

        totals.grid_columnconfigure(1, weight=1)
        total_row(0, "Subtotal:", "lbl_subtotal")
        total_row(1, "VAT:", "lbl_vat")
        total_row(2, "TOTAL:", "lbl_total", True)

        # ---------- Bottom status ----------
        bottom = tk.Frame(window_frame, bg=WHITE, padx=2, pady=5)
        bottom.pack(fill=tk.X)
        status = tk.Frame(bottom, bg="#f7fafc", bd=1, relief=tk.SOLID, padx=10, pady=6)
        status.pack(fill=tk.X, expand=True)
        self.lbl_credit = tk.Label(status, text="Credit Limit: 0.00   |   O/S Balance: 0.00",
                                   font=("Segoe UI",10,"bold"), bg="#f7fafc", fg="#4a5568", anchor="w")
        self.lbl_credit.pack(side=tk.LEFT)
        self.lbl_num_items = tk.Label(status, text="Items: 0", font=("Segoe UI",10,"bold"),
                                      bg="#f7fafc", fg="#4a5568", anchor="e")
        self.lbl_num_items.pack(side=tk.RIGHT)
        self.lbl_ready = tk.Label(status, text="● READY", font=("Segoe UI",10,"bold"),
                                   bg="#f7fafc", fg="#16803c", anchor="w")
        self.lbl_ready.pack(side=tk.RIGHT, padx=(0,20))

        # Fixed checkout controls
        controls = tk.Frame(window_frame, bg=WHITE, pady=4)
        controls.pack(fill=tk.X)
        themed_button(controls, "🗑️ REMOVE ITEM (Del)", self.delete_selected_item, kind="danger", font=("Segoe UI",10,"bold"), padx=14, pady=8).pack(side=tk.LEFT, padx=(2,5))
        themed_button(controls, "💳 DONE / PAYMENT  F12", self.checkout, kind="success", font=("Segoe UI",12,"bold"), padx=28, pady=10).pack(side=tk.RIGHT, padx=2)

        # Draw tabs now that the UI exists
        self.refresh_invoice_tabs()
        self.load_current_invoice()

        # -----------------------------------------------------
        # MULTI-INVOICE INITIALIZATION
        # -----------------------------------------------------
        self.invoice_counter = 0
        self.invoices = {}
        self.current_invoice_id = None

        # Create the first invoice ONLY after all POS widgets exist
        self.create_new_invoice(switch_to=True)

    def _focus_barcode(self):
        """Return the cashier to the fastest barcode-entry workflow."""
        try:
            self.code_entry.focus_set()
            self.code_entry.select_range(0, tk.END)
        except Exception as exc:
            _bkpos_logger.warning("Could not focus barcode entry", exc_info=exc)
        return "break"

    def _handle_escape(self):
        """Clear transient product input without touching the current cart."""
        try:
            self.clear_product_input()
            self.code_entry.focus_set()
        except Exception as exc:
            _bkpos_logger.warning("Could not clear transient product input", exc_info=exc)
        return "break"

    # ========================================================
    # PERMISSION HELPER
    # ========================================================

    def can(self, permission):

        if self.is_admin:
            return True

        return bool(
            self.permissions.get(
                permission,
                False
            )
        )

    # ========================================================
    # DATE
    # ========================================================

    def update_date(self):

        self.lbl_date.config(
            text=time.strftime(
                "%d %B %Y"
            )
        )

        self.after(
            60000,
            self.update_date
        )

        # UX and dashboard installers are run once during application setup.
        # Do not install them here: update_date() runs every minute, and the
        # dashboard installer modifies instance methods. Re-installing it on
        # the live instance makes callbacks unbound and breaks dashboard buttons.

    # ========================================================
    # QUANTITY VALIDATION
    # ========================================================

    def _validate_qty_keystroke(
        self,
        proposed_value
    ):

        if proposed_value == "":
            return True

        return proposed_value.isdigit()

    # ========================================================
    # MENU
    # ========================================================

    def create_menu_bar(self):

        menu_bar = tk.Menu(
            self
        )

        # ----------------------------------------------------
        # FILE
        # ----------------------------------------------------

        file_menu = tk.Menu(
            menu_bar,
            tearoff=0
        )

        file_menu.add_command(
            label="Log Out",
            command=self.log_out
        )

        file_menu.add_separator()

        file_menu.add_command(
            label="Exit",
            command=self.quit
        )

        menu_bar.add_cascade(
            label="File",
            menu=file_menu
        )

        # ----------------------------------------------------
        # INVOICE
        # ----------------------------------------------------

        invoice_menu = tk.Menu(
            menu_bar,
            tearoff=0
        )

        invoice_menu.add_command(
            label="New Invoice    Ctrl+N",
            command=self.create_new_invoice
        )

        invoice_menu.add_command(
            label="Open Invoices  Ctrl+I",
            command=self.open_invoice_selector
        )

        invoice_menu.add_separator()

        invoice_menu.add_command(
            label="Close Current Invoice",
            command=self.close_current_invoice
        )

        invoice_menu.add_command(
            label="Close All Open Invoices",
            command=self.close_all_invoices
        )

        menu_bar.add_cascade(
            label="Invoice",
            menu=invoice_menu
        )

        # ----------------------------------------------------
        # HISTORY / REPRINT
        # ----------------------------------------------------
        if self.can("can_view_reports") or getattr(self, "is_admin", False):
            menu_bar.add_command(
                label="History",
                command=lambda: HistoryWindow(self)
            )

        # ----------------------------------------------------
        # RETURNS / REFUNDS
        # ----------------------------------------------------

        returns_menu = tk.Menu(
            menu_bar,
            tearoff=0
        )

        returns_menu.add_command(
            label="Returns & Refunds    Ctrl+Shift+R",
            command=lambda: ReturnsWindow(self)
        )

        menu_bar.add_cascade(
            label="Returns",
            menu=returns_menu
        )

        # ----------------------------------------------------
        # STOCK
        # ----------------------------------------------------

        if self.can(
            "can_access_stock"
        ):

            stock_menu = tk.Menu(
                menu_bar,
                tearoff=0
            )

            stock_menu.add_command(
                label="Price Lookup Alt+L",
                command=self.open_lookup
            )

            menu_bar.add_cascade(
                label="Stock",
                menu=stock_menu
            )

        # ----------------------------------------------------
        # DEBTORS
        # ----------------------------------------------------

        if self.can(
            "can_access_debtors"
        ):

            debtors_menu = tk.Menu(
                menu_bar,
                tearoff=0
            )

            debtors_menu.add_command(
                label="Debtors Maintenance",
                command=lambda: DebitorsWindow(self)
            )

            if self.can(
                "can_view_reports"
            ):

                debtors_menu.add_separator()

                debtors_menu.add_command(
                    label="📊 Sales Report",
                    command=self.open_sales_report
                )

                debtors_menu.add_command(
                    label="Reports",
                    command=self.open_reports
                )

            menu_bar.add_cascade(
                label="Debtors",
                menu=debtors_menu
            )

        # ----------------------------------------------------
        # REPORTS
        #
        # If the cashier has report permission but no Debtors
        # permission, give Reports its own top-level menu.
        # ----------------------------------------------------

        elif self.can(
            "can_view_reports"
        ):

            reports_menu = tk.Menu(
                menu_bar,
                tearoff=0
            )

            reports_menu.add_command(
                label="📊 Sales Report",
                command=self.open_sales_report
            )

            reports_menu.add_command(
                label="Reports",
                command=self.open_reports
            )

            menu_bar.add_cascade(
                label="Reports",
                menu=reports_menu
            )

        # ----------------------------------------------------
        # UTILITY
        # ----------------------------------------------------

        if self.can(
            "can_access_utility"
        ):

            utility_menu = tk.Menu(
                menu_bar,
                tearoff=0
            )

            utility_menu.add_command(
                label="Utility Settings",
                command=lambda: UtilityWindow(self)
            )

            utility_menu.add_command(
                label="Multi-Branch Operations",
                command=lambda: MultiBranchOperationsWindow(self)
            )

            utility_menu.add_command(
                label="Executive Decision Support",
                command=lambda: ExecutiveDecisionSupportWindow(self)
            )

            utility_menu.add_command(
                label="Shift & Cashier Control Center",
                command=lambda: __import__("shift_control").ShiftControlWindow(self)
            )

            utility_menu.add_command(
                label="Audit & Compliance Center",
                command=lambda: __import__("compliance_control").ComplianceControlWindow(self)
            )

            utility_menu.add_command(
                label="Advanced Inventory Forecasting",
                command=lambda: __import__("inventory_forecasting").InventoryForecastingWindow(self)
            )

            utility_menu.add_command(
                label="Customer & Supplier Credit Management",
                command=lambda: __import__("credit_management").CreditManagementWindow(self)
            )

            utility_menu.add_command(
                label="Advanced Pricing & Promotion Management",
                command=lambda: __import__("advanced_pricing").AdvancedPricingWindow(self)
            )

            utility_menu.add_command(
                label="End-of-Day & Period Operations",
                command=lambda: __import__("end_of_day_operations").EndOfDayOperationsWindow(self)
            )

            utility_menu.add_command(
                label="Automated Alerts & Management Notifications",
                command=lambda: __import__("automated_alerts").AutomatedAlertsWindow(self)
            )

            utility_menu.add_command(
                label="Backup & Disaster Recovery Center",
                command=lambda: __import__("backup_recovery_upgrade").BackupRecoveryUpgradeWindow(self)
            )

            utility_menu.add_command(
                label="Performance & Scalability Center",
                command=lambda: __import__("performance_scalability").PerformanceScalabilityWindow(self)
            )


            if self.is_admin:

                utility_menu.add_separator()

                utility_menu.add_command(
                    label="Manage Users",
                    command=lambda: ManageUsersWindow(self)
                )

            menu_bar.add_cascade(
                label="Utility",
                menu=utility_menu
            )

        self.config(
            menu=menu_bar
        )

    # ========================================================
    # LOGOUT
    # ========================================================

    def log_out(self):

        if messagebox.askyesno(
            "Log Out",
            "Log out and return to the login screen?",
            parent=self
        ):

            self.logout_requested = True

            self.destroy()

    # ========================================================
    # STOCK / REPORTS
    # ========================================================

    def open_lookup(self):

        if not self.can(
            "can_access_stock"
        ):

            messagebox.showerror(
                "Permission Denied",
                "You do not have permission to access Stock.",
                parent=self
            )

            return

        PriceLookupWindow(
            self
        )

    def open_reports(self):
        if not self.can("can_view_reports"):
            messagebox.showerror("Permission Denied","You do not have permission to view Reports.",parent=self)
            return
        ProfessionalReportWindow(self, "general", "Management Report")


    def open_sales_report(self):
        if not self.can("can_view_reports"):
            messagebox.showerror("Permission Denied","You do not have permission to view Sales Reports.",parent=self)
            return
        ProfessionalReportWindow(self, "sales", "Sales Report")


    # ========================================================
    # MULTI-INVOICE
    # ========================================================

    def create_new_invoice(
        self,
        switch_to=True
    ):

        invoice_id = self.next_invoice_id

        self.next_invoice_id += 1

        self.invoices[invoice_id] = {
            "cart": [],
            "customer_num": "CASH",
            "customer_name": "Cash Sale",
            "customer_id": None,
            "customer_type": "Retail"
        }

        if switch_to:

            self.switch_invoice(
                invoice_id
            )

        else:

            self.refresh_invoice_tabs()

        return invoice_id

    def current_invoice(self):

        return self.invoices[
            self.current_invoice_id
        ]

    def switch_invoice(
        self,
        invoice_id
    ):

        if invoice_id not in self.invoices:
            return

        # Save current customer information
        if (
            self.current_invoice_id
            in self.invoices
        ):

            current = self.invoices[
                self.current_invoice_id
            ]

            current["customer_num"] = self._sale_account_code() or "CASH"

            current["customer_name"] = (
                self.entry_name.get().strip()
                or "Cash Sale"
            )
            current.setdefault("customer_id", None)
            current.setdefault("customer_type", "Retail")

        self.current_invoice_id = invoice_id

        self.load_current_invoice()

        self.refresh_invoice_tabs()

        self.code_entry.focus_set()

    def load_current_invoice(self):

        if self.current_invoice_id is None:
            return

        invoice = self.current_invoice()

        account = invoice.get("customer_num", "CASH") or "CASH"
        self._refresh_sale_account_options(account)
        self.entry_num.set(account)

        self.entry_name.config(state="normal")
        self.entry_name.delete(
            0,
            tk.END
        )

        self.entry_name.insert(
            0,
            invoice.get(
                "customer_name",
                "Cash Sale"
            )
        )
        self.entry_name.config(state="readonly")
        invoice.setdefault("customer_id", None)
        invoice.setdefault("customer_type", "Retail")

        self.update_cart_display()

        self.clear_product_input()

        self.lbl_current_invoice.config(
            text=f"Invoice {self.current_invoice_id:03d}"
        )

    def refresh_invoice_tabs(self):

        if not hasattr(
            self,
            "invoice_tabs_frame"
        ):
            return

        for widget in self.invoice_tabs_frame.winfo_children():

            widget.destroy()

        for invoice_id, invoice in self.invoices.items():

            # Cart prices are VAT-inclusive.
            total = sum(
                item["value"]
                for item in invoice["cart"]
            )

            if invoice_id == self.current_invoice_id:

                bg = "#2c5282"
                fg = "white"

            else:

                bg = "#ffffff"
                fg = "#2d3748"

            text = (
                f"Invoice {invoice_id:03d}   "
                f"R {total:.2f}"
            )

            tk.Button(
                self.invoice_tabs_frame,
                text=text,
                font=("Segoe UI", 11, "bold"),
                bg=bg,
                fg=fg,
                relief=tk.RAISED,
                bd=1,
                padx=8,
                pady=4,
                command=lambda iid=invoice_id:
                    self.switch_invoice(iid)
            ).pack(
                side=tk.LEFT,
                padx=2
            )

        tk.Button(
            self.invoice_tabs_frame,
            text="+ New Invoice",
            font=("Segoe UI", 11, "bold"),
            bg="#38a169",
            fg="white",
            padx=8,
            pady=4,
            command=self.create_new_invoice
        ).pack(
            side=tk.LEFT,
            padx=5
        )

    def open_invoice_selector(self):

        InvoiceSelectorWindow(
            self
        )

    def close_current_invoice(self):

        if self.current_invoice_id is None:
            return

        invoice = self.current_invoice()

        if invoice["cart"]:

            answer = messagebox.askyesno(
                "Close Invoice",
                f"Invoice {self.current_invoice_id:03d} "
                f"contains items.\n\n"
                "Close it without completing the sale?",
                parent=self
            )

            if not answer:
                return

        closing_id = self.current_invoice_id

        del self.invoices[
            closing_id
        ]

        if not self.invoices:

            self.create_new_invoice()

            return

        remaining = list(
            self.invoices.keys()
        )

        new_current = remaining[-1]

        self.current_invoice_id = new_current

        self.load_current_invoice()

        self.refresh_invoice_tabs()

    def close_all_invoices(self):

        has_items = any(
            invoice["cart"]
            for invoice in self.invoices.values()
        )

        if has_items:

            answer = messagebox.askyesno(
                "Close All Invoices",
                "One or more open invoices contain items.\n\n"
                "Close all of them without completing the sales?",
                parent=self
            )

            if not answer:
                return

        self.invoices.clear()

        self.current_invoice_id = None

        self.create_new_invoice()

    # ========================================================
    # PRODUCT LOOKUP
    # ========================================================

    def handle_exact_barcode_entry(
        self,
        event=None
    ):

        query = (
            self.code_entry
            .get()
            .strip()
        )

        if not query:
            return

        conn = sqlite3.connect(
            DB_NAME
        )

        cursor = conn.cursor()

        try:

            cursor.execute(
                """
                SELECT
                    barcode,
                    description,
                    selling_price,
                    soh,
                    cost_price
                FROM products
                WHERE barcode = ?
                """,
                (query,)
            )

            exact_match = cursor.fetchone()

        finally:

            conn.close()

        if exact_match:

            self.populate_selected_product(
                exact_match
            )

            # Price is automatically accepted if
            # cashier cannot edit price.
            if not self.can(
                "can_edit_price"
            ):

                self.add_current_item_to_cart()

        else:

            self.open_f3_lookup()

    def _sale_account_code(self):
        """Return the canonical account code behind the account selector."""
        value = self.entry_num.get().strip() if hasattr(self, "entry_num") else ""
        if value.startswith("CASH"):
            return "CASH"
        return value.split(" — ", 1)[0].strip()

    def _refresh_sale_account_options(self, selected_account=None):
        """Load CASH plus every active debtor account into the sale selector."""
        if not hasattr(self, "entry_num"):
            return
        selected_account = selected_account or self._sale_account_code() or "CASH"
        conn = sqlite3.connect(DB_NAME)
        try:
            rows = conn.execute(
                "SELECT id, name FROM customers WHERE active=1 ORDER BY name COLLATE NOCASE, id"
            ).fetchall()
        except Exception as exc:
            _bkpos_logger.warning("Could not load debtor accounts", exc_info=exc)
            rows = []
        finally:
            conn.close()

        values = ["CASH — Cash Sale"] + [
            f"CUST-{int(row[0]):06d} — {row[1] or 'Debtor'}" for row in rows
        ]
        self.entry_num["values"] = values
        match = next((v for v in values if v.startswith(selected_account + " — ")), None)
        if selected_account == "CASH":
            match = values[0]
        self.entry_num.set(match or values[0])
        return match or values[0]

    def on_sale_account_selected(self, event=None):
        """Apply the selected CASH or debtor account to the current invoice."""
        account = self._sale_account_code()
        if not account:
            return "break"

        inv = self.current_invoice()
        if account == "CASH":
            inv["customer_id"] = None
            inv["customer_num"] = "CASH"
            inv["customer_name"] = "Cash Sale"
            inv["customer_type"] = "Retail"
            self.entry_name.config(state="normal")
            self.entry_name.delete(0, tk.END)
            self.entry_name.insert(0, "Cash Sale")
            self.entry_name.config(state="readonly")
            self.update_cart_display()
            self.code_entry.focus_set()
            return "break"

        try:
            customer_id = int(account.replace("CUST-", ""))
        except ValueError:
            messagebox.showwarning("Invalid Account", "Please select CASH or an active debtor account.", parent=self)
            self._refresh_sale_account_options("CASH")
            return "break"

        conn = sqlite3.connect(DB_NAME)
        try:
            row = conn.execute(
                "SELECT id, name, COALESCE(customer_type,'Retail') FROM customers WHERE id=? AND active=1",
                (customer_id,)
            ).fetchone()
        finally:
            conn.close()

        if not row:
            messagebox.showwarning("Account Not Found", "The selected debtor account is no longer active.", parent=self)
            self._refresh_sale_account_options("CASH")
            return "break"

        inv["customer_id"] = int(row[0])
        inv["customer_num"] = account
        inv["customer_name"] = row[1] or account
        inv["customer_type"] = row[2] or "Retail"
        self.entry_name.config(state="normal")
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, inv["customer_name"])
        self.entry_name.config(state="readonly")
        try:
            self._apply_current_customer_price()
        except Exception as exc:
            _bkpos_logger.warning("Could not refresh customer pricing after account selection", exc_info=exc)
        self.update_cart_display()
        self.code_entry.focus_set()
        return "break"

    def open_customer_lookup(self, event=None):
        """Open the same professional F3 customer selector used by quotations."""
        if event is not None and getattr(event, "widget", None) not in (self.entry_num, self.entry_name):
            # Top-level F3 remains the product lookup unless a customer field has focus.
            return None
        if hasattr(self, "customer_lookup_window") and self.customer_lookup_window is not None:
            try:
                if self.customer_lookup_window.winfo_exists():
                    self.customer_lookup_window.lift()
                    self.customer_lookup_window.focus_force()
                    return "break"
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in ui/pos.py", exc_info=exc)
        typed = self._sale_account_code() if hasattr(self, "entry_num") else ""
        if typed in ("CASH", "BULK") or typed.startswith("CUST-"):
            typed = "" if typed in ("CASH", "BULK") else typed.replace("CUST-", "")
        self.customer_lookup_window = CustomerLookupWindow(
            self, initial_query=typed, on_select_callback=self.on_customer_selected
        )
        return "break"

    def on_customer_selected(self, customer_id, customer_name, customer_type="Retail", phone=""):
        inv = self.current_invoice()
        inv["customer_id"] = int(customer_id)
        inv["customer_type"] = customer_type or "Retail"
        inv["customer_num"] = f"CUST-{int(customer_id):06d}"
        inv["customer_name"] = customer_name or "Cash Sale"
        self._refresh_sale_account_options(inv["customer_num"])
        self.entry_num.set(inv["customer_num"])
        self.entry_name.config(state="normal")
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, inv["customer_name"])
        self.entry_name.config(state="readonly")
        try:
            self._apply_current_customer_price()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in ui/pos.py", exc_info=exc)
        try:
            self.update_cart_display()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in ui/pos.py", exc_info=exc)
        try:
            self.code_entry.focus_set()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in ui/pos.py", exc_info=exc)

    def open_f3_lookup(
        self,
        event=None
    ):

        if (
            hasattr(
                self,
                "f3_window"
            )
            and self.f3_window is not None
            and self.f3_window.winfo_exists()
        ):

            self.f3_window.lift()

            self.f3_window.focus_force()

            return

        typed_text = (
            self.code_entry
            .get()
            .strip()
        )

        self.f3_window = F3SearchWindow(
            self,
            initial_query=typed_text,
            on_select_callback=self.on_f3_select
        )

    def on_f3_select(
        self,
        barcode
    ):

        conn = sqlite3.connect(
            DB_NAME
        )

        cursor = conn.cursor()

        try:

            cursor.execute(
                """
                SELECT
                    barcode,
                    description,
                    selling_price,
                    soh,
                    cost_price
                FROM products
                WHERE barcode = ?
                """,
                (barcode,)
            )

            product = cursor.fetchone()

        finally:

            conn.close()

        if product:

            self.populate_selected_product(
                product
            )

    def populate_selected_product(
        self,
        product
    ):

        barcode, name, price, stock, cost = product

        self.selected_product_data = {
            "code": barcode,
            "name": name,
            "price": price if price is not None else 0.0,
            "cost": cost if cost is not None else 0.0
        }

        self.code_entry.delete(
            0,
            tk.END
        )

        self.code_entry.insert(
            0,
            barcode
        )

        self.desc_display.config(
            state="normal"
        )

        self.desc_display.delete(
            0,
            tk.END
        )

        self.desc_display.insert(
            0,
            name
        )

        self.desc_display.config(
            state="readonly"
        )

        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        self.price_display.config(
            state="normal"
        )

        self.price_display.delete(
            0,
            tk.END
        )

        self.price_display.insert(
            0,
            f"{self.selected_product_data['price']:.2f}"
        )

        if not self.can(
            "can_edit_price"
        ):

            self.price_display.config(
                state="readonly"
            )

        self.lbl_credit.config(
            text=(
                "Credit Limit: 0.00 "
                "OS Bal: 0.00 "
                f"SOH: {stock:.1f}"
            )
        )

        if self.can(
            "can_edit_price"
        ):

            self.price_display.focus_set()

            self.price_display.select_range(
                0,
                tk.END
            )

        else:

            self.qty_entry.focus_set()

            self.qty_entry.select_range(
                0,
                tk.END
            )

    def confirm_price_and_focus_qty(
        self,
        event=None
    ):

        if not self.can(
            "can_edit_price"
        ):

            self.qty_entry.focus_set()

            self.qty_entry.select_range(
                0,
                tk.END
            )

            return

        try:

            edited_price = float(
                self.price_display
                .get()
                .strip()
            )

        except ValueError:

            messagebox.showerror(
                "Invalid Price",
                "Please enter a valid number.",
                parent=self
            )

            self.price_display.select_range(
                0,
                tk.END
            )

            return

        if hasattr(
            self,
            "selected_product_data"
        ):

            self.selected_product_data[
                "price"
            ] = edited_price

        self.qty_entry.config(
            state="normal"
        )

        self.qty_entry.focus_set()

        self.qty_entry.select_range(
            0,
            tk.END
        )

    # ========================================================
    # CART
    # ========================================================

    def add_current_item_to_cart(
        self,
        event=None
    ):

        if (
            not hasattr(
                self,
                "selected_product_data"
            )
            or not self.selected_product_data
        ):
            return

        # ----------------------------------------------------
        # QUANTITY
        # ----------------------------------------------------

        try:

            qty = float(
                self.qty_entry
                .get()
                .strip()
            )

        except ValueError:

            qty = 1.0

        if qty <= 0:
            qty = 1.0

        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        try:

            price = float(
                self.price_display
                .get()
                .strip()
            )

        except ValueError:

            price = float(
                self.selected_product_data[
                    "price"
                ]
            )

        item = self.selected_product_data

        val = price * qty

        invoice = self.current_invoice()

        invoice["cart"].append(
            {
                "code": item["code"],
                "name": item["name"],
                "qty": qty,
                "price": price,
                "cost": item["cost"],
                "value": val
            }
        )

        self.update_cart_display()

        self.selected_product_data = None

        self.clear_product_input()

        self.code_entry.focus_set()

    def clear_product_input(self):

        self.code_entry.delete(
            0,
            tk.END
        )

        self.desc_display.config(
            state="normal"
        )

        self.desc_display.delete(
            0,
            tk.END
        )

        self.desc_display.config(
            state="readonly"
        )

        self.price_display.config(
            state="normal"
        )

        self.price_display.delete(
            0,
            tk.END
        )

        self.price_display.insert(
            0,
            "0"
        )

        if not self.can(
            "can_edit_price"
        ):

            self.price_display.config(
                state="readonly"
            )

        self.qty_entry.config(
            state="normal"
        )

        self.qty_entry.delete(
            0,
            tk.END
        )

        self.qty_entry.insert(
            0,
            "1"
        )

        if not self.can(
            "can_edit_qty"
        ):

            self.qty_entry.config(
                state="readonly"
            )

        self.lbl_credit.config(
            text="Credit Limit: 0.00 OS Bal: 0.00"
        )

    def update_cart_display(self):

        if not hasattr(
            self,
            "tree"
        ):
            return

        for row in self.tree.get_children():

            self.tree.delete(
                row
            )

        invoice = self.current_invoice()

        subtotal = 0.0

        total_items = 0.0

        for item in invoice["cart"]:

            self.tree.insert(
                "",
                tk.END,
                values=(
                    item["code"],
                    item["name"],
                    f"{item['qty']:.0f}",
                    f"{item['price']:.2f}",
                    f"{item['value']:.2f}"
                )
            )

            subtotal += item["value"]

            total_items += item["qty"]

        # Selling prices are VAT-inclusive.
        total = subtotal
        vat = total * 15 / 115
        subtotal_ex_vat = total - vat

        self.lbl_subtotal.config(
            text=f"{subtotal_ex_vat:.2f}"
        )

        self.lbl_vat.config(
            text=f"{vat:.2f}"
        )

        self.lbl_total.config(
            text=f"{total:.2f}"
        )

        self.lbl_num_items.config(
            text=f"Num Items: {total_items:.1f}"
        )

        self.refresh_invoice_tabs()

    # ========================================================
    # DELETE ITEM
    # ========================================================

    def delete_selected_item(
        self,
        event=None
    ):

        if not self.can(
            "can_delete_items"
        ):

            messagebox.showwarning(
                "Permission Denied",
                "You do not have permission to delete cart items.",
                parent=self
            )

            return "break"

        selected = self.tree.selection()

        if not selected:
            return

        selected_index = self.tree.index(
            selected[0]
        )

        invoice = self.current_invoice()

        if selected_index < len(
            invoice["cart"]
        ):

            invoice["cart"].pop(
                selected_index
            )

            self.update_cart_display()

        return "break"

    # ========================================================
    # EDIT CART ITEM
    # ========================================================

    def open_edit_cart_item(
        self,
        event
    ):

        if not self.can(
            "can_delete_items"
        ):

            messagebox.showwarning(
                "Permission Denied",
                "You do not have permission to edit cart items.",
                parent=self
            )

            return

        row_id = self.tree.identify_row(
            event.y
        )

        if not row_id:
            return

        self.tree.selection_set(
            row_id
        )

        self.tree.focus(
            row_id
        )

        index = self.tree.index(
            row_id
        )

        invoice = self.current_invoice()

        if index >= len(
            invoice["cart"]
        ):
            return

        item = invoice["cart"][index]

        dialog = EditCartItemDialog(
            self,
            item["name"],
            item["qty"],
            item["price"],
            can_edit_price=self.can(
                "can_edit_price"
            ),
            can_edit_qty=self.can(
                "can_edit_qty"
            )
        )

        self.wait_window(
            dialog
        )

        if dialog.result is not None:

            new_qty, new_price = (
                dialog.result
            )

            if not self.can(
                "can_edit_qty"
            ):

                new_qty = item["qty"]

            if not self.can(
                "can_edit_price"
            ):

                new_price = item["price"]

            item["qty"] = new_qty

            item["price"] = new_price

            item["value"] = (
                new_qty * new_price
            )

            self.update_cart_display()

    def open_direct_credit_note(self, sale_id=None):
        """Open Credit Note directly for the invoice currently selected in POS.

        F12 -> Credit Note must stay on the current invoice. No Returns page,
        Sales Management page, or invoice search is opened.
        """
        try:
            invoice_id = self.current_invoice_id
            CreditNoteWindow(self, invoice_id=invoice_id, sale_id=sale_id)
        except Exception as exc:
            messagebox.showerror("Credit Note", f"Could not open Credit Note:\n{exc}", parent=self)

    def process_direct_credit_note(self):
        """Issue a credit note directly for the currently selected cart item.

        This is intentionally a POS-side return action: it does not open the
        Returns window. The selected cart line is credited, removed from the
        current invoice, and its quantity is restored to SOH.
        """
        invoice = self.current_invoice()
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(
                "Select Product",
                "Select the product you want to credit before pressing F12.",
                parent=self,
            )
            return False
        idx = self.tree.index(selected[0])
        cart = invoice.get("cart", [])
        if idx < 0 or idx >= len(cart):
            messagebox.showerror("Credit Note", "The selected product could not be found.", parent=self)
            return False
        item = cart[idx]
        try:
            qty = float(item.get("qty", 0) or 0)
            price = float(item.get("price", 0) or 0)
        except (TypeError, ValueError):
            messagebox.showerror("Credit Note", "Invalid product quantity or price.", parent=self)
            return False
        if qty <= 0:
            messagebox.showerror("Credit Note", "The selected product has no quantity to credit.", parent=self)
            return False
        total = round(qty * price, 2)
        from security_controls import require_permission, require_branch
        actor_ctx={"username": getattr(self,"cashier_username","Unknown"),
                   "role": getattr(self,"cashier_role",""), "is_admin": getattr(self,"is_admin",False),
                   "can_issue_credit_notes": getattr(self,"permissions",{}).get("can_issue_credit_notes",False),
                   "branch_id": getattr(self,"current_branch_id",1)}
        try:
            require_permission(actor_ctx, "can_issue_credit_notes")
            require_branch(actor_ctx, getattr(self,"current_branch_id",1))
        except PermissionError as exc:
            messagebox.showerror("Permission Denied", str(exc), parent=self); return False
        if not messagebox.askyesno(
            "Confirm Credit Note",
            f"Issue a Credit Note for this product?\n\n"
            f"{item.get('name', '')}\n"
            f"Quantity: {qty:g}\n"
            f"Amount: R {total:,.2f}\n\n"
            "The quantity will be added back to SOH.",
            parent=self,
        ):
            return False

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        try:
            # Keep standalone POS credit notes separate from returns linked to a
            # completed sale. This avoids inventing an original sale id.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS credit_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    invoice_ref TEXT,
                    barcode TEXT,
                    description TEXT,
                    qty REAL NOT NULL,
                    price REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    cashier TEXT DEFAULT 'Unknown',
                    reason TEXT DEFAULT 'Product return / Credit Note'
                )
            """)
            barcode = str(item.get("code", ""))
            cur.execute("SELECT COALESCE(soh, 0) FROM products WHERE barcode = ?", (barcode,))
            stock = cur.fetchone()
            if stock is None:
                raise ValueError(f"Product {barcode} was not found in Product Master.")
            soh_before = float(stock[0] or 0)
            cur.execute("""
                INSERT INTO credit_notes
                    (invoice_ref, barcode, description, qty, price, total_amount, cashier)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(self.current_invoice_id), barcode, item.get("name", ""), qty, price,
                total, getattr(self, "cashier_username", "Unknown")
            ))
            note_id = cur.lastrowid
            cur.execute(
                "UPDATE products SET soh = COALESCE(soh, 0) + ? WHERE barcode = ?",
                (qty, barcode),
            )
            if cur.rowcount != 1:
                raise ValueError("Stock could not be restored.")
            from services.stock_service import record_stock_movement
            record_stock_movement(
                barcode, "RETURN", qty, reference=f"CREDIT NOTE #{note_id}",
                description=item.get("name", ""), qty_before=soh_before,
                qty_after=soh_before + qty,
                cashier=getattr(self, "cashier_username", "Unknown"), conn=conn)
            try:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        username TEXT,
                        action TEXT,
                        details TEXT,
                        reference TEXT
                    )
                """)
                cur.execute("""
                    INSERT INTO audit_log (event_time, timestamp, username, action, details, reference, event_type)
                    VALUES (datetime('now','localtime'), datetime('now','localtime'), ?, 'CREDIT NOTE', ?, ?, 'CREDIT NOTE')
                """, (getattr(self, "cashier_username", "Unknown"),
                      f"Returned {qty:g} x {item.get('name','')} to stock; SOH {soh_before:g} -> {soh_before + qty:g}",
                      f"CREDIT NOTE #{note_id}"))
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in ui/pos.py", exc_info=exc)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            messagebox.showerror("Credit Note Failed", str(exc), parent=self)
            return False
        finally:
            conn.close()

        invoice["cart"].pop(idx)
        self.update_cart_display()
        self.clear_product_input()
        messagebox.showinfo(
            "Credit Note Completed",
            f"Credit Note #{note_id} completed.\n\n"
            f"Product: {item.get('name','')}\n"
            f"Quantity: {qty:g}\n"
            f"Credit: R {total:,.2f}\n\n"
            "Stock has been increased.",
            parent=self,
        )
        return True

    # ========================================================
    # PAYMENT
    # ========================================================

    def ask_payment_type(self, total_override=None):

        # Payment handling lives in payment.py so the main POS
        # remains stable.  The method keeps the existing app API.
        from payment import get_payment

        invoice = self.current_invoice()

        # Cart prices are already VAT-inclusive.
        total = total_override if total_override is not None else sum(
            item["value"]
            for item in invoice["cart"]
        )

        vat = total - (total / 1.15)

        subtotal = total / 1.15

        return get_payment(
            self,
            total,
            len(invoice["cart"])
        )

    # ========================================================
    # CHECKOUT
    # ========================================================

    def checkout(
        self,
        event=None
    ):

        invoice = self.current_invoice()

        if not invoice["cart"]:

            messagebox.showwarning(
                "Empty Cart",
                "Cannot checkout - cart is empty!",
                parent=self
            )

            return

        # Every invoice must have an explicit sale account: CASH or a real
        # active debtor account. The dropdown normally prevents an empty value,
        # but this guard also protects programmatic/legacy invoice states.
        account = (invoice.get("customer_num") or self._sale_account_code() or "").strip()
        if not account:
            messagebox.showwarning(
                "Sale Account Required",
                "Select CASH or a debtor account before making the invoice.",
                parent=self
            )
            self.entry_num.focus_set()
            return
        if account == "CASH":
            invoice["customer_id"] = None
            invoice["customer_num"] = "CASH"
            invoice["customer_name"] = "Cash Sale"
        else:
            customer_id = invoice.get("customer_id")
            if not customer_id or not account.startswith("CUST-"):
                messagebox.showwarning(
                    "Sale Account Required",
                    "Select CASH or a valid debtor account from Account / No. before making the invoice.",
                    parent=self
                )
                self.entry_num.focus_set()
                return
            check_conn = sqlite3.connect(DB_NAME)
            try:
                active = check_conn.execute(
                    "SELECT 1 FROM customers WHERE id=? AND active=1", (int(customer_id),)
                ).fetchone()
            finally:
                check_conn.close()
            if not active:
                messagebox.showwarning(
                    "Account Not Available",
                    "The selected debtor account is no longer active. Select another account.",
                    parent=self
                )
                self._refresh_sale_account_options("CASH")
                self.entry_num.focus_set()
                return

        subtotal = sum(
            item["value"]
            for item in invoice["cart"]
        )

        # Promotions are evaluated before payment but do not mutate the open cart.
        # The selected promotion is applied transactionally to the sale copy.
        sale_cart = list(invoice["cart"])
        promotion = {"promotion_id": None, "discount": 0.0, "total": subtotal, "cart": sale_cart, "name": ""}
        try:
            from services.promotion_service import calculate_best_promotion
            promo_conn = sqlite3.connect(DB_NAME)
            promotion = calculate_best_promotion(promo_conn, sale_cart)
            promo_conn.close()
        except Exception as exc:
            _bkpos_logger.warning("Promotion evaluation failed; continuing at normal price", exc_info=exc)
        sale_cart = promotion["cart"]
        total = promotion["total"]
        vat = total * 15 / 115
        subtotal_ex_vat = total - vat

        total_cost = sum(
            item["cost"] * item["qty"]
            for item in invoice["cart"]
        )

        payment_info = self.ask_payment_type(total_override=total)

        if payment_info is None:
            return

        payment_type = payment_info["payment_type"]
        amount_tendered = payment_info["amount_tendered"]
        change_amount = payment_info["change"]

        # Customer account / debtor control. A credit sale must be attached
        # to a real customer and must remain within that customer's limit.
        if payment_type == "Credit Account":
            customer_id = invoice.get("customer_id")
            if not customer_id:
                messagebox.showwarning(
                    "Customer Account Required",
                    "Select a customer with F3 Customer Lookup before using Credit Account.",
                    parent=self
                )
                return
            try:
                from customer_accounts import ensure_schema as ensure_customer_accounts, balance as customer_balance
                ensure_customer_accounts()
                account_conn = sqlite3.connect(DB_NAME)
                row = account_conn.execute("SELECT name, COALESCE(credit_limit,0), active FROM customers WHERE id=?", (int(customer_id),)).fetchone()
                current_balance = customer_balance(int(customer_id), account_conn)
                account_conn.close()
                if not row or not row[2]:
                    raise ValueError("The selected customer account is inactive or no longer exists.")
                limit = float(row[1] or 0)
                if limit <= 0:
                    raise ValueError(f"{row[0]} has no credit limit. Set a credit limit in Customer & Pricing first.")
                if current_balance + total > limit + 1e-9:
                    raise ValueError(
                        f"Credit limit exceeded for {row[0]}.\n\n"
                        f"Credit limit: R {limit:,.2f}\n"
                        f"Current balance: R {current_balance:,.2f}\n"
                        f"Invoice: R {total:,.2f}\n"
                        f"Available credit: R {max(limit-current_balance,0):,.2f}"
                    )
            except Exception as exc:
                messagebox.showwarning("Credit Account", str(exc), parent=self)
                return

        conn = sqlite3.connect(DB_NAME)

        try:
            from services.sales_service import post_sale
            sale_id = post_sale(
                conn,
                cart=sale_cart,
                total=total,
                total_cost=total_cost,
                payment_info=payment_info,
                payment_type=payment_type,
                cashier=self.cashier_username,
                branch_id=getattr(self, "current_branch_id", 1),
                branch_name=getattr(self, "current_branch_name", "Main Store"),
                customer_id=invoice.get("customer_id"),
                customer_account=invoice.get("customer_num", "CASH"),
                customer_name=invoice.get("customer_name", "Cash Sale"),
                promotion_id=promotion.get("promotion_id"),
                promotion_discount=promotion.get("discount", 0.0),
            )
            conn.commit()

            sold_items = list(sale_cart)

            # Remove ONLY the completed invoice
            completed_invoice_id = (
                self.current_invoice_id
            )

            del self.invoices[
                completed_invoice_id
            ]

            # If no other invoices exist,
            # automatically create a new one.
            if not self.invoices:

                self.current_invoice_id = None

                self.create_new_invoice()

            else:

                self.current_invoice_id = list(
                    self.invoices.keys()
                )[-1]

                self.load_current_invoice()

                self.refresh_invoice_tabs()

            if promotion.get("discount", 0) > 0:
                messagebox.showinfo(
                    "Promotion Applied",
                    f"Promotion: {promotion.get('name','')}\n\nDiscount: R {promotion.get('discount',0):,.2f}\nNew total: R {total:,.2f}",
                    parent=self
                )

            # Ask the cashier whether the completed invoice should be printed.
            # The sale is already safely saved at this point.
            print_invoice = messagebox.askyesno(
                "Print Invoice",
                f"Invoice {completed_invoice_id:03d} has been confirmed.\n\n"
                "Do you want to print the invoice now?",
                parent=self
            )

            self.generate_pdf_receipt(
                sold_items,
                total,
                payment_type,
                invoice_number=f"{completed_invoice_id:03d}",
                customer_name=invoice.get(
                    "customer_name",
                    "Cash Sale"
                ),
                payment_info=payment_info,
                print_thermal=print_invoice
            )

        except Exception as e:

            conn.rollback()

            messagebox.showerror(
                "Database Error",
                (
                    "Failed to save sale:\n\n"
                    f"{str(e)}"
                ),
                parent=self
            )

        finally:

            conn.close()

    # ========================================================
    # PDF RECEIPT
    # ========================================================

    # ========================================================
    # RECEIPT PRINTING + PDF
    # ========================================================

    def generate_pdf_receipt(
            self,
            sold_items,
            total,
            payment_type,
            invoice_number="",
            customer_name="Cash Sale",
            payment_info=None,
            print_thermal=True
    ):
        """
        Complete receipt handling.

        1. Prints directly to the Epson thermal printer.
        2. Creates a PDF copy for sharing.
        3. Printer/PDF errors do NOT affect the completed sale.
        """

        printed = False
        print_error = None

        jasper_previewed = False
        jasper_error = None
        jasper_file = None

        pdf_filename = None
        pdf_error = None

        # ====================================================
        # JASPER VIEWER PREVIEW
        # ====================================================
        # This is presentation-only. The sale has already been committed to
        # SQLite above; Jasper never owns invoice or stock business logic.
        if print_thermal:
            try:
                from jasper_reports.jasper_receipt import (
                    find_jasper_viewer, get_branch_info, write_jrpxml, open_in_jasperviewer
                )
                # Only create/launch the preview when a Jasper runtime has been
                # configured. Existing receipt printing remains unchanged for
                # installations that do not use JasperViewer yet.
                if find_jasper_viewer():
                    branch = get_branch_info(DB_NAME)
                    jasper_file = write_jrpxml(
                        items=sold_items,
                        total=total,
                        payment_type=payment_type,
                        cashier=self.cashier_name,
                        invoice_number=invoice_number,
                        customer_name=customer_name,
                        store_name=get_store_name(),
                        store_address=branch.get("address", ""),
                        store_phone=branch.get("phone", ""),
                        payment_info=payment_info or {},
                    )
                    jasper_previewed, jasper_error = open_in_jasperviewer(jasper_file)
            except Exception as e:
                jasper_error = str(e)

        # ====================================================
        # DIRECT THERMAL PRINTING
        # ====================================================

        try:

            if not print_thermal:
                raise RuntimeError("Thermal printing skipped by cashier.")

            from services.receipt_printing import safe_print_receipt

            receipt_result = safe_print_receipt(
                items=sold_items,
                total=total,
                payment_type=payment_type,
                cashier=self.cashier_name,
                invoice_number=invoice_number,
                customer_name=customer_name,
                subtotal=float(total) / 1.15,
                vat=float(total) - (float(total) / 1.15),
                amount_tendered=(payment_info or {}).get("amount_tendered", 0),
                change=(payment_info or {}).get("change", 0),
                cash_amount=(payment_info or {}).get("cash", 0),
                card_amount=(payment_info or {}).get("card", 0)
            )

            printed = receipt_result.success
            if not receipt_result.success:
                print_error = (
                    "SALE COMPLETED - RECEIPT NOT PRINTED.\n\n"
                    f"Printer: {receipt_result.printer_name}\n\n"
                    f"Reason: {receipt_result.message}\n\n"
                    "You can reprint this receipt from History after resolving the printer problem."
                )

        except Exception as e:
            print_error = str(e)

        # ====================================================
        # CREATE PDF COPY
        # ====================================================

        try:

            from reportlab.lib.pagesizes import A5
            from reportlab.pdfgen import canvas

            os.makedirs(
                "receipts",
                exist_ok=True
            )

            timestamp = time.strftime(
                "%Y%m%d_%H%M%S"
            )

            if invoice_number:

                pdf_name = (
                    f"receipt_"
                    f"{invoice_number}_"
                    f"{timestamp}.pdf"
                )

            else:

                pdf_name = (
                    f"receipt_"
                    f"{timestamp}.pdf"
                )

            pdf_filename = os.path.abspath(
                os.path.join(
                    "receipts",
                    pdf_name
                )
            )

            c = canvas.Canvas(
                pdf_filename,
                pagesize=A5
            )

            width, height = A5

            y = height - 40

            # ------------------------------------------------
            # HEADER
            # ------------------------------------------------

            c.setFont(
                "Helvetica-Bold",
                18
            )

            c.drawString(
                50,
                y,
                get_store_name()
            )

            y -= 25

            c.setFont(
                "Helvetica",
                11
            )

            if invoice_number:
                c.drawString(
                    50,
                    y,
                    f"Invoice: {invoice_number}"
                )

                y -= 18

            c.setFont(
                "Helvetica",
                9
            )

            c.drawString(
                50,
                y,
                f"Date: {time.strftime('%Y-%m-%d %H:%M')}"
            )

            y -= 15

            c.drawString(
                50,
                y,
                f"Cashier: {self.cashier_name}"
            )

            y -= 15

            c.drawString(
                50,
                y,
                f"Customer: {customer_name or 'Cash Sale'}"
            )

            y -= 15

            c.drawString(
                50,
                y,
                f"Payment: {payment_type}"
            )

            y -= 15

            # Payment details are included when supplied by the F12 dialog.
            if payment_info:
                cash_amount = float(payment_info.get("cash", 0) or 0)
                card_amount = float(payment_info.get("card", 0) or 0)
                amount_tendered = float(
                    payment_info.get("amount_tendered", 0) or 0
                )
                change_amount = float(
                    payment_info.get("change", 0) or 0
                )

                if payment_type == "Cash":
                    c.drawString(
                        50, y,
                        f"Amount tendered: R {amount_tendered:.2f}"
                    )
                    y -= 15
                    c.drawString(
                        50, y,
                        f"Change: R {change_amount:.2f}"
                    )
                    y -= 15

                elif payment_type == "Split Payment":
                    c.drawString(
                        50, y,
                        f"Cash: R {cash_amount:.2f}"
                    )
                    y -= 15
                    c.drawString(
                        50, y,
                        f"Card: R {card_amount:.2f}"
                    )
                    y -= 15

            y -= 10

            c.line(
                50,
                y + 10,
                width - 50,
                y + 10
            )

            # ------------------------------------------------
            # COLUMN HEADINGS
            # ------------------------------------------------

            c.setFont(
                "Helvetica-Bold",
                9
            )

            c.drawString(
                50,
                y,
                "Item"
            )

            c.drawString(
                200,
                y,
                "Qty"
            )

            c.drawString(
                250,
                y,
                "Price"
            )

            c.drawString(
                320,
                y,
                "Total"
            )

            y -= 15

            # ------------------------------------------------
            # ITEMS
            # ------------------------------------------------

            c.setFont(
                "Helvetica",
                9
            )

            for item in sold_items:

                name = str(
                    item.get(
                        "name",
                        ""
                    )
                )[:25]

                qty = float(
                    item.get(
                        "qty",
                        0
                    ) or 0
                )

                price = float(
                    item.get(
                        "price",
                        0
                    ) or 0
                )

                value = float(
                    item.get(
                        "value",
                        0
                    ) or 0
                )

                c.drawString(
                    50,
                    y,
                    name
                )

                c.drawString(
                    200,
                    y,
                    f"{qty:.0f}"
                )

                c.drawString(
                    250,
                    y,
                    f"{price:.2f}"
                )

                c.drawString(
                    320,
                    y,
                    f"{value:.2f}"
                )

                y -= 15

                if y < 60:
                    c.showPage()

                    y = height - 40

                    c.setFont(
                        "Helvetica",
                        9
                    )

            # ------------------------------------------------
            # TOTALS
            # ------------------------------------------------

            # Receipt totals are VAT-inclusive.
            total_inclusive = sum(
                float(
                    item.get(
                        "value",
                        0
                    ) or 0
                )
                for item in sold_items
            )

            subtotal = total_inclusive / 1.15
            vat = total_inclusive - subtotal

            y -= 5

            c.line(
                50,
                y + 10,
                width - 50,
                y + 10
            )

            y -= 5

            c.setFont(
                "Helvetica-Bold",
                10
            )

            c.drawString(
                50,
                y,
                "Subtotal:"
            )

            c.drawString(
                320,
                y,
                f"R {subtotal:.2f}"
            )

            y -= 15

            c.drawString(
                50,
                y,
                "VAT (15%):"
            )

            c.drawString(
                320,
                y,
                f"R {vat:.2f}"
            )

            y -= 18

            c.setFont(
                "Helvetica-Bold",
                14
            )

            c.drawString(
                50,
                y,
                "TOTAL:"
            )

            c.drawString(
                320,
                y,
                f"R {float(total):.2f}"
            )

            y -= 30

            c.setFont(
                "Helvetica",
                10
            )

            c.drawString(
                50,
                y,
                "Thank you for shopping!"
            )

            y -= 15

            c.drawString(
                50,
                y,
                "Please come again"
            )

            c.save()

        except ImportError:

            pdf_error = (
                "ReportLab is not installed."
            )

        except Exception as e:

            pdf_error = str(e)

        # ====================================================
        # RESULT MESSAGE
        # ====================================================

        message = (
            "Transaction saved!\n\n"
            f"Items sold: {len(sold_items)}\n"
            f"Total: R {float(total):.2f}\n"
            f"Payment: {payment_type}\n"
            "Stock has been updated.\n\n"
        )

        if jasper_previewed:
            message += (
                "JasperViewer preview opened successfully.\n"
            )
        elif jasper_error:
            message += (
                "JasperViewer preview was not opened.\n"
                f"Preview status: {jasper_error}\n"
            )

        if printed:

            message += (
                "Receipt printed successfully.\n"
                f"Printer: {receipt_result.printer_name}\n"
            )

        else:

            message += (
                "Receipt could NOT be printed.\n\n"
                f"Printer error:\n{print_error}\n"
            )

        if pdf_filename:

            message += (
                "\nPDF receipt saved:\n"
                f"{pdf_filename}"
            )

        elif pdf_error:

            message += (
                "\nPDF receipt was not created:\n"
                f"{pdf_error}"
            )

        messagebox.showinfo(
            "Sale Complete!",
            message,
            parent=self
        )

        # ====================================================
        # SHARE PDF
        # ====================================================

        if (
                pdf_filename
                and os.path.exists(pdf_filename)
        ):

            if messagebox.askyesno(
                    "Share Receipt",
                    "Would you like to share this receipt?",
                    parent=self
            ):
                self.show_share_options(
                    pdf_filename
                )

    # ========================================================
    # SHARE RECEIPT
    # ========================================================

    def show_share_options(
        self,
        filename
    ):

        popup = tk.Toplevel(
            self
        )

        popup.title(
            "Share Receipt"
        )

        popup.geometry(
            "360x260"
        )

        popup.resizable(
            False,
            False
        )

        popup.configure(
            bg="#f0f4f8"
        )

        popup.transient(
            self
        )

        popup.grab_set()

        popup.update_idletasks()

        x = (
            popup.winfo_screenwidth() // 2
            - 180
        )

        y = (
            popup.winfo_screenheight() // 2
            - 130
        )

        popup.geometry(
            f"360x260+{x}+{y}"
        )

        tk.Label(
            popup,
            text="Share Receipt",
            font=("Segoe UI", 14, "bold"),
            bg="#2c5282",
            fg="white",
            pady=10
        ).pack(
            fill=tk.X
        )

        body = tk.Frame(
            popup,
            bg="#f0f4f8",
            padx=20,
            pady=15
        )

        body.pack(
            fill=tk.BOTH,
            expand=True
        )

        tk.Label(
            body,
            text="How would you like to share?",
            font=("Segoe UI", 11),
            bg="#f0f4f8"
        ).pack(
            pady=5
        )

        btn_frame = tk.Frame(
            body,
            bg="#f0f4f8"
        )

        btn_frame.pack(
            pady=10
        )

        def share_email():

            try:

                if os.name == "nt":

                    os.startfile(
                        filename
                    )

                else:

                    webbrowser.open(
                        f"file://{filename}"
                    )

                messagebox.showinfo(
                    "Email",
                    (
                        "The PDF has been opened.\n\n"
                        "From your email app: create a new email, "
                        "then attach this PDF file."
                    ),
                    parent=popup
                )

            except Exception as e:

                messagebox.showerror(
                    "Could not open PDF",
                    str(e),
                    parent=popup
                )

            popup.destroy()

        def share_whatsapp():

            popup.destroy()

            self._ask_whatsapp_number(
                filename
            )

        tk.Button(
            btn_frame,
            text="Email",
            font=("Segoe UI", 11, "bold"),
            bg="#3182ce",
            fg="white",
            width=12,
            height=2,
            command=share_email
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Button(
            btn_frame,
            text="WhatsApp",
            font=("Segoe UI", 11, "bold"),
            bg="#25D366",
            fg="white",
            width=12,
            height=2,
            command=share_whatsapp
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Label(
            body,
            text=(
                "Note: WhatsApp Web can't auto-attach a file,\n"
                "so the receipt folder will also open for you\n"
                "to drag the PDF into the chat."
            ),
            font=("Segoe UI", 8),
            fg="#4a5568",
            bg="#f0f4f8",
            justify="center"
        ).pack(
            pady=(10, 0)
        )

        tk.Button(
            popup,
            text="Close",
            font=("Segoe UI", 9),
            command=popup.destroy
        ).pack(
            pady=8
        )

    # ========================================================
    # WHATSAPP
    # ========================================================

    def _ask_whatsapp_number(
        self,
        filename
    ):

        phone_popup = tk.Toplevel(
            self
        )

        phone_popup.title(
            "WhatsApp"
        )

        phone_popup.geometry(
            "320x180"
        )

        phone_popup.resizable(
            False,
            False
        )

        phone_popup.configure(
            bg="#f0f4f8"
        )

        phone_popup.transient(
            self
        )

        phone_popup.grab_set()

        phone_popup.update_idletasks()

        x = (
            phone_popup.winfo_screenwidth() // 2
            - 160
        )

        y = (
            phone_popup.winfo_screenheight() // 2
            - 90
        )

        phone_popup.geometry(
            f"320x180+{x}+{y}"
        )

        tk.Label(
            phone_popup,
            text="Customer's WhatsApp Number",
            font=("Segoe UI", 11, "bold"),
            bg="#f0f4f8"
        ).pack(
            pady=(15, 5)
        )

        tk.Label(
            phone_popup,
            text="(include country code, e.g. 27821234567)",
            font=("Segoe UI", 8),
            fg="#4a5568",
            bg="#f0f4f8"
        ).pack()

        entry_phone = tk.Entry(
            phone_popup,
            font=("Segoe UI", 14),
            width=20,
            justify="center"
        )

        entry_phone.pack(
            pady=10
        )

        entry_phone.focus_set()

        def send():

            number = (
                entry_phone
                .get()
                .strip()
                .replace(" ", "")
                .replace("+", "")
            )

            if not number.isdigit():

                messagebox.showerror(
                    "Invalid Number",
                    (
                        "Please enter digits only, "
                        "with country code."
                    ),
                    parent=phone_popup
                )

                return

            message = (
                "Hi! Here is your receipt from "
                f"{get_store_name()}. Please see "
                "the attached PDF."
            )

            encoded_message = (
                urllib.parse.quote(
                    message
                )
            )

            url = (
                f"https://wa.me/"
                f"{number}"
                f"?text={encoded_message}"
            )

            webbrowser.open(
                url
            )

            try:

                if os.name == "nt":

                    os.startfile(
                        os.path.dirname(
                            filename
                        )
                    )

                else:

                    webbrowser.open(
                        f"file://"
                        f"{os.path.dirname(filename)}"
                    )

            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in ui/pos.py", exc_info=exc)

            phone_popup.destroy()

        tk.Button(
            phone_popup,
            text="Open WhatsApp",
            font=("Segoe UI", 10, "bold"),
            bg="#25D366",
            fg="white",
            command=send
        ).pack(
            pady=5
        )

        entry_phone.bind(
            "<Return>",
            lambda e: send()
        )


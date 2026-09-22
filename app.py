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


# ============================================================
# DATABASE
# ============================================================

from core.config import DB_PATH, _startup_database_safety
from services.lifecycle_hardening import startup_runtime, clean_shutdown, install_exception_hook

DB_NAME = DB_PATH

startup_runtime()
install_exception_hook()

init_db()
_startup_database_safety()


# ============================================================
# COLORS
# ============================================================

UI_BG = "#eef2f7"
FRAME_BG = "#e1e8f0"
WHITE = "#ffffff"
BLUE_TEXT = "#2c5282"
BLUE_BORDER = "#3182ce"
PURPLE_LABEL = "#7c3aed"
LOOKUP_BG = "#d4ecee"
HEADER_COLOR = "#2c5282"


# ============================================================
# F3 DATA LOOKUP
# ============================================================


# Public imports retained for backwards compatibility with feature modules.
from ui.windows import (
    CustomerLookupWindow, F3SearchWindow, EditCartItemDialog, InvoiceSelectorWindow
)
from ui.pos import FamilySupermarketPOS

from management_upgrades import install as install_management_upgrades


install_management_upgrades(FamilySupermarketPOS)


from pos_six_upgrades import install as install_six_upgrades


install_six_upgrades(FamilySupermarketPOS)


from product_master_wholesale import install as install_product_master_wholesale


install_product_master_wholesale(FamilySupermarketPOS)


from customer_pricing import install as install_customer_pricing


install_customer_pricing(FamilySupermarketPOS)


from menu_organization import install as install_menu_organization


install_menu_organization(FamilySupermarketPOS)


from sales_management import install as install_sales_management


install_sales_management(FamilySupermarketPOS)


from smart_pos_controls import install as install_smart_pos_controls


install_smart_pos_controls(FamilySupermarketPOS)


from financial_controls import install as install_financial_controls


install_financial_controls(FamilySupermarketPOS)


# Phase 4 — advanced financial controls (read-only management controls).
from phase4_financial_controls import FinancialControlsWindow

_old_create_menu_bar_phase4 = FamilySupermarketPOS.create_menu_bar
def _create_menu_bar_phase4(self):
    _old_create_menu_bar_phase4(self)
    try:
        mb = self.nametowidget(self["menu"])
        util = None
        for i in range(mb.index("end") + 1):
            if mb.type(i) == "cascade" and mb.entrycget(i, "label") == "Utility":
                util = mb.nametowidget(mb.entrycget(i, "menu")); break
        if util is not None and (getattr(self, "is_admin", False) or self.can("can_view_reports")):
            util.add_separator()
            util.add_command(label="Advanced Financial Controls", command=lambda: FinancialControlsWindow(self))
    except Exception as exc:
        from core.logger import logger
        logger.warning("Suppressed exception while installing Phase 4 menu", exc_info=exc)
FamilySupermarketPOS.create_menu_bar = _create_menu_bar_phase4


from budget_expenses import install as install_budget_expenses


install_budget_expenses(FamilySupermarketPOS)


from quotation import install as install_quotation


install_quotation(FamilySupermarketPOS)


from professional_menu_cleanup import install as install_professional_menu


install_professional_menu(FamilySupermarketPOS)


from production_upgrade import install as install_production_upgrade


install_production_upgrade(FamilySupermarketPOS)


from dashboard import install as install_dashboard


install_dashboard(FamilySupermarketPOS)


def main():

    """
    Shows login screen, then the main POS.

    The login.py supplied with the permissions system returns:

        {
            "username": ...,
            "full_name": ...,
            "role": ...,
            "can_edit_price": ...,
            ...
        }

    This app accepts that dictionary.
    """

    while True:

        login_result = show_login_window()

        if login_result is None:

            break

        # ----------------------------------------------------
        # New permissions login.py format
        # ----------------------------------------------------

        if isinstance(
            login_result,
            dict
        ):

            username = login_result.get(
                "username",
                ""
            )

            full_name = login_result.get(
                "full_name",
                username
            )

            role = login_result.get(
                "role",
                "Cashier"
            )

            permissions = {
                key: login_result.get(
                    key,
                    False
                )
                for key in [
                    "can_edit_price",
                    "can_edit_qty",
                    "can_delete_items",
                    "can_view_reports",
                    "can_access_stock",
                    "can_access_debtors",
                    "can_access_creditors",
                    "can_access_utility"
                ]
            }

        # ----------------------------------------------------
        # Backwards compatibility with old login.py
        # ----------------------------------------------------

        else:

            try:

                username, full_name, role = (
                    login_result
                )

            except Exception:

                messagebox.showerror(
                    "Login Error",
                    "Invalid login result returned by login.py."
                )

                break

            permissions = {}

        # ----------------------------------------------------
        # Start POS
        # ----------------------------------------------------

        app = FamilySupermarketPOS(
            username,
            full_name,
            role,
            permissions
        )

        app.mainloop()

        if not app.logout_requested:

            break


if __name__ == "__main__":
    try:
        main()
    finally:
        clean_shutdown()

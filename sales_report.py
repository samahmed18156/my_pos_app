from core.config import DB_PATH
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

try:
    from customer_accounts import ensure_schema as ensure_customer_account_schema
except ImportError:
    ensure_customer_account_schema = None

COLORS = {
    "bg": "#f0f4f8",
    "header": "#2b6cb0",
    "accent_blue": "#3182ce",
    "accent_green": "#38a169",
    "accent_red": "#e53e3e",
    "accent_orange": "#dd6b20",
    "accent_purple": "#805ad5",
    "card_bg": "#ffffff",
    "text_primary": "#1a202c",
    "text_secondary": "#4a5568",
    "border": "#e2e8f0",
}

FONTS = {
    "title": ("Segoe UI", 18, "bold"),
    "heading": ("Segoe UI", 13, "bold"),
    "normal": ("Segoe UI", 11),
    "small": ("Segoe UI", 9),
    "number": ("Segoe UI", 22, "bold"),
}


class SalesReportWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Sales Report")
        self.geometry("1000x700")
        self.configure(bg=COLORS["bg"])
        self.minsize(900, 600)

        # Header
        header = tk.Frame(self, bg=COLORS["header"], height=50)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        tk.Label(header, text="📊 Sales Report", font=("Segoe UI", 16, "bold"),
                 fg="white", bg=COLORS["header"]).pack(pady=10)

        # Main container
        main_frame = tk.Frame(self, bg=COLORS["bg"], padx=20, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ===== DATE RANGE SELECTION =====
        filter_frame = tk.LabelFrame(main_frame, text="📅 Select Date Range",
                                     font=FONTS["heading"], bg=COLORS["bg"],
                                     fg=COLORS["text_primary"], padx=15, pady=10)
        filter_frame.pack(fill=tk.X, pady=(0, 15))

        # Quick buttons
        quick_frame = tk.Frame(filter_frame, bg=COLORS["bg"])
        quick_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(quick_frame, text="Quick Select:", font=FONTS["normal"],
                 bg=COLORS["bg"], fg=COLORS["text_secondary"]).pack(side=tk.LEFT, padx=(0, 10))

        self.selected_period = tk.StringVar(value="today")

        periods = [
            ("Today", "today"),
            ("Yesterday", "yesterday"),
            ("This Week", "week"),
            ("This Month", "month"),
            ("All Time", "all")
        ]

        for text, value in periods:
            rb = tk.Radiobutton(quick_frame, text=text, variable=self.selected_period,
                               value=value, font=FONTS["normal"], bg=COLORS["bg"],
                               command=self.load_report)
            rb.pack(side=tk.LEFT, padx=5)

        # Custom date range
        custom_frame = tk.Frame(filter_frame, bg=COLORS["bg"])
        custom_frame.pack(fill=tk.X, pady=(5, 0))

        tk.Label(custom_frame, text="From:", font=FONTS["normal"],
                 bg=COLORS["bg"], fg=COLORS["text_secondary"]).pack(side=tk.LEFT, padx=(0, 5))

        self.from_date = tk.Entry(custom_frame, font=FONTS["normal"], width=12, bd=1, relief=tk.SOLID)
        self.from_date.pack(side=tk.LEFT, padx=(0, 10))
        self.from_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        tk.Label(custom_frame, text="To:", font=FONTS["normal"],
                 bg=COLORS["bg"], fg=COLORS["text_secondary"]).pack(side=tk.LEFT, padx=(0, 5))

        self.to_date = tk.Entry(custom_frame, font=FONTS["normal"], width=12, bd=1, relief=tk.SOLID)
        self.to_date.pack(side=tk.LEFT, padx=(0, 10))
        self.to_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        tk.Button(custom_frame, text="Apply Custom", font=FONTS["small"],
                  bg=COLORS["accent_blue"], fg="white", padx=10,
                  command=self.load_custom_report).pack(side=tk.LEFT)
        tk.Button(custom_frame, text="View in JasperViewer", font=FONTS["small"], bg=COLORS["accent_purple"], fg="white", padx=10, command=self.view_in_jasperviewer).pack(side=tk.LEFT, padx=6)

        # ===== SUMMARY CARDS =====
        self.summary_frame = tk.Frame(main_frame, bg=COLORS["bg"])
        self.summary_frame.pack(fill=tk.X, pady=(0, 15))

        # ===== REPORT TABLE =====
        tk.Label(main_frame, text="Transaction Details", font=FONTS["heading"],
                 bg=COLORS["bg"], fg=COLORS["text_primary"]).pack(anchor="w", pady=(0, 5))

        table_frame = tk.Frame(main_frame, bg=COLORS["card_bg"], bd=1, relief=tk.SOLID)
        table_frame.pack(fill=tk.BOTH, expand=False)
        table_frame.configure(height=250)

        columns = ("id", "date", "total", "payment", "cashier")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        self.tree.heading("id", text="Receipt #")
        self.tree.heading("date", text="Date & Time")
        self.tree.heading("total", text="Total")
        self.tree.heading("payment", text="Payment")
        self.tree.heading("cashier", text="Cashier")
        self.tree.column("id", width=80, anchor="center")
        self.tree.column("date", width=200, anchor="center")
        self.tree.column("total", width=130, anchor="e")
        self.tree.column("payment", width=130, anchor="center")
        self.tree.column("cashier", width=130, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # ===== DEBTOR COLLECTIONS =====
        tk.Label(main_frame, text="Debtor Payments Received", font=FONTS["heading"],
                 bg=COLORS["bg"], fg=COLORS["text_primary"]).pack(anchor="w", pady=(12, 5))
        collections_frame = tk.Frame(main_frame, bg=COLORS["card_bg"], bd=1, relief=tk.SOLID)
        collections_frame.pack(fill=tk.X)
        collection_cols = ("payment","date","customer","amount","method","reference","cashier")
        self.collection_tree = ttk.Treeview(collections_frame, columns=collection_cols, show="headings", height=5)
        for col, heading, width, anchor in [
            ("payment","Payment #",90,"center"),("date","Date & Time",150,"center"),
            ("customer","Customer",180,"w"),("amount","Amount",110,"e"),
            ("method","Method",120,"center"),("reference","Reference",150,"w"),
            ("cashier","Cashier",110,"center")]:
            self.collection_tree.heading(col,text=heading); self.collection_tree.column(col,width=width,anchor=anchor)
        csb=ttk.Scrollbar(collections_frame,orient=tk.VERTICAL,command=self.collection_tree.yview)
        self.collection_tree.configure(yscrollcommand=csb.set); csb.pack(side=tk.RIGHT,fill=tk.Y)
        self.collection_tree.pack(fill=tk.X,expand=True,padx=2,pady=2)

        # Bottom info
        bottom_frame = tk.Frame(main_frame, bg=COLORS["bg"])
        bottom_frame.pack(fill=tk.X, pady=(10, 0))

        self.lbl_total = tk.Label(bottom_frame, text="Total: R 0.00", font=FONTS["heading"],
                                  bg=COLORS["bg"], fg=COLORS["accent_blue"])
        self.lbl_total.pack(side=tk.LEFT, padx=(0, 30))

        self.lbl_count = tk.Label(bottom_frame, text="Transactions: 0", font=FONTS["normal"],
                                  bg=COLORS["bg"], fg=COLORS["text_secondary"])
        self.lbl_count.pack(side=tk.LEFT)

        # Load default report
        self.load_report()

    def view_in_jasperviewer(self):
        try:
            from jasper_reports.report_viewer import open_table_report
            rows=[self.tree.item(i,"values") for i in self.tree.get_children()]
            open_table_report("Sales Report",["Receipt #","Date & Time","Total","Payment","Cashier"],rows,period=f"{self.from_date.get()} to {self.to_date.get()}",parent=self)
        except Exception as exc: messagebox.showerror("JasperViewer",str(exc),parent=self)

    def load_report(self):
        """Load report based on selected period"""
        period = self.selected_period.get()

        today = datetime.now().date()

        if period == "today":
            from_date = today.strftime("%Y-%m-%d")
            to_date = today.strftime("%Y-%m-%d")
        elif period == "yesterday":
            yesterday = today - timedelta(days=1)
            from_date = yesterday.strftime("%Y-%m-%d")
            to_date = yesterday.strftime("%Y-%m-%d")
        elif period == "week":
            week_start = today - timedelta(days=today.weekday())
            from_date = week_start.strftime("%Y-%m-%d")
            to_date = today.strftime("%Y-%m-%d")
        elif period == "month":
            month_start = today.replace(day=1)
            from_date = month_start.strftime("%Y-%m-%d")
            to_date = today.strftime("%Y-%m-%d")
        else:  # all
            from_date = "2000-01-01"
            to_date = today.strftime("%Y-%m-%d")

        self.load_data(from_date, to_date)

    def load_custom_report(self):
        """Load report with custom date range"""
        from_date = self.from_date.get().strip()
        to_date = self.to_date.get().strip()

        if not from_date or not to_date:
            messagebox.showerror("Error", "Please enter both dates!")
            return

        try:
            # Validate dates
            datetime.strptime(from_date, "%Y-%m-%d")
            datetime.strptime(to_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Invalid date format! Use YYYY-MM-DD")
            return

        self.selected_period.set("custom")
        self.load_data(from_date, to_date)

    def load_data(self, from_date, to_date):
        """Load sales data from database"""
        # The legacy report can be opened directly, so ensure the customer-account
        # tables it reports on exist before opening the report connection.
        if ensure_customer_account_schema:
            ensure_customer_account_schema()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get sales data. Credit notes/returns are kept separately so the
        # original sale history remains auditable; the report shows NET sales
        # by deducting return_history for the same date range.
        cursor.execute("""
            SELECT id, timestamp, total_amount, payment_type, cashier 
            FROM sales_history 
            WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?
              AND COALESCE(voided, 0) = 0
            ORDER BY timestamp DESC
        """, (from_date, to_date))

        rows = cursor.fetchall()

        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0)
            FROM return_history
            WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?
        """, (from_date, to_date))
        return_total = float(cursor.fetchone()[0] or 0)

        cursor.execute("""SELECT p.id,p.payment_date,c.name,p.amount,p.payment_method,
                                 COALESCE(p.reference,''),COALESCE(p.cashier,'Unknown')
                          FROM customer_account_payments p
                          JOIN customers c ON c.id=p.customer_id
                          WHERE DATE(p.payment_date) >= ? AND DATE(p.payment_date) <= ?
                          ORDER BY p.payment_date DESC, p.id DESC""",(from_date,to_date))
        debtor_payments = cursor.fetchall()
        debtor_collections_total = sum(float(r[3] or 0) for r in debtor_payments)

        # Clear table
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Calculate totals
        total_amount = 0.0
        total_count = 0
        payment_breakdown = {}
        cashier_breakdown = {}

        for row in rows:
            sale_id, timestamp, total, payment, cashier = row

            # Insert into table
            self.tree.insert("", tk.END, values=(
                f"#{sale_id}",
                str(timestamp)[:16] if timestamp else "N/A",
                f"R {total:.2f}" if total else "R 0.00",
                payment or "Unknown",
                cashier or "Unknown"
            ))

            total_amount += total or 0
            total_count += 1

            # Payment breakdown
            pay_key = payment or "Unknown"
            payment_breakdown[pay_key] = payment_breakdown.get(pay_key, 0) + (total or 0)

            # Cashier breakdown
            cash_key = cashier or "Unknown"
            cashier_breakdown[cash_key] = cashier_breakdown.get(cash_key, 0) + (total or 0)

        for item in self.collection_tree.get_children():
            self.collection_tree.delete(item)
        for pid,stamp,cname,amt,method,ref,cashier in debtor_payments:
            self.collection_tree.insert("", tk.END, values=(
                f"PAY-{pid:06d}", str(stamp)[:16], cname or "Unknown",
                f"R {float(amt):,.2f}", method or "Cash", ref or "", cashier or "Unknown"
            ))

        conn.close()

        # Sales Report total is NET sales: credit notes reduce the same
        # amount from the report without deleting the original sale record.
        net_total = total_amount - return_total

        # Update summary
        self.update_summary(net_total, total_count, payment_breakdown, cashier_breakdown, from_date, to_date, debtor_collections_total)

        # Update bottom labels
        self.lbl_total.config(text=f"Sales: R {net_total:,.2f}   |   Credit Notes: R {return_total:,.2f}   |   Debtor Payments: R {debtor_collections_total:,.2f}")
        self.lbl_count.config(text=f"Transactions: {total_count}")

    def update_summary(self, total, count, payment_breakdown, cashier_breakdown, from_date, to_date, debtor_collections_total=0.0):
        """Update summary cards"""
        # Clear old summary
        for widget in self.summary_frame.winfo_children():
            widget.destroy()

        # Date range label
        date_label = tk.Label(self.summary_frame,
                              text=f"📅 {from_date} to {to_date}",
                              font=FONTS["normal"], bg=COLORS["bg"], fg=COLORS["text_secondary"])
        date_label.pack(anchor="w", pady=(0, 10))

        # Summary row
        summary_row = tk.Frame(self.summary_frame, bg=COLORS["bg"])
        summary_row.pack(fill=tk.X)

        # Total Sales Card
        card1 = self.create_summary_card(summary_row, "💰 Total Sales", f"R {total:,.2f}", COLORS["accent_blue"])
        card1.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # Transactions Card
        card2 = self.create_summary_card(summary_row, "🧾 Transactions", str(count), COLORS["accent_green"])
        card2.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # Average per Transaction
        avg = total / count if count > 0 else 0
        card3 = self.create_summary_card(summary_row, "📊 Average per Transaction", f"R {avg:,.2f}", COLORS["accent_orange"])
        card3.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        card4 = self.create_summary_card(summary_row, "💵 Debtor Payments Received", f"R {debtor_collections_total:,.2f}", COLORS["accent_green"])
        card4.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # Payment breakdown (second row)
        if payment_breakdown:
            summary_row2 = tk.Frame(self.summary_frame, bg=COLORS["bg"])
            summary_row2.pack(fill=tk.X, pady=(10, 0))

            tk.Label(summary_row2, text="💳 Payment Breakdown:", font=FONTS["normal"],
                     bg=COLORS["bg"], fg=COLORS["text_secondary"]).pack(anchor="w")

            pay_frame = tk.Frame(summary_row2, bg=COLORS["bg"])
            pay_frame.pack(fill=tk.X, pady=(5, 0))

            for i, (method, amount) in enumerate(payment_breakdown.items()):
                color = [COLORS["accent_blue"], COLORS["accent_green"], COLORS["accent_orange"],
                        COLORS["accent_purple"], COLORS["accent_red"]][i % 5]
                tk.Label(pay_frame, text=f"{method}: R {amount:,.2f}", font=FONTS["small"],
                         bg=COLORS["bg"], fg=color).pack(side=tk.LEFT, padx=10)

        # Cashier breakdown (third row)
        if cashier_breakdown:
            summary_row3 = tk.Frame(self.summary_frame, bg=COLORS["bg"])
            summary_row3.pack(fill=tk.X, pady=(10, 0))

            tk.Label(summary_row3, text="👤 Cashier Breakdown:", font=FONTS["normal"],
                     bg=COLORS["bg"], fg=COLORS["text_secondary"]).pack(anchor="w")

            cashier_frame = tk.Frame(summary_row3, bg=COLORS["bg"])
            cashier_frame.pack(fill=tk.X, pady=(5, 0))

            for cashier, amount in cashier_breakdown.items():
                tk.Label(cashier_frame, text=f"{cashier}: R {amount:,.2f}", font=FONTS["small"],
                         bg=COLORS["bg"], fg=COLORS["accent_purple"]).pack(side=tk.LEFT, padx=10)

    def create_summary_card(self, parent, title, value, color):
        """Create a summary card"""
        card = tk.Frame(parent, bg=COLORS["card_bg"], bd=1, relief=tk.SOLID, height=70)
        card.pack_propagate(False)

        inner = tk.Frame(card, bg=COLORS["card_bg"], padx=15, pady=8)
        inner.pack(fill=tk.BOTH, expand=True)

        tk.Label(inner, text=title, font=FONTS["small"],
                 bg=COLORS["card_bg"], fg=COLORS["text_secondary"]).pack(anchor="w")
        tk.Label(inner, text=value, font=FONTS["number"],
                 bg=COLORS["card_bg"], fg=color).pack(anchor="w")

        return card
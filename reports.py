from core.config import DB_PATH
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from ui.window_polish import polish_window
try:
    from tkcalendar import DateEntry  # optional enhanced date picker
except ImportError:
    class DateEntry(ttk.Entry):
        """Small built-in fallback so Reports works without tkcalendar."""
        def __init__(self, master=None, **kwargs):
            kwargs.pop("date_pattern", None)
            super().__init__(master, **kwargs)
        def set_date(self, value):
            if hasattr(value, "strftime"):
                value = value.strftime("%Y-%m-%d")
            self.delete(0, tk.END)
            self.insert(0, str(value))

BG_COLOR = "#eef2f7"
HEADER_COLOR = "#2c5282"
WHITE = "#ffffff"


class ReportsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        polish_window(self)
        self.title("Sales Reports")
        self.geometry("1050x750")
        self.configure(bg=BG_COLOR)

        # Header
        header = tk.Frame(self, bg=HEADER_COLOR, height=50)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        tk.Label(header, text="📊 SALES REPORTS", font=("Arial", 16, "bold"),
                 fg="white", bg=HEADER_COLOR).pack(pady=10)

        # ===== TAB CONTROL =====
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: Daily Summary
        self.tab_daily = tk.Frame(self.notebook, bg=BG_COLOR)
        self.notebook.add(self.tab_daily, text="📅 Daily Summary")

        # Tab 2: Date Picker Report
        self.tab_date = tk.Frame(self.notebook, bg=BG_COLOR)
        self.notebook.add(self.tab_date, text="📆 Date Search")

        # Tab 3: Sales Summary
        self.tab_summary = tk.Frame(self.notebook, bg=BG_COLOR)
        self.notebook.add(self.tab_summary, text="📊 Sales Summary")

        # Tab 4: Product Sales
        self.tab_products = tk.Frame(self.notebook, bg=BG_COLOR)
        self.notebook.add(self.tab_products, text="📦 Product Sales")

        self.create_daily_tab()
        self.create_date_tab()
        self.create_summary_tab()
        self.create_products_tab()

        # Load data
        self.load_daily_summary()
        self.load_summary()
        self.load_product_sales()

    def view_current_tab_jasper(self):
        try:
            from jasper_reports.report_viewer import open_table_report
            tab=self.notebook.index(self.notebook.select())
            if tab==0:
                rows=[self.daily_tree.item(i,"values") for i in self.daily_tree.get_children()]
                open_table_report("Daily Sales Summary",["Date","Transactions","Total Sales","Average"],rows,parent=self)
            elif tab==1:
                rows=[self.date_tree.item(i,"values") for i in self.date_tree.get_children()]
                open_table_report("Sales by Date",["Receipt #","Time","Total","Payment"],rows,parent=self)
            elif tab==2:
                rows=[self.tree.item(i,"values") for i in self.tree.get_children()]
                open_table_report("Sales Summary",["Receipt #","Date & Time","Total","Payment"],rows,parent=self)
            else:
                rows=[self.product_tree.item(i,"values") for i in self.product_tree.get_children()]
                open_table_report("Product Sales Report",["Product","Quantity","Sales"],rows,parent=self)
        except Exception as exc:
            messagebox.showerror("JasperViewer",str(exc),parent=self)

    # ============================================================
    # TAB 1: DAILY SALES SUMMARY
    # ============================================================
    def create_daily_tab(self):
        main_frame = tk.Frame(self.tab_daily, bg=BG_COLOR, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(main_frame, text="📅 Daily Sales Summary", font=("Arial", 14, "bold"),
                 bg=BG_COLOR, fg="#2c5282").pack(anchor="w", pady=(0, 10))

        # ==== 3 Summary Boxes ====
        summary_frame = tk.Frame(main_frame, bg=BG_COLOR)
        summary_frame.pack(fill=tk.X, pady=(0, 15))

        # Box 1: Today's Sales
        box1 = tk.Frame(summary_frame, bg=WHITE, bd=2, relief=tk.GROOVE, height=80)
        box1.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        tk.Label(box1, text="📆 Today", font=("Arial", 10, "bold"),
                 bg=WHITE, fg="#4a5568").pack(pady=(5, 0))
        self.lbl_today_sales = tk.Label(box1, text="R 0.00", font=("Arial", 18, "bold"),
                                        bg=WHITE, fg="#2c5282")
        self.lbl_today_sales.pack()
        self.lbl_today_count = tk.Label(box1, text="0 transactions", font=("Arial", 9),
                                        bg=WHITE, fg="#718096")
        self.lbl_today_count.pack()

        # Box 2: Yesterday's Sales
        box2 = tk.Frame(summary_frame, bg=WHITE, bd=2, relief=tk.GROOVE, height=80)
        box2.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        tk.Label(box2, text="📆 Yesterday", font=("Arial", 10, "bold"),
                 bg=WHITE, fg="#4a5568").pack(pady=(5, 0))
        self.lbl_yesterday_sales = tk.Label(box2, text="R 0.00", font=("Arial", 18, "bold"),
                                            bg=WHITE, fg="#dd6b20")
        self.lbl_yesterday_sales.pack()
        self.lbl_yesterday_count = tk.Label(box2, text="0 transactions", font=("Arial", 9),
                                            bg=WHITE, fg="#718096")
        self.lbl_yesterday_count.pack()

        # Box 3: This Week's Sales
        box3 = tk.Frame(summary_frame, bg=WHITE, bd=2, relief=tk.GROOVE, height=80)
        box3.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        tk.Label(box3, text="📆 This Week", font=("Arial", 10, "bold"),
                 bg=WHITE, fg="#4a5568").pack(pady=(5, 0))
        self.lbl_week_sales = tk.Label(box3, text="R 0.00", font=("Arial", 18, "bold"),
                                       bg=WHITE, fg="#38a169")
        self.lbl_week_sales.pack()
        self.lbl_week_count = tk.Label(box3, text="0 transactions", font=("Arial", 9),
                                       bg=WHITE, fg="#718096")
        self.lbl_week_count.pack()

        # JasperViewer
        tk.Button(main_frame, text="VIEW CURRENT REPORT IN JASPER VIEWER", command=self.view_current_tab_jasper,
                  bg="#805ad5", fg="white", font=("Arial",10,"bold"), padx=14, pady=7).pack(anchor="e", pady=(0,8))

        # Refresh Button
        btn_frame = tk.Frame(main_frame, bg=BG_COLOR)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Button(btn_frame, text="🔄 Refresh", font=("Arial", 11, "bold"),
                  bg="#3182ce", fg="white", padx=20, command=self.refresh_all).pack(side=tk.LEFT)

        # ==== Daily Sales Table ====
        tk.Label(main_frame, text="Sales by Day (Last 7 Days)", font=("Arial", 12, "bold"),
                 bg=BG_COLOR).pack(anchor="w", pady=(10, 5))

        table_frame = tk.Frame(main_frame, bg=WHITE, bd=1, relief=tk.SOLID)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("date", "transactions", "total", "average")
        self.daily_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=8)

        self.daily_tree.heading("date", text="Date")
        self.daily_tree.heading("transactions", text="Transactions")
        self.daily_tree.heading("total", text="Total Sales")
        self.daily_tree.heading("average", text="Average per Transaction")

        self.daily_tree.column("date", width=150, anchor="center")
        self.daily_tree.column("transactions", width=120, anchor="center")
        self.daily_tree.column("total", width=150, anchor="e")
        self.daily_tree.column("average", width=180, anchor="e")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.daily_tree.yview)
        self.daily_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.daily_tree.pack(fill=tk.BOTH, expand=True)

    # ============================================================
    # TAB 2: DATE PICKER REPORT
    # ============================================================
    def create_date_tab(self):
        main_frame = tk.Frame(self.tab_date, bg=BG_COLOR, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(main_frame, text="📆 Search Sales by Date", font=("Arial", 14, "bold"),
                 bg=BG_COLOR, fg="#2c5282").pack(anchor="w", pady=(0, 10))

        # ==== Date Selection ====
        date_frame = tk.Frame(main_frame, bg=BG_COLOR)
        date_frame.pack(fill=tk.X, pady=(0, 15))

        # Date picker
        tk.Label(date_frame, text="Select Date:", font=("Arial", 12, "bold"),
                 bg=BG_COLOR).pack(side=tk.LEFT, padx=(0, 10))

        self.date_picker = DateEntry(date_frame, width=20, font=("Arial", 12),
                                     bg="#f0f4f8", fg="#2d3748",
                                     date_pattern='yyyy-mm-dd')
        self.date_picker.pack(side=tk.LEFT, padx=(0, 10))
        self.date_picker.set_date(datetime.now())

        # Search button
        tk.Button(date_frame, text="🔍 Search", font=("Arial", 11, "bold"),
                  bg="#3182ce", fg="white", padx=20, command=self.load_date_report).pack(side=tk.LEFT)

        # Quick links
        quick_frame = tk.Frame(date_frame, bg=BG_COLOR)
        quick_frame.pack(side=tk.LEFT, padx=20)

        tk.Button(quick_frame, text="Today", font=("Arial", 9),
                  bg="#e2e8f0", fg="#2d3748", padx=10,
                  command=lambda: [self.date_picker.set_date(datetime.now()), self.load_date_report()]).pack(side=tk.LEFT, padx=2)

        tk.Button(quick_frame, text="Yesterday", font=("Arial", 9),
                  bg="#e2e8f0", fg="#2d3748", padx=10,
                  command=lambda: [self.date_picker.set_date(datetime.now() - timedelta(days=1)), self.load_date_report()]).pack(side=tk.LEFT, padx=2)

        tk.Button(quick_frame, text="This Week", font=("Arial", 9),
                  bg="#e2e8f0", fg="#2d3748", padx=10,
                  command=self.load_week_report).pack(side=tk.LEFT, padx=2)

        # ==== Results ====
        result_frame = tk.Frame(main_frame, bg=WHITE, bd=1, relief=tk.SOLID)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # Summary for selected date
        summary_frame = tk.Frame(result_frame, bg=WHITE, pady=10)
        summary_frame.pack(fill=tk.X)

        # Left side - Date summary
        info_frame = tk.Frame(summary_frame, bg=WHITE)
        info_frame.pack(side=tk.LEFT, padx=15)

        tk.Label(info_frame, text="📊 Report for:", font=("Arial", 10, "bold"),
                 bg=WHITE, fg="#4a5568").pack(anchor="w")
        self.lbl_report_date = tk.Label(info_frame, text="", font=("Arial", 14, "bold"),
                                        bg=WHITE, fg="#2c5282")
        self.lbl_report_date.pack(anchor="w")

        # Right side - Stats
        stats_frame = tk.Frame(summary_frame, bg=WHITE)
        stats_frame.pack(side=tk.RIGHT, padx=15)

        self.lbl_selected_total = tk.Label(stats_frame, text="Total: R 0.00",
                                           font=("Arial", 14, "bold"), bg=WHITE, fg="#2c5282")
        self.lbl_selected_total.pack(anchor="e")

        self.lbl_selected_count = tk.Label(stats_frame, text="Transactions: 0",
                                           font=("Arial", 10), bg=WHITE, fg="#4a5568")
        self.lbl_selected_count.pack(anchor="e")

        self.lbl_selected_avg = tk.Label(stats_frame, text="Average: R 0.00",
                                         font=("Arial", 10), bg=WHITE, fg="#4a5568")
        self.lbl_selected_avg.pack(anchor="e")

        # Divider
        tk.Frame(result_frame, bg="#e2e8f0", height=2).pack(fill=tk.X, padx=10)

        # Table for selected date
        table_frame = tk.Frame(result_frame, bg=WHITE)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ("id", "time", "total", "payment")
        self.date_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)

        self.date_tree.heading("id", text="Receipt #")
        self.date_tree.heading("time", text="Time")
        self.date_tree.heading("total", text="Total")
        self.date_tree.heading("payment", text="Payment")

        self.date_tree.column("id", width=100, anchor="center")
        self.date_tree.column("time", width=150, anchor="center")
        self.date_tree.column("total", width=150, anchor="e")
        self.date_tree.column("payment", width=150, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.date_tree.yview)
        self.date_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.date_tree.pack(fill=tk.BOTH, expand=True)

        # Load default
        self.load_date_report()

    # ============================================================
    # TAB 3: SALES SUMMARY
    # ============================================================
    def create_summary_tab(self):
        main_frame = tk.Frame(self.tab_summary, bg=BG_COLOR, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Summary Boxes
        summary_frame = tk.Frame(main_frame, bg=BG_COLOR)
        summary_frame.pack(fill=tk.X, pady=(0, 15))

        box1 = tk.Frame(summary_frame, bg=WHITE, bd=2, relief=tk.GROOVE, height=70)
        box1.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        tk.Label(box1, text="💰 Total Sales", font=("Arial", 10, "bold"),
                 bg=WHITE).pack(pady=(8, 0))
        self.lbl_total_sales = tk.Label(box1, text="R 0.00", font=("Arial", 16, "bold"),
                                        bg=WHITE, fg="#2c5282")
        self.lbl_total_sales.pack()

        box2 = tk.Frame(summary_frame, bg=WHITE, bd=2, relief=tk.GROOVE, height=70)
        box2.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        tk.Label(box2, text="🧾 Transactions", font=("Arial", 10, "bold"),
                 bg=WHITE).pack(pady=(8, 0))
        self.lbl_transactions = tk.Label(box2, text="0", font=("Arial", 16, "bold"),
                                         bg=WHITE, fg="#38a169")
        self.lbl_transactions.pack()

        box3 = tk.Frame(summary_frame, bg=WHITE, bd=2, relief=tk.GROOVE, height=70)
        box3.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        tk.Label(box3, text="📦 Items Sold", font=("Arial", 10, "bold"),
                 bg=WHITE).pack(pady=(8, 0))
        self.lbl_total_items = tk.Label(box3, text="0", font=("Arial", 16, "bold"),
                                        bg=WHITE, fg="#dd6b20")
        self.lbl_total_items.pack()

        btn_frame = tk.Frame(main_frame, bg=BG_COLOR)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Button(btn_frame, text="🔄 Refresh", font=("Arial", 11, "bold"),
                  bg="#3182ce", fg="white", padx=20, command=self.refresh_all).pack(side=tk.LEFT)

        tk.Label(main_frame, text="Recent Sales", font=("Arial", 12, "bold"),
                 bg=BG_COLOR).pack(anchor="w", pady=(10, 5))

        table_frame = tk.Frame(main_frame, bg=WHITE, bd=1, relief=tk.SOLID)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("id", "date", "total", "payment")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)

        self.tree.heading("id", text="Receipt #")
        self.tree.heading("date", text="Date & Time")
        self.tree.heading("total", text="Total")
        self.tree.heading("payment", text="Payment")

        self.tree.column("id", width=80, anchor="center")
        self.tree.column("date", width=200, anchor="center")
        self.tree.column("total", width=120, anchor="e")
        self.tree.column("payment", width=120, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)

    # ============================================================
    # TAB 4: PRODUCT SALES
    # ============================================================
    def create_products_tab(self):
        main_frame = tk.Frame(self.tab_products, bg=BG_COLOR, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(main_frame, text="📦 Product Sales Report", font=("Arial", 12, "bold"),
                 bg=BG_COLOR, fg="#2c5282").pack(anchor="w", pady=(0, 10))

        table_frame = tk.Frame(main_frame, bg=WHITE, bd=1, relief=tk.SOLID)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ("barcode", "name", "price", "stock", "total_sold", "total_value")
        self.product_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

        self.product_tree.heading("barcode", text="Barcode")
        self.product_tree.heading("name", text="Product Name")
        self.product_tree.heading("price", text="Price")
        self.product_tree.heading("stock", text="Stock (SOH)")
        self.product_tree.heading("total_sold", text="Total Sold")
        self.product_tree.heading("total_value", text="Total Value")

        self.product_tree.column("barcode", width=120, anchor="center")
        self.product_tree.column("name", width=280, anchor="w")
        self.product_tree.column("price", width=100, anchor="e")
        self.product_tree.column("stock", width=100, anchor="center")
        self.product_tree.column("total_sold", width=100, anchor="center")
        self.product_tree.column("total_value", width=120, anchor="e")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.product_tree.yview)
        self.product_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.product_tree.pack(fill=tk.BOTH, expand=True)

        info_frame = tk.Frame(main_frame, bg=BG_COLOR)
        info_frame.pack(fill=tk.X, pady=(10, 0))

        self.lbl_total_products = tk.Label(info_frame, text="Total Products: 0",
                                           font=("Arial", 10, "bold"), bg=BG_COLOR, fg="#4a5568")
        self.lbl_total_products.pack(side=tk.LEFT)

        tk.Button(info_frame, text="🔄 Refresh", font=("Arial", 10, "bold"),
                  bg="#3182ce", fg="white", padx=15, command=self.load_product_sales).pack(side=tk.RIGHT)

    # ============================================================
    # LOAD DATA FUNCTIONS
    # ============================================================
    def refresh_all(self):
        self.load_daily_summary()
        self.load_summary()
        self.load_product_sales()
        self.load_date_report()

    def load_daily_summary(self):
        """Load daily sales summary"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        cursor.execute("""
            SELECT COUNT(*), SUM(total_amount) 
            FROM sales_history 
            WHERE DATE(timestamp) = ?
        """, (today,))
        result = cursor.fetchone()
        today_count = result[0] or 0
        today_total = result[1] or 0.0
        self.lbl_today_sales.config(text=f"R {today_total:.2f}")
        self.lbl_today_count.config(text=f"{today_count} transactions")

        cursor.execute("""
            SELECT COUNT(*), SUM(total_amount) 
            FROM sales_history 
            WHERE DATE(timestamp) = ?
        """, (yesterday,))
        result = cursor.fetchone()
        yesterday_count = result[0] or 0
        yesterday_total = result[1] or 0.0
        self.lbl_yesterday_sales.config(text=f"R {yesterday_total:.2f}")
        self.lbl_yesterday_count.config(text=f"{yesterday_count} transactions")

        cursor.execute("""
            SELECT COUNT(*), SUM(total_amount) 
            FROM sales_history 
            WHERE DATE(timestamp) >= ?
        """, (week_ago,))
        result = cursor.fetchone()
        week_count = result[0] or 0
        week_total = result[1] or 0.0
        self.lbl_week_sales.config(text=f"R {week_total:.2f}")
        self.lbl_week_count.config(text=f"{week_count} transactions")

        for row in self.daily_tree.get_children():
            self.daily_tree.delete(row)

        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT COUNT(*), SUM(total_amount) 
                FROM sales_history 
                WHERE DATE(timestamp) = ?
            """, (date,))
            result = cursor.fetchone()
            count = result[0] or 0
            total = result[1] or 0.0
            avg = total / count if count > 0 else 0.0

            self.daily_tree.insert("", 0, values=(
                date,
                count,
                f"R {total:.2f}",
                f"R {avg:.2f}"
            ))

        conn.close()

    def load_date_report(self):
        """Load report for selected date"""
        selected_date = self.date_picker.get()
        self.lbl_report_date.config(text=f"{selected_date}")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get summary for date
        cursor.execute("""
            SELECT COUNT(*), SUM(total_amount) 
            FROM sales_history 
            WHERE DATE(timestamp) = ?
        """, (selected_date,))
        result = cursor.fetchone()
        count = result[0] or 0
        total = result[1] or 0.0
        avg = total / count if count > 0 else 0.0

        self.lbl_selected_total.config(text=f"Total: R {total:.2f}")
        self.lbl_selected_count.config(text=f"Transactions: {count}")
        self.lbl_selected_avg.config(text=f"Average: R {avg:.2f}")

        # Clear table
        for row in self.date_tree.get_children():
            self.date_tree.delete(row)

        # Get transactions for date
        cursor.execute("""
            SELECT id, timestamp, total_amount, payment_type
            FROM sales_history 
            WHERE DATE(timestamp) = ?
            ORDER BY timestamp DESC
        """, (selected_date,))
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            sale_id, timestamp, total, payment = row
            time_str = str(timestamp)[11:16] if timestamp else "N/A"
            self.date_tree.insert("", tk.END, values=(
                f"#{sale_id}",
                time_str,
                f"R {total:.2f}",
                payment or "Unknown"
            ))

    def load_week_report(self):
        """Load report for current week (Mon-Sun)"""
        today = datetime.now()
        # Get Monday of this week
        monday = today - timedelta(days=today.weekday())
        self.date_picker.set_date(monday)
        self.load_date_report()

    def load_summary(self):
        """Load sales summary data"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT SUM(total_amount) FROM sales_history")
        total_sales = cursor.fetchone()[0] or 0.0
        self.lbl_total_sales.config(text=f"R {total_sales:.2f}")

        cursor.execute("SELECT COUNT(*) FROM sales_history")
        total_transactions = cursor.fetchone()[0] or 0
        self.lbl_transactions.config(text=str(total_transactions))
        self.lbl_total_items.config(text=str(total_transactions))

        for row in self.tree.get_children():
            self.tree.delete(row)

        cursor.execute("""
            SELECT id, timestamp, total_amount, payment_type
            FROM sales_history
            ORDER BY id DESC
            LIMIT 50
        """)
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            sale_id, timestamp, total, payment = row
            date_str = str(timestamp)[:16] if timestamp else "N/A"
            self.tree.insert("", tk.END, values=(
                f"#{sale_id}",
                date_str,
                f"R {total:.2f}",
                payment or "Unknown"
            ))

    def load_product_sales(self):
        """Load product sales data - uses real sold quantities from
        sale_items, not a guess based on current stock level."""
        for row in self.product_tree.get_children():
            self.product_tree.delete(row)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT barcode, description, selling_price, soh
            FROM products
            ORDER BY description
        """)
        products = cursor.fetchall()

        # Real totals sold per barcode, from every completed sale.
        cursor.execute("""
            SELECT barcode, SUM(qty), SUM(value)
            FROM sale_items
            GROUP BY barcode
        """)
        sold_totals = {row[0]: (row[1] or 0, row[2] or 0.0) for row in cursor.fetchall()}

        total_products = 0
        total_sold_all = 0

        for product in products:
            barcode, name, price, stock = product
            stock_disp = f"{stock:.0f}" if stock is not None else "0"

            sold, total_value = sold_totals.get(barcode, (0, 0.0))

            self.product_tree.insert("", tk.END, values=(
                barcode,
                name[:30],
                f"R {price:.2f}" if price else "R 0.00",
                stock_disp,
                f"{sold:.0f}",
                f"R {total_value:.2f}"
            ))

            total_products += 1
            total_sold_all += sold

        conn.close()

        self.lbl_total_products.config(text=f"Total Products: {total_products} | Total Items Sold: {total_sold_all:.0f}")
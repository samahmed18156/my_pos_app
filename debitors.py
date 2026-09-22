from core.config import DB_PATH
import sqlite3
import datetime
import tkinter as tk
from tkinter import ttk, messagebox

# UI Color Palette matching Stock Window & POS Main Theme
from ui.window_polish import polish_window
UI_BG = "#d9e3f0"
FRAME_BG = "#e5ecf4"
WHITE = "#ffffff"
BLUE_TEXT = "#4169e1"
HEADER_BG = "#2a52be"


class DebitorsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        polish_window(self)
        self.title("Debtors Maintenance & Account Enquiry")
        self.geometry("1000x650")
        self.configure(bg=UI_BG)

        self.init_db()

        # Inner Frame Container
        main_frame = tk.Frame(self, bg=FRAME_BG, bd=2, relief=tk.RAISED)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ---------------- TOP HEADER & CONTROLS ----------------
        top_frame = tk.Frame(main_frame, bg=FRAME_BG)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(top_frame, text="DEBTORS / ACCOUNTS", font=("Arial", 14, "bold"), bg=FRAME_BG, fg="black").pack(
            side=tk.LEFT)

        # Search / Select Debtor
        search_frame = tk.Frame(top_frame, bg=FRAME_BG)
        search_frame.pack(side=tk.RIGHT)

        tk.Label(search_frame, text="Account:", font=("Arial", 11, "bold"), bg=FRAME_BG).pack(side=tk.LEFT, padx=5)
        self.cb_debtor = ttk.Combobox(search_frame, font=("Arial", 11), width=25)
        self.cb_debtor.pack(side=tk.LEFT, padx=5)
        self.cb_debtor.bind("<<ComboboxSelected>>", self.on_debtor_selected)

        # ---------------- ACTION BUTTONS BAR ----------------
        btn_bar = tk.Frame(main_frame, bg=FRAME_BG)
        btn_bar.pack(fill=tk.X, padx=10, pady=5)

        tk.Button(btn_bar, text="New Account", font=("Arial", 10, "bold"), bg=HEADER_BG, fg=WHITE, width=15,
                  command=self.add_debtor_popup).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_bar, text="New Invoice", font=("Arial", 10, "bold"), bg=HEADER_BG, fg=WHITE, width=15,
                  command=self.add_invoice_popup).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_bar, text="Receive Payment", font=("Arial", 10, "bold"), bg=HEADER_BG, fg=WHITE, width=15,
                  command=self.receive_payment_popup).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_bar, text="Refresh", font=("Arial", 10, "bold"), bg="#555", fg=WHITE, width=10,
                  command=self.load_debtors_combo).pack(side=tk.RIGHT, padx=2)

        # ---------------- MAIN TREEVIEW TABLE (ENQUIRY / LEDGER) ----------------
        table_frame = tk.Frame(main_frame, bg=WHITE, bd=1, relief=tk.SOLID)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview.Heading", font=("Arial", 11, "bold"), background=WHITE, foreground="black")
        style.configure("Treeview", font=("Arial", 10), rowheight=25)

        columns = ("trans_id", "date", "type", "description", "amount", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")

        self.tree.heading("trans_id", text="Doc #")
        self.tree.heading("date", text="Date")
        self.tree.heading("type", text="Type")
        self.tree.heading("description", text="Description")
        self.tree.heading("amount", text="Amount (R)")
        self.tree.heading("status", text="Status")

        self.tree.column("trans_id", width=90, anchor="center")
        self.tree.column("date", width=130, anchor="center")
        self.tree.column("type", width=100, anchor="center")
        self.tree.column("description", width=300)
        self.tree.column("amount", width=120, anchor="e")
        self.tree.column("status", width=100, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True)

        # ---------------- BOTTOM TOTALS & ACCOUNT SUMMARY ----------------
        bottom_frame = tk.Frame(main_frame, bg=FRAME_BG)
        bottom_frame.pack(fill=tk.X, padx=10, pady=5)

        # Left Info Labels
        info_left = tk.Frame(bottom_frame, bg=FRAME_BG)
        info_left.pack(side=tk.LEFT)

        self.lbl_cust_name = tk.Label(info_left, text="Customer: None Selected", font=("Arial", 11, "bold"),
                                      bg=FRAME_BG)
        self.lbl_cust_name.pack(anchor="w")

        self.lbl_phone = tk.Label(info_left, text="Phone: -", font=("Arial", 10), bg=FRAME_BG)
        self.lbl_phone.pack(anchor="w")

        # Right Summary Totals Box
        summary_right = tk.Frame(bottom_frame, bg=FRAME_BG)
        summary_right.pack(side=tk.RIGHT)

        tk.Label(summary_right, text="Credit Limit:", font=("Arial", 12, "bold"), fg=BLUE_TEXT, bg=FRAME_BG).grid(row=0,
                                                                                                                  column=0,
                                                                                                                  sticky="e",
                                                                                                                  padx=5)
        self.lbl_limit = tk.Label(summary_right, text="0.00", font=("Arial", 12, "bold"), fg=BLUE_TEXT, bg=WHITE,
                                  width=12, bd=1, relief=tk.SOLID, anchor="e")
        self.lbl_limit.grid(row=0, column=1, pady=2)

        tk.Label(summary_right, text="Current Balance:", font=("Arial", 12, "bold"), fg=BLUE_TEXT, bg=FRAME_BG).grid(
            row=1, column=0, sticky="e", padx=5)
        self.lbl_balance = tk.Label(summary_right, text="0.00", font=("Arial", 12, "bold"), fg=BLUE_TEXT, bg=WHITE,
                                    width=12, bd=1, relief=tk.SOLID, anchor="e")
        self.lbl_balance.grid(row=1, column=1, pady=2)

        self.load_debtors_combo()

    def init_db(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS debtors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                acc_num TEXT UNIQUE,
                name TEXT,
                phone TEXT,
                credit_limit REAL DEFAULT 0.0,
                balance REAL DEFAULT 0.0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS debtor_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                acc_num TEXT,
                trans_date TEXT,
                trans_type TEXT,
                description TEXT,
                amount REAL,
                status TEXT
            )
        """)
        conn.commit()
        conn.close()

    def load_debtors_combo(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT acc_num, name FROM debtors")
        rows = cursor.fetchall()
        conn.close()

        values = [f"{r[0]} - {r[1]}" for r in rows]
        self.cb_debtor['values'] = values
        if values:
            self.cb_debtor.current(0)
            self.on_debtor_selected()

    def on_debtor_selected(self, event=None):
        selected = self.cb_debtor.get()
        if not selected:
            return
        acc_num = selected.split(" - ")[0]

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name, phone, credit_limit, balance FROM debtors WHERE acc_num = ?", (acc_num,))
        debtor = cursor.fetchone()

        if debtor:
            name, phone, limit, balance = debtor
            self.lbl_cust_name.config(text=f"Customer: {name} ({acc_num})")
            self.lbl_phone.config(text=f"Phone: {phone}")
            self.lbl_limit.config(text=f"{limit:.2f}")
            self.lbl_balance.config(text=f"{balance:.2f}")

        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Load Ledger Transactions
        cursor.execute(
            "SELECT id, trans_date, trans_type, description, amount, status FROM debtor_transactions WHERE acc_num = ?",
            (acc_num,))
        for row in cursor.fetchall():
            doc_no = f"INV-{row[0]:04d}" if row[2] == "INVOICE" else f"PAY-{row[0]:04d}"
            self.tree.insert("", tk.END, values=(doc_no, row[1], row[2], row[3], f"{row[4]:.2f}", row[5]))

        conn.close()

    # Popups for Actions
    def add_debtor_popup(self):
        pop = tk.Toplevel(self)
        pop.title("Add New Debtor Account")
        pop.geometry("350x250")

        tk.Label(pop, text="Account Number:").pack(pady=2)
        e_acc = tk.Entry(pop)
        e_acc.pack()

        tk.Label(pop, text="Customer Name:").pack(pady=2)
        e_name = tk.Entry(pop)
        e_name.pack()

        tk.Label(pop, text="Phone:").pack(pady=2)
        e_phone = tk.Entry(pop)
        e_phone.pack()

        tk.Label(pop, text="Credit Limit:").pack(pady=2)
        e_limit = tk.Entry(pop)
        e_limit.pack()

        def save():
            acc, name, phone, limit = e_acc.get(), e_name.get(), e_phone.get(), e_limit.get() or 0
            if acc and name:
                try:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("INSERT INTO debtors (acc_num, name, phone, credit_limit) VALUES (?, ?, ?, ?)",
                              (acc, name, phone, float(limit)))
                    conn.commit()
                    conn.close()
                    pop.destroy()
                    self.load_debtors_combo()
                except Exception as ex:
                    messagebox.showerror("Error", str(ex))

        tk.Button(pop, text="Save Account", bg=HEADER_BG, fg=WHITE, command=save).pack(pady=10)

    def add_invoice_popup(self):
        selected = self.cb_debtor.get()
        if not selected:
            return
        acc_num = selected.split(" - ")[0]

        pop = tk.Toplevel(self)
        pop.title("Post New Invoice")
        pop.geometry("300x200")

        tk.Label(pop, text="Description:").pack(pady=2)
        e_desc = tk.Entry(pop)
        e_desc.insert(0, "Store Purchase")
        e_desc.pack()

        tk.Label(pop, text="Invoice Amount (R):").pack(pady=2)
        e_amt = tk.Entry(pop)
        e_amt.pack()

        def save():
            amt = float(e_amt.get() or 0)
            date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            if amt > 0:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute(
                    "INSERT INTO debtor_transactions (acc_num, trans_date, trans_type, description, amount, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (acc_num, date_str, "INVOICE", e_desc.get(), amt, "UNPAID"))
                c.execute("UPDATE debtors SET balance = balance + ? WHERE acc_num = ?", (amt, acc_num))
                conn.commit()
                conn.close()
                pop.destroy()
                self.on_debtor_selected()

        tk.Button(pop, text="Post Invoice", bg=HEADER_BG, fg=WHITE, command=save).pack(pady=10)

    def receive_payment_popup(self):
        selected = self.cb_debtor.get()
        if not selected:
            return
        acc_num = selected.split(" - ")[0]

        pop = tk.Toplevel(self)
        pop.title("Receive Payment")
        pop.geometry("300x180")

        tk.Label(pop, text="Payment Amount (R):").pack(pady=5)
        e_amt = tk.Entry(pop)
        e_amt.pack()

        def save():
            amt = float(e_amt.get() or 0)
            date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            if amt > 0:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute(
                    "INSERT INTO debtor_transactions (acc_num, trans_date, trans_type, description, amount, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (acc_num, date_str, "PAYMENT", "Payment Received", -amt, "CLEARED"))
                c.execute("UPDATE debtors SET balance = balance - ? WHERE acc_num = ?", (amt, acc_num))
                conn.commit()
                conn.close()
                pop.destroy()
                self.on_debtor_selected()

        tk.Button(pop, text="Record Payment", bg=HEADER_BG, fg=WHITE, command=save).pack(pady=10)
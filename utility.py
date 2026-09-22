from core.config import DB_PATH
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

BG_BLUE = "#e6f2ff"
HEADER_BLUE = "#003366"


class UtilityWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("UTILITY - Financial Profit & Expenses")
        self.geometry("650x550")
        self.configure(bg=BG_BLUE)

        tk.Label(self, text="Expense Capture & Profit Analysis", font=("Arial", 14, "bold"), bg=HEADER_BLUE, fg="white"
                 ).pack(fill=tk.X, pady=8)

        # Top Frame: Capture Form
        exp_frame = tk.LabelFrame(self, text="Log Operational Expense", bg=BG_BLUE, font=("Arial", 10, "bold"))
        exp_frame.pack(fill=tk.X, padx=15, pady=10)

        tk.Label(exp_frame, text="Category:", bg=BG_BLUE).grid(row=0, column=0, padx=5, pady=5)
        self.cat_cb = ttk.Combobox(exp_frame,
                                   values=["Shop Rent", "Food", "Petrol Cost", "Electricity", "Workers Salary",
                                           "Other"], state="readonly")
        self.cat_cb.grid(row=0, column=1, padx=5, pady=5)
        self.cat_cb.current(0)

        tk.Label(exp_frame, text="Amount (R):", bg=BG_BLUE).grid(row=0, column=2, padx=5, pady=5)
        self.amt_entry = tk.Entry(exp_frame, width=12)
        self.amt_entry.grid(row=0, column=3, padx=5, pady=5)

        tk.Button(exp_frame, text="Save Expense", bg="#005b96", fg="white", font=("Arial", 10, "bold"),
                  command=self.save_expense).grid(row=0, column=4, padx=10, pady=5)

        # Financial Summary Block
        self.summary_frame = tk.Frame(self, bg="white", bd=2, relief=tk.GROOVE)
        self.summary_frame.pack(fill=tk.X, padx=15, pady=5)

        self.lbl_gross = tk.Label(self.summary_frame, text="Gross Profit: R 0.00", font=("Arial", 11, "bold"),
                                  fg="blue", bg="white")
        self.lbl_gross.pack(anchor="w", padx=10, pady=2)

        self.lbl_exp = tk.Label(self.summary_frame, text="Total Expenses: R 0.00", font=("Arial", 11, "bold"), fg="red",
                                bg="white")
        self.lbl_exp.pack(anchor="w", padx=10, pady=2)

        self.lbl_net = tk.Label(self.summary_frame, text="Net Profit: R 0.00", font=("Arial", 12, "bold"), bg="white")
        self.lbl_net.pack(anchor="w", padx=10, pady=4)

        # Expense Analytics Table
        tk.Label(self, text="Individual Expense Impact Breakdown:", font=("Arial", 10, "bold"), bg=BG_BLUE).pack(
            anchor="w", padx=15, pady=(10, 0))

        self.tree = ttk.Treeview(self, columns=("cat", "amt", "pct"), show="headings", height=8)
        self.tree.heading("cat", text="Expense Category")
        self.tree.heading("amt", text="Total Expense")
        self.tree.heading("pct", text="% of Gross Profit")

        self.tree.column("cat", width=220)
        self.tree.column("amt", width=140, anchor="e")
        self.tree.column("pct", width=140, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        self.load_analytics()

    def save_expense(self):
        cat = self.cat_cb.get()
        try:
            amt = float(self.amt_entry.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Enter a valid amount.")
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO expenses (category, amount) VALUES (?, ?)", (cat, amt))
        conn.commit()
        conn.close()

        messagebox.showinfo("Saved", "Expense logged successfully.")
        self.amt_entry.delete(0, tk.END)
        self.load_analytics()

    def load_analytics(self):
        for r in self.tree.get_children(): self.tree.delete(r)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT SUM(total_amount - total_cost) FROM sales_history")
        gross_profit = cursor.fetchone()[0] or 0.0

        cursor.execute("SELECT category, SUM(amount) FROM expenses GROUP BY category")
        exp_breakdown = cursor.fetchall()
        total_exp = sum(item[1] for item in exp_breakdown)
        conn.close()

        net_profit = gross_profit - total_exp

        self.lbl_gross.config(text=f"Gross Sales Profit: R {gross_profit:.2f}")
        self.lbl_exp.config(text=f"Total Expenses: R {total_exp:.2f}")

        net_color = "green" if net_profit >= 0 else "red"
        self.lbl_net.config(text=f"NET PROFIT AFTER EXPENSES: R {net_profit:.2f}", fg=net_color)

        for cat, amt in exp_breakdown:
            pct = (amt / gross_profit * 100) if gross_profit > 0 else 0.0
            self.tree.insert("", tk.END, values=(cat, f"R {amt:.2f}", f"{pct:.1f}%"))
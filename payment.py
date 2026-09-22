from core.logger import logger as _bkpos_logger
import tkinter as tk
from tkinter import messagebox


class PaymentDialog(tk.Toplevel):
    """Fast, cashier-friendly POS payment window.

    The payment logic/API is intentionally kept compatible with app.py.
    The dialog returns a payment dictionary when confirmed, or None when
    cancelled.
    """

    NON_TENDERED_METHODS = (
        "Bank Transfer",
        "Other",
        "Laybye",
        "Discount",
        "Credit Account",
    )

    METHOD_BUTTONS = (
        ("CASH", "Cash"),
        ("CARD", "Card"),
        ("BANK TRANSFER", "Bank Transfer"),
        ("OTHER", "Other"),
        ("SPLIT PAYMENT", "Split Payment"),
        ("LAYBYE", "Laybye"),
        ("DISCOUNT", "Discount"),
        ("CREDIT ACCOUNT", "Credit Account"),
        ("CREDIT NOTE / RETURN", "Credit Note"),
    )

    def __init__(self, parent, total, item_count=0):
        super().__init__(parent)

        self.result = None
        self.total = round(float(total), 2)
        self.item_count = int(item_count or 0)
        self._method_buttons = {}

        self.title("Payment")
        self.geometry("680x650")
        self.minsize(680, 650)
        self.resizable(False, False)
        self.configure(bg="#eef2f7")
        self.transient(parent)
        self.grab_set()

        self.payment_var = tk.StringVar(value="Cash")
        self.cash_var = tk.StringVar(value=f"{self.total:.2f}")
        self.card_var = tk.StringVar(value="0.00")
        self.amount_tendered_var = tk.StringVar(value=f"R {self.total:.2f}")
        self.change_var = tk.StringVar(value="R 0.00")
        self.status_var = tk.StringVar(value="")

        self._build()
        self._select_payment("Cash")

        self.bind("<Escape>", lambda e: self.cancel())
        self.bind("<Return>", lambda e: self.confirm())
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.update_idletasks()
        try:
            self.center_on_parent(parent)
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in payment.py", exc_info=exc)

        self.wait_visibility()
        self.focus_force()

    def center_on_parent(self, parent):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + max((pw - w) // 2, 0)
            y = py + max((ph - h) // 2, 0)
        except Exception:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = max((sw - w) // 2, 0)
            y = max((sh - h) // 2, 0)
        self.geometry(f"{w}x{h}+{x}+{y}")

    # =========================================================
    # UI
    # =========================================================

    def _build(self):
        # Professional cashier payment layout: clear hierarchy, large total,
        # two-column payment methods, and a fixed action bar.
        header = tk.Frame(self, bg="#1f4e79", height=92)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        title_box = tk.Frame(header, bg="#1f4e79")
        title_box.pack(side=tk.LEFT, padx=24, pady=12)
        tk.Label(title_box, text="PAYMENT", font=("Arial", 20, "bold"),
                 fg="white", bg="#1f4e79").pack(anchor="w")
        tk.Label(title_box, text=f"{self.item_count} item(s)  •  Select payment method",
                 font=("Arial", 9), fg="#dbeafe", bg="#1f4e79").pack(anchor="w", pady=(2, 0))

        due = tk.Frame(header, bg="#1f4e79")
        due.pack(side=tk.RIGHT, padx=24, pady=10)
        tk.Label(due, text="AMOUNT DUE", font=("Arial", 9, "bold"),
                 fg="#dbeafe", bg="#1f4e79").pack(anchor="e")
        tk.Label(due, text=f"R {self.total:,.2f}", font=("Arial", 25, "bold"),
                 fg="white", bg="#1f4e79").pack(anchor="e")

        body = tk.Frame(self, bg="#eef2f7", padx=18, pady=14)
        body.pack(fill=tk.BOTH, expand=True)

        content = tk.Frame(body, bg="#eef2f7")
        content.pack(fill=tk.BOTH, expand=True)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        # Left: payment methods
        methods_card = tk.Frame(content, bg="white", highlightthickness=1,
                                highlightbackground="#d6dee8")
        methods_card.grid(row=0, column=0, sticky="nsew", padx=(0, 7))

        tk.Label(methods_card, text="PAYMENT METHOD", font=("Arial", 11, "bold"),
                 fg="#2d3748", bg="white").pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(methods_card, text="Choose how the customer is paying", font=("Arial", 9),
                 fg="#718096", bg="white").pack(anchor="w", padx=16, pady=(0, 10))

        grid = tk.Frame(methods_card, bg="white")
        grid.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        for c in range(2):
            grid.columnconfigure(c, weight=1)
        for r in range(5):
            grid.rowconfigure(r, weight=1)

        for index, (label, method) in enumerate(self.METHOD_BUTTONS):
            row, col = divmod(index, 2)
            btn = tk.Button(
                grid, text=label, font=("Arial", 10, "bold"),
                bg="white", fg="#2d3748", activebackground="#dbeafe",
                activeforeground="#1a365d", relief=tk.FLAT, bd=0,
                highlightthickness=1, highlightbackground="#cbd5e0",
                cursor="hand2", wraplength=125, command=lambda m=method: self._select_payment(m)
            )
            btn.grid(row=row, column=col, sticky="nsew", padx=4, pady=4, ipady=7)
            self._method_buttons[method] = btn

        # Right: payment details
        details = tk.Frame(content, bg="white", highlightthickness=1,
                           highlightbackground="#d6dee8")
        details.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

        top = tk.Frame(details, bg="white")
        top.pack(fill=tk.X, padx=18, pady=(14, 8))
        self.selected_label = tk.Label(top, text="CASH PAYMENT", font=("Arial", 13, "bold"),
                                       fg="#1f4e79", bg="white")
        self.selected_label.pack(side=tk.LEFT)
        tk.Label(top, text=f"Invoice total  R {self.total:,.2f}", font=("Arial", 9, "bold"),
                 fg="#718096", bg="white").pack(side=tk.RIGHT)

        self.entry_area = tk.Frame(details, bg="white")
        self.entry_area.pack(fill=tk.X, padx=18, pady=4)
        self.entry_area.columnconfigure(1, weight=1)

        self.cash_label = tk.Label(self.entry_area, text="Cash received", font=("Arial", 10, "bold"),
                                   fg="#4a5568", bg="white")
        self.cash_label.grid(row=0, column=0, sticky="w", pady=8)
        self.cash_entry = tk.Entry(self.entry_area, textvariable=self.cash_var, font=("Arial", 17, "bold"),
                                   width=14, bd=1, relief=tk.SOLID, justify="right")
        self.cash_entry.grid(row=0, column=1, sticky="e", pady=8)

        self.card_label = tk.Label(self.entry_area, text="Card amount", font=("Arial", 10, "bold"),
                                   fg="#4a5568", bg="white")
        self.card_label.grid(row=1, column=0, sticky="w", pady=8)
        self.card_entry = tk.Entry(self.entry_area, textvariable=self.card_var, font=("Arial", 17, "bold"),
                                   width=14, bd=1, relief=tk.SOLID, justify="right")
        self.card_entry.grid(row=1, column=1, sticky="e", pady=8)

        self.tendered_label = tk.Label(self.entry_area, text="Amount tendered", font=("Arial", 10, "bold"),
                                       fg="#4a5568", bg="white")
        self.tendered_label.grid(row=2, column=0, sticky="w", pady=(18, 6))
        self.tendered_value = tk.Label(self.entry_area, textvariable=self.amount_tendered_var,
                                       font=("Arial", 14, "bold"), fg="#1f4e79", bg="white")
        self.tendered_value.grid(row=2, column=1, sticky="e", pady=(18, 6))

        self.change_label = tk.Label(self.entry_area, text="CHANGE", font=("Arial", 11, "bold"),
                                     fg="#4a5568", bg="white")
        self.change_label.grid(row=3, column=0, sticky="w", pady=8)
        self.change_value = tk.Label(self.entry_area, textvariable=self.change_var,
                                     font=("Arial", 22, "bold"), fg="#2f855a", bg="white")
        self.change_value.grid(row=3, column=1, sticky="e", pady=8)

        hint = tk.Frame(details, bg="#f7fafc", highlightthickness=1, highlightbackground="#e2e8f0")
        hint.pack(fill=tk.X, padx=18, pady=(12, 0))
        self.status_var.set("Enter the cash received. Change is calculated automatically.")
        self.status_label = tk.Label(hint, textvariable=self.status_var, font=("Arial", 9),
                                     fg="#4a5568", bg="#f7fafc", wraplength=300,
                                     justify="center", padx=10, pady=10)
        self.status_label.pack(fill=tk.X)

        # Fixed action bar
        actions = tk.Frame(body, bg="#eef2f7")
        actions.pack(fill=tk.X, pady=(12, 0))
        tk.Label(actions, text="Enter = confirm    •    Esc = cancel    •    Alt+C/A/B/O/S/L/D = payment method",
                 font=("Arial", 8), fg="#718096", bg="#eef2f7").pack(side=tk.LEFT)

        tk.Button(actions, text="CANCEL   (Esc)", font=("Arial", 10, "bold"),
                  bg="#c53030", fg="white", activebackground="#9b2c2c",
                  activeforeground="white", relief=tk.FLAT, bd=0, cursor="hand2",
                  height=2, command=self.cancel).pack(side=tk.RIGHT, padx=(8, 0), ipadx=12)
        tk.Button(actions, text="CONFIRM PAYMENT   (Enter)", font=("Arial", 11, "bold"),
                  bg="#2f855a", fg="white", activebackground="#276749",
                  activeforeground="white", relief=tk.FLAT, bd=0, cursor="hand2",
                  height=2, command=self.confirm).pack(side=tk.RIGHT, ipadx=14)

        self.cash_entry.bind("<KeyRelease>", lambda e: self._update_amounts())
        self.card_entry.bind("<KeyRelease>", lambda e: self._update_amounts())

        shortcuts = {"c": "Cash", "a": "Card", "b": "Bank Transfer", "o": "Other",
                     "s": "Split Payment", "l": "Laybye", "d": "Discount"}
        for key, method in shortcuts.items():
            self.bind(f"<Alt-{key}>", lambda e, m=method: self._select_payment(m))

    def _set_button_state(self):
        selected = self.payment_var.get()
        for method, btn in self._method_buttons.items():
            if method == selected:
                btn.config(
                    bg="#2c5282",
                    fg="white",
                    activebackground="#2b6cb0",
                    activeforeground="white",
                    highlightbackground="#2c5282",
                )
            else:
                btn.config(
                    bg="white",
                    fg="#2d3748",
                    activebackground="#dbeafe",
                    activeforeground="#1a365d",
                    highlightbackground="#cbd5e0",
                )

    # =========================================================
    # PAYMENT METHOD
    # =========================================================

    def _select_payment(self, method):
        # Credit Note is a direct product-return action from F12. The cashier
        # selects a cart line first; no Returns window is opened.
        if method == "Credit Note":
            handler = getattr(self.master, "open_direct_credit_note", None)
            if callable(handler):
                self.grab_release()
                self.destroy()
                self.master.after(10, lambda: handler(getattr(self.master, "current_invoice_id", None)))
            else:
                messagebox.showerror(
                    "Credit Note",
                    "Credit Note workspace is not available in this POS version.",
                    parent=self,
                )
            return

        self.payment_var.set(method)
        self._set_button_state()

        titles = {
            "Cash": "CASH PAYMENT",
            "Card": "CARD PAYMENT",
            "Bank Transfer": "BANK TRANSFER",
            "Other": "OTHER PAYMENT",
            "Split Payment": "SPLIT PAYMENT",
            "Laybye": "LAYBYE",
            "Credit Note": "CREDIT NOTE",
            "Discount": "DISCOUNT",
            "Credit Account": "CREDIT ACCOUNT",
        }
        self.selected_label.config(text=titles.get(method, "PAYMENT"))

        if method == "Cash":
            self.cash_entry.config(state="normal")
            self.card_entry.config(state="disabled")
            self.cash_var.set(f"{self.total:.2f}")
            self.card_var.set("0.00")
            self.status_var.set(
                "Enter the cash received. Change is calculated automatically."
            )

        elif method == "Card":
            self.cash_entry.config(state="disabled")
            self.card_entry.config(state="normal")
            self.cash_var.set("0.00")
            self.card_var.set(f"{self.total:.2f}")
            self.status_var.set(
                "The card payment must cover the full invoice amount."
            )

        elif method == "Split Payment":
            self.cash_entry.config(state="normal")
            self.card_entry.config(state="normal")
            self.cash_var.set("0.00")
            self.card_var.set(f"{self.total:.2f}")
            self.status_var.set(
                "Enter the cash portion. The remaining balance is assigned to card."
            )

        else:
            self.cash_entry.config(state="disabled")
            self.card_entry.config(state="disabled")
            self.cash_var.set("0.00")
            self.card_var.set("0.00")

            messages = {
                "Bank Transfer": "Confirm only after the bank transfer has been received.",
                "Other": "Confirm to record this sale as Other payment.",
                "Laybye": "Confirm to record this sale as a Laybye.",
                "Credit Note": "Confirm to record this sale against a Credit Note.",
                "Discount": "Confirm to record this sale using the Discount payment type.",
                "Credit Account": "Charge this sale to the selected customer account.",
            }
            self.status_var.set(messages.get(method, ""))

        self._update_amounts()

        if method in ("Cash", "Split Payment"):
            self.cash_entry.focus_set()
            self.cash_entry.select_range(0, tk.END)
        elif method == "Card":
            self.card_entry.focus_set()
            self.card_entry.select_range(0, tk.END)

    @staticmethod
    def _number(value):
        try:
            return float(str(value).replace(",", "").strip() or "0")
        except (TypeError, ValueError):
            return None

    # =========================================================
    # AMOUNTS
    # =========================================================

    def _update_amounts(self):
        method = self.payment_var.get()

        if method == "Cash":
            cash = self._number(self.cash_var.get())
            if cash is None:
                self.amount_tendered_var.set("R 0.00")
                self.change_var.set("R 0.00")
                return

            change = cash - self.total
            self.amount_tendered_var.set(f"R {cash:.2f}")
            self.change_var.set(f"R {max(change, 0):.2f}")

        elif method == "Card":
            card = self._number(self.card_var.get()) or 0.0
            self.amount_tendered_var.set(f"R {card:.2f}")
            self.change_var.set("R 0.00")

        elif method == "Split Payment":
            cash = self._number(self.cash_var.get()) or 0.0
            remaining = round(self.total - cash, 2)

            if remaining >= 0:
                self.card_var.set(f"{remaining:.2f}")
                self.amount_tendered_var.set(
                    f"R {cash + remaining:.2f}"
                )
                self.change_var.set("R 0.00")
            else:
                self.card_var.set("0.00")
                self.amount_tendered_var.set(f"R {cash:.2f}")
                self.change_var.set(f"R {abs(remaining):.2f}")

        elif method in self.NON_TENDERED_METHODS:
            self.amount_tendered_var.set("R 0.00")
            self.change_var.set("R 0.00")

    # =========================================================
    # CONFIRM
    # =========================================================

    def confirm(self):
        method = self.payment_var.get()

        if method in self.NON_TENDERED_METHODS:
            descriptions = {
                "Bank Transfer": "Bank transfer",
                "Other": "Other payment",
                "Laybye": "Laybye",
                "Credit Note": "Credit Note",
                "Discount": "Discount",
                "Credit Account": "Credit Account",
            }
            summary = (
                "CONFIRM PAYMENT\n\n"
                f"Payment method: {method}\n"
                f"Invoice total: R {self.total:.2f}\n\n"
                f"{descriptions[method]} selected.\n"
                "Do you want to complete this payment?"
            )

            if not messagebox.askyesno(
                "Confirm Payment",
                summary,
                parent=self,
            ):
                return

            self.result = {
                "payment_type": method,
                "cash": 0.0,
                "card": 0.0,
                "amount_tendered": 0.0,
                "change": 0.0,
            }
            self.destroy()
            return

        cash = self._number(self.cash_var.get())
        card = self._number(self.card_var.get())

        if cash is None or card is None:
            messagebox.showwarning(
                "Invalid Amount",
                "Please enter valid payment amounts.",
                parent=self,
            )
            return

        if cash < 0 or card < 0:
            messagebox.showwarning(
                "Invalid Amount",
                "Payment amounts cannot be negative.",
                parent=self,
            )
            return

        if method == "Cash":
            if cash < self.total:
                messagebox.showwarning(
                    "Insufficient Cash",
                    f"Cash received: R {cash:.2f}\n"
                    f"Amount due: R {self.total:.2f}\n\n"
                    "The amount received is insufficient.",
                    parent=self,
                )
                return
            card = 0.0

        elif method == "Card":
            if card < self.total:
                messagebox.showwarning(
                    "Insufficient Card Payment",
                    f"Card amount: R {card:.2f}\n"
                    f"Amount due: R {self.total:.2f}\n\n"
                    "The card payment is insufficient.",
                    parent=self,
                )
                return
            cash = 0.0

        elif method == "Split Payment":
            if cash > self.total:
                messagebox.showwarning(
                    "Invalid Split Payment",
                    f"Cash portion: R {cash:.2f}\n"
                    f"Invoice total: R {self.total:.2f}\n\n"
                    "The cash portion cannot be greater than the invoice total.",
                    parent=self,
                )
                return
            card = round(self.total - cash, 2)

        change = (
            round(max(cash - self.total, 0.0), 2)
            if method == "Cash"
            else 0.0
        )

        payment_label = "Cash + Card" if method == "Split Payment" else method
        summary = (
            "CONFIRM PAYMENT\n\n"
            f"Payment method: {payment_label}\n"
            f"Invoice total: R {self.total:.2f}\n"
            f"Cash: R {cash:.2f}\n"
            f"Card: R {card:.2f}\n"
            f"Amount tendered: R {cash + card:.2f}\n"
            f"Change: R {change:.2f}\n\n"
            "Complete this sale?"
        )

        if not messagebox.askyesno(
            "Confirm Payment",
            summary,
            parent=self,
        ):
            return

        self.result = {
            "payment_type": payment_label,
            "cash": round(cash, 2),
            "card": round(card, 2),
            "amount_tendered": round(cash + card, 2),
            "change": change,
        }
        self.destroy()

    # =========================================================
    # CANCEL
    # =========================================================

    def cancel(self):
        self.result = None
        self.destroy()


def get_payment(parent, total, item_count=0):
    """Open the payment dialog and return payment details."""
    dialog = PaymentDialog(parent, total, item_count)
    parent.wait_window(dialog)
    return dialog.result

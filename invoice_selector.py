import tkinter as tk
from tkinter import ttk, messagebox

UI_BG = "#eef2f7"
HEADER_COLOR = "#2c5282"

class InvoiceSelectorWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Open Invoices")
        self.geometry("500x380")
        self.resizable(False, False)
        self.configure(bg=UI_BG)
        self.transient(parent)
        self.grab_set()

        tk.Label(
            self,
            text="OPEN INVOICES",
            font=("Arial", 15, "bold"),
            bg=HEADER_COLOR,
            fg="white",
            pady=12,
        ).pack(fill=tk.X)

        body = tk.Frame(self, bg=UI_BG, padx=15, pady=15)
        body.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            body,
            columns=("invoice", "items", "total"),
            show="headings",
            height=10,
        )
        self.tree.heading("invoice", text="Invoice")
        self.tree.heading("items", text="Items")
        self.tree.heading("total", text="Total")
        self.tree.column("invoice", width=150, anchor="center")
        self.tree.column("items", width=100, anchor="center")
        self.tree.column("total", width=150, anchor="e")
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.load_invoices()
        self.tree.bind("<Double-1>", lambda e: self.select_invoice())

        buttons = tk.Frame(self, bg=UI_BG, pady=10)
        buttons.pack(fill=tk.X)

        tk.Button(
            buttons, text="Open Selected", font=("Arial", 10, "bold"),
            bg="#3182ce", fg="white", width=15,
            command=self.select_invoice,
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(
            buttons, text="New Invoice", font=("Arial", 10, "bold"),
            bg="#38a169", fg="white", width=15,
            command=self.new_invoice,
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            buttons, text="Close", font=("Arial", 10),
            width=12, command=self.destroy,
        ).pack(side=tk.RIGHT, padx=10)

        self.bind("<Escape>", lambda e: self.destroy())

    def load_invoices(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for invoice_id, invoice in self.parent.invoices.items():
            item_count = sum(float(item.get("qty", 0) or 0) for item in invoice["cart"])
            total = sum(float(item.get("value", 0) or 0) for item in invoice["cart"])

            self.tree.insert(
                "",
                tk.END,
                iid=str(invoice_id),
                values=(f"Invoice {invoice_id:03d}", f"{item_count:g}", f"R {total:.2f}"),
            )

        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])

    def select_invoice(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(
                "Select Invoice",
                "Please select an invoice.",
                parent=self,
            )
            return

        invoice_id = int(selected[0])
        if invoice_id not in self.parent.invoices:
            self.destroy()
            return

        self.parent.switch_invoice(invoice_id)
        self.destroy()

    def new_invoice(self):
        self.parent.create_new_invoice(switch_to=True)
        self.destroy()

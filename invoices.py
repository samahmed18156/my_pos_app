import tkinter as tk
from tkinter import messagebox

VAT_RATE = 0.15

def vat_from_inclusive(total):
    return float(total) * VAT_RATE / (1.0 + VAT_RATE)

def net_from_inclusive(total):
    total = float(total)
    return total - vat_from_inclusive(total)

class InvoiceManagerMixin:
    """Multi-invoice management used by FamilySupermarketPOS."""

    def create_new_invoice(self, switch_to=True):
        invoice_id = self.next_invoice_id
        self.next_invoice_id += 1
        self.invoices[invoice_id] = {
            "cart": [],
            "customer_num": "CASH",
            "customer_name": "Cash Sale",
        }
        if switch_to:
            self.switch_invoice(invoice_id)
        else:
            self.refresh_invoice_tabs()
        return invoice_id

    def current_invoice(self):
        if self.current_invoice_id is None:
            return None
        return self.invoices[self.current_invoice_id]

    def switch_invoice(self, invoice_id):
        if invoice_id not in self.invoices:
            return
        if self.current_invoice_id is not None and self.current_invoice_id in self.invoices:
            current = self.invoices[self.current_invoice_id]
            current["customer_num"] = self._sale_account_code() if hasattr(self, "_sale_account_code") else (self.entry_num.get().strip() or "CASH")
            current["customer_name"] = self.entry_name.get().strip() or "Cash Sale"

        self.current_invoice_id = invoice_id
        self.load_current_invoice()
        self.refresh_invoice_tabs()
        if hasattr(self, "code_entry"):
            self.code_entry.focus_set()

    def load_current_invoice(self):
        if self.current_invoice_id is None:
            return
        invoice = self.current_invoice()

        self.entry_num.set(invoice.get("customer_num", "CASH"))
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, invoice.get("customer_name", "Cash Sale"))

        self.update_cart_display()
        self.clear_product_input()
        self.lbl_current_invoice.config(
            text=f"Invoice {self.current_invoice_id:03d}"
        )

    def refresh_invoice_tabs(self):
        if not hasattr(self, "invoice_tabs_frame"):
            return

        for widget in self.invoice_tabs_frame.winfo_children():
            widget.destroy()

        for invoice_id, invoice in self.invoices.items():
            total = sum(float(item.get("value", 0) or 0) for item in invoice["cart"])

            if invoice_id == self.current_invoice_id:
                bg, fg = "#2c5282", "white"
            else:
                bg, fg = "#ffffff", "#2d3748"

            tk.Button(
                self.invoice_tabs_frame,
                text=f"Invoice {invoice_id:03d}   R {total:.2f}",
                font=("Arial", 9, "bold"),
                bg=bg,
                fg=fg,
                relief=tk.RAISED,
                bd=1,
                padx=8,
                pady=4,
                command=lambda iid=invoice_id: self.switch_invoice(iid),
            ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            self.invoice_tabs_frame,
            text="+ New Invoice",
            font=("Arial", 9, "bold"),
            bg="#38a169",
            fg="white",
            padx=8,
            pady=4,
            command=self.create_new_invoice,
        ).pack(side=tk.LEFT, padx=5)

    def open_invoice_selector(self):
        from invoice_selector import InvoiceSelectorWindow
        InvoiceSelectorWindow(self)

    def close_current_invoice(self):
        if self.current_invoice_id is None:
            return

        invoice = self.current_invoice()
        if invoice["cart"]:
            if not messagebox.askyesno(
                "Close Invoice",
                f"Invoice {self.current_invoice_id:03d} contains items.\n\n"
                "Close it without completing the sale?",
                parent=self,
            ):
                return

        del self.invoices[self.current_invoice_id]

        if not self.invoices:
            self.current_invoice_id = None
            self.create_new_invoice()
            return

        self.current_invoice_id = list(self.invoices.keys())[-1]
        self.load_current_invoice()
        self.refresh_invoice_tabs()

    def close_all_invoices(self):
        has_items = any(invoice["cart"] for invoice in self.invoices.values())

        if has_items:
            if not messagebox.askyesno(
                "Close All Invoices",
                "One or more open invoices contain items.\n\n"
                "Close all of them without completing the sales?",
                parent=self,
            ):
                return

        self.invoices.clear()
        self.current_invoice_id = None
        self.create_new_invoice()

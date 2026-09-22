"""Reusable POS popup windows.

These classes were moved out of app.py without changing their public APIs.
"""
from core.logger import logger as _bkpos_logger
import sqlite3
import time
import tkinter as tk
from tkinter import ttk, messagebox

from core.config import DB_PATH
DB_NAME = DB_PATH

UI_BG = "#eef2f7"
HEADER_COLOR = "#2c5282"

class CustomerLookupWindow(tk.Toplevel):
    """Keyboard-first customer selector used anywhere the POS needs a customer."""
    def __init__(self, parent, initial_query="", on_select_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.on_select_callback = on_select_callback
        self.title("Customer Lookup • F3")
        self.geometry("1040x650")
        self.minsize(900, 560)
        self.configure(bg="#eef2f6")
        self.transient(parent)
        self.grab_set()

        header = tk.Frame(self, bg="#243447", height=72)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="CUSTOMER LOOKUP", font=("Segoe UI", 18, "bold"),
                 fg="white", bg="#243447").pack(side="left", padx=22, pady=(12, 0))
        tk.Label(header, text="F3  •  Select a customer for the current sale",
                 font=("Segoe UI", 9), fg="#dbe7f3", bg="#243447").pack(side="left", padx=18, pady=(16, 0))
        tk.Label(header, text="ESC Close  •  ENTER Select  •  DOUBLE-CLICK Select",
                 font=("Segoe UI", 8, "bold"), fg="#dbe7f3", bg="#243447").pack(side="right", padx=22, pady=16)

        controls = tk.Frame(self, bg="white", bd=1, relief="solid")
        controls.pack(fill="x", padx=18, pady=(16, 10))
        tk.Label(controls, text="SEARCH", font=("Segoe UI", 9, "bold"),
                 fg="#344054", bg="white").pack(side="left", padx=(16, 8), pady=14)
        self.entry_search = tk.Entry(controls, font=("Segoe UI", 13), bd=1, relief="solid")
        self.entry_search.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=10, ipady=5)
        self.entry_search.insert(0, initial_query)
        tk.Button(controls, text="SEARCH", command=self.refresh,
                  font=("Segoe UI", 9, "bold"), bg="#2c5282", fg="white", bd=0,
                  padx=18, pady=9).pack(side="left", padx=(0, 8), pady=10)
        tk.Button(controls, text="CLEAR", command=self.clear_search,
                  font=("Segoe UI", 9, "bold"), bg="#edf2f7", fg="#243447", bd=0,
                  padx=14, pady=9).pack(side="left", padx=(0, 14), pady=10)

        info = tk.Frame(self, bg="#eef2f6")
        info.pack(fill="x", padx=18, pady=(0, 6))
        self.result_label = tk.Label(info, text="", font=("Segoe UI", 9),
                                     fg="#667085", bg="#eef2f6")
        self.result_label.pack(side="left")

        table_frame = tk.Frame(self, bg="white", bd=1, relief="solid")
        table_frame.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        cols = ("account", "name", "type", "phone")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        headings = {"account":"ACCOUNT", "name":"CUSTOMER", "type":"TYPE", "phone":"PHONE"}
        widths = {"account":180, "name":390, "type":140, "phone":190}
        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="w")
        style = ttk.Style(self)
        style.configure("CustomerLookup.Treeview", font=("Segoe UI", 10), rowheight=34,
                        background="white", fieldbackground="white")
        style.configure("CustomerLookup.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.map("CustomerLookup.Treeview", background=[("selected", "#dbeafe")],
                  foreground=[("selected", "#17202a")])
        self.tree.configure(style="CustomerLookup.Treeview")
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        footer = tk.Frame(self, bg="white", height=62, bd=1, relief="solid")
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Label(footer, text="Select a customer to apply the customer's pricing type to the sale.",
                 font=("Segoe UI", 8), fg="#667085", bg="white").pack(side="left", padx=18)
        tk.Button(footer, text="CANCEL", command=self.destroy, font=("Segoe UI", 9, "bold"),
                  bg="#edf2f7", fg="#243447", bd=0, padx=18, pady=9).pack(side="right", padx=(8, 14), pady=10)
        tk.Button(footer, text="SELECT CUSTOMER  ENTER", command=self.confirm_selection,
                  font=("Segoe UI", 9, "bold"), bg="#2c5282", fg="white", bd=0,
                  padx=20, pady=9).pack(side="right", pady=10)

        self.entry_search.bind("<KeyRelease>", self.search_changed)
        self.entry_search.bind("<Up>", lambda e: self.move_selection(-1))
        self.entry_search.bind("<Down>", lambda e: self.move_selection(1))
        self.entry_search.bind("<Return>", lambda e: self.confirm_selection())
        self.tree.bind("<Return>", lambda e: self.confirm_selection())
        self.tree.bind("<Double-1>", lambda e: self.confirm_selection())
        self.tree.bind("<ButtonRelease-1>", self.on_mouse_click)
        self.bind("<Escape>", lambda e: self.destroy())
        self.rows = []
        self.refresh()
        self.entry_search.focus_force()

    def search_changed(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape"):
            return
        self.refresh()

    def clear_search(self):
        self.entry_search.delete(0, tk.END)
        self.refresh()
        self.entry_search.focus_force()

    def refresh(self, event=None):
        q = self.entry_search.get().strip()
        conn = sqlite3.connect(DB_NAME)
        try:
            rows = conn.execute("""
                SELECT id, name, COALESCE(customer_type,'Retail'), COALESCE(phone,'')
                FROM customers
                WHERE active=1
                  AND (?='' OR name LIKE ? COLLATE NOCASE
                       OR phone LIKE ? COLLATE NOCASE
                       OR CAST(id AS TEXT) LIKE ?)
                ORDER BY name COLLATE NOCASE
                LIMIT 500
            """, (q, f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
        except Exception:
            rows = []
        finally:
            conn.close()
        self.rows = rows
        self.tree.delete(*self.tree.get_children())
        for cid, name, ctype, phone in rows:
            self.tree.insert("", "end", values=(f"CUST-{int(cid):06d}", name or "", ctype or "Retail", phone or ""))
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])
            self.tree.see(children[0])
        self.result_label.config(text=f"{len(rows)} customer(s) found")

    def move_selection(self, step):
        children = self.tree.get_children()
        if not children:
            return "break"
        selected = self.tree.selection()
        current = children.index(selected[0]) if selected else (-1 if step > 0 else 0)
        idx = max(0, min(len(children) - 1, current + step))
        self.tree.selection_set(children[idx])
        self.tree.focus(children[idx])
        self.tree.see(children[idx])
        return "break"

    def on_mouse_click(self, event=None):
        row_id = self.tree.identify_row(event.y) if event else None
        if row_id:
            self.tree.selection_set(row_id)
            self.tree.focus(row_id)

    def confirm_selection(self):
        selected = self.tree.selection()
        if not selected:
            return "break"
        idx = self.tree.index(selected[0])
        cid, name, ctype, phone = self.rows[idx]
        if self.on_select_callback:
            self.on_select_callback(int(cid), name or "", ctype or "Retail", phone or "")
        self.destroy()
        return "break"


class F3SearchWindow(tk.Toplevel):
    """Professional product selector for the sales screen (F3)."""
    def __init__(self, parent, initial_query="", on_select_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.on_select_callback = on_select_callback
        self.title("Product Lookup • F3")
        self.geometry("1040x650")
        self.minsize(900, 560)
        self.configure(bg="#eef2f6")
        self.transient(parent)
        self.grab_set()

        header = tk.Frame(self, bg="#243447", height=72)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="PRODUCT LOOKUP", font=("Segoe UI", 18, "bold"),
                 fg="white", bg="#243447").pack(side="left", padx=22, pady=(12,0))
        tk.Label(header, text="F3  •  Select a product to add to the current invoice",
                 font=("Segoe UI", 9), fg="#dbe7f3", bg="#243447").pack(side="left", padx=18, pady=(16,0))
        tk.Label(header, text="ESC Close  •  ENTER Select  •  DOUBLE-CLICK Select",
                 font=("Segoe UI", 8, "bold"), fg="#dbe7f3", bg="#243447").pack(side="right", padx=22, pady=16)

        controls = tk.Frame(self, bg="white", bd=1, relief="solid")
        controls.pack(fill="x", padx=18, pady=(16,10))
        tk.Label(controls, text="SEARCH", font=("Segoe UI", 9, "bold"),
                 fg="#344054", bg="white").pack(side="left", padx=(16,8), pady=14)
        self.cmb_search_by = ttk.Combobox(controls, values=["Description", "Barcode"],
                                          width=14, state="readonly", font=("Segoe UI", 10))
        self.cmb_search_by.set("Description")
        self.cmb_search_by.pack(side="left", padx=(0,10), pady=10)
        self.entry_search = tk.Entry(controls, font=("Segoe UI", 12), bd=1, relief="solid")
        self.entry_search.pack(side="left", fill="x", expand=True, padx=(0,10), pady=10, ipady=5)
        self.entry_search.insert(0, initial_query)
        tk.Button(controls, text="SEARCH", command=self.filter_products,
                  font=("Segoe UI", 9, "bold"), bg="#2c5282", fg="white",
                  activebackground="#23446b", activeforeground="white", bd=0,
                  padx=18, pady=9).pack(side="left", padx=(0,8), pady=10)
        tk.Button(controls, text="CLEAR", command=self.clear_search,
                  font=("Segoe UI", 9, "bold"), bg="#edf2f7", fg="#243447",
                  bd=0, padx=14, pady=9).pack(side="left", padx=(0,14), pady=10)

        info = tk.Frame(self, bg="#eef2f6")
        info.pack(fill="x", padx=18, pady=(0,6))
        self.result_label = tk.Label(info, text="", font=("Segoe UI", 9),
                                     fg="#667085", bg="#eef2f6")
        self.result_label.pack(side="left")

        table_frame = tk.Frame(self, bg="white", bd=1, relief="solid")
        table_frame.pack(fill="both", expand=True, padx=18, pady=(0,12))
        cols=("barcode","description","category","supplier","retail","soh")
        self.tree=ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        headings={"barcode":"BARCODE","description":"DESCRIPTION","category":"CATEGORY",
                  "supplier":"SUPPLIER","retail":"RETAIL PRICE","soh":"SOH"}
        widths={"barcode":145,"description":300,"category":135,"supplier":170,"retail":115,"soh":80}
        for c in cols:
            self.tree.heading(c,text=headings[c])
            self.tree.column(c,width=widths[c],anchor="e" if c in ("retail","soh") else "w")
        style=ttk.Style(self)
        try:
            style.configure("Lookup.Treeview", font=("Segoe UI", 10), rowheight=32,
                            background="white", fieldbackground="white")
            style.configure("Lookup.Treeview.Heading", font=("Segoe UI", 9, "bold"))
            style.map("Lookup.Treeview", background=[("selected","#dbeafe")],
                      foreground=[("selected","#17202a")])
            self.tree.configure(style="Lookup.Treeview")
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in ui/windows.py", exc_info=exc)
        sb=ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        footer=tk.Frame(self,bg="white",height=62,bd=1,relief="solid")
        footer.pack(fill="x",side="bottom")
        footer.pack_propagate(False)
        tk.Label(footer,text="Select a product to use its current selling price and stock information.",
                 font=("Segoe UI",8),fg="#667085",bg="white").pack(side="left",padx=18)
        tk.Button(footer,text="CANCEL",command=self.destroy,font=("Segoe UI",9,"bold"),
                  bg="#edf2f7",fg="#243447",bd=0,padx=18,pady=9).pack(side="right",padx=(8,14),pady=10)
        tk.Button(footer,text="SELECT PRODUCT  ENTER",command=self.confirm_selection,
                  font=("Segoe UI",9,"bold"),bg="#2c5282",fg="white",bd=0,padx=20,pady=9).pack(side="right",pady=10)

        self.cmb_search_by.bind("<<ComboboxSelected>>", self.filter_products)

        # Keyboard-first lookup: Up/Down work immediately while the search box
        # has focus.  The cashier does not need to click the grid first.
        # ONLY search box bindings - nothing else
        self.entry_search.bind("<KeyRelease>", self.filter_products)
        self.entry_search.bind("<Up>", lambda e: self.move_selection(-1))
        self.entry_search.bind("<Down>", lambda e: self.move_selection(1))
        self.entry_search.bind("<Return>", lambda e: self.confirm_selection())

        # Tree bindings - ONLY for mouse and Enter, NOT arrows
        self.tree.bind("<Return>", lambda e: self.confirm_selection())
        self.tree.bind("<Double-1>", lambda e: self.confirm_selection())
        self.tree.bind("<ButtonRelease-1>", self.on_mouse_click)

        # Escape to close
        self.bind("<Escape>", lambda e: self.destroy())
        self.filter_products()
        self.entry_search.focus_set()
        # FORCE focus to stay on search box
        self.entry_search.focus_set()
        self.entry_search.focus_force()  # <-- ADD THIS
        self.after(100, lambda: self.entry_search.focus_force())  # <-- ADD THIS

    def clear_search(self):
        self.entry_search.delete(0, tk.END)
        self.filter_products()
        self.entry_search.focus_set()

    def on_search_key(self, event):
        """Filter products only when typing characters"""
        # Only filter for letters, numbers, and space
        if event.char.isalnum() or event.char == " ":
            self.filter_products()
    def move_selection(self, step):
        """Move product selection with arrow keys"""
        # Guard against double-firing from multiple bindings
        import time
        if hasattr(self, "_last_arrow_time"):
            if time.time() - self._last_arrow_time < 0.1:
                return "break"
        self._last_arrow_time = time.time()

        children = self.tree.get_children()

        if not children:
            return "break"

        selected = self.tree.selection()

        if selected:
            current_index = children.index(selected[0])
        else:
            # Start from beginning if nothing selected
            current_index = -1 if step > 0 else 0

        new_index = current_index + step

        # Keep within bounds
        new_index = max(0, min(new_index, len(children) - 1))

        # Move selection
        item_id = children[new_index]
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        self.tree.see(item_id)

        return "break"

    def on_mouse_click(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row);
            self.tree.focus(row)

    def filter_products(self, event=None):
        # Don't filter when arrow keys are pressed
        if event and event.keysym in ("Up", "Down", "Left", "Right"):
            return

        query = self.entry_search.get().strip()
        for row in self.tree.get_children(): self.tree.delete(row)
        conn = sqlite3.connect(DB_NAME);
        cursor = conn.cursor()
        try:
            field = "description" if self.cmb_search_by.get() == "Description" else "barcode"
            cursor.execute(f"""SELECT barcode, description, category, supplier, selling_price, soh
                              FROM products WHERE {field} LIKE ? COLLATE NOCASE
                              ORDER BY description ASC LIMIT 250""", (f"%{query}%",))
            rows = cursor.fetchall()
        except Exception:
            cursor.execute("""SELECT barcode, description, '', '', selling_price, soh FROM products
                            WHERE description LIKE ? OR barcode LIKE ? ORDER BY description LIMIT 250""",
                           (f"%{query}%", f"%{query}%"))
            rows = cursor.fetchall()
        finally:
            conn.close()
        for barcode, desc, cat, supplier, price, soh in rows:
            self.tree.insert("", tk.END, values=(barcode or "", desc or "", cat or "", supplier or "",
                                                 f"R {float(price or 0):,.2f}", f"{float(soh or 0):g}"))
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0]);
            self.tree.focus(children[0]);
            self.tree.see(children[0])
        self.result_label.config(text=f"{len(rows)} product(s) found")

    def confirm_selection(self):
        selected = self.tree.selection()
        if not selected:
            return "break"

        barcode = str(self.tree.item(selected[0])["values"][0])

        # Close the modal FIRST.  The quotation screen must never be left with
        # the F3 lookup sitting on top of it, even if the receiving callback
        # performs another UI action or raises an exception.
        try:
            self.grab_release()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in ui/windows.py", exc_info=exc)
        try:
            self.destroy()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in ui/windows.py", exc_info=exc)

        if self.on_select_callback:
            try:
                self.on_select_callback(barcode)
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in ui/windows.py", exc_info=exc)

        return "break"


class EditCartItemDialog(tk.Toplevel):

    def __init__(
        self,
        parent,
        item_name,
        current_qty,
        current_price,
        can_edit_price=True,
        can_edit_qty=True
    ):

        super().__init__(parent)

        self.result = None

        self.can_edit_price = can_edit_price
        self.can_edit_qty = can_edit_qty

        self.title("Edit Item")
        self.geometry("340x280")
        self.resizable(False, False)
        self.configure(
            bg="#f0f4f8"
        )

        self.transient(parent)
        self.grab_set()

        self.update_idletasks()

        x = (
            self.winfo_screenwidth() // 2
            - 170
        )

        y = (
            self.winfo_screenheight() // 2
            - 140
        )

        self.geometry(
            f"340x280+{x}+{y}"
        )

        tk.Label(
            self,
            text="Edit Item",
            font=("Arial", 14, "bold"),
            bg="#2c5282",
            fg="white",
            pady=10
        ).pack(
            fill=tk.X
        )

        body = tk.Frame(
            self,
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
            text=item_name,
            font=("Arial", 10, "bold"),
            bg="#f0f4f8",
            wraplength=280,
            justify="left"
        ).pack(
            anchor="w",
            pady=(0, 10)
        )

        tk.Label(
            body,
            text="Quantity:",
            font=("Arial", 10, "bold"),
            bg="#f0f4f8"
        ).pack(
            anchor="w"
        )

        self.entry_qty = tk.Entry(
            body,
            font=("Arial", 12),
            width=15,
            justify="center"
        )

        self.entry_qty.insert(
            0,
            f"{current_qty:.0f}"
        )

        self.entry_qty.pack(
            anchor="w",
            pady=(0, 10)
        )

        if not can_edit_qty:

            self.entry_qty.config(
                state="readonly"
            )

        else:

            vcmd_qty = self.register(
                self._validate_qty_keystroke
            )

            self.entry_qty.config(
                validate="key",
                validatecommand=(
                    vcmd_qty,
                    "%P"
                )
            )

        tk.Label(
            body,
            text="Price:",
            font=("Arial", 10, "bold"),
            bg="#f0f4f8"
        ).pack(
            anchor="w"
        )

        self.entry_price = tk.Entry(
            body,
            font=("Arial", 12),
            width=15,
            justify="right"
        )

        self.entry_price.insert(
            0,
            f"{current_price:.2f}"
        )

        self.entry_price.pack(
            anchor="w",
            pady=(0, 15)
        )

        if not can_edit_price:

            self.entry_price.config(
                state="readonly"
            )

        btn_frame = tk.Frame(
            body,
            bg="#f0f4f8"
        )

        btn_frame.pack(
            fill=tk.X
        )

        tk.Button(
            btn_frame,
            text="Save",
            font=("Arial", 10, "bold"),
            bg="#38a169",
            fg="white",
            width=10,
            command=self._save
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Button(
            btn_frame,
            text="Cancel",
            font=("Arial", 10, "bold"),
            width=10,
            command=self._cancel
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        if can_edit_qty:

            self.entry_qty.select_range(
                0,
                tk.END
            )

            self.entry_qty.focus_set()

        else:

            self.entry_price.focus_set()

        self.entry_qty.bind(
            "<Return>",
            lambda e: self.entry_price.focus_set()
        )

        self.entry_price.bind(
            "<Return>",
            lambda e: self._save()
        )

        self.bind(
            "<Escape>",
            lambda e: self._cancel()
        )

    def _validate_qty_keystroke(
        self,
        proposed_value
    ):

        if proposed_value == "":
            return True

        return proposed_value.isdigit()

    def _save(self):

        qty_text = (
            self.entry_qty.get()
            .strip()
        )

        price_text = (
            self.entry_price.get()
            .strip()
        )

        if self.can_edit_qty:

            if (
                not qty_text
                or not qty_text.isdigit()
                or int(qty_text) <= 0
            ):

                messagebox.showerror(
                    "Invalid Quantity",
                    "Please enter a whole number greater than 0.",
                    parent=self
                )

                return

            new_qty = float(
                qty_text
            )

        else:

            try:
                new_qty = float(
                    qty_text
                )
            except ValueError:
                return

        if self.can_edit_price:

            try:

                new_price = float(
                    price_text
                )

            except ValueError:

                messagebox.showerror(
                    "Invalid Price",
                    "Please enter a valid number for the price.",
                    parent=self
                )

                return

        else:

            try:
                new_price = float(
                    price_text
                )
            except ValueError:
                return

        self.result = (
            new_qty,
            new_price
        )

        self.destroy()

    def _cancel(self):

        self.result = None

        self.destroy()


class InvoiceSelectorWindow(tk.Toplevel):

    def __init__(self, parent):

        super().__init__(parent)

        self.parent = parent

        self.title("Open Invoices")
        self.geometry("500x380")
        self.resizable(False, False)

        self.configure(
            bg=UI_BG
        )

        self.transient(parent)
        self.grab_set()

        tk.Label(
            self,
            text="OPEN INVOICES",
            font=("Arial", 15, "bold"),
            bg=HEADER_COLOR,
            fg="white",
            pady=12
        ).pack(
            fill=tk.X
        )

        body = tk.Frame(
            self,
            bg=UI_BG,
            padx=15,
            pady=15
        )

        body.pack(
            fill=tk.BOTH,
            expand=True
        )

        columns = (
            "invoice",
            "items",
            "total"
        )

        self.tree = ttk.Treeview(
            body,
            columns=columns,
            show="headings",
            height=10
        )

        self.tree.heading(
            "invoice",
            text="Invoice"
        )

        self.tree.heading(
            "items",
            text="Items"
        )

        self.tree.heading(
            "total",
            text="Total"
        )

        self.tree.column(
            "invoice",
            width=150,
            anchor="center"
        )

        self.tree.column(
            "items",
            width=100,
            anchor="center"
        )

        self.tree.column(
            "total",
            width=150,
            anchor="e"
        )

        self.tree.pack(
            fill=tk.BOTH,
            expand=True
        )

        self.load_invoices()

        self.tree.bind(
            "<Double-1>",
            lambda e: self.select_invoice()
        )

        button_frame = tk.Frame(
            self,
            bg=UI_BG,
            pady=10
        )

        button_frame.pack(
            fill=tk.X
        )

        tk.Button(
            button_frame,
            text="Open Selected",
            font=("Arial", 10, "bold"),
            bg="#3182ce",
            fg="white",
            width=15,
            command=self.select_invoice
        ).pack(
            side=tk.LEFT,
            padx=10
        )

        tk.Button(
            button_frame,
            text="New Invoice",
            font=("Arial", 10, "bold"),
            bg="#38a169",
            fg="white",
            width=15,
            command=self.new_invoice
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Button(
            button_frame,
            text="Close",
            font=("Arial", 10),
            width=12,
            command=self.destroy
        ).pack(
            side=tk.RIGHT,
            padx=10
        )

        self.bind(
            "<Escape>",
            lambda e: self.destroy()
        )

    def load_invoices(self):

        for row in self.tree.get_children():

            self.tree.delete(
                row
            )

        for invoice_id, invoice in self.parent.invoices.items():

            item_count = sum(
                item["qty"]
                for item in invoice["cart"]
            )

            subtotal = sum(
                item["value"]
                for item in invoice["cart"]
            )

            # Prices in the POS are VAT-inclusive.
            # Extract the VAT portion from the selling price.
            total = subtotal
            vat = total - (total / 1.15)
            subtotal_ex_vat = total / 1.15

            self.tree.insert(
                "",
                tk.END,
                iid=str(invoice_id),
                values=(
                    f"Invoice {invoice_id:03d}",
                    f"{item_count:.0f}",
                    f"R {total:.2f}"
                )
            )

        current_id = self.parent.current_invoice_id

        if str(current_id) in self.tree.get_children():

            self.tree.selection_set(
                str(current_id)
            )

            self.tree.focus(
                str(current_id)
            )

    def select_invoice(self):

        selected = self.tree.selection()

        if not selected:

            messagebox.showwarning(
                "No Selection",
                "Please select an invoice.",
                parent=self
            )

            return

        invoice_id = int(
            selected[0]
        )

        self.parent.switch_invoice(
            invoice_id
        )

        self.destroy()

    def new_invoice(self):

        self.parent.create_new_invoice()

        self.destroy()


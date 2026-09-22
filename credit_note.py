from core.logger import logger as _bkpos_logger
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ui.window_polish import polish_window
try:
    from core.config import DB_PATH
    DB_NAME = DB_PATH
except Exception:
    DB_NAME = 'pos_store.db'


class CreditNoteWindow(tk.Toplevel):
    """F12 Credit Note for the currently selected/open POS invoice.

    A credit note is treated as a stock-and-sales adjustment, not as a normal
    payment.  Every credited quantity is returned to SOH and recorded in
    return_history so Sales Report can deduct the same value from sales.
    The original open invoice is never posted as a sale just because a credit
    note is made against it.
    """

    def __init__(self, parent, invoice_id=None, sale_id=None):
        super().__init__(parent)
        polish_window(self)
        self.parent = parent
        self.invoice_id = invoice_id
        self.sale_id = sale_id
        self.cashier = getattr(parent, 'cashier_username', 'Unknown')
        self.items = []

        self.title('Credit Note / Product Return')
        self.geometry('950x600')
        self.minsize(820, 520)
        self.configure(bg='#eef2f7')
        self.transient(parent)
        self.grab_set()

        self.total_var = tk.StringVar(value='Credit Note Total: R 0.00')
        self.reason_var = tk.StringVar()
        self.info_var = tk.StringVar(value='')

        self._build()
        self.load_current_invoice()
        self.bind('<Escape>', lambda e: self.destroy())
        self.bind('<F12>', lambda e: self.process_credit_note())
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        self.wait_visibility()
        self.focus_force()

    def db(self):
        return sqlite3.connect(DB_NAME)

    def _ensure_return_tables(self, conn):
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS return_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                original_sale_id INTEGER NOT NULL,
                total_amount REAL NOT NULL DEFAULT 0,
                refund_type TEXT NOT NULL,
                cashier TEXT DEFAULT 'Unknown',
                reason TEXT DEFAULT ''
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS return_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                return_id INTEGER NOT NULL,
                sale_item_id INTEGER NOT NULL,
                barcode TEXT,
                description TEXT,
                qty REAL NOT NULL,
                price REAL NOT NULL,
                value REAL NOT NULL
            )
        ''')
        conn.commit()

    def _build(self):
        header = tk.Frame(self, bg='#2c5282', height=76)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text='CREDIT NOTE / PRODUCT RETURN', font=('Arial', 18, 'bold'),
                 fg='white', bg='#2c5282').pack(side=tk.LEFT, padx=22, pady=18)
        tk.Label(header, text='F12', font=('Arial', 13, 'bold'), fg='white', bg='#2c5282').pack(side=tk.RIGHT, padx=22)

        top = tk.Frame(self, bg='#eef2f7', padx=16, pady=12)
        top.pack(fill=tk.X)
        tk.Label(top, text='CURRENT INVOICE:', font=('Arial', 11, 'bold'), bg='#eef2f7').pack(side=tk.LEFT)
        self.invoice_label = tk.Label(top, text='', font=('Arial', 13, 'bold'), fg='#2c5282', bg='#eef2f7')
        self.invoice_label.pack(side=tk.LEFT, padx=8)
        tk.Label(top, textvariable=self.info_var, font=('Arial', 10, 'bold'), fg='#4a5568', bg='#eef2f7').pack(side=tk.LEFT, padx=18)

        frame = tk.Frame(self, bg='white', highlightthickness=1, highlightbackground='#d6dee8')
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))
        tk.Label(frame, text='PRODUCTS ON THIS INVOICE — ENTER CREDIT QTY',
                 font=('Arial', 11, 'bold'), bg='white').pack(anchor='w', padx=10, pady=8)

        cols = ('code', 'description', 'qty', 'price', 'credit_qty', 'value')
        self.items_tree = ttk.Treeview(frame, columns=cols, show='headings')
        headings = {'code':'Code', 'description':'Description', 'qty':'Invoice Qty',
                    'price':'Price', 'credit_qty':'Credit Qty', 'value':'Credit Value'}
        widths = {'code':110, 'description':320, 'qty':90, 'price':100, 'credit_qty':100, 'value':120}
        for c in cols:
            self.items_tree.heading(c, text=headings[c])
            self.items_tree.column(c, width=widths[c], anchor='center')
        self.items_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.items_tree.bind('<Double-1>', self.edit_qty)

        actions = tk.Frame(self, bg='#eef2f7', padx=16, pady=10)
        actions.pack(fill=tk.X)
        tk.Button(actions, text='CREDIT ENTIRE INVOICE', font=('Arial', 10, 'bold'),
                  bg='#dd6b20', fg='white', padx=14, pady=7,
                  command=self.credit_entire_invoice).pack(side=tk.LEFT, padx=4)
        tk.Label(actions, text='Reason:', font=('Arial', 10, 'bold'), bg='#eef2f7').pack(side=tk.LEFT, padx=(18,4))
        tk.Entry(actions, textvariable=self.reason_var, font=('Arial', 10), width=28).pack(side=tk.LEFT)
        tk.Label(actions, textvariable=self.total_var, font=('Arial', 14, 'bold'), bg='#eef2f7').pack(side=tk.RIGHT, padx=12)
        tk.Button(actions, text='CANCEL', font=('Arial', 10, 'bold'), bg='#718096', fg='white',
                  padx=16, pady=7, command=self.destroy).pack(side=tk.RIGHT, padx=4)
        tk.Button(actions, text='ISSUE CREDIT NOTE  (F12)', font=('Arial', 10, 'bold'), bg='#38a169', fg='white',
                  padx=16, pady=7, command=self.process_credit_note).pack(side=tk.RIGHT, padx=4)

    def load_current_invoice(self):
        if self.invoice_id is None or self.invoice_id not in getattr(self.parent, 'invoices', {}):
            self.info_var.set('No active invoice was supplied.')
            return

        invoice = self.parent.invoices[self.invoice_id]
        self.invoice_label.config(text=f'Invoice {int(self.invoice_id):03d}')
        self.info_var.set('Current POS invoice — credit note will return stock and reduce Sales Report.')
        self.items = []
        self.items_tree.delete(*self.items_tree.get_children())

        for idx, item in enumerate(invoice.get('cart', [])):
            qty = float(item.get('qty', 0) or 0)
            price = float(item.get('price', 0) or 0)
            if qty <= 0:
                continue
            line = {'index': idx, 'code': str(item.get('code', '')), 'description': str(item.get('name', '')),
                    'qty': qty, 'price': price, 'credit_qty': 0.0,
                    'cost': float(item.get('cost', 0) or 0)}
            self.items.append(line)
            self.items_tree.insert('', tk.END, iid=str(len(self.items)-1),
                                   values=(line['code'], line['description'], f'{qty:g}', f'R {price:,.2f}', '0', 'R 0.00'))
        self.recalculate()

    def edit_qty(self, _event=None):
        sel = self.items_tree.selection()
        if not sel:
            return
        i = int(sel[0])
        line = self.items[i]
        value = simpledialog.askfloat('Credit Quantity',
                                      f"How many '{line['description']}' do you want to credit?",
                                      initialvalue=line['credit_qty'], minvalue=0, maxvalue=line['qty'], parent=self)
        if value is None:
            return
        line['credit_qty'] = min(float(value), line['qty'])
        self.refresh_line(i)
        self.recalculate()

    def refresh_line(self, i):
        line = self.items[i]
        value = line['credit_qty'] * line['price']
        self.items_tree.item(str(i), values=(line['code'], line['description'], f"{line['qty']:g}",
                                             f"R {line['price']:,.2f}", f"{line['credit_qty']:g}", f"R {value:,.2f}"))

    def credit_entire_invoice(self):
        for i, line in enumerate(self.items):
            line['credit_qty'] = line['qty']
            self.refresh_line(i)
        self.recalculate()

    def recalculate(self):
        total = sum(x['credit_qty'] * x['price'] for x in self.items)
        self.total_var.set(f'Credit Note Total: R {total:,.2f}')

    def process_credit_note(self):
        if self.invoice_id is None or self.invoice_id not in getattr(self.parent, 'invoices', {}):
            messagebox.showerror('Credit Note', 'The current invoice is no longer available.', parent=self)
            return

        lines = [x for x in self.items if x['credit_qty'] > 0]
        if not lines:
            messagebox.showwarning('Credit Note', 'Enter at least one Credit Qty.', parent=self)
            return

        total = sum(x['credit_qty'] * x['price'] for x in lines)
        invoice_number = int(self.invoice_id)
        reason = self.reason_var.get().strip() or 'Product return / Credit Note'

        if not messagebox.askyesno(
            'Confirm Credit Note',
            f'Issue Credit Note for Invoice #{invoice_number:03d}?\n\n'
            f'Products credited: {len(lines)}\n'
            f'Credit total: R {total:,.2f}\n\n'
            'The credited quantity will be added back to SOH.\n'
            'The same value will be deducted from Sales Report.\n'
            'This invoice will NOT be posted as a sale.',
            parent=self):
            return

        conn = self.db()
        try:
            self._ensure_return_tables(conn)
            cur = conn.cursor()

            # A credit note from the current POS invoice is a stock return /
            # sales adjustment. It always puts the credited quantity back.
            # Use 0 as original_sale_id because this invoice has not been
            # posted to sales_history yet.
            cur.execute('''
                INSERT INTO return_history
                (original_sale_id, total_amount, refund_type, cashier, reason)
                VALUES (?, ?, ?, ?, ?)
            ''', (0, total, 'CREDIT NOTE', self.cashier, f'Invoice #{invoice_number:03d}: {reason}'))
            return_id = cur.lastrowid

            stock_changes = []
            for line in lines:
                barcode = line['code']
                qty = float(line['credit_qty'])
                price = float(line['price'])
                value = qty * price

                from services.branch_stock_service import get_branch_soh, change_stock
                branch_id=getattr(self.parent,'current_branch_id',1) if hasattr(self,'parent') else 1
                row = cur.execute('SELECT 1 FROM products WHERE barcode = ?', (barcode,)).fetchone()
                if row is None:
                    raise RuntimeError(f'Product {barcode} was not found in the product database.')
                before = get_branch_soh(cur.connection, branch_id, barcode)
                _, after = change_stock(cur.connection, branch_id, barcode, qty, expected_before=before)
                stock_changes.append((line['description'], qty, before, after))

                # No real sale_item exists for an open invoice, so 0 is used
                # as the source line identifier. The barcode/description are
                # retained for a complete audit trail.
                cur.execute('''
                    INSERT INTO return_items
                    (return_id, sale_item_id, barcode, description, qty, price, value)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (return_id, 0, barcode, line['description'], qty, price, value))

                # Record through the canonical stock-movement service.  This
                # deliberately supports both the current schema and legacy
                # databases where quantity is NOT NULL.
                from services.stock_service import record_stock_movement
                record_stock_movement(
                    barcode=barcode,
                    movement_type='RETURN',
                    quantity=qty,
                    reference=f'CREDIT NOTE #{return_id}',
                    description=line['description'],
                    qty_before=before,
                    qty_after=after,
                    cost_price=float(line.get('cost', 0) or 0),
                    reason=reason,
                    cashier=self.cashier,
                    conn=conn,
                )

            # Remove only the credited quantities from the current POS invoice.
            invoice = self.parent.invoices[self.invoice_id]
            for line in lines:
                remaining = float(line['qty']) - float(line['credit_qty'])
                original_index = line['index']
                if 0 <= original_index < len(invoice.get('cart', [])):
                    if remaining <= 0.000001:
                        invoice['cart'][original_index]['qty'] = 0
                        invoice['cart'][original_index]['value'] = 0
                    else:
                        invoice['cart'][original_index]['qty'] = remaining
                        invoice['cart'][original_index]['value'] = remaining * invoice['cart'][original_index]['price']

            invoice['cart'] = [x for x in invoice.get('cart', []) if float(x.get('qty', 0) or 0) > 0]
            conn.commit()

            try:
                self.parent.update_cart_display()
                self.parent.refresh_invoice_tabs()
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in credit_note.py", exc_info=exc)

            stock_text = '\n'.join(
                f"{name}: +{qty:g} SOH ({before:g} → {after:g})"
                for name, qty, before, after in stock_changes
            )
            messagebox.showinfo(
                'Credit Note Completed',
                f'Credit Note #{return_id} completed for Invoice #{invoice_number:03d}.\n\n'
                f'Credit total: R {total:,.2f}\n\n'
                f'STOCK RETURNED:\n{stock_text}\n\n'
                f'R {total:,.2f} will be deducted from Sales Report.',
                parent=self)
            self.destroy()

        except Exception as exc:
            conn.rollback()
            messagebox.showerror('Credit Note Failed', str(exc), parent=self)
        finally:
            conn.close()

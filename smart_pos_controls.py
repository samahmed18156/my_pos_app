"""Smart checkout, pricing protection, stock intelligence and management dashboard.

Designed as a non-invasive layer over the existing POS. New functionality lives in
this module so app.py does not need manual edits.
"""
from core.logger import logger as _bkpos_logger
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from core.config import DB_PATH
DB_NAME = DB_PATH


def db():
    return sqlite3.connect(DB_NAME)


def ensure_schema():
    c = db(); cur = c.cursor()
    def col(table, name, typ):
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
        if name not in cols:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
    col("sales_history", "customer_id", "INTEGER")
    col("sales_history", "customer_type", "TEXT DEFAULT 'Retail'")
    col("sales_history", "customer_name", "TEXT DEFAULT 'Cash Sale'")
    col("sales_history", "status", "TEXT DEFAULT 'COMPLETED'")
    col("sales_history", "below_cost_override", "INTEGER DEFAULT 0")
    col("sales_history", "invoice_ref", "TEXT")
    cur.execute("""CREATE TABLE IF NOT EXISTS sale_lifecycle (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        event_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL,
        username TEXT DEFAULT 'Unknown',
        details TEXT DEFAULT ''
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sale_lifecycle_sale ON sale_lifecycle(sale_id,event_time)")
    cur.execute("""CREATE TABLE IF NOT EXISTS stock_alert_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        barcode TEXT, description TEXT, soh REAL, min_stock REAL,
        alert_type TEXT, username TEXT DEFAULT 'System'
    )""")
    c.commit(); c.close()


def audit(parent, action, details, entity_type="POS", entity_id=""):
    try:
        c = db(); c.execute(
            "INSERT INTO audit_log(event_time,username,role,action,entity_type,entity_id,details,branch_id,event_type) VALUES(datetime('now','localtime'),?,?,?,?,?,?,?,?)",
            (getattr(parent, "cashier_username", "Unknown"), getattr(parent, "cashier_role", ""),
             action, entity_type, str(entity_id), details, getattr(parent, "current_branch_id", 1), action))
        c.commit(); c.close()
    except Exception as exc:
        _bkpos_logger.warning("Suppressed exception in smart_pos_controls.py", exc_info=exc)


def current_customer(parent):
    inv = parent.current_invoice()
    ctype = inv.get("customer_type", "Retail")
    cid = inv.get("customer_id")
    return ctype, cid, inv.get("customer_name", "Cash Sale")


def smart_price(parent, barcode, qty, retail_price):
    """Resolve retail/bulk/wholesale price while preserving VAT-inclusive prices."""
    try:
        from customer_pricing import get_customer, get_price_for_sale
        ctype, cid, _ = current_customer(parent)
        cust = get_customer(cid) if cid else {"type": ctype, "price_list_id": None}
        if ctype == "Retail":
            cust = {"type": "Retail", "price_list_id": None}
        return float(get_price_for_sale(barcode, qty, retail_price, cust))
    except Exception:
        return float(retail_price or 0)


def available_stock(barcode):
    c = db(); r = c.execute("SELECT description,COALESCE(soh,0),COALESCE(min_stock,0),COALESCE(cost_price,0),COALESCE(selling_price,0) FROM products WHERE barcode=?", (str(barcode),)).fetchone(); c.close()
    return r


def add_price_wrapper(original):
    def wrapped(self, event=None):
        data = getattr(self, "selected_product_data", None)
        if data:
            try:
                qty = float(self.qty_entry.get().strip() or 1)
            except Exception:
                qty = 1
            data["base_price"] = float(data.get("base_price", data.get("price", 0)) or 0)
            data["price"] = smart_price(self, data["code"], qty, data["base_price"])
            # Store the resolved price in the normal price field so the original method uses it.
            try:
                self.price_display.config(state="normal")
                self.price_display.delete(0, tk.END); self.price_display.insert(0, f"{data['price']:.2f}")
                if not self.can("can_edit_price"): self.price_display.config(state="readonly")
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in smart_pos_controls.py", exc_info=exc)
        result = original(self, event)
        try:
            inv = self.current_invoice()
            if inv.get("cart"):
                item = inv["cart"][-1]
                item.setdefault("base_price", float(data.get("base_price", item.get("price", 0)) if data else item.get("price", 0)))
                item["price"] = smart_price(self, item["code"], item["qty"], item["base_price"])
                item["value"] = item["price"] * item["qty"]
                self.update_cart_display()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in smart_pos_controls.py", exc_info=exc)
        return result
    return wrapped


def edit_wrapper(original):
    def wrapped(self, event):
        result = original(self, event)
        try:
            inv = self.current_invoice()
            for item in inv.get("cart", []):
                item.setdefault("base_price", item.get("price", 0))
                item["price"] = smart_price(self, item["code"], item["qty"], item["base_price"])
                item["value"] = item["price"] * item["qty"]
            self.update_cart_display()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in smart_pos_controls.py", exc_info=exc)
        return result
    return wrapped


def checkout_wrapper(original):
    def wrapped(self, event=None):
        ensure_schema()
        inv = self.current_invoice()
        cart = inv.get("cart", [])
        if not cart:
            return original(self, event)

        # Stock policy: this POS intentionally allows negative SOH.
        # The shop can sell an item even when SOH is zero; the resulting
        # SOH is allowed to become -1, -2, etc. We warn, but never block,
        # because the shop may have physical stock that has not yet been
        # received/entered into the system.
        shortages = []
        low = []
        below = []
        for item in cart:
            r = available_stock(item["code"])
            if not r:
                continue
            desc, soh, min_stock, cost, selling = r
            requested = float(item["qty"])
            available = float(soh)
            remaining = available - requested
            if requested > available:
                shortages.append(
                    f"{item['name']}: selling {requested:g}, current SOH {available:g}, "
                    f"new SOH will be {remaining:g}"
                )
            if remaining <= float(min_stock) and float(min_stock) > 0:
                low.append(f"{item['name']} (remaining {remaining:g})")
            if float(item.get("price", 0)) < float(item.get("cost", cost) or cost):
                below.append(f"{item['name']}: sell R{float(item['price']):,.2f} < cost R{float(item.get('cost', cost)):,.2f}")

        # Inform the cashier, but allow the sale to continue into negative SOH.
        if shortages:
            messagebox.showwarning(
                "Negative Stock Warning",
                "This sale will make one or more stock balances negative.\n\n"
                + "\n".join(shortages)
                + "\n\nThe sale is allowed to continue.",
                parent=self,
            )
            audit(self, "NEGATIVE_STOCK_SALE_ALLOWED", "; ".join(shortages), "SALE")

        override = False
        if below:
            allowed = getattr(self, "is_admin", False) or self.can("can_edit_price")
            if not allowed:
                messagebox.showerror("Below Cost Sale", "Checkout blocked because one or more items are below cost.\n\n" + "\n".join(below), parent=self)
                audit(self, "BELOW_COST_BLOCKED", "; ".join(below), "SALE")
                return
            answer = messagebox.askyesno("Below Cost Sale", "One or more items are below cost:\n\n" + "\n".join(below) + "\n\nContinue anyway?", parent=self)
            if not answer:
                return
            override = True
            audit(self, "BELOW_COST_OVERRIDE", "; ".join(below), "SALE")

        if low:
            messagebox.showwarning("Low Stock Warning", "These products will be at/below minimum stock after this sale:\n\n" + "\n".join(low), parent=self)

        before = None
        invoice_ref = f"INV-{getattr(self,'current_invoice_id',0):03d}"
        try:
            c = db(); before = c.execute("SELECT COALESCE(MAX(id),0) FROM sales_history").fetchone()[0]; c.close()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in smart_pos_controls.py", exc_info=exc)
        result = original(self, event)
        try:
            c = db(); row = c.execute("SELECT id,customer_id,customer_type,customer_name FROM sales_history WHERE id>? ORDER BY id DESC LIMIT 1", (before or 0,)).fetchone()
            if row:
                sid = row[0]
                c.execute("UPDATE sales_history SET customer_id=?,customer_type=?,customer_name=?,status='COMPLETED',below_cost_override=?,invoice_ref=? WHERE id=?",
                          (inv.get("customer_id"), inv.get("customer_type", "Retail"), inv.get("customer_name", "Cash Sale"), int(override), invoice_ref, sid))
                c.execute("INSERT INTO sale_lifecycle(sale_id,status,username,details) VALUES(?,?,?,?)",
                          (sid, "COMPLETED", getattr(self,"cashier_username","Unknown"), f"{inv.get('customer_type','Retail')} sale; customer={inv.get('customer_name','Cash Sale')}"))
                c.commit()
            c.close()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in smart_pos_controls.py", exc_info=exc)
        return result
    return wrapped


class SmartManagementDashboard(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent); ensure_schema(); self.parent=parent
        self.title("POS Management Dashboard"); self.geometry("1180x720"); self.minsize(1000,620); self.build(); self.refresh()
    def build(self):
        tk.Label(self,text="POS MANAGEMENT DASHBOARD",font=("Arial",19,"bold"),bg="#24476b",fg="white",pady=12).pack(fill="x")
        self.summary=tk.Frame(self,padx=12,pady=12); self.summary.pack(fill="x")
        self.cards={}
        for key,title in [("sales","Sales"),("profit","Profit"),("vat","VAT"),("transactions","Transactions"),("returns","Returns"),("retail","Retail"),("bulk","Bulk"),("wholesale","Wholesale")]:
            f=tk.Frame(self.summary,bd=1,relief="groove",padx=14,pady=10); f.pack(side="left",fill="both",expand=True,padx=4)
            tk.Label(f,text=title,font=("Arial",10,"bold")).pack(); v=tk.Label(f,text="R 0.00",font=("Arial",15,"bold")); v.pack(pady=4); self.cards[key]=v
        bar=tk.Frame(self,padx=12); bar.pack(fill="x"); tk.Button(bar,text="REFRESH",font=("Arial",10,"bold"),command=self.refresh).pack(side="left")
        tk.Button(bar,text="Stock Alerts",command=self.stock_alerts).pack(side="left",padx=8)
        cols=("type","qty","value","profit"); self.tree=ttk.Treeview(self,columns=cols,show="headings",height=18)
        for c,t,w in [("type","Sales Type",180),("qty","Transactions",130),("value","Sales (R)",180),("profit","Profit (R)",180)]: self.tree.heading(c,text=t); self.tree.column(c,width=w,anchor="e" if c!="type" else "center")
        self.tree.pack(fill="both",expand=True,padx=12,pady=12)
    def refresh(self):
        try:
            c=db(); sales=c.execute("SELECT COALESCE(SUM(total_amount),0),COALESCE(SUM(total_cost),0),COUNT(*) FROM sales_history WHERE date(timestamp)=date('now','localtime') AND COALESCE(status,'COMPLETED')='COMPLETED'").fetchone()
            vat=float(sales[0])*15/115; returns=c.execute("SELECT COALESCE(SUM(total_amount),0) FROM return_history WHERE date(timestamp)=date('now','localtime')").fetchone()[0] or 0
            self.cards["sales"].config(text=f"R {float(sales[0]):,.2f}"); self.cards["profit"].config(text=f"R {float(sales[0])-float(sales[1]):,.2f}"); self.cards["vat"].config(text=f"R {vat:,.2f}"); self.cards["transactions"].config(text=str(sales[2])); self.cards["returns"].config(text=f"R {float(returns):,.2f}")
            self.tree.delete(*self.tree.get_children())
            rows=c.execute("SELECT COALESCE(customer_type,'Retail'),COUNT(*),COALESCE(SUM(total_amount),0),COALESCE(SUM(total_amount-total_cost),0) FROM sales_history WHERE date(timestamp)=date('now','localtime') AND COALESCE(status,'COMPLETED')='COMPLETED' GROUP BY COALESCE(customer_type,'Retail') ORDER BY customer_type").fetchall()
            for r in rows:self.tree.insert("","end",values=(r[0],r[1],f"R {r[2]:,.2f}",f"R {r[3]:,.2f}"))
            for typ in ("Retail","Bulk","Wholesale"):
                r=next((x for x in rows if x[0]==typ),None); self.cards[typ.lower()].config(text=f"R {float(r[2]):,.2f}" if r else "R 0.00")
            c.close()
        except Exception as e: messagebox.showerror("Dashboard",str(e),parent=self)
    def stock_alerts(self):
        c=db(); rows=c.execute("SELECT barcode,description,COALESCE(soh,0),COALESCE(min_stock,0) FROM products WHERE COALESCE(active,1)=1 AND (COALESCE(soh,0)<=0 OR COALESCE(soh,0)<=COALESCE(min_stock,0)) ORDER BY soh,description").fetchall(); c.close()
        w=tk.Toplevel(self);w.title("Stock Alerts");w.geometry("760x480")
        t=ttk.Treeview(w,columns=("code","desc","soh","min","status"),show="headings")
        for c,h in zip(("code","desc","soh","min","status"),("Barcode","Description","SOH","Minimum","Status")):t.heading(c,text=h);t.column(c,width=140 if c!="desc" else 260)
        for r in rows:t.insert("","end",values=(*r,"OUT OF STOCK" if float(r[2])<=0 else "LOW STOCK"))
        t.pack(fill="both",expand=True,padx=10,pady=10)


def install(app_cls):
    ensure_schema()
    original_add = app_cls.add_current_item_to_cart
    if not getattr(app_cls, "_smart_price_installed", False):
        app_cls.add_current_item_to_cart = add_price_wrapper(original_add)
        app_cls.open_edit_cart_item = edit_wrapper(app_cls.open_edit_cart_item)
        app_cls.checkout = checkout_wrapper(app_cls.checkout)
        app_cls._smart_price_installed = True

    original_menu = app_cls.create_menu_bar
    def menu(self):
        result = original_menu(self)
        # Add a single management dashboard entry to the existing Utility menu.
        try:
            top = self.nametowidget(self.cget("menu"))
            for i in range(top.index("end") + 1):
                if top.type(i) == "cascade" and top.entrycget(i,"label") == "Utility":
                    sub = self.nametowidget(top.entrycget(i,"menu"))
                    sub.add_separator()
                    sub.add_command(label="Smart Management Dashboard", command=lambda: SmartManagementDashboard(self))
                    break
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in smart_pos_controls.py", exc_info=exc)
        return result
    if not getattr(app_cls, "_smart_menu_installed", False):
        app_cls.create_menu_bar = menu; app_cls._smart_menu_installed = True
    return app_cls

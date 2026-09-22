from core.logger import logger as _bkpos_logger
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from core.config import DB_PATH
DB_NAME = DB_PATH

CUSTOMER_TYPES = ("Retail", "Bulk", "Wholesale")


def connect():
    return sqlite3.connect(DB_NAME)


def ensure_schema():
    c = connect()
    cur = c.cursor()
    # Create the customer table if this module is ever initialized before the
    # older customer module. Existing customer data is preserved.
    cur.execute("""CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, phone TEXT, address TEXT, email TEXT,
        credit_limit REAL DEFAULT 0, active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    # Extend the existing customer table without destroying existing customers.
    cols = {r[1] for r in cur.execute("PRAGMA table_info(customers)").fetchall()}
    if "customer_type" not in cols:
        cur.execute("ALTER TABLE customers ADD COLUMN customer_type TEXT DEFAULT 'Retail'")
    if "price_list_id" not in cols:
        cur.execute("ALTER TABLE customers ADD COLUMN price_list_id INTEGER")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS wholesale_price_lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS wholesale_price_list_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            price_list_id INTEGER NOT NULL,
            barcode TEXT NOT NULL,
            min_qty REAL NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL,
            UNIQUE(price_list_id, barcode, min_qty)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customer_pricing_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            username TEXT,
            customer_id INTEGER,
            customer_type TEXT,
            price_list_id INTEGER,
            action TEXT,
            details TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_wpl_items_lookup ON wholesale_price_list_items(price_list_id, barcode, min_qty)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_customers_type ON customers(customer_type)")

    # Give existing customers a sensible default.
    cur.execute("UPDATE customers SET customer_type='Retail' WHERE customer_type IS NULL OR customer_type=''")
    # A default wholesale list makes setup easier, but it is not automatically assigned.
    cur.execute("INSERT OR IGNORE INTO wholesale_price_lists(name,description) VALUES('Default Wholesale','Default wholesale price list')")
    c.commit()
    c.close()


def get_customer(customer_id):
    if not customer_id:
        return None
    c = connect()
    row = c.execute("SELECT id,name,phone,customer_type,price_list_id FROM customers WHERE id=? AND active=1", (customer_id,)).fetchone()
    c.close()
    if not row:
        return None
    return {"id": row[0], "name": row[1], "phone": row[2], "type": row[3] or "Retail", "price_list_id": row[4]}


def get_price_for_sale(barcode, qty, retail_price, customer=None):
    """Return the correct VAT-inclusive unit price for the current customer/quantity."""
    ensure_schema()
    try:
        qty = float(qty)
    except Exception:
        qty = 1.0
    customer = customer or {"type": "Retail", "price_list_id": None}
    ctype = customer.get("type", "Retail")

    c = connect()
    try:
        if ctype == "Wholesale" and customer.get("price_list_id"):
            row = c.execute(
                """SELECT unit_price FROM wholesale_price_list_items
                   WHERE price_list_id=? AND barcode=? AND min_qty<=?
                   ORDER BY min_qty DESC LIMIT 1""",
                (customer["price_list_id"], str(barcode), qty),
            ).fetchone()
            if row:
                return float(row[0])

        if ctype == "Bulk":
            row = c.execute(
                """SELECT unit_price FROM product_wholesale_prices
                   WHERE barcode=? AND min_qty<=?
                   ORDER BY min_qty DESC LIMIT 1""",
                (str(barcode), qty),
            ).fetchone()
            if row:
                return float(row[0])
    finally:
        c.close()
    return float(retail_price or 0)


def audit(parent, action, customer_id, details):
    try:
        c = connect()
        c.execute(
            "INSERT INTO audit_log(event_time,username,role,action,entity_type,entity_id,details,branch_id,event_type) VALUES(datetime('now','localtime'),?,?,?,?,?,?,?,?)",
            (
                getattr(parent, "cashier_username", "Unknown"),
                getattr(parent, "cashier_role", ""),
                action,
                "customer_pricing",
                str(customer_id or ""),
                details,
                getattr(parent, "current_branch_id", 1),
            ),
        )
        c.commit()
        c.close()
    except Exception as exc:
        _bkpos_logger.warning("Suppressed exception in customer_pricing.py", exc_info=exc)


class CustomerPricingWindow(tk.Toplevel):
    """Select the customer type for the current invoice and manage customers/lists."""

    def __init__(self, parent):
        super().__init__(parent)
        ensure_schema()
        self.parent = parent
        self.title("Customer & Pricing — Retail / Bulk / Wholesale")
        self.geometry("980x650")
        self.minsize(900, 600)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.customer_rows = []
        self.build()
        self.refresh_customers()
        self.refresh_lists()
        self.load_current()

    def build(self):
        header = tk.Frame(self, bg="#24476b", padx=14, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="CUSTOMER & PRICING", fg="white", bg="#24476b", font=("Arial", 18, "bold")).pack(side="left")
        self.current_label = tk.Label(header, text="", fg="white", bg="#24476b", font=("Arial", 11, "bold"))
        self.current_label.pack(side="right")

        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=12, pady=12)
        self.sale_tab = tk.Frame(tabs, padx=16, pady=16)
        self.customers_tab = tk.Frame(tabs, padx=12, pady=12)
        self.lists_tab = tk.Frame(tabs, padx=12, pady=12)
        tabs.add(self.sale_tab, text="Current Sale")
        tabs.add(self.customers_tab, text="Customers")
        tabs.add(self.lists_tab, text="Wholesale Price Lists")

        # Current sale
        tk.Label(self.sale_tab, text="CUSTOMER TYPE", font=("Arial", 13, "bold")).pack(anchor="w")
        self.type_var = tk.StringVar(value="Retail")
        rf = tk.Frame(self.sale_tab); rf.pack(fill="x", pady=10)
        for text in CUSTOMER_TYPES:
            tk.Radiobutton(rf, text=text, variable=self.type_var, value=text, font=("Arial", 12, "bold"), command=self.type_changed).pack(side="left", padx=(0, 24))
        tk.Label(self.sale_tab, text="Customer (optional for Retail/Bulk; recommended for Wholesale):", font=("Arial", 11, "bold")).pack(anchor="w", pady=(12, 4))
        self.customer_combo = ttk.Combobox(self.sale_tab, state="readonly", width=60)
        self.customer_combo.pack(fill="x")
        self.customer_combo.bind("<<ComboboxSelected>>", lambda e: self.customer_changed())
        self.customer_info = tk.Label(self.sale_tab, text="Retail uses the normal selling price.", justify="left", anchor="w", font=("Arial", 11))
        self.customer_info.pack(fill="x", pady=18)
        tk.Button(self.sale_tab, text="APPLY TO CURRENT INVOICE", font=("Arial", 12, "bold"), width=28, height=2, command=self.apply).pack(anchor="w", pady=10)
        tk.Button(self.sale_tab, text="CLEAR CUSTOMER / RETAIL SALE", width=28, command=self.clear_sale).pack(anchor="w")

        # Customers
        top = tk.Frame(self.customers_tab); top.pack(fill="x", pady=(0, 8))
        tk.Button(top, text="+ New Customer", command=self.edit_customer).pack(side="left")
        tk.Button(top, text="Edit Selected", command=self.edit_selected_customer).pack(side="left", padx=6)
        self.customer_tree = ttk.Treeview(self.customers_tab, columns=("id","name","type","list","phone"), show="headings")
        for col, txt, width in [("id","ID",55),("name","Name",230),("type","Type",100),("list","Wholesale Price List",220),("phone","Phone",140)]:
            self.customer_tree.heading(col, text=txt); self.customer_tree.column(col, width=width)
        self.customer_tree.pack(fill="both", expand=True)

        # Price lists
        top2 = tk.Frame(self.lists_tab); top2.pack(fill="x", pady=(0, 8))
        tk.Button(top2, text="+ New Price List", command=self.new_price_list).pack(side="left")
        tk.Button(top2, text="Edit Selected List", command=self.edit_price_list).pack(side="left", padx=6)
        tk.Button(top2, text="Manage List Prices", command=self.manage_list_prices).pack(side="left")
        self.list_tree = ttk.Treeview(self.lists_tab, columns=("id","name","description","active"), show="headings")
        for col, txt, width in [("id","ID",55),("name","Name",240),("description","Description",400),("active","Active",80)]:
            self.list_tree.heading(col, text=txt); self.list_tree.column(col, width=width)
        self.list_tree.pack(fill="both", expand=True)

        bottom = tk.Frame(self, padx=12, pady=10); bottom.pack(fill="x")
        tk.Button(bottom, text="Close", width=14, command=self.destroy).pack(side="right")

    def load_current(self):
        inv = self.parent.current_invoice()
        ctype = inv.get("customer_type", "Retail")
        self.type_var.set(ctype if ctype in CUSTOMER_TYPES else "Retail")
        cid = inv.get("customer_id")
        self.refresh_customer_combo(cid)
        self.update_info()

    def refresh_customer_combo(self, selected_id=None):
        c = connect(); rows = c.execute("SELECT id,name,customer_type,phone FROM customers WHERE active=1 ORDER BY name").fetchall(); c.close()
        self.customer_rows = rows
        values = [f"{r[0]} — {r[1]} [{r[2] or 'Retail'}]" for r in rows]
        self.customer_combo["values"] = values
        if selected_id:
            for i, r in enumerate(rows):
                if r[0] == selected_id:
                    self.customer_combo.current(i); break
            else: self.customer_combo.set("")
        else:
            self.customer_combo.set("")

    def type_changed(self):
        self.update_info()

    def customer_changed(self):
        self.update_info()

    def update_info(self):
        ctype = self.type_var.get()
        selected = self.customer_rows[self.customer_combo.current()] if self.customer_combo.current() >= 0 else None
        if ctype == "Retail":
            text = "Retail customer: normal retail selling price. Quantity does not change the price."
        elif ctype == "Bulk":
            text = "Bulk customer: the POS automatically uses the product's quantity price break (Bulk tiers) when quantity qualifies."
        else:
            if selected:
                cid = selected[0]; cust = get_customer(cid); lid = cust.get("price_list_id") if cust else None
                list_name = "No price list assigned"
                if lid:
                    c = connect(); r = c.execute("SELECT name FROM wholesale_price_lists WHERE id=?", (lid,)).fetchone(); c.close(); list_name = r[0] if r else "No price list assigned"
                text = f"Wholesale customer: uses assigned wholesale price list — {list_name}."
            else:
                text = "Wholesale customer: select a customer with an assigned wholesale price list."
        self.customer_info.config(text=text)
        self.current_label.config(text=f"Current: {ctype}")

    def apply(self):
        inv = self.parent.current_invoice()
        ctype = self.type_var.get()
        selected = self.customer_rows[self.customer_combo.current()] if self.customer_combo.current() >= 0 else None
        customer = get_customer(selected[0]) if selected else None
        if ctype == "Wholesale" and not customer:
            messagebox.showwarning("Wholesale", "Select a wholesale customer first.", parent=self); return
        if ctype == "Wholesale" and not customer.get("price_list_id"):
            messagebox.showwarning("Wholesale", "This customer does not have a wholesale price list assigned.", parent=self); return
        inv["customer_type"] = ctype
        inv["customer_id"] = customer["id"] if customer else None
        inv["customer_name"] = customer["name"] if customer else ("Bulk Customer" if ctype == "Bulk" else "Cash Sale")
        inv["customer_num"] = str(customer["id"]) if customer else ("BULK" if ctype == "Bulk" else "CASH")
        # Re-price any items already in the invoice using the selected customer mode.
        for item in inv.get("cart", []):
            item["price"] = get_price_for_sale(item["code"], item["qty"], item.get("base_price", item.get("price", 0)), customer if ctype != "Retail" else {"type":"Retail"})
            item["value"] = item["price"] * item["qty"]
        self.parent.load_current_invoice()
        self.parent.update_cart_display()
        audit(self.parent, "CUSTOMER_PRICING_SELECTED", customer["id"] if customer else "", f"Type={ctype}; Customer={customer['name'] if customer else 'None'}")
        messagebox.showinfo("Pricing Applied", f"Current invoice is now using: {ctype}", parent=self)
        self.destroy()

    def clear_sale(self):
        inv = self.parent.current_invoice()
        inv["customer_type"] = "Retail"; inv["customer_id"] = None; inv["customer_name"] = "Cash Sale"; inv["customer_num"] = "CASH"
        for item in inv.get("cart", []):
            item["price"] = item.get("base_price", item.get("price", 0)); item["value"] = item["price"] * item["qty"]
        self.parent.load_current_invoice(); self.parent.update_cart_display(); self.destroy()

    def refresh_customers(self):
        if not hasattr(self, "customer_tree"): return
        c = connect(); rows = c.execute("SELECT c.id,c.name,COALESCE(c.customer_type,'Retail'),COALESCE(w.name,''),COALESCE(c.phone,'') FROM customers c LEFT JOIN wholesale_price_lists w ON w.id=c.price_list_id WHERE c.active=1 ORDER BY c.name").fetchall(); c.close()
        self.customer_tree.delete(*self.customer_tree.get_children())
        for r in rows: self.customer_tree.insert("", "end", iid=str(r[0]), values=r)

    def edit_selected_customer(self):
        s = self.customer_tree.selection()
        if not s: messagebox.showwarning("Customer", "Select a customer first.", parent=self); return
        self.edit_customer(int(s[0]))

    def edit_customer(self, cid=None):
        c = connect(); row = c.execute("SELECT name,phone,address,email,credit_limit,customer_type,price_list_id FROM customers WHERE id=?", (cid,)).fetchone() if cid else None; c.close()
        w = tk.Toplevel(self); w.title("Edit Customer" if cid else "New Customer"); w.geometry("540x430"); w.transient(self); w.grab_set()
        vals = [tk.StringVar(value=str(x or "")) for x in (row or ("","","","","0","Retail",""))]
        fields = ["Name","Phone","Address","Email","Credit Limit"]
        for i, (lab, var) in enumerate(zip(fields, vals[:5])):
            tk.Label(w,text=lab+":",font=("Arial",10,"bold")).grid(row=i,column=0,sticky="w",padx=15,pady=7); tk.Entry(w,textvariable=var,width=38).grid(row=i,column=1,pady=7)
        tk.Label(w,text="Customer Type:",font=("Arial",10,"bold")).grid(row=5,column=0,sticky="w",padx=15,pady=7)
        type_var = tk.StringVar(value=vals[5].get() if vals[5].get() in CUSTOMER_TYPES else "Retail")
        type_combo = ttk.Combobox(w,textvariable=type_var,values=CUSTOMER_TYPES,state="readonly",width=35); type_combo.grid(row=5,column=1,pady=7)
        tk.Label(w,text="Wholesale Price List:",font=("Arial",10,"bold")).grid(row=6,column=0,sticky="w",padx=15,pady=7)
        c=connect(); lists=c.execute("SELECT id,name FROM wholesale_price_lists WHERE active=1 ORDER BY name").fetchall(); c.close()
        list_var=tk.StringVar(); list_combo=ttk.Combobox(w,textvariable=list_var,values=[f"{x[0]} — {x[1]}" for x in lists],state="readonly",width=35); list_combo.grid(row=6,column=1,pady=7)
        if vals[6].get():
            for i,x in enumerate(lists):
                if x[0] == int(vals[6].get()): list_combo.current(i); break
        def save():
            if not vals[0].get().strip(): messagebox.showwarning("Customer","Name is required.",parent=w); return
            try: limit=float(vals[4].get() or 0)
            except ValueError: messagebox.showerror("Customer","Credit limit must be numeric.",parent=w); return
            lid=None
            if list_combo.current()>=0: lid=lists[list_combo.current()][0]
            c=connect()
            try:
                if cid:
                    c.execute("UPDATE customers SET name=?,phone=?,address=?,email=?,credit_limit=?,customer_type=?,price_list_id=? WHERE id=?",(vals[0].get().strip(),vals[1].get(),vals[2].get(),vals[3].get(),limit,type_var.get(),lid,cid)); act="CUSTOMER_PRICING_UPDATED"
                else:
                    cur=c.execute("INSERT INTO customers(name,phone,address,email,credit_limit,customer_type,price_list_id) VALUES(?,?,?,?,?,?,?)",(vals[0].get().strip(),vals[1].get(),vals[2].get(),vals[3].get(),limit,type_var.get(),lid)); cid_new=cur.lastrowid; act="CUSTOMER_PRICING_CREATED"
                c.commit()
            finally: c.close()
            audit(self.parent,act,cid or cid_new,f"Type={type_var.get()}; PriceList={lid or 'None'}")
            w.destroy(); self.refresh_customers(); self.refresh_customer_combo()
        tk.Button(w,text="SAVE CUSTOMER",font=("Arial",11,"bold"),command=save,width=20).grid(row=8,column=0,columnspan=2,pady=16)

    def refresh_lists(self):
        if not hasattr(self,"list_tree"): return
        c=connect(); rows=c.execute("SELECT id,name,description,active FROM wholesale_price_lists ORDER BY name").fetchall(); c.close()
        self.list_tree.delete(*self.list_tree.get_children())
        for r in rows:self.list_tree.insert("","end",iid=str(r[0]),values=(r[0],r[1],r[2],"Yes" if r[3] else "No"))

    def new_price_list(self): self.edit_price_list(None)

    def edit_price_list(self):
        s=self.list_tree.selection(); self.edit_price_list(int(s[0]) if s else None)

    def edit_price_list(self,cid=None):
        c=connect(); row=c.execute("SELECT name,description,active FROM wholesale_price_lists WHERE id=?",(cid,)).fetchone() if cid else None; c.close()
        w=tk.Toplevel(self);w.title("Wholesale Price List");w.geometry("430x260");w.transient(self);w.grab_set()
        name=tk.StringVar(value=row[0] if row else ""); desc=tk.StringVar(value=row[1] if row else ""); active=tk.BooleanVar(value=bool(row[2]) if row else True)
        for i,(lab,var) in enumerate([("Name",name),("Description",desc)]):
            tk.Label(w,text=lab+":",font=("Arial",10,"bold")).grid(row=i,column=0,padx=15,pady=10,sticky="w");tk.Entry(w,textvariable=var,width=30).grid(row=i,column=1,pady=10)
        tk.Checkbutton(w,text="Active",variable=active).grid(row=2,column=1,sticky="w",pady=5)
        def save():
            if not name.get().strip():messagebox.showwarning("Price List","Name is required.",parent=w);return
            c=connect()
            try:
                if cid:c.execute("UPDATE wholesale_price_lists SET name=?,description=?,active=? WHERE id=?",(name.get().strip(),desc.get(),int(active.get()),cid));pid=cid
                else:pid=c.execute("INSERT INTO wholesale_price_lists(name,description,active) VALUES(?,?,?)",(name.get().strip(),desc.get(),int(active.get()))).lastrowid
                c.commit()
            except sqlite3.IntegrityError:messagebox.showerror("Price List","A price list with that name already exists.",parent=w);c.close();return
            c.close();audit(self.parent,"PRICE_LIST_SAVED",pid,name.get().strip());w.destroy();self.refresh_lists()
        tk.Button(w,text="SAVE PRICE LIST",command=save,width=20).grid(row=4,column=0,columnspan=2,pady=16)

    def manage_list_prices(self):
        s=self.list_tree.selection()
        if not s:messagebox.showwarning("Price List","Select a price list first.",parent=self);return
        PriceListItemsWindow(self,int(s[0]))


class PriceListItemsWindow(tk.Toplevel):
    def __init__(self,parent,list_id):
        super().__init__(parent);ensure_schema();self.parent=parent;self.list_id=list_id;self.title("Wholesale Price List Items");self.geometry("820x560");self.transient(parent)
        c=connect();self.list_name=c.execute("SELECT name FROM wholesale_price_lists WHERE id=?",(list_id,)).fetchone();c.close();self.build();self.refresh()
    def build(self):
        tk.Label(self,text=f"WHOLESALE PRICE LIST: {self.list_name[0] if self.list_name else ''}",font=("Arial",16,"bold")).pack(anchor="w",padx=12,pady=10)
        bar=tk.Frame(self);bar.pack(fill="x",padx=12,pady=5)
        tk.Label(bar,text="Barcode:").pack(side="left");self.code=tk.Entry(bar,width=20);self.code.pack(side="left",padx=5)
        tk.Label(bar,text="Min Qty:").pack(side="left");self.qty=tk.Entry(bar,width=10);self.qty.insert(0,"1");self.qty.pack(side="left",padx=5)
        tk.Label(bar,text="Price (VAT incl.):").pack(side="left");self.price=tk.Entry(bar,width=12);self.price.pack(side="left",padx=5)
        tk.Button(bar,text="Save / Update",command=self.save).pack(side="left",padx=8)
        cols=("barcode","description","qty","price");self.tree=ttk.Treeview(self,columns=cols,show="headings")
        for col,txt,w in [("barcode","Barcode",180),("description","Description",330),("qty","Min Qty",100),("price","Unit Price",130)]:self.tree.heading(col,text=txt);self.tree.column(col,width=w)
        self.tree.pack(fill="both",expand=True,padx=12,pady=8);self.tree.bind("<<TreeviewSelect>>",self.select)
        tk.Button(self,text="Delete Selected",command=self.delete).pack(anchor="w",padx=12,pady=(0,10))
    def refresh(self):
        c=connect();rows=c.execute("SELECT i.id,i.barcode,COALESCE(p.description,''),i.min_qty,i.unit_price FROM wholesale_price_list_items i LEFT JOIN products p ON p.barcode=i.barcode WHERE i.price_list_id=? ORDER BY i.barcode,i.min_qty",(self.list_id,)).fetchall();c.close();self.tree.delete(*self.tree.get_children())
        for r in rows:self.tree.insert("","end",iid=str(r[0]),values=(r[1],r[2],f"{r[3]:g}",f"R {r[4]:.2f}"))
    def select(self,_=None):
        s=self.tree.selection()
        if not s:return
        r=self.tree.item(s[0],"values");self.code.delete(0,"end");self.code.insert(0,r[0]);self.qty.delete(0,"end");self.qty.insert(0,r[2]);self.price.delete(0,"end");self.price.insert(0,r[3].replace("R ",""))
    def save(self):
        try:q=float(self.qty.get());p=float(self.price.get())
        except ValueError:messagebox.showerror("Invalid","Minimum quantity and price must be numeric.",parent=self);return
        code=self.code.get().strip()
        if not code or q<=0 or p<0:messagebox.showerror("Invalid","Enter a valid barcode, quantity and price.",parent=self);return
        c=connect();exists=c.execute("SELECT barcode FROM products WHERE barcode=?",(code,)).fetchone()
        if not exists:c.close();messagebox.showerror("Product","Barcode does not exist in Product Master.",parent=self);return
        c.execute("INSERT INTO wholesale_price_list_items(price_list_id,barcode,min_qty,unit_price) VALUES(?,?,?,?) ON CONFLICT(price_list_id,barcode,min_qty) DO UPDATE SET unit_price=excluded.unit_price",(self.list_id,code,q,p));c.commit();c.close();audit(self.parent.parent,"WHOLESALE_PRICE_SAVED",self.list_id,f"Barcode={code}; MinQty={q:g}; Price=R {p:.2f}");self.refresh()
    def delete(self):
        s=self.tree.selection()
        if not s:return
        if not messagebox.askyesno("Delete","Delete selected wholesale price?",parent=self):return
        c=connect();c.execute("DELETE FROM wholesale_price_list_items WHERE id=?",(s[0],));c.commit();c.close();self.refresh()


def install(app_cls):
    ensure_schema()
    original_init = app_cls.__init__
    def init(self,*args,**kwargs):
        original_init(self,*args,**kwargs)
        # Ensure every existing invoice has the new pricing fields.
        for inv in getattr(self,"invoices",{}).values():
            inv.setdefault("customer_type","Retail");inv.setdefault("customer_id",None)
            inv.setdefault("customer_name","Cash Sale");inv.setdefault("customer_num","CASH")
        self._pricing_window = None
    app_cls.__init__ = init

    # Add the customer/pricing menu without touching app.py.
    old_menu = app_cls.create_menu_bar
    def menu(self):
        old_menu(self)
        mb=self.nametowidget(self.cget("menu"))
        m=tk.Menu(mb,tearoff=0)
        m.add_command(label="👤 Customer & Pricing (Retail / Bulk / Wholesale)",command=lambda:open_customer_pricing(self))
        m.add_separator()
        m.add_command(label="⚙ Customer & Wholesale Setup",command=lambda:open_customer_pricing(self))
        mb.add_cascade(label="Customer / Pricing",menu=m)
        self.bind("<F9>",lambda e:open_customer_pricing(self))
    app_cls.create_menu_bar = menu

    # Persist customer/pricing information on completed sales.
    old_checkout = app_cls.checkout
    def checkout(self, event=None):
        inv = self.current_invoice()
        sale_customer = {
            "customer_id": inv.get("customer_id"),
            "customer_type": inv.get("customer_type", "Retail"),
            "customer_name": inv.get("customer_name", "Cash Sale"),
        }
        result = old_checkout(self, event)
        try:
            c = connect()
            cols = {r[1] for r in c.execute("PRAGMA table_info(sales_history)").fetchall()}
            for name, definition in [("customer_id", "INTEGER"), ("customer_type", "TEXT DEFAULT 'Retail'"), ("customer_name", "TEXT DEFAULT 'Cash Sale'")]:
                if name not in cols:
                    c.execute(f"ALTER TABLE sales_history ADD COLUMN {name} {definition}")
            row = c.execute("SELECT id FROM sales_history ORDER BY id DESC LIMIT 1").fetchone()
            if row:
                c.execute("UPDATE sales_history SET customer_id=?,customer_type=?,customer_name=? WHERE id=?",
                          (sale_customer["customer_id"], sale_customer["customer_type"], sale_customer["customer_name"], row[0]))
                c.commit()
            c.close()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in customer_pricing.py", exc_info=exc)
        return result
    app_cls.checkout = checkout

    # Make new invoices retail by default.
    old_new=app_cls.create_new_invoice
    def new_invoice(self,*args,**kwargs):
        iid=old_new(self,*args,**kwargs)
        inv=self.invoices.get(iid)
        if inv:
            inv.setdefault("customer_type","Retail");inv.setdefault("customer_id",None)
        return iid
    app_cls.create_new_invoice=new_invoice

    # Recalculate pricing as the cashier changes quantity.
    def bind_quantity_refresh(self):
        try:
            self.qty_entry.bind("<KeyRelease>", lambda e: self._apply_current_customer_price(), add="+")
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in customer_pricing.py", exc_info=exc)
    # __init__ is already wrapped above; add the binding after the original UI exists.
    previous_init = app_cls.__init__
    def init_with_quantity_binding(self,*args,**kwargs):
        previous_init(self,*args,**kwargs)
        bind_quantity_refresh(self)
    app_cls.__init__ = init_with_quantity_binding

    # Save/load pricing fields when switching invoices.
    old_switch=app_cls.switch_invoice
    def switch(self,invoice_id):
        if getattr(self,"current_invoice_id",None) in getattr(self,"invoices",{}):
            inv=self.invoices[self.current_invoice_id]
            inv["customer_num"]=self.entry_num.get().strip() or inv.get("customer_num","CASH")
            inv["customer_name"]=self.entry_name.get().strip() or inv.get("customer_name","Cash Sale")
        old_switch(self,invoice_id)
        inv=self.current_invoice();inv.setdefault("customer_type","Retail");inv.setdefault("customer_id",None)
    app_cls.switch_invoice=switch

    old_pop=app_cls.populate_selected_product
    def populate(self,product):
        old_pop(self,product)
        try:self._apply_current_customer_price()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in customer_pricing.py", exc_info=exc)
    app_cls.populate_selected_product=populate

    old_add=app_cls.add_current_item_to_cart
    def add(self,event=None):
        try:self._apply_current_customer_price()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in customer_pricing.py", exc_info=exc)
        result=old_add(self,event)
        try:
            # Store the original retail price so switching pricing modes is reversible.
            inv=self.current_invoice()
            if inv.get("cart"):
                item=inv["cart"][-1]
                item.setdefault("base_price", float(getattr(self,"_current_retail_price",item["price"])))
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in customer_pricing.py", exc_info=exc)
        return result
    app_cls.add_current_item_to_cart=add

    # When quantity changes, refresh the displayed tier price for Bulk/Wholesale.
    old_clear=app_cls.clear_product_input
    def clear(self,*args,**kwargs):
        return old_clear(self,*args,**kwargs)
    app_cls.clear_product_input=clear

    return app_cls


def open_customer_pricing(parent):
    try:
        if getattr(parent,"_pricing_window",None) and parent._pricing_window.winfo_exists():
            parent._pricing_window.lift();parent._pricing_window.focus_force();return
    except Exception as exc:
        _bkpos_logger.warning("Suppressed exception in customer_pricing.py", exc_info=exc)
    parent._pricing_window=CustomerPricingWindow(parent)


def _apply_current_customer_price(self):
    inv=self.current_invoice()
    ctype=inv.get("customer_type","Retail")
    customer=get_customer(inv.get("customer_id")) if inv.get("customer_id") else {"type":ctype,"price_list_id":None}
    if ctype != "Retail" and not customer: customer={"type":ctype,"price_list_id":None}
    item=getattr(self,"selected_product_data",None)
    if not item:return
    try:qty=float(self.qty_entry.get().strip() or 1)
    except Exception:qty=1
    retail=float(item.get("retail_price",item.get("price",0)) or 0)
    item["retail_price"]=retail
    price=get_price_for_sale(item.get("code"),qty,retail,customer if ctype != "Retail" else {"type":"Retail"})
    self._current_retail_price=retail
    self.price_display.config(state="normal")
    self.price_display.delete(0,"end");self.price_display.insert(0,f"{price:.2f}")
    if not self.can("can_edit_price"):self.price_display.config(state="readonly")
    item["price"]=price

# Expose helper as a method after install is called.
_old_install=install
def install(app_cls):
    result=_old_install(app_cls)
    app_cls._apply_current_customer_price=_apply_current_customer_price
    return result

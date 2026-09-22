from core.logger import logger as _bkpos_logger
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

from core.config import DB_PATH
DB_NAME = DB_PATH


def db():
    return sqlite3.connect(DB_NAME)


def ensure_schema():
    c = db()
    cur = c.cursor()
    # Product-master data fields. Legacy stock-control columns are preserved in the database
    # for reporting/compatibility, but this screen never edits stock quantities or reorder controls.
    fields = {
        "category": "TEXT DEFAULT ''",
        "supplier": "TEXT DEFAULT ''",
        "min_stock": "REAL DEFAULT 0",
        "active": "INTEGER DEFAULT 1",
        "unit_of_sale": "TEXT DEFAULT 'EA'",
        "packing": "REAL DEFAULT 1",
        "reorder_qty": "REAL DEFAULT 0",
        "locked": "INTEGER DEFAULT 0",
    }
    cur.execute("PRAGMA table_info(products)")
    cols = {r[1] for r in cur.fetchall()}
    for name, definition in fields.items():
        if name not in cols:
            cur.execute(f"ALTER TABLE products ADD COLUMN {name} {definition}")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_wholesale_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT NOT NULL,
            min_qty REAL NOT NULL,
            unit_price REAL NOT NULL,
            label TEXT DEFAULT 'Wholesale',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(barcode, min_qty)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_wholesale_barcode_qty ON product_wholesale_prices(barcode, min_qty)")

    # Controlled Product Category master list. These are seeded once and can
    # be extended by the user from the Product Master screen.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    default_categories = [
        "BEVERAGES", "GROCERY", "DAIRY", "MEAT", "FROZEN",
        "CLEANING", "HOUSEHOLD", "SNACKS", "CONFECTIONERY", "TOILETRIES"
    ]
    for cat in default_categories:
        cur.execute("INSERT OR IGNORE INTO product_categories(name, active) VALUES(?,1)", (cat,))
    # Preserve any existing category values already stored on products.
    existing_categories = cur.execute(
        "SELECT DISTINCT TRIM(category) FROM products "
        "WHERE TRIM(COALESCE(category,''))<>''"
    ).fetchall()
    for (cat,) in existing_categories:
        cur.execute("INSERT OR IGNORE INTO product_categories(name, active) VALUES(?,1)", (cat,))
    c.commit()
    c.close()


def get_best_price(barcode, qty, retail_price):
    """Return the best quantity price. The highest qualifying min_qty wins."""
    try:
        c = db()
        row = c.execute(
            "SELECT unit_price FROM product_wholesale_prices WHERE barcode=? AND min_qty<=? ORDER BY min_qty DESC LIMIT 1",
            (str(barcode), float(qty)),
        ).fetchone()
        c.close()
        return float(row[0]) if row else float(retail_price)
    except Exception:
        return float(retail_price)



class CategoryManagerWindow(tk.Toplevel):
    """Controlled master list for product categories."""

    def __init__(self, parent, selected_barcode=None):
        super().__init__(parent)
        self.initial_barcode = selected_barcode
        ensure_schema()
        self.parent = parent
        self.title("Product Categories")
        self.geometry("560x500")
        self.minsize(500, 430)
        self.transient(parent)
        self.grab_set()
        self.name_var = tk.StringVar()
        self._build()
        self._load()

    def _build(self):
        top = tk.Frame(self, padx=14, pady=12)
        top.pack(fill="x")
        tk.Label(top, text="PRODUCT CATEGORIES", font=("Arial", 16, "bold")).pack(anchor="w")
        tk.Label(top, text="Select a category in Product Master, or add another category here.",
                 font=("Arial", 10)).pack(anchor="w", pady=(3, 10))

        form = tk.Frame(self, padx=14)
        form.pack(fill="x")
        tk.Label(form, text="New Category:", font=("Arial", 10, "bold")).pack(side="left")
        entry = tk.Entry(form, textvariable=self.name_var, font=("Arial", 11), width=30)
        entry.pack(side="left", padx=8)
        entry.bind("<Return>", lambda _e: self._add())
        tk.Button(form, text="ADD CATEGORY", command=self._add, width=15).pack(side="left")

        frame = tk.Frame(self, padx=14, pady=12)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=("name","status"), show="headings")
        self.tree.heading("name", text="Category")
        self.tree.heading("status", text="Status")
        self.tree.column("name", width=340)
        self.tree.column("status", width=100, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        buttons = tk.Frame(self, padx=14, pady=10)
        buttons.pack(fill="x")
        tk.Button(buttons, text="RENAME SELECTED", command=self._rename, width=18).pack(side="left")
        tk.Button(buttons, text="DEACTIVATE", command=self._deactivate, width=14).pack(side="left", padx=6)
        tk.Button(buttons, text="ACTIVATE", command=self._activate, width=12).pack(side="left")
        tk.Button(buttons, text="CLOSE", command=self.destroy, width=12).pack(side="right")

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        c = db()
        rows = c.execute("SELECT id,name,active FROM product_categories ORDER BY name COLLATE NOCASE").fetchall()
        c.close()
        for rid, name, active in rows:
            self.tree.insert("", "end", iid=str(rid), values=(name, "Active" if active else "Inactive"))

    def _add(self):
        name = " ".join(self.name_var.get().strip().split())
        if not name:
            messagebox.showwarning("Category", "Enter a category name.", parent=self)
            return
        c = db()
        try:
            c.execute("INSERT INTO product_categories(name,active) VALUES(?,1)", (name,))
            c.commit()
            self.name_var.set("")
            self._load()
            if hasattr(self.parent, "_load_category_supplier_lists"):
                self.parent._load_category_supplier_lists()
            messagebox.showinfo("Category Added", f'"{name}" is now available in Product Master.', parent=self)
        except sqlite3.IntegrityError:
            messagebox.showerror("Already Exists", "That category already exists.", parent=self)
        finally:
            c.close()

    def _selected_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _rename(self):
        rid = self._selected_id()
        if not rid:
            messagebox.showwarning("Category", "Select a category first.", parent=self)
            return
        old = self.tree.item(str(rid), "values")[0]
        new = tk.simpledialog.askstring("Rename Category", f"New name for:\n{old}", initialvalue=old, parent=self)
        if new is None:
            return
        new = " ".join(new.strip().split())
        if not new:
            return
        c = db()
        try:
            c.execute("UPDATE product_categories SET name=? WHERE id=?", (new, rid))
            c.execute("UPDATE products SET category=? WHERE TRIM(category)=TRIM(?)", (new, old))
            c.commit()
            self._load()
            if hasattr(self.parent, "_load_category_supplier_lists"):
                self.parent._load_category_supplier_lists()
            messagebox.showinfo("Category Renamed", f'"{old}" was renamed to "{new}".', parent=self)
        except sqlite3.IntegrityError:
            messagebox.showerror("Already Exists", "A category with that name already exists.", parent=self)
        finally:
            c.close()

    def _set_active(self, active):
        rid = self._selected_id()
        if not rid:
            messagebox.showwarning("Category", "Select a category first.", parent=self)
            return
        c = db()
        c.execute("UPDATE product_categories SET active=? WHERE id=?", (int(active), rid))
        c.commit()
        c.close()
        self._load()
        if hasattr(self.parent, "_load_category_supplier_lists"):
            self.parent._load_category_supplier_lists()

    def _deactivate(self):
        self._set_active(False)

    def _activate(self):
        self._set_active(True)


class ProductMasterWindow(tk.Toplevel):
    """Professional product master with retail + quantity/wholesale pricing.

    Stock quantities are deliberately not editable here; GRN/stock controls own SOH.
    """

    def __init__(self, parent, selected_barcode=None):
        super().__init__(parent)
        ensure_schema()
        self.parent = parent
        self.initial_barcode = selected_barcode
        self.title("Product Details & Pricing — Retail / Wholesale")
        self.geometry("1180x760")
        self.minsize(1050, 680)
        self.transient(parent)
        self.search_var = tk.StringVar()
        self.selected = None
        self._build()
        self._load_products()
        if self.initial_barcode:
            self.after(50, lambda: self._select_barcode(self.initial_barcode))

    def _build(self):
        top = tk.Frame(self, padx=12, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="PRODUCT MASTER", font=("Arial", 18, "bold")).pack(side="left")
        tk.Label(top, text="Search:", font=("Arial", 11, "bold")).pack(side="left", padx=(35, 6))
        e = tk.Entry(top, textvariable=self.search_var, font=("Arial", 12), width=35)
        e.pack(side="left")
        e.bind("<KeyRelease>", lambda _e: self._load_products())
        tk.Button(top, text="Refresh", command=self._load_products, width=10).pack(side="left", padx=6)
        # Keep the primary save action in the fixed top toolbar so it is always visible,
        # even when the product details area is resized or the screen is short.
        tk.Button(top, text="SAVE PRODUCT", command=self._save, width=15,
                  font=("Arial", 10, "bold")).pack(side="right", padx=(6, 0))

        # Use a fixed footer row instead of allowing the PanedWindow to consume
        # the entire Toplevel height. This guarantees the Save/Close controls
        # remain visible on smaller screens.
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        body = tk.PanedWindow(self, orient="horizontal", sashrelief="raised")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        left = tk.Frame(body)
        body.add(left, minsize=430)
        cols = ("barcode", "description", "retail")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=25)
        for col, text, width in [("barcode", "Barcode", 145), ("description", "Description", 230), ("retail", "Retail", 90)]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w" if col in ("barcode", "description") else "e")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._select)
        self.tree.bind("<Double-1>", lambda _e: self._edit(self.selected))

        right = tk.Frame(body, padx=16, pady=8)
        body.add(right, minsize=540)
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)
        self.general = tk.Frame(self.notebook, padx=18, pady=15)
        self.pricing = tk.Frame(self.notebook, padx=18, pady=15)
        self.history = tk.Frame(self.notebook, padx=18, pady=15)
        self.notebook.add(self.general, text="General")
        self.notebook.add(self.pricing, text="Pricing")
        self.notebook.add(self.history, text="History")

        self.vars = {k: tk.StringVar() for k in ["barcode","description","category","supplier","retail","cost"]}
        # Category and Supplier are controlled lists. They are intentionally
        # readonly so Product Master uses the existing master data instead of
        # creating spelling variations by free-typing.
        self.category_combo = None
        self.supplier_combo = None
        self._form(self.general, [
            ("Barcode", "barcode"), ("Description", "description"), ("Category", "category"),
            ("Supplier", "supplier"),
        ])
        self._load_category_supplier_lists()
        tk.Button(
            self.general, text="MANAGE CATEGORIES", command=self._open_category_manager,
            width=18, font=("Arial", 9, "bold")
        ).grid(row=2, column=2, padx=(12, 0), pady=7, sticky="w")
        self._form(self.pricing, [("Retail Price (VAT incl.)", "retail"), ("Cost Price", "cost")])
        tk.Label(self.pricing, text="WHOLESALE / BULK PRICE BREAKS", font=("Arial", 13, "bold")).grid(row=5, column=0, columnspan=3, sticky="w", pady=(22, 8))
        self.tiers = ttk.Treeview(self.pricing, columns=("qty","price","label"), show="headings", height=7)
        for col, text, width in [("qty","Minimum Qty",120),("price","Unit Price",120),("label","Label",180)]:
            self.tiers.heading(col,text=text); self.tiers.column(col,width=width,anchor="e" if col != "label" else "w")
        self.tiers.grid(row=6,column=0,columnspan=3,sticky="nsew")
        tk.Button(self.pricing,text="Add / Edit Tier",command=self._tier_dialog,width=16).grid(row=7,column=0,pady=8,sticky="w")
        tk.Button(self.pricing,text="Delete Tier",command=self._delete_tier,width=13).grid(row=7,column=1,pady=8,sticky="w")
        self.pricing.grid_columnconfigure(2, weight=1)

        self.history_text = tk.Text(self.history, height=25, wrap="word", state="disabled")
        self.history_text.pack(fill="both",expand=True)

        bottom = tk.Frame(self, padx=12, pady=8, relief="raised", bd=1)
        bottom.pack(fill="x", side="bottom")
        tk.Label(bottom, text="Product details are saved here. Stock/SOH is controlled by GRN, sales and returns.",
                 font=("Arial", 9), anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(bottom,text="SAVE PRODUCT",font=("Arial",11,"bold"),width=17,command=self._save).pack(side="left", padx=6)
        tk.Button(bottom,text="CLOSE",width=12,command=self.destroy).pack(side="right")

    def _form(self, parent, fields):
        for r,(label,key) in enumerate(fields):
            tk.Label(parent,text=label+":",font=("Arial",10,"bold")).grid(row=r,column=0,sticky="w",pady=7)
            if key == "category":
                self.category_combo = ttk.Combobox(parent, textvariable=self.vars[key], state="readonly", font=("Arial",11), width=36)
                self.category_combo.grid(row=r,column=1,sticky="w",pady=7)
                self.category_combo.bind("<Button-1>", lambda _e: self._load_category_supplier_lists())
                self.category_combo.bind("<FocusIn>", lambda _e: self._load_category_supplier_lists())
            elif key == "supplier":
                self.supplier_combo = ttk.Combobox(parent, textvariable=self.vars[key], state="readonly", font=("Arial",11), width=36)
                self.supplier_combo.grid(row=r,column=1,sticky="w",pady=7)
                self.supplier_combo.bind("<Button-1>", lambda _e: self._load_category_supplier_lists())
                self.supplier_combo.bind("<FocusIn>", lambda _e: self._load_category_supplier_lists())
            else:
                tk.Entry(parent,textvariable=self.vars[key],font=("Arial",11),width=38).grid(row=r,column=1,sticky="w",pady=7)

    def _open_category_manager(self):
        CategoryManagerWindow(self)

    def _load_category_supplier_lists(self, _event=None):
        """Refresh the controlled Category and Supplier dropdown lists."""
        try:
            c = db()
            categories = [r[0] for r in c.execute(
                "SELECT name FROM product_categories WHERE active=1 ORDER BY name COLLATE NOCASE"
            ).fetchall()]
            # Suppliers are maintained in the existing Supplier accounts.
            # Also include supplier names already stored against products so
            # existing product data remains selectable even if an old supplier
            # account was archived/renamed.
            supplier_rows = c.execute(
                "SELECT DISTINCT TRIM(name) FROM accounts WHERE type='Supplier' AND TRIM(COALESCE(name,''))<>'' ORDER BY TRIM(name) COLLATE NOCASE"
            ).fetchall()
            product_supplier_rows = c.execute(
                "SELECT DISTINCT TRIM(supplier) FROM products WHERE TRIM(COALESCE(supplier,''))<>'' ORDER BY TRIM(supplier) COLLATE NOCASE"
            ).fetchall()
            c.close()
            suppliers = sorted({r[0] for r in supplier_rows + product_supplier_rows if r[0]}, key=str.casefold)
            # Blank is deliberately available for products with no category or supplier.
            categories = [""] + categories
            suppliers = [""] + suppliers
            if self.category_combo is not None:
                self.category_combo["values"] = categories
            if self.supplier_combo is not None:
                self.supplier_combo["values"] = suppliers
        except Exception:
            # Do not prevent Product Master from opening if an optional legacy
            # supplier table/data source is temporarily unavailable.
            if self.category_combo is not None:
                self.category_combo["values"] = [""]
            if self.supplier_combo is not None:
                self.supplier_combo["values"] = [""]

    def _load_products(self):
        q=self.search_var.get().strip()
        c=db(); rows=c.execute("SELECT barcode,description,selling_price FROM products WHERE barcode LIKE ? OR description LIKE ? ORDER BY description LIMIT 500",(f"%{q}%",f"%{q}%")).fetchall(); c.close()
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("","end",values=(r[0],r[1],f"R {float(r[2] or 0):.2f}"),iid=str(r[0]))

    def _select_barcode(self, code):
        if not code: return
        self.search_var.set(code)
        self._load_products()
        if self.tree.exists(str(code)):
            self.tree.selection_set(str(code))
            self.tree.focus(str(code))
            self._select()

    def _select(self,_e=None):
        sel=self.tree.selection()
        if not sel:return
        code=self.tree.item(sel[0],"values")[0]
        c=db(); row=c.execute("SELECT barcode,description,selling_price,cost_price,category,supplier FROM products WHERE barcode=?",(code,)).fetchone(); c.close()
        if row:self._show(row)

    def _show(self,row):
        self.selected=row[0]
        keys=["barcode","description","retail","cost","category","supplier"]
        for k,v in zip(keys,row):
            if k == "active":
                continue
            if k in self.vars:
                self.vars[k].set("" if v is None else str(v))
        self._load_tiers(); self._load_history()

    def _load_tiers(self):
        self.tiers.delete(*self.tiers.get_children())
        if not self.selected:return
        c=db(); rows=c.execute("SELECT id,min_qty,unit_price,label FROM product_wholesale_prices WHERE barcode=? ORDER BY min_qty",(self.selected,)).fetchall(); c.close()
        for r in rows:self.tiers.insert("","end",iid=str(r[0]),values=(f"{r[1]:g}",f"R {r[2]:.2f}",r[3]))

    def _tier_dialog(self):
        if not self.selected:
            messagebox.showinfo("Product", "Select or save a product first.", parent=self); return
        win=tk.Toplevel(self); win.title("Wholesale Price Break"); win.geometry("360x250"); win.transient(self); win.grab_set()
        vals=[tk.StringVar(),tk.StringVar(),tk.StringVar(value="Wholesale / Bulk")]
        for i,(lab,var) in enumerate(zip(["Minimum Quantity","Unit Price","Label"],vals)):
            tk.Label(win,text=lab+":",font=("Arial",10,"bold")).pack(anchor="w",padx=18,pady=(12,2)); tk.Entry(win,textvariable=var,font=("Arial",12),width=25).pack(padx=18)
        def save():
            try:q=float(vals[0].get()); p=float(vals[1].get())
            except ValueError:messagebox.showerror("Invalid","Enter numeric quantity and price.",parent=win);return
            if q<=0 or p<0:messagebox.showerror("Invalid","Quantity must be above zero and price cannot be negative.",parent=win);return
            c=db(); c.execute("INSERT INTO product_wholesale_prices(barcode,min_qty,unit_price,label) VALUES(?,?,?,?) ON CONFLICT(barcode,min_qty) DO UPDATE SET unit_price=excluded.unit_price,label=excluded.label",(self.selected,q,p,vals[2].get().strip() or "Wholesale")); c.commit();c.close(); win.destroy(); self._load_tiers()
        tk.Button(win,text="Save Tier",command=save,width=14).pack(pady=16)

    def _delete_tier(self):
        sel=self.tiers.selection()
        if not sel:return
        c=db(); c.execute("DELETE FROM product_wholesale_prices WHERE id=?",(sel[0],)); c.commit();c.close(); self._load_tiers()

    def _edit(self,code):
        if code:
            self.search_var.set(code); self._load_products(); self.tree.selection_set(code); self._select()
        else:
            messagebox.showinfo("Product Details & Pricing","New products are added only through Product Management. Select an existing product to maintain pricing and wholesale tiers.",parent=self)

    def _save(self):
        # Re-check the live database schema immediately before saving. This is
        # important when an older POS database is being upgraded in-place.
        # Product Master must be able to save even if the database was created
        # before the newer product fields existed.
        ensure_schema()
        if not self.selected:
            messagebox.showinfo("Product Master","New products are added only through Product Management. Select an existing product first.",parent=self); return
        code=self.vars["barcode"].get().strip(); desc=self.vars["description"].get().strip()
        if not code or not desc:messagebox.showerror("Missing","Barcode and description are required.",parent=self);return
        try:
            retail=float(self.vars["retail"].get() or 0); cost=float(self.vars["cost"].get() or 0)
        except ValueError:messagebox.showerror("Invalid","Retail and cost prices must be numeric.",parent=self);return
        c=db()
        try:
            # Verify the columns on THIS live connection as well.
            cols={r[1] for r in c.execute("PRAGMA table_info(products)").fetchall()}
            required={
                "category":"TEXT DEFAULT ''",
                "supplier":"TEXT DEFAULT ''",
                "unit_of_sale":"TEXT DEFAULT 'EA'",
                "packing":"REAL DEFAULT 1",
            }
            for name,definition in required.items():
                if name not in cols:
                    c.execute(f"ALTER TABLE products ADD COLUMN {name} {definition}")
            exists=c.execute("SELECT barcode FROM products WHERE barcode=?",(code,)).fetchone()
            if exists:
                # Product Master never changes SOH. GRN, sales and returns own stock.
                c.execute("UPDATE products SET description=?,selling_price=?,cost_price=?,category=?,supplier=? WHERE barcode=?",
                           (desc,retail,cost,self.vars["category"].get(),self.vars["supplier"].get(),code))
                action="PRODUCT_UPDATED"
            else:
                # New products always start at zero SOH. Receive stock through GRN.
                c.execute("INSERT INTO products(barcode,description,selling_price,cost_price,soh,category,supplier,active,unit_of_sale,packing) VALUES(?,?,?,?,?,?,?,?,?,?)",
                           (code,desc,retail,cost,0,self.vars["category"].get(),self.vars["supplier"].get(),1,1,"EA",1))
                action="PRODUCT_CREATED"
            c.execute("CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,username TEXT,role TEXT,action TEXT,entity_type TEXT,entity_id TEXT,details TEXT,branch_id INTEGER DEFAULT 1)")
            user=getattr(self.parent,"cashier_username","Unknown")
            role=getattr(self.parent,"cashier_role","")
            branch=getattr(self.parent,"current_branch_id",1)
            c.execute("INSERT INTO audit_log(event_time,username,role,action,entity_type,entity_id,details,branch_id,event_type) VALUES(datetime('now','localtime'),?,?,?,?,?,?,?,?)",(user,role,action,"product",code,f"{desc} | Retail R {retail:.2f} | Cost R {cost:.2f}",branch,action))
            c.commit()
            self.selected=code; self._load_products(); self.tree.selection_set(code); self._select(); messagebox.showinfo("Saved","Product saved successfully.",parent=self)
        except Exception as e:
            c.rollback(); messagebox.showerror("Save Error",str(e),parent=self)
        finally:c.close()

    def _load_history(self):
        self.history_text.config(state="normal"); self.history_text.delete("1.0","end")
        if not self.selected:self.history_text.insert("end","Select a product to view history."); self.history_text.config(state="disabled"); return
        c=db();
        rows=c.execute("SELECT timestamp,username,action,details FROM audit_log WHERE entity_type='product' AND entity_id=? ORDER BY id DESC LIMIT 100",(self.selected,)).fetchall()
        moves=c.execute("SELECT timestamp,movement_type,qty,qty_before,qty_after,reference,reason,cashier FROM stock_movements WHERE barcode=? ORDER BY id DESC LIMIT 100",(self.selected,)).fetchall() if c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stock_movements'").fetchone() else []
        c.close()
        self.history_text.insert("end","AUDIT / PRODUCT CHANGES\n"+"="*70+"\n")
        for r in rows:self.history_text.insert("end",f"{r[0]} | {r[1] or ''} | {r[2]} | {r[3] or ''}\n")
        self.history_text.insert("end","\nSTOCK MOVEMENTS\n"+"="*70+"\n")
        for r in moves:self.history_text.insert("end",f"{r[0]} | {r[1]} | Qty {r[2]:g} | {r[3]:g} -> {r[4]:g} | {r[5] or ''} | {r[6] or ''} | {r[7] or ''}\n")
        self.history_text.config(state="disabled")


def install(app_cls):
    ensure_schema()
    from tkinter import Menu
    original_menu = app_cls.create_menu_bar
    def menu_with_product_master(self):
        original_menu(self)
        menu = self.nametowidget(self.cget("menu"))
        # Add to the existing Management menu if present; otherwise create a small Product menu.
        target = None
        try:
            end = menu.index("end")
            for i in range(end + 1):
                if menu.type(i) == "cascade" and menu.entrycget(i, "label") == "Management":
                    target = menu.nametowidget(menu.entrycget(i, "menu")); break
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in product_master_wholesale.py", exc_info=exc)
        # Product Master / Pricing is provided once by the organized Stock menu.
        # Do not add a second Management/Products entry for the same work.
    app_cls.create_menu_bar = menu_with_product_master

    # Automatic quantity-break pricing. Manual price edits by authorized users are respected.
    original_add = app_cls.add_current_item_to_cart
    def add_with_wholesale(self, event=None):
        try:
            item=getattr(self,"selected_product_data",None)
            if item:
                qty=float(self.qty_entry.get().strip() or 1)
                base=float(item.get("price",0) or 0)
                displayed=float(self.price_display.get().strip() or base)
                tier=get_best_price(item.get("code"),qty,base)
                if abs(displayed-base) < 0.000001 or not self.can("can_edit_price"):
                    self.price_display.config(state="normal")
                    self.price_display.delete(0,"end"); self.price_display.insert(0,f"{tier:.2f}")
                    if not self.can("can_edit_price"): self.price_display.config(state="readonly")
                    item["price"]=tier
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in product_master_wholesale.py", exc_info=exc)
        return original_add(self,event)
    app_cls.add_current_item_to_cart = add_with_wholesale
    return app_cls

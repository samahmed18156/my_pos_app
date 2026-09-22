from core.logger import logger as _bkpos_logger
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from core.config import DB_PATH
from core.document_numbers import next_document_number
DB_NAME = DB_PATH

def conn():
    return sqlite3.connect(DB_NAME)

class ProfessionalGRNWindow(tk.Toplevel):
    """Professional GRN workflow. Receives stock for existing products only; never creates products."""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Goods Received Note | Stock Receiving")
        self.geometry("1320x820")
        self.minsize(1120, 720)
        self.configure(bg="#eef2f7")
        self.transient(parent)
        self.grab_set()
        self.rows = []
        self.edit_index = None
        self._build_style()
        self.build()
        self._new_grn()

    def _build_style(self):
        s = ttk.Style(self)
        try: s.theme_use("clam")
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in professional_grn.py", exc_info=exc)
        s.configure("GRN.Treeview", rowheight=32, font=("Arial", 10))
        s.configure("GRN.Treeview.Heading", font=("Arial", 10, "bold"))
        s.configure("GRN.TCombobox", padding=5)

    def build(self):
        header = tk.Frame(self, bg="#1f4e78", height=72)
        header.pack(fill="x")
        tk.Label(header, text="GOODS RECEIVED NOTE", bg="#1f4e78", fg="white",
                 font=("Arial", 20, "bold")).pack(side="left", padx=20, pady=(12, 0))
        tk.Label(header, text="STOCK RECEIVING • EXISTING PRODUCTS ONLY", bg="#1f4e78", fg="#dbeafe",
                 font=("Arial", 9, "bold")).pack(side="left", padx=12, pady=(20, 0))
        self.status = tk.Label(header, text="NEW GRN", bg="#1f4e78", fg="white", font=("Arial", 10, "bold"))
        self.status.pack(side="right", padx=20, pady=20)

        top = tk.Frame(self, bg="white", padx=16, pady=12)
        top.pack(fill="x", padx=16, pady=12)
        for c in range(4): top.grid_columnconfigure(c, weight=1)
        self.fields = {}
        specs = [("GRN Number", "grn_no", "readonly"), ("Supplier Account", "account", "readonly"),
                 ("Supplier Name", "supplier", "readonly"), ("Supplier Invoice", "invoice", "normal"),
                 ("Reference / Delivery Note", "ref", "normal"), ("VAT Mode", "vat", "combo"),
                 ("Received Date", "date", "normal"), ("Payment Terms", "terms", "readonly")]
        for i,(lab,key,kind) in enumerate(specs):
            r,c = divmod(i,4)
            tk.Label(top,text=lab,bg="white",fg="#374151",font=("Arial",9,"bold")).grid(row=r*2,column=c,sticky="w",padx=8,pady=(2,2))
            if kind == "combo":
                e=ttk.Combobox(top, values=["Inclusive","Exclusive"], state="readonly", style="GRN.TCombobox", width=22)
                e.set("Inclusive")
            else:
                e=tk.Entry(top,font=("Arial",11),relief="solid",bd=1)
                if kind=="readonly": e.configure(state="readonly",readonlybackground="#f3f4f6")
            e.grid(row=r*2+1,column=c,sticky="ew",padx=8,pady=(0,8))
            self.fields[key]=e
        self.fields["account"].bind("<F3>", self.open_supplier_lookup)
        self.fields["supplier"].bind("<F3>", self.open_supplier_lookup)
        self.fields["invoice"].bind("<Return>", lambda e:self.code.focus_set())
        self.fields["vat"].bind("<<ComboboxSelected>>", lambda e:self.update_total())
        tk.Label(top,text="F3 Supplier Lookup",bg="white",fg="#2563eb",font=("Arial",8,"bold")).grid(row=1,column=1,sticky="e",padx=10)

        entrybox=tk.LabelFrame(self,text="  RECEIVE STOCK ITEM  ",bg="#eef2f7",fg="#1f4e78",font=("Arial",10,"bold"),padx=10,pady=8)
        entrybox.pack(fill="x",padx=16)
        labels=[("Barcode / Product","code",16),("Quantity","qty",10),("Unit Cost","cost",12)]
        for i,(lab,key,wid) in enumerate(labels):
            tk.Label(entrybox,text=lab,bg="#eef2f7",font=("Arial",9,"bold")).grid(row=0,column=i*2,sticky="w",padx=6)
            e=tk.Entry(entrybox,font=("Arial",12),width=wid)
            e.grid(row=1,column=i*2,padx=6,pady=4)
            self.__dict__[key]=e
        self.code.bind("<F3>",self.open_product_lookup)
        self.code.bind("<Return>",lambda e:self._lookup_barcode())
        self.qty.bind("<Return>",lambda e:self.cost.focus_set())
        self.cost.bind("<Return>",lambda e:self.add_or_update())
        tk.Button(entrybox,text="F3 PRODUCT LOOKUP",bg="#2563eb",fg="white",font=("Arial",10,"bold"),bd=0,padx=12,command=self.open_product_lookup).grid(row=1,column=6,padx=6)
        self.item_action=tk.Button(entrybox,text="ADD ITEM",bg="#16803c",fg="white",font=("Arial",10,"bold"),bd=0,padx=18,command=self.add_or_update)
        self.item_action.grid(row=1,column=7,padx=6)
        tk.Button(entrybox,text="CLEAR FIELDS",bg="#64748b",fg="white",font=("Arial",10,"bold"),bd=0,padx=12,command=self.clear_item_fields).grid(row=1,column=8,padx=6)
        self.stock_hint=tk.Label(entrybox,text="Select an existing product • GRN increases SOH when posted",bg="#eef2f7",fg="#64748b",font=("Arial",8,"bold"))
        self.stock_hint.grid(row=2,column=0,columnspan=9,sticky="w",padx=6,pady=(2,0))

        tablebox=tk.Frame(self,bg="white",padx=10,pady=10)
        tablebox.pack(fill="both",expand=True,padx=16,pady=12)
        cols=("code","desc","soh","qty","after","cost","value")
        self.tree=ttk.Treeview(tablebox,columns=cols,show="headings",style="GRN.Treeview",selectmode="browse")
        heads=[("code","Barcode",150), ("desc","Description",330), ("soh","Current SOH",95), ("qty","Qty Received",105), ("after","SOH After",95), ("cost","Unit Cost",110), ("value","Line Value",125)]
        for c,h,w in heads:
            self.tree.heading(c,text=h); self.tree.column(c,width=w,anchor="e" if c in ("soh","qty","after","cost","value") else "w")
        vs=ttk.Scrollbar(tablebox,orient="vertical",command=self.tree.yview); self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left",fill="both",expand=True); vs.pack(side="right",fill="y")
        self.tree.bind("<<TreeviewSelect>>",self.select_item)
        self.tree.bind("<Double-1>",self.edit_selected)
        self.tree.bind("<Delete>",self.remove_selected)

        footer=tk.Frame(self,bg="#eef2f7")
        footer.pack(fill="x",padx=16,pady=(0,14))
        left=tk.Frame(footer,bg="#eef2f7"); left.pack(side="left")
        for text,cmd,bg in [("EDIT SELECTED",self.edit_selected,"#2563eb"),("REMOVE SELECTED",self.remove_selected,"#dc2626"),("NEW GRN",self._new_grn,"#64748b")]:
            tk.Button(left,text=text,font=("Arial",9,"bold"),bg=bg,fg="white",bd=0,padx=12,pady=8,command=cmd).pack(side="left",padx=(0,6))
        totals=tk.Frame(footer,bg="white",padx=18,pady=9); totals.pack(side="right")
        self.total=tk.Label(totals,text="SUBTOTAL  R 0.00     VAT  R 0.00     TOTAL  R 0.00",bg="white",fg="#111827",font=("Arial",13,"bold"))
        self.total.pack()
        actions=tk.Frame(self,bg="#dbe4ee",pady=10); actions.pack(fill="x",side="bottom")
        tk.Button(actions,text="CREDIT NOTE",font=("Arial",11,"bold"),bg="#b45309",fg="white",bd=0,padx=18,pady=9,command=self.open_credit_note).pack(side="right",padx=8)
        tk.Button(actions,text="POST GRN  (Ctrl+Enter)",font=("Arial",11,"bold"),bg="#16803c",fg="white",bd=0,padx=18,pady=9,command=self.post).pack(side="right",padx=8)
        tk.Button(actions,text="CLEAR / RESET",font=("Arial",10,"bold"),bg="#64748b",fg="white",bd=0,padx=14,pady=9,command=self._new_grn).pack(side="right",padx=4)
        tk.Label(actions,text="F3 Lookup  •  ↑/↓ Select  •  Enter Choose/Add  •  Delete Remove  •  CREDIT NOTE = Supplier Stock Return",bg="#dbe4ee",fg="#475569",font=("Arial",9,"bold")).pack(side="left",padx=16)
        self.bind("<Control-Return>",lambda e:self.post())
        self.bind("<Escape>",lambda e:self._close())

    def _next_grn_no(self):
        c=conn()
        try:
            return next_document_number(c, "grn", "GRN")
        finally:c.close()

    def _new_grn(self):
        self.rows=[]; self.edit_index=None
        for key in ("account","supplier","invoice","ref","terms"):
            self._set_entry(self.fields[key],"")
        self._set_entry(self.fields["grn_no"],self._next_grn_no())
        self._set_entry(self.fields["date"],datetime.now().strftime("%d %b %Y"))
        self.fields["vat"].set("Inclusive")
        self.clear_item_fields(); self.refresh_tree(); self.update_total()
        self.status.config(text="NEW GRN")
        self.code.focus_set()

    def _set_entry(self,e,v):
        e.configure(state="normal"); e.delete(0,"end"); e.insert(0,v or "")
        if e in (self.fields["account"],self.fields["supplier"],self.fields["grn_no"],self.fields["terms"]): e.configure(state="readonly")

    def _lookup_barcode(self):
        code=self.code.get().strip()
        if not code:return
        c=conn(); row=c.execute("SELECT description,soh,cost_price FROM products WHERE barcode=?",(code,)).fetchone(); c.close()
        if row:
            self.cost.delete(0,"end"); self.cost.insert(0,f"{float(row[2] or 0):.2f}")
            self.qty.focus_set(); self.qty.selection_range(0,"end")
        else: self.open_product_lookup()

    def clear_item_fields(self):
        self.code.delete(0,"end"); self.qty.delete(0,"end"); self.qty.insert(0,"1"); self.cost.delete(0,"end"); self.edit_index=None; self.item_action.config(text="ADD ITEM"); self.code.focus_set()

    def add_or_update(self):
        code=self.code.get().strip()
        try:q=float(self.qty.get()); cost=float(self.cost.get())
        except Exception: messagebox.showerror("Invalid Item","Enter a valid product, quantity and unit cost.",parent=self); return
        if not code or q<=0 or cost<0: messagebox.showwarning("Invalid Item","Quantity must be greater than zero and cost cannot be negative.",parent=self); return
        c=conn(); row=c.execute("SELECT description,COALESCE(soh,0) FROM products WHERE barcode=? AND COALESCE(active,1)=1",(code,)).fetchone(); c.close()
        if not row: messagebox.showerror("Product Not Found","This barcode is not in Product Management. Create the product first, then receive it through GRN.",parent=self); return
        item=(code,row[0],float(row[1] or 0),q,cost,q*cost)
        if self.edit_index is None: self.rows.append(item)
        else: self.rows[self.edit_index]=item
        self.refresh_tree(); self.clear_item_fields(); self.update_total()

    def refresh_tree(self):
        for x in self.tree.get_children():self.tree.delete(x)
        for i,(code,desc,soh,q,cost,value) in enumerate(self.rows):
            self.tree.insert("","end",iid=str(i),values=(code,desc,f"{soh:g}",f"{q:g}",f"{soh+q:g}",f"R {cost:,.2f}",f"R {value:,.2f}"))

    def select_item(self,event=None):
        pass

    def edit_selected(self,event=None):
        sel=self.tree.selection()
        if not sel:return "break"
        i=int(sel[0]); code,desc,soh,q,cost,value=self.rows[i]
        self.code.delete(0,"end");self.code.insert(0,code);self.qty.delete(0,"end");self.qty.insert(0,str(q));self.cost.delete(0,"end");self.cost.insert(0,str(cost))
        self.edit_index=i;self.item_action.config(text="UPDATE ITEM");self.qty.focus_set();self.qty.selection_range(0,"end");return "break"

    def remove_selected(self,event=None):
        sel=self.tree.selection()
        if not sel:return "break"
        i=int(sel[0])
        if messagebox.askyesno("Remove Item","Remove the selected item from this GRN?",parent=self):
            self.rows.pop(i);self.refresh_tree();self.update_total()
        return "break"

    def update_total(self):
        gross=sum(x[5] for x in self.rows)
        if self.fields["vat"].get()=="Inclusive": vat=gross*15/115; sub=gross-vat; total=gross
        else: vat=gross*.15; sub=gross; total=gross+vat
        self.total.config(text=f"SUBTOTAL  R {sub:,.2f}     VAT  R {vat:,.2f}     TOTAL  R {total:,.2f}")

    def open_supplier_lookup(self,event=None):
        w=tk.Toplevel(self);w.title("Supplier Lookup — F3");w.geometry("820x560");w.configure(bg="#eef2f7");w.transient(self);w.grab_set()
        tk.Label(w,text="SUPPLIER LOOKUP",font=("Arial",17,"bold"),bg="#1f4e78",fg="white",pady=12).pack(fill="x")
        search=tk.Entry(w,font=("Arial",12));search.pack(fill="x",padx=14,pady=12);search.focus_set()
        tree=ttk.Treeview(w,columns=("account","name","phone","terms"),show="headings",height=18)
        for c,h,wd in [("account","Account",170),("name","Supplier",300),("phone","Phone",150),("terms","Terms",150)]:tree.heading(c,text=h);tree.column(c,width=wd)
        tree.pack(fill="both",expand=True,padx=14)
        def load():
            for x in tree.get_children():tree.delete(x)
            q=search.get().strip();c=conn()
            try:
                rows=c.execute("SELECT supplier_account_no,name,COALESCE(phone,''),COALESCE(payment_terms,'') FROM accounts WHERE type='Supplier' AND (supplier_account_no LIKE ? OR name LIKE ? OR phone LIKE ?) ORDER BY name COLLATE NOCASE",(f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
            except Exception: rows=[]
            finally:c.close()
            for r in rows:tree.insert("","end",values=r)
            if tree.get_children():tree.selection_set(tree.get_children()[0]);tree.focus(tree.get_children()[0])
        def choose(event=None):
            sel=tree.selection()
            if not sel:return "break"
            v=tree.item(sel[0],"values");self._set_entry(self.fields["account"],v[0]);self._set_entry(self.fields["supplier"],v[1]);self._set_entry(self.fields["terms"],v[3]);w.grab_release();w.destroy();self.fields["invoice"].focus_set();return "break"
        def move(delta):
            ids=tree.get_children();
            if not ids:return "break"
            cur=tree.focus();i=ids.index(cur) if cur in ids else 0;i=max(0,min(len(ids)-1,i+delta));tree.selection_set(ids[i]);tree.focus(ids[i]);tree.see(ids[i]);return "break"
        def search_changed(event=None):
            if event is not None and event.keysym in ("Up","Down","Return","Escape"):
                return
            load()

        search.bind("<KeyRelease>", search_changed)
        search.bind("<Down>", lambda e: move(1))
        search.bind("<Up>", lambda e: move(-1))
        search.bind("<Return>", choose)
        tree.bind("<Return>", choose)
        tree.bind("<Double-1>", choose)
        w.bind("<Escape>", lambda e: (w.grab_release(), w.destroy()))
        load()

    def open_product_lookup(self,event=None):
        w=tk.Toplevel(self);w.title("Product Lookup — F3");w.geometry("980x640");w.configure(bg="#eef2f7");w.transient(self);w.grab_set()
        tk.Label(w,text="PRODUCT LOOKUP",font=("Arial",17,"bold"),bg="#1f4e78",fg="white",pady=12).pack(fill="x")
        tk.Label(w,text="Choose an existing product from Product Management. This screen never creates products.",bg="#eef2f7",fg="#475569",font=("Arial",10,"bold"),pady=8).pack(fill="x")
        search=tk.Entry(w,font=("Arial",12));search.pack(fill="x",padx=14,pady=10);search.focus_set()
        tree=ttk.Treeview(w,columns=("barcode","desc","category","supplier","soh","cost","retail"),show="headings",height=20)
        for c,h,wd,a in [("barcode","Barcode",150, "w"),("desc","Description",300,"w"),("category","Category",120,"w"),("supplier","Supplier",150,"w"),("soh","SOH",80,"e"),("cost","Cost",90,"e"),("retail","Retail",90,"e")]:tree.heading(c,text=h);tree.column(c,width=wd,anchor=a)
        tree.pack(fill="both",expand=True,padx=14)
        def load():
            for x in tree.get_children():tree.delete(x)
            q=search.get().strip();c=conn()
            try:
                sql="SELECT barcode,description,COALESCE(category,''),COALESCE(supplier,''),COALESCE(soh,0),COALESCE(cost_price,0),COALESCE(selling_price,0) FROM products WHERE COALESCE(active,1)=1"
                params=[]
                if q: sql += " AND (barcode LIKE ? OR description LIKE ? OR category LIKE ? OR supplier LIKE ?)";params=[f"%{q}%"]*4
                rows=c.execute(sql+" ORDER BY description COLLATE NOCASE",params).fetchall()
            except Exception:rows=[]
            finally:c.close()
            for r in rows:tree.insert("","end",values=(r[0],r[1],r[2],r[3],f"{float(r[4]):g}",f"R {float(r[5]):,.2f}",f"R {float(r[6]):,.2f}"))
            ids=tree.get_children()
            if ids:tree.selection_set(ids[0]);tree.focus(ids[0]);tree.see(ids[0])
        def move(delta):
            ids=tree.get_children();
            if not ids:return "break"
            cur=tree.focus();i=ids.index(cur) if cur in ids else 0;i=max(0,min(len(ids)-1,i+delta));tree.selection_set(ids[i]);tree.focus(ids[i]);tree.see(ids[i]);return "break"
        def choose(event=None):
            sel=tree.selection()
            if not sel:return "break"
            v=tree.item(sel[0],"values");self.code.delete(0,"end");self.code.insert(0,v[0]);self.cost.delete(0,"end");self.cost.insert(0,v[5].replace("R ","").replace(",",""));w.grab_release();w.destroy();self.qty.focus_set();self.qty.selection_range(0,"end");return "break"
        def search_changed(event=None):
            if event is not None and event.keysym in ("Up","Down","Return","Escape"):
                return
            load()

        search.bind("<KeyRelease>", search_changed)
        search.bind("<Down>", lambda e: move(1))
        search.bind("<Up>", lambda e: move(-1))
        search.bind("<Return>", choose)
        tree.bind("<Return>", choose)
        tree.bind("<Double-1>", choose)
        w.bind("<Escape>", lambda e: (w.grab_release(), w.destroy(), self.code.focus_set()))
        load()

    def open_credit_note(self):
        """Open the supplier stock-return credit note workflow from the current GRN.
        It is linked to the selected supplier and uses previously received supplier stock.
        """
        account=self.fields["account"].get().strip()
        supplier=self.fields["supplier"].get().strip()
        if not account or not supplier:
            messagebox.showwarning("Credit Note", "Select an existing supplier with F3 before creating a supplier credit note.", parent=self)
            return
        try:
            from supplier_credits import SupplierCreditsWindow
            w=SupplierCreditsWindow(self, preselect_account=account, preselect_name=supplier)
            self.wait_window(w)
        except Exception as e:
            messagebox.showerror("Credit Note", f"Unable to open Supplier Credit Note.\n\n{e}", parent=self)

    def post(self):
        account=self.fields["account"].get().strip(); supplier=self.fields["supplier"].get().strip()
        if not account or not supplier:
            messagebox.showwarning("GRN","Select an existing supplier with F3 before posting.",parent=self); return
        if not self.rows:
            messagebox.showwarning("GRN","Add at least one stock item before posting.",parent=self); return
        gross=sum(x[5] for x in self.rows)
        if self.fields["vat"].get()=="Inclusive": vat=gross*15/115; sub=gross-vat; total=gross
        else: vat=gross*.15; sub=gross; total=gross+vat
        no=self.fields["grn_no"].get()
        if not messagebox.askyesno("Confirm GRN Posting",f"Post {no}?\n\nItems: {len(self.rows)}\nTotal: R {total:,.2f}\n\nThis will increase stock on hand.",parent=self): return
        c=conn()
        try:
            supplier_id=None
            row=c.execute("SELECT id FROM accounts WHERE type='Supplier' AND supplier_account_no=? LIMIT 1",(account,)).fetchone()
            if row: supplier_id=row[0]
            if not supplier_id:
                row=c.execute("SELECT id FROM accounts WHERE type='Supplier' AND name=? LIMIT 1",(supplier,)).fetchone()
                supplier_id=row[0] if row else None
            if not supplier_id: raise ValueError("Supplier account could not be resolved.")
            from services.grn_service import post_grn
            result=post_grn(c, supplier_id=supplier_id, supplier_account=account, supplier_name=supplier,
                             items=[{"barcode":x[0],"description":x[1],"qty":x[3],"cost":x[4]} for x in self.rows],
                             branch_id=getattr(self.parent,"current_branch_id",1),
                             cashier=getattr(self.parent,"cashier_username","Unknown"),
                             supplier_invoice=self.fields["invoice"].get(), reference=self.fields["ref"].get(),
                             vat_mode=self.fields["vat"].get(), grn_no=no, po_no=getattr(self, 'po_no', None))
            c.commit(); self.status.config(text=f"POSTED {no}")
            messagebox.showinfo("GRN Posted",f"{no} posted successfully.\n\n{len(self.rows)} item(s) received.\nSupplier liability: R {result['total']:,.2f}\nStock on hand updated.",parent=self); self._new_grn()
        except Exception as e:
            c.rollback(); messagebox.showerror("GRN Error",str(e),parent=self)
        finally: c.close()

    def _close(self):
        try:self.grab_release()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in professional_grn.py", exc_info=exc)
        self.destroy()

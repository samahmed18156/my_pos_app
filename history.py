"""BKPOS central document history and reprint centre."""
from __future__ import annotations
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from core.config import DB_PATH

from ui.window_polish import polish_window
BG="#eef2f7"; NAVY="#172033"; WHITE="white"

def db(): return sqlite3.connect(DB_PATH)

def _table_exists(c, name):
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

def _open_selected(parent, kind, doc_id):
    from document_viewer import _open
    if kind in ("SALE", "GRN"):
        _open(kind, doc_id, parent=parent)
        return
    from jasper_reports.report_viewer import open_table_report
    c=db()
    try:
        if kind == "RETURN":
            h=c.execute("SELECT id,timestamp,original_sale_id,total_amount,refund_type,cashier,reason FROM return_history WHERE id=?",(int(doc_id),)).fetchone()
            if not h: raise ValueError("Customer return / credit note could not be found.")
            items=c.execute("SELECT barcode,description,qty,price,value FROM return_items WHERE return_id=? ORDER BY id",(h[0],)).fetchall() if _table_exists(c,"return_items") else []
            rows=[(r[0],r[1],r[2],f"R {float(r[3] or 0):,.2f}",f"R {float(r[4] or 0):,.2f}") for r in items]
            open_table_report("Customer Credit Note / Return",["Barcode","Description","Qty","Price","Value"],rows,
                              summary=[("Document",f"CN-{h[0]:06d}"),("Original Sale",f"INV-{int(h[2]):06d}"),("Refund Type",h[4] or ""),("Cashier",h[5] or ""),("Reason",h[6] or ""),("Total",f"R {float(h[3] or 0):,.2f}")],period=str(h[1] or ""),parent=parent)
        elif kind == "SUPPLIER_CREDIT":
            h=c.execute("SELECT id,credit_no,credit_date,amount,reason,reference,created_by,supplier_id FROM supplier_credits WHERE id=?",(int(doc_id),)).fetchone()
            if not h: raise ValueError("Supplier credit note could not be found.")
            items=c.execute("SELECT grn_id,grn_item_id,qty,cost FROM supplier_credit_items WHERE credit_id=? ORDER BY id",(h[0],)).fetchall() if _table_exists(c,"supplier_credit_items") else []
            rows=[]
            for r in items:
                desc=c.execute("SELECT description,barcode FROM grn_items WHERE id=?",(r[1],)).fetchone() if _table_exists(c,"grn_items") else None
                rows.append((desc[1] if desc else "",desc[0] if desc else "",r[2],f"R {float(r[3] or 0):,.2f}",f"R {float(r[2] or 0)*float(r[3] or 0):,.2f}"))
            open_table_report("Supplier Credit Note",["Barcode","Description","Qty","Cost","Value"],rows,
                              summary=[("Credit Note",h[1]),("Reason",h[4] or ""),("Reference",h[5] or ""),("Created By",h[6] or ""),("Total",f"R {float(h[3] or 0):,.2f}")],period=str(h[2] or ""),parent=parent)
        elif kind == "CUSTOMER_PAYMENT":
            h=c.execute("SELECT id,amount,payment_method,reference,notes,cashier,payment_date,customer_id FROM customer_account_payments WHERE id=?",(int(doc_id),)).fetchone()
            if not h: raise ValueError("Customer receipt could not be found.")
            name=c.execute("SELECT name FROM customers WHERE id=?",(h[7],)).fetchone()
            alloc=c.execute("SELECT invoice_id,amount FROM customer_account_payment_allocations WHERE payment_id=? ORDER BY id",(h[0],)).fetchall() if _table_exists(c,"customer_account_payment_allocations") else []
            rows=[(a[0],f"R {float(a[1] or 0):,.2f}") for a in alloc]
            open_table_report("Customer Receipt",["Invoice ID","Allocated Amount"],rows,
                              summary=[("Receipt",f"RCT-{h[0]:06d}"),("Customer",name[0] if name else ""),("Payment Method",h[2] or ""),("Reference",h[3] or ""),("Cashier",h[5] or ""),("Amount",f"R {float(h[1] or 0):,.2f}")],period=str(h[6] or ""),parent=parent)
        elif kind == "SUPPLIER_PAYMENT":
            h=c.execute("SELECT id,payment_no,payment_date,amount,payment_method,reference,notes,created_by,supplier_name FROM supplier_payments WHERE id=?",(int(doc_id),)).fetchone()
            if not h: raise ValueError("Supplier payment could not be found.")
            alloc=c.execute("SELECT grn_id,amount FROM supplier_payment_allocations WHERE payment_id=? ORDER BY id",(h[0],)).fetchall() if _table_exists(c,"supplier_payment_allocations") else []
            rows=[(a[0],f"R {float(a[1] or 0):,.2f}") for a in alloc]
            open_table_report("Supplier Payment Receipt",["GRN ID","Allocated Amount"],rows,
                              summary=[("Payment",h[1]),("Supplier",h[8] or ""),("Payment Method",h[4] or ""),("Reference",h[5] or ""),("Created By",h[7] or ""),("Amount",f"R {float(h[3] or 0):,.2f}")],period=str(h[2] or ""),parent=parent)
        else:
            raise ValueError(f"Unsupported history document type: {kind}")
    finally:
        c.close()

class HistoryWindow(tk.Toplevel):
    """Centralized archive for finalized documents with JasperViewer reprint."""
    def __init__(self,parent):
        super().__init__(parent); polish_window(self); self.parent=parent; self.title("BKPOS • Document History & Reprint"); self.geometry("1450x800"); self.minsize(1100,650); self.configure(bg=BG); self.transient(parent)
        self._build(); self.refresh(); self.bind("<Escape>",lambda e:self.destroy()); self.bind("<Double-1>",lambda e:self.view_selected())
    def _build(self):
        tk.Label(self,text="DOCUMENT HISTORY & REPRINT CENTRE",font=("Arial",21,"bold"),bg=NAVY,fg=WHITE,pady=14).pack(fill="x")
        tk.Label(self,text="Find any finalized invoice, GRN, credit note, return, customer receipt or supplier payment and re-open the exact original document in JasperViewer.",font=("Arial",10),bg=NAVY,fg="#cbd5e1",pady=0).pack(fill="x",pady=(0,14))
        bar=tk.Frame(self,bg=WHITE); bar.pack(fill="x",padx=15,pady=12)
        tk.Label(bar,text="FROM",bg=WHITE,font=("Arial",9,"bold")).pack(side="left",padx=(10,4)); self.frm=tk.Entry(bar,width=12); self.frm.insert(0,datetime.now().strftime("%Y-%m-%d")); self.frm.pack(side="left",padx=4,pady=8)
        tk.Label(bar,text="TO",bg=WHITE,font=("Arial",9,"bold")).pack(side="left",padx=(10,4)); self.to=tk.Entry(bar,width=12); self.to.insert(0,datetime.now().strftime("%Y-%m-%d")); self.to.pack(side="left",padx=4)
        tk.Label(bar,text="TYPE",bg=WHITE,font=("Arial",9,"bold")).pack(side="left",padx=(16,4)); self.typ=ttk.Combobox(bar,state="readonly",width=24,values=["All","Sales Invoice","GRN","Customer Credit Note / Return","Supplier Credit Note","Customer Receipt","Supplier Payment"]); self.typ.set("All"); self.typ.pack(side="left",padx=4)
        tk.Label(bar,text="SEARCH",bg=WHITE,font=("Arial",9,"bold")).pack(side="left",padx=(16,4)); self.search=tk.Entry(bar,width=32); self.search.pack(side="left",padx=4); self.search.bind("<Return>",lambda e:self.refresh())
        tk.Button(bar,text="SEARCH",command=self.refresh,bg="#2b6cb0",fg=WHITE,font=("Arial",10,"bold"),bd=0,padx=16,pady=8).pack(side="left",padx=8)
        self.count=tk.StringVar(value=""); tk.Label(bar,textvariable=self.count,bg=WHITE,fg=NAVY,font=("Arial",10,"bold")).pack(side="right",padx=12)
        frame=tk.Frame(self,bg=WHITE,bd=1,relief="solid"); frame.pack(fill="both",expand=True,padx=15,pady=(0,12))
        cols=("date","type","number","account","amount","status","id","kind"); self.tree=ttk.Treeview(frame,columns=cols,show="headings",selectmode="browse")
        heads={"date":"DATE","type":"DOCUMENT","number":"DOCUMENT NO.","account":"CUSTOMER / SUPPLIER","amount":"AMOUNT","status":"STATUS","id":"ID","kind":""}; widths={"date":145,"type":190,"number":170,"account":300,"amount":130,"status":120,"id":0,"kind":0}
        for c in cols:self.tree.heading(c,text=heads[c]); self.tree.column(c,width=widths[c],anchor="e" if c=="amount" else "w",stretch=False if c in ("id","kind") else True)
        self.tree.pack(fill="both",expand=True,padx=8,pady=8)
        act=tk.Frame(self,bg=BG); act.pack(fill="x",padx=15,pady=(0,12)); tk.Button(act,text="VIEW / REPRINT IN JASPER VIEWER",command=self.view_selected,bg="#2f855a",fg=WHITE,font=("Arial",11,"bold"),bd=0,padx=20,pady=10).pack(side="left"); tk.Button(act,text="REFRESH",command=self.refresh,bg="#475569",fg=WHITE,font=("Arial",10,"bold"),bd=0,padx=16,pady=10).pack(side="left",padx=8); tk.Button(act,text="CLOSE  ESC",command=self.destroy,bg=NAVY,fg=WHITE,font=("Arial",10,"bold"),bd=0,padx=18,pady=10).pack(side="right")
    def _add(self, rows, date, typ, number, account, amount, status, doc_id, kind):
        rows.append((str(date or ""),typ,str(number or ""),str(account or ""),f"R {float(amount or 0):,.2f}",status,str(doc_id),kind))
    def refresh(self):
        try:
            datetime.strptime(self.frm.get().strip(),"%Y-%m-%d"); datetime.strptime(self.to.get().strip(),"%Y-%m-%d")
            a,b=self.frm.get().strip(),self.to.get().strip(); q=f"%{self.search.get().strip()}%"; wanted=self.typ.get(); c=db(); rows=[]
            if wanted in ("All","Sales Invoice") and _table_exists(c,"sales_history"):
                for r in c.execute("SELECT timestamp,id,total_amount,customer_name,COALESCE(voided,0) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ? AND (CAST(id AS TEXT) LIKE ? OR COALESCE(customer_name,'') LIKE ?) ORDER BY id DESC",(a,b,q,q)).fetchall(): self._add(rows,r[0],"Sales Invoice",f"INV-{r[1]:06d}",r[3] or "Cash Sale",r[2],"VOIDED" if r[4] else "COMPLETED",r[1],"SALE")
            if wanted in ("All","GRN") and _table_exists(c,"grn_headers"):
                for r in c.execute("SELECT created_at,id,grn_no,total,supplier_name FROM grn_headers WHERE date(created_at) BETWEEN ? AND ? AND (COALESCE(grn_no,'') LIKE ? OR COALESCE(supplier_name,'') LIKE ?) ORDER BY id DESC",(a,b,q,q)).fetchall(): self._add(rows,r[0],"GRN",r[2],r[4],r[3],"COMPLETED",r[1],"GRN")
            if wanted in ("All","Customer Credit Note / Return"):
                if _table_exists(c,"return_history"):
                    for r in c.execute("SELECT timestamp,id,total_amount,refund_type,cashier FROM return_history WHERE date(timestamp) BETWEEN ? AND ? AND (CAST(id AS TEXT) LIKE ? OR COALESCE(refund_type,'') LIKE ?) ORDER BY id DESC",(a,b,q,q)).fetchall(): self._add(rows,r[0],"Customer Credit Note / Return",f"CN-{r[1]:06d}",r[3] or "Customer",r[2],"COMPLETED",r[1],"RETURN")
                if _table_exists(c,"credit_notes"):
                    for r in c.execute("SELECT timestamp,id,total_amount,invoice_ref,cashier FROM credit_notes WHERE date(timestamp) BETWEEN ? AND ? AND (CAST(id AS TEXT) LIKE ? OR COALESCE(invoice_ref,'') LIKE ?) ORDER BY id DESC",(a,b,q,q)).fetchall(): self._add(rows,r[0],"Customer Credit Note / Return",f"CN-{r[1]:06d}",r[3] or "Customer",r[2],"COMPLETED",r[1],"CUSTOMER_CREDIT")
            if wanted in ("All","Supplier Credit Note") and _table_exists(c,"supplier_credits"):
                for r in c.execute("SELECT credit_date,id,credit_no,amount,reason FROM supplier_credits WHERE date(credit_date) BETWEEN ? AND ? AND (COALESCE(credit_no,'') LIKE ? OR COALESCE(reason,'') LIKE ?) ORDER BY id DESC",(a,b,q,q)).fetchall(): self._add(rows,r[0],"Supplier Credit Note",r[2],r[4] or "Supplier",r[3],"COMPLETED",r[1],"SUPPLIER_CREDIT")
            if wanted in ("All","Customer Receipt") and _table_exists(c,"customer_account_payments"):
                for r in c.execute("SELECT payment_date,id,amount,payment_method,reference FROM customer_account_payments WHERE date(payment_date) BETWEEN ? AND ? AND (CAST(id AS TEXT) LIKE ? OR COALESCE(reference,'') LIKE ?) ORDER BY id DESC",(a,b,q,q)).fetchall(): self._add(rows,r[0],"Customer Receipt",f"RCT-{r[1]:06d}",r[3] or "Customer",r[2],"COMPLETED",r[1],"CUSTOMER_PAYMENT")
            if wanted in ("All","Supplier Payment") and _table_exists(c,"supplier_payments"):
                for r in c.execute("SELECT payment_date,id,payment_no,amount,supplier_name FROM supplier_payments WHERE date(payment_date) BETWEEN ? AND ? AND (COALESCE(payment_no,'') LIKE ? OR COALESCE(supplier_name,'') LIKE ?) ORDER BY id DESC",(a,b,q,q)).fetchall(): self._add(rows,r[0],"Supplier Payment",r[2],r[4],r[3],"COMPLETED",r[1],"SUPPLIER_PAYMENT")
            c.close(); rows.sort(key=lambda x:x[0],reverse=True); self.tree.delete(*self.tree.get_children());
            for r in rows:self.tree.insert("","end",values=r)
            self.count.set(f"{len(rows)} document(s)")
        except Exception as exc: messagebox.showerror("Document History",str(exc),parent=self)
    def view_selected(self):
        sel=self.tree.selection()
        if not sel:return messagebox.showwarning("Document History","Select a document first.",parent=self)
        v=self.tree.item(sel[0],"values"); kind=v[7]; doc_id=v[6]
        try:
            if kind == "CUSTOMER_CREDIT":
                # Standalone POS credit note has its own schema; render directly.
                c=db(); h=c.execute("SELECT id,timestamp,invoice_ref,barcode,description,qty,price,total_amount,cashier,reason FROM credit_notes WHERE id=?",(int(doc_id),)).fetchone(); c.close()
                if not h: raise ValueError("Customer credit note could not be found.")
                from jasper_reports.report_viewer import open_table_report
                open_table_report("Customer Credit Note",["Barcode","Description","Qty","Price","Value"],[(h[3],h[4],h[5],f"R {float(h[6]):,.2f}",f"R {float(h[7]):,.2f}")],summary=[("Credit Note",f"CN-{h[0]:06d}"),("Invoice Reference",h[2] or ""),("Cashier",h[8] or ""),("Reason",h[9] or ""),("Total",f"R {float(h[7]):,.2f}")],period=str(h[1] or ""),parent=self)
            else:
                _open_selected(self,kind,int(doc_id))
        except Exception as exc: messagebox.showerror("JasperViewer",str(exc),parent=self)

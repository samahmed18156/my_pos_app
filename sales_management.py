"""
Unified Sales / Invoice Management for Family Supermarket POS.

One invoice system for Retail, Bulk and Wholesale. The invoice does not
change its format based on customer type; only the pricing/customer metadata
changes.
"""
from core.logger import logger as _bkpos_logger
from store_settings import get_store_name
import os, sqlite3, tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from core.config import DB_PATH
DB_NAME = DB_PATH


def db():
    return sqlite3.connect(DB_NAME)


def ensure_schema():
    c = db(); cur = c.cursor()
    # Keep one unified sales table; these fields describe the customer/pricing
    # used on the sale without creating separate invoice systems.
    fields = {
        "customer_id": "INTEGER",
        "customer_name": "TEXT DEFAULT 'Cash Sale'",
        "customer_type": "TEXT DEFAULT 'Retail'",
        "pricing_mode": "TEXT DEFAULT 'Retail'",
        "voided": "INTEGER DEFAULT 0",
    }
    cur.execute("PRAGMA table_info(sales_history)")
    cols = {r[1] for r in cur.fetchall()}
    for name, definition in fields.items():
        if name not in cols:
            cur.execute(f"ALTER TABLE sales_history ADD COLUMN {name} {definition}")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_history(timestamp)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales_history(customer_id)")
    c.commit(); c.close()


def money(v):
    return f"R {float(v or 0):,.2f}"


class SaleDetailsWindow(tk.Toplevel):
    def __init__(self, parent, sale_id):
        super().__init__(parent)
        ensure_schema()
        self.parent = parent; self.sale_id = int(sale_id)
        self.title(f"Invoice / Sale #{self.sale_id:03d}")
        self.geometry("980x650"); self.minsize(850, 560)
        self.configure(bg="#eef2f7")
        self.build(); self.load()

    def build(self):
        tk.Label(self, text="INVOICE / SALE DETAILS", font=("Arial",18,"bold"),
                 bg="#2c5282", fg="white", pady=12).pack(fill="x")
        self.info = tk.Label(self, text="", font=("Arial",11,"bold"),
                             bg="#eef2f7", anchor="w", justify="left", padx=15, pady=10)
        self.info.pack(fill="x")
        cols=("barcode","description","qty","price","value")
        self.tree=ttk.Treeview(self,columns=cols,show="headings")
        for c,h,w in [("barcode","Barcode",160),("description","Description",360),
                      ("qty","Qty",80),("price","Unit Price",120),("value","Value",130)]:
            self.tree.heading(c,text=h); self.tree.column(c,width=w)
        self.tree.pack(fill="both",expand=True,padx=15,pady=8)
        bottom=tk.Frame(self,bg="#eef2f7",padx=15,pady=10); bottom.pack(fill="x")
        self.total=tk.Label(bottom,text="",font=("Arial",15,"bold"),bg="#eef2f7")
        self.total.pack(side="left")
        tk.Button(bottom,text="CREDIT NOTE / RETURN  (F12)",font=("Arial",10,"bold"),
                  bg="#dd6b20",fg="white",command=self.open_credit_note).pack(side="right",padx=5)
        tk.Button(bottom,text="EXPORT INVOICE PDF",font=("Arial",10,"bold"),
                  command=self.export_pdf).pack(side="right",padx=5)
        tk.Button(bottom,text="CLOSE",command=self.destroy).pack(side="right",padx=5)
        self.bind("<F12>", lambda e: self.open_credit_note())

    def load(self):
        c=db()
        sale=c.execute("""SELECT id,timestamp,total_amount,total_cost,payment_type,
                          cashier,amount_tendered,change_amount,cash_amount,card_amount,
                          customer_name,customer_type,pricing_mode,voided
                          FROM sales_history WHERE id=?""",(self.sale_id,)).fetchone()
        items=c.execute("""SELECT barcode,description,qty,price,value
                           FROM sale_items WHERE sale_id=? ORDER BY id""",(self.sale_id,)).fetchall()
        c.close()
        if not sale:
            messagebox.showerror("Invoice","Sale not found.",parent=self); self.destroy(); return
        self.sale=sale; self.items=items
        (sid,stamp,total,cost,pay,cashier,tender,change,cash_amt,card_amt,
         cname,ctype,pmode,voided)=sale
        status="VOIDED" if voided else "COMPLETED"
        self.info.config(text=f"Invoice #{sid:03d}   |   {stamp}   |   {status}\n"
                              f"Customer: {cname or 'Cash Sale'}   |   Type: {ctype or 'Retail'}   |   Pricing: {pmode or ctype or 'Retail'}\n"
                              f"Cashier: {cashier or 'Unknown'}   |   Payment: {pay or 'Unknown'}")
        self.tree.delete(*self.tree.get_children())
        for r in items: self.tree.insert("", "end", values=(r[0],r[1],r[2],money(r[3]),money(r[4])))
        vat=float(total or 0)*15/115
        self.total.config(text=f"Subtotal ex VAT: {money(float(total or 0)-vat)}   |   VAT: {money(vat)}   |   TOTAL: {money(total)}")

    def open_credit_note(self):
        """Open the credit-note workspace for THIS displayed invoice."""
        try:
            handler = getattr(self.parent, "open_direct_credit_note", None)
            if callable(handler):
                self.parent.selected_sale_id_for_credit_note = self.sale_id
                handler(self.sale_id)
            else:
                from credit_note import CreditNoteWindow
                CreditNoteWindow(self.parent, sale_id=self.sale_id)
        except Exception as exc:
            messagebox.showerror("Credit Note", f"Could not open Credit Note:\n{exc}", parent=self)

    def export_pdf(self):
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            p=filedialog.asksaveasfilename(defaultextension=".pdf",
                filetypes=[("PDF","*.pdf")],initialfile=f"invoice_{self.sale_id:03d}.pdf")
            if not p: return
            c=canvas.Canvas(p,pagesize=A4); w,h=A4; y=h-45
            c.setFont("Helvetica-Bold",16); c.drawString(40,y,get_store_name()); y-=25
            c.setFont("Helvetica-Bold",13); c.drawString(40,y,f"Invoice #{self.sale_id:03d}"); y-=18
            sale=self.sale
            c.setFont("Helvetica",9)
            for line in [f"Date: {sale[1]}",f"Customer: {sale[10] or 'Cash Sale'}",
                         f"Customer Type: {sale[11] or 'Retail'}",f"Pricing: {sale[12] or sale[11] or 'Retail'}",
                         f"Cashier: {sale[5] or 'Unknown'}",f"Payment: {sale[4] or 'Unknown'}"]:
                c.drawString(40,y,line); y-=14
            y-=8; c.setFont("Helvetica-Bold",9)
            c.drawString(40,y,"Barcode"); c.drawString(150,y,"Description"); c.drawString(390,y,"Qty")
            c.drawString(440,y,"Price"); c.drawString(510,y,"Value"); y-=14
            c.setFont("Helvetica",9)
            for barcode,desc,qty,price,value in self.items:
                if y<70: c.showPage(); y=h-50
                c.drawString(40,y,str(barcode)[:18]); c.drawString(150,y,str(desc)[:34])
                c.drawRightString(420,y,f"{float(qty):g}"); c.drawRightString(490,y,f"{float(price):.2f}")
                c.drawRightString(570,y,f"{float(value):.2f}"); y-=14
            total=float(sale[2] or 0); vat=total*15/115
            y-=10; c.setFont("Helvetica-Bold",10)
            c.drawRightString(570,y,f"Subtotal ex VAT: R {total-vat:,.2f}"); y-=16
            c.drawRightString(570,y,f"VAT (included): R {vat:,.2f}"); y-=16
            c.drawRightString(570,y,f"TOTAL: R {total:,.2f}")
            c.save()
            messagebox.showinfo("Invoice",f"Invoice PDF created:\n{p}",parent=self)
        except Exception as e:
            messagebox.showerror("Invoice PDF",str(e),parent=self)


class SalesManagementWindow(tk.Toplevel):
    """Search and manage every completed sale using the same invoice format."""
    def __init__(self,parent):
        super().__init__(parent); ensure_schema()
        self.parent=parent; self.title("Sales & Invoice Management")
        self.geometry("1180x700"); self.minsize(1000,600); self.configure(bg="#eef2f7")
        self.build(); self.refresh()

    def build(self):
        tk.Label(self,text="SALES & INVOICE MANAGEMENT",font=("Arial",19,"bold"),
                 bg="#2c5282",fg="white",pady=12).pack(fill="x")
        bar=tk.Frame(self,bg="#eef2f7",pady=10); bar.pack(fill="x",padx=12)
        tk.Label(bar,text="Search:",bg="#eef2f7",font=("Arial",11,"bold")).pack(side="left")
        self.q=tk.Entry(bar,width=28,font=("Arial",11)); self.q.pack(side="left",padx=6)
        self.q.bind("<Return>",lambda e:self.refresh())
        tk.Label(bar,text="From",bg="#eef2f7").pack(side="left",padx=(15,3))
        self.frm=tk.Entry(bar,width=11); self.frm.insert(0,datetime.now().strftime("%Y-%m-%d")); self.frm.pack(side="left")
        tk.Label(bar,text="To",bg="#eef2f7").pack(side="left",padx=3)
        self.to=tk.Entry(bar,width=11); self.to.insert(0,datetime.now().strftime("%Y-%m-%d")); self.to.pack(side="left")
        tk.Button(bar,text="SEARCH",command=self.refresh).pack(side="left",padx=8)
        tk.Button(bar,text="VIEW INVOICE",font=("Arial",10,"bold"),command=self.view).pack(side="right")
        cols=("id","date","customer","type","pricing","total","payment","cashier","status")
        self.tree=ttk.Treeview(self,columns=cols,show="headings")
        heads={"id":"Invoice #","date":"Date","customer":"Customer","type":"Customer Type",
               "pricing":"Pricing","total":"Total","payment":"Payment","cashier":"Cashier","status":"Status"}
        widths={"id":80,"date":145,"customer":190,"type":100,"pricing":110,"total":110,"payment":105,"cashier":110,"status":90}
        for col in cols:self.tree.heading(col,text=heads[col]);self.tree.column(col,width=widths[col],anchor="center")
        self.tree.pack(fill="both",expand=True,padx=15,pady=8)
        self.tree.bind("<Double-1>",lambda e:self.view())
        self.summary=tk.Label(self,text="",bg="#eef2f7",font=("Arial",12,"bold"),anchor="w")
        self.summary.pack(fill="x",padx=15,pady=(0,10))

    def refresh(self):
        try:
            a,b=self.frm.get().strip(),self.to.get().strip()
            datetime.strptime(a,"%Y-%m-%d");datetime.strptime(b,"%Y-%m-%d")
            q=self.q.get().strip()
            c=db()
            rows=c.execute("""SELECT id,timestamp,COALESCE(customer_name,'Cash Sale'),
                COALESCE(customer_type,'Retail'),COALESCE(pricing_mode,customer_type,'Retail'),
                total_amount,payment_type,cashier,COALESCE(voided,0)
                FROM sales_history
                WHERE date(timestamp) BETWEEN ? AND ?
                AND (?='' OR CAST(id AS TEXT) LIKE ? OR COALESCE(customer_name,'') LIKE ?
                     OR COALESCE(cashier,'') LIKE ?
                     OR EXISTS(SELECT 1 FROM sale_items si WHERE si.sale_id=sales_history.id
                               AND (si.barcode LIKE ? OR si.description LIKE ?)))
                ORDER BY id DESC""",(a,b,q,f"%{q}%",f"%{q}%",f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
            c.close()
            self.tree.delete(*self.tree.get_children())
            gross=0
            for r in rows:
                gross+=float(r[5] or 0)
                self.tree.insert("", "end",values=(r[0],r[1],r[2],r[3],r[4],money(r[5]),r[6],r[7], "VOIDED" if r[8] else "COMPLETED"))
            self.summary.config(text=f"Transactions: {len(rows)}   |   Sales: {money(gross)}")
        except Exception as e:
            messagebox.showerror("Sales Management",str(e),parent=self)

    def view(self):
        sel=self.tree.selection()
        if not sel: messagebox.showwarning("Sales","Select an invoice.",parent=self); return
        SaleDetailsWindow(self,self.tree.item(sel[0],"values")[0])


def install(app_cls):
    ensure_schema()
    old_checkout=getattr(app_cls,"checkout",None)
    if old_checkout and not getattr(app_cls,"_unified_sales_installed",False):
        def checkout_with_customer(self,*args,**kwargs):
            inv=dict(self.current_invoice())
            result=old_checkout(self,*args,**kwargs)
            # The existing checkout already handles payment/stock/receipt.
            # We only enrich the newly created sale record, preserving that
            # single invoice workflow.
            try:
                c=db()
                row=c.execute("SELECT id FROM sales_history ORDER BY id DESC LIMIT 1").fetchone()
                if row:
                    sid=row[0]
                    c.execute("""UPDATE sales_history SET customer_name=?,customer_type=?,
                                 pricing_mode=?,customer_id=? WHERE id=?""",
                              (inv.get("customer_name") or "Cash Sale",
                               inv.get("customer_type") or "Retail",
                               inv.get("customer_type") or "Retail",
                               inv.get("customer_id"),sid))
                    c.commit()
                c.close()
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in sales_management.py", exc_info=exc)
            return result
        app_cls.checkout=checkout_with_customer
        app_cls._unified_sales_installed=True
    app_cls.open_sales_management=lambda self: SalesManagementWindow(self)
    return app_cls

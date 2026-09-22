"""
Professional A4-style lookup and statement windows for Family Supermarket POS.
Designed to complement professional_reports.py without replacing existing data-entry
windows.
"""
from core.logger import logger as _bkpos_logger
from store_settings import get_store_name
import sqlite3, tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from core.config import DB_PATH
DB_NAME=DB_PATH

def db(): return sqlite3.connect(DB_NAME)
def money(v): return f"R {float(v or 0):,.2f}"

class A4Popup(tk.Toplevel):
    def __init__(self,parent,title,subtitle=""):
        super().__init__(parent); self.parent=parent
        self.title(title); self.geometry("1100x820"); self.minsize(900,650)
        self.configure(bg="#d9dee5"); self.transient(parent)
        top=tk.Frame(self,bg="#243447",height=58); top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top,text=title.upper(),font=("Segoe UI",15,"bold"),fg="white",bg="#243447").pack(side="left",padx=18,pady=14)
        tk.Button(top,text="CLOSE",command=self.destroy,font=("Segoe UI",10,"bold")).pack(side="right",padx=10,pady=11)
        outer=tk.Frame(self,bg="#d9dee5"); outer.pack(fill="both",expand=True)
        self.canvas=tk.Canvas(outer,bg="#d9dee5",highlightthickness=0)
        sb=ttk.Scrollbar(outer,orient="vertical",command=self.canvas.yview); sb.pack(side="right",fill="y")
        self.canvas.configure(yscrollcommand=sb.set); self.canvas.pack(side="left",fill="both",expand=True)
        self.page=tk.Frame(self.canvas,bg="white",width=794,height=1123)
        self.win=self.canvas.create_window((20,20),window=self.page,anchor="nw")
        self.canvas.bind("<Configure>",lambda e:self.center(e.width))
        self.page.grid_propagate(False)
        self.header(subtitle)

    def center(self,w):
        self.canvas.coords(self.win,max(20,(w-794)//2),20)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def header(self,subtitle):
        tk.Label(self.page,text=get_store_name(),font=("Georgia",20,"bold"),bg="white",fg="#17202a").pack(pady=(32,2))
        tk.Label(self.page,text=subtitle,font=("Segoe UI",12,"bold"),bg="white",fg="#34495e").pack()
        tk.Frame(self.page,bg="#17202a",height=2,width=690).pack(pady=12)
        tk.Label(self.page,text=f"Generated: {datetime.now():%Y-%m-%d %H:%M}",font=("Segoe UI",8),bg="white",fg="#667085").pack()

    def section(self,title):
        tk.Label(self.page,text=title,font=("Segoe UI",11,"bold"),bg="white",fg="#243447",anchor="w").pack(fill="x",padx=52,pady=(18,6))

    def table(self,headers,rows,widths=None):
        f=tk.Frame(self.page,bg="white"); f.pack(fill="x",padx=52)
        widths=widths or [max(10,min(32,len(str(h))+7)) for h in headers]
        for j,h in enumerate(headers):
            tk.Label(f,text=h,font=("Segoe UI",8,"bold"),bg="#e9eef3",fg="#243447",anchor="w",padx=5,pady=6,width=widths[j]).grid(row=0,column=j,sticky="ew")
        for i,row in enumerate(rows,1):
            bg="#fff" if i%2 else "#f7f9fb"
            for j,v in enumerate(row):
                tk.Label(f,text=str(v),font=("Segoe UI",8),bg=bg,fg="#1f2933",anchor="w",padx=5,pady=5,width=widths[j]).grid(row=i,column=j,sticky="ew")

class PriceLookupWindow(A4Popup):
    def _close_after_selection(self):
        """Close the lookup immediately after a product is chosen."""
        try:
            self.grab_release()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in professional_lookup.py", exc_info=exc)
        try:
            self.destroy()
        except Exception:
            try:
                self.top.destroy()
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in professional_lookup.py", exc_info=exc)


    def __init__(self,parent):
        super().__init__(parent,"Price Lookup","PRODUCT PRICE & STOCK LOOKUP")
        self.section("SEARCH PRODUCT")
        bar=tk.Frame(self.page,bg="white"); bar.pack(fill="x",padx=52,pady=4)
        tk.Label(bar,text="Barcode / Description",bg="white",font=("Segoe UI",9,"bold")).pack(side="left")
        self.q=tk.Entry(bar,font=("Segoe UI",11),width=38); self.q.pack(side="left",padx=10)
        tk.Button(bar,text="SEARCH",command=self.search,font=("Segoe UI",9,"bold")).pack(side="left")
        tk.Button(bar,text="CLEAR",command=self.clear,font=("Segoe UI",9,"bold")).pack(side="left",padx=8)
        self.results=tk.Frame(self.page,bg="white"); self.results.pack(fill="x",padx=52,pady=15)
        self.search(); self.bind("<Return>",lambda e:self.search()); self.q.focus_set()

    def clear(self):
        self.q.delete(0,tk.END); self.search(); self.q.focus_set()

    def search(self):
        for w in self.results.winfo_children(): w.destroy()
        q=self.q.get().strip()
        c=db()
        try:
            rows=c.execute("""SELECT barcode,description,category,supplier,cost_price,selling_price,soh,active
                              FROM products
                              WHERE (?='' OR barcode LIKE ? OR description LIKE ? OR category LIKE ? OR supplier LIKE ?)
                              ORDER BY description LIMIT 100""",
                           (q,f"%{q}%",f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
        except Exception:
            rows=c.execute("""SELECT barcode,description,cost_price,selling_price,soh FROM products
                              WHERE (?='' OR barcode LIKE ? OR description LIKE ?) ORDER BY description LIMIT 100""",
                           (q,f"%{q}%",f"%{q}%")).fetchall()
        c.close()
        headers=["Barcode","Description","Category","Supplier","Cost","Retail","SOH","Status"]
        formatted=[]
        for r in rows:
            if len(r)==8:
                formatted.append((r[0] or "",r[1] or "",r[2] or "",r[3] or "",money(r[4]),money(r[5]),f"{float(r[6] or 0):g}","ACTIVE" if r[7] else "INACTIVE"))
            else:
                formatted.append((r[0] or "",r[1] or "","","",money(r[2]),money(r[3]),f"{float(r[4] or 0):g}",""))
        self.table(headers,formatted,[14,28,16,18,13,13,9,12])


class LookupCenterWindow(A4Popup):
    def __init__(self,parent):
        super().__init__(parent,"Professional Lookup & Statements","BUSINESS LOOKUP CENTRE")
        self.section("AVAILABLE PROFESSIONAL VIEWS")
        options=[
            ("PRODUCT / PRICE LOOKUP","Find barcode, selling price, cost, SOH and product status",self.open_price),
            ("FINANCIAL CONTROL REPORT","A4 financial, stock and reconciliation reporting",self.open_financial),
            ("STOCK RECONCILIATION","Review stock movements and current SOH",self.open_stock),
            ("CASH-UP / RECONCILIATION","Review cashier cash and payment reconciliation",self.open_cash),
            ("VAT / PROFIT / STOCK RECONCILIATION","Reconcile VAT, profit and stock valuation",self.open_tax),
            ("INVOICE LIFECYCLE","Review open, completed and voided invoice status",self.open_invoice),
        ]
        for name,desc,cmd in options:
            f=tk.Frame(self.page,bg="#f7f9fb",bd=1,relief="solid"); f.pack(fill="x",padx=52,pady=5)
            tk.Label(f,text=name,font=("Segoe UI",10,"bold"),bg="#f7f9fb",fg="#243447",anchor="w").pack(fill="x",padx=12,pady=(10,2))
            tk.Label(f,text=desc,font=("Segoe UI",9),bg="#f7f9fb",fg="#52606d",anchor="w").pack(fill="x",padx=12,pady=(0,7))
            tk.Button(f,text="OPEN",command=cmd,font=("Segoe UI",9,"bold")).pack(anchor="e",padx=10,pady=(0,10))
    def open_price(self): PriceLookupWindow(self.parent)
    def open_financial(self):
        try: __import__("professional_reports").ProfessionalReportWindow(self.parent,"financial","Financial Control Report")
        except Exception as e: messagebox.showerror("Report",str(e),parent=self)
    def open_stock(self):
        try: __import__("professional_reports").ProfessionalReportWindow(self.parent,"stock","Stock Reconciliation Report")
        except Exception as e: messagebox.showerror("Report",str(e),parent=self)
    def open_cash(self):
        try: __import__("professional_reports").ProfessionalReportWindow(self.parent,"cashup","Cash-Up & Reconciliation Report")
        except Exception as e: messagebox.showerror("Report",str(e),parent=self)
    def open_invoice(self):
        try: __import__("professional_reports").ProfessionalReportWindow(self.parent,"lifecycle","Invoice Lifecycle Report")
        except Exception as e: messagebox.showerror("Report",str(e),parent=self)
    def open_tax(self):
        try: __import__("professional_reports").ProfessionalReportWindow(self.parent,"tax","VAT, Profit & Stock Reconciliation")
        except Exception as e: messagebox.showerror("Report",str(e),parent=self)

def install(app_cls):
    return app_cls

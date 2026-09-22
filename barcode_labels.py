from core.logger import logger as _bkpos_logger

import sqlite3, tkinter as tk
from tkinter import ttk, messagebox, filedialog
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.graphics.barcode import code128
from core.config import DB_PATH
DB_NAME=DB_PATH
class BarcodeLabelWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent);self.parent=parent;self.title("Barcode & Label Printing");self.geometry("1050x650");self.configure(bg="#eef2f7");self.build();self.refresh()
    def build(self):
        tk.Label(self,text="BARCODE & LABEL PRINTING",font=("Arial",19,"bold"),bg="#2c5282",fg="white",pady=12).pack(fill="x")
        f=tk.Frame(self,bg="#eef2f7",pady=10);f.pack(fill="x")
        tk.Label(f,text="Search",bg="#eef2f7").pack(side="left");self.q=tk.Entry(f,width=35);self.q.pack(side="left",padx=6);self.q.bind("<KeyRelease>",lambda e:self.refresh())
        tk.Button(f,text="SELECTED → PDF LABELS",command=self.make_labels).pack(side="right")
        cols=("barcode","description","price","qty");self.tree=ttk.Treeview(self,columns=cols,show="headings")
        for c,h,w in [("barcode","Barcode",180),("description","Description",430),("price","Selling Price",130),("qty","Labels",100)]:self.tree.heading(c,text=h);self.tree.column(c,width=w)
        self.tree.pack(fill="both",expand=True,padx=15,pady=8);self.tree.bind("<Double-1>",lambda e:self.make_labels())
    def refresh(self):
        q=self.q.get().strip() if hasattr(self,"q") else "";c=sqlite3.connect(DB_NAME)
        rows=c.execute("SELECT barcode,description,selling_price FROM products WHERE barcode LIKE ? OR description LIKE ? ORDER BY description",(f"%{q}%",f"%{q}%")).fetchall();c.close()
        for i in self.tree.get_children():self.tree.delete(i)
        for r in rows:self.tree.insert("", "end",values=(r[0],r[1],f"R {r[2]:.2f}",1))
    def make_labels(self):
        sel=self.tree.selection()
        if not sel:messagebox.showwarning("Labels","Select one or more products.",parent=self);return
        p=filedialog.asksaveasfilename(defaultextension=".pdf",filetypes=[("PDF","*.pdf")],initialfile="barcode_labels.pdf")
        if not p:return
        c=canvas.Canvas(p,pagesize=(100*mm,50*mm))
        for iid in sel:
            vals=self.tree.item(iid,"values"); barcode,desc,price=vals[0],vals[1],float(str(vals[2]).replace("R ",""))
            n=1
            try:n=max(1,int(vals[3]))
            except BaseException as exc:
                _bkpos_logger.warning("Suppressed exception in barcode_labels.py", exc_info=exc)
            for _ in range(n):
                c.setFont("Helvetica-Bold",11);c.drawString(5*mm,43*mm,desc[:38])
                c.setFont("Helvetica-Bold",14);c.drawString(5*mm,34*mm,f"R {price:,.2f}")
                b=code128.Code128(str(barcode),barHeight=13*mm,barWidth=0.32*mm)
                b.drawOn(c,5*mm,10*mm);c.setFont("Helvetica",8);c.drawCentredString(50*mm,6*mm,str(barcode));c.showPage()
        c.save();messagebox.showinfo("Labels",f"PDF labels created:\n{p}\n\nPrint the PDF to your label printer.",parent=self)

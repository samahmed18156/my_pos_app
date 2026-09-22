
import sqlite3, tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from core.config import DB_PATH
DB_NAME=DB_PATH
class AdvancedReportsWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent; self.title("Advanced Reports"); self.geometry("1220x760"); self.configure(bg="#eef2f7")
        self.build()
    def build(self):
        tk.Label(self,text="ADVANCED REPORTS",font=("Arial",19,"bold"),bg="#2c5282",fg="white",pady=12).pack(fill="x")
        f=tk.Frame(self,bg="#eef2f7",pady=10);f.pack(fill="x")
        tk.Label(f,text="From (YYYY-MM-DD)",bg="#eef2f7").pack(side="left");self.frm=tk.Entry(f,width=13);self.frm.insert(0,datetime.now().strftime("%Y-%m-%d"));self.frm.pack(side="left",padx=5)
        tk.Label(f,text="To",bg="#eef2f7").pack(side="left");self.to=tk.Entry(f,width=13);self.to.insert(0,datetime.now().strftime("%Y-%m-%d"));self.to.pack(side="left",padx=5)
        tk.Button(f,text="RUN REPORT",font=("Arial",10,"bold"),command=self.refresh).pack(side="left",padx=8)
        tk.Button(f,text="EXPORT CSV",command=self.export_csv).pack(side="left")
        tk.Button(f,text="VIEW IN JASPER VIEWER",command=self.view_in_jasperviewer).pack(side="left",padx=8)
        self.summary=tk.Label(self,text="",font=("Arial",12,"bold"),bg="#eef2f7",justify="left",anchor="w");self.summary.pack(fill="x",padx=15)
        cols=("metric","value");self.tree=ttk.Treeview(self,columns=cols,show="headings");self.tree.heading("metric",text="Report");self.tree.heading("value",text="Value");self.tree.column("metric",width=420);self.tree.column("value",width=500);self.tree.pack(fill="both",expand=True,padx=15,pady=10)
        self.refresh()
    def query(self):
        a,b=self.frm.get().strip(),self.to.get().strip()
        datetime.strptime(a,"%Y-%m-%d");datetime.strptime(b,"%Y-%m-%d")
        c=sqlite3.connect(DB_NAME)
        rows=[]
        def one(label,sql,args=()):
            v=c.execute(sql,args).fetchone()[0] or 0;rows.append((label,v));return v
        sales=one("Gross sales", "SELECT COALESCE(SUM(total_amount),0) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ?",(a,b))
        cost=one("Cost of sales","SELECT COALESCE(SUM(total_cost),0) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ?",(a,b))
        vat=one("VAT included in sales","SELECT COALESCE(SUM(total_amount*15/115),0) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ?",(a,b))
        tx=one("Transactions","SELECT COUNT(*) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ?",(a,b))
        cash=one("Cash","SELECT COALESCE(SUM(cash_amount),0) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ?",(a,b))
        card=one("Card","SELECT COALESCE(SUM(card_amount),0) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ?",(a,b))
        refunds=one("Refunds","SELECT COALESCE(SUM(total_amount),0) FROM return_history WHERE date(timestamp) BETWEEN ? AND ?",(a,b))
        stock=one("Current stock value","SELECT COALESCE(SUM(soh*cost_price),0) FROM products")
        profit=sales-cost-refunds;rows.append(("Estimated gross profit after refunds",profit))
        top=c.execute("""SELECT description, SUM(qty) q, SUM(value) v FROM sale_items s JOIN sales_history h ON h.id=s.sale_id
                         WHERE date(h.timestamp) BETWEEN ? AND ? GROUP BY barcode,description ORDER BY q DESC LIMIT 15""",(a,b)).fetchall()
        for d,q,v in top:rows.append((f"Top product: {d} ({q:g} units)",v))
        c.close();return rows,sales,cost,vat,tx,cash,card,refunds,stock,profit
    def refresh(self):
        try:r=self.query()
        except Exception as e:messagebox.showerror("Report",f"Invalid date or report error:\n{e}",parent=self);return
        rows,sales,cost,vat,tx,cash,card,refunds,stock,profit=r
        self.summary.config(text=f"Sales R {sales:,.2f}   |   Cost R {cost:,.2f}   |   Profit R {profit:,.2f}   |   VAT R {vat:,.2f}   |   Transactions {tx}   |   Cash R {cash:,.2f}   |   Card R {card:,.2f}   |   Refunds R {refunds:,.2f}   |   Stock value R {stock:,.2f}")
        for i in self.tree.get_children():self.tree.delete(i)
        for x in rows:self.tree.insert("", "end",values=(x[0],f"R {x[1]:,.2f}" if isinstance(x[1],(int,float)) else x[1]))
        self.last_rows=rows
    def view_in_jasperviewer(self):
        try:
            from jasper_reports.report_viewer import open_table_report
            rows=getattr(self,"last_rows",[])
            open_table_report("Advanced Sales & Profit Report",["Report","Value"],[(r[0],f"R {r[1]:,.2f}" if isinstance(r[1],(int,float)) else r[1]) for r in rows],period=f"{self.frm.get()} to {self.to.get()}",parent=self)
        except Exception as exc: messagebox.showerror("JasperViewer",str(exc),parent=self)

    def export_csv(self):
        if not hasattr(self,"last_rows"):return
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")],initialfile="advanced_report.csv")
        if not p:return
        import csv
        with open(p,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f);w.writerow(["Report","Value"]);w.writerows(self.last_rows)
        messagebox.showinfo("Export",f"Report saved:\n{p}",parent=self)

from core.logger import logger as _bkpos_logger
from store_settings import get_store_name
import os, sqlite3, tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta

from core.config import DB_PATH
from services.tax_profit_stock_audit import audit as tax_profit_stock_audit
from services.document_formatting import validate_report_period, report_filename
DB_NAME = DB_PATH

def db():
    return sqlite3.connect(DB_NAME)

def money(v):
    return f"R {float(v or 0):,.2f}"

class ProfessionalReportWindow(tk.Toplevel):
    """A4-style report preview for all major POS reports."""
    def __init__(self, parent, report_type="sales", title=None, from_date=None, to_date=None):
        super().__init__(parent)
        self.parent = parent
        self.report_type = report_type
        self.title(title or "POS Report Preview")
        self.geometry("1120x850")
        self.minsize(900, 700)
        self.configure(bg="#d9dee5")
        today=datetime.now().strftime("%Y-%m-%d")
        self.from_date=from_date or today
        self.to_date=to_date or today
        self.rows=[]
        self.build()
        self.refresh()

    def build(self):
        top=tk.Frame(self,bg="#243447",height=58); top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top,text="REPORT PREVIEW",font=("Segoe UI",16,"bold"),fg="white",bg="#243447").pack(side="left",padx=18,pady=14)
        tk.Button(top,text="EXPORT PDF",font=("Segoe UI",10,"bold"),command=self.export_pdf).pack(side="right",padx=8,pady=11)
        tk.Button(top,text="VIEW IN JASPER VIEWER",font=("Segoe UI",10,"bold"),command=self.view_in_jasperviewer).pack(side="right",padx=4,pady=11)
        tk.Button(top,text="PRINT",font=("Segoe UI",10,"bold"),command=self.print_report).pack(side="right",padx=4,pady=11)
        tk.Button(top,text="CLOSE",font=("Segoe UI",10,"bold"),command=self._close).pack(side="right",padx=4,pady=11)

        filt=tk.Frame(self,bg="#eef2f7",height=54); filt.pack(fill="x"); filt.pack_propagate(False)
        tk.Label(filt,text="From",bg="#eef2f7",font=("Segoe UI",10,"bold")).pack(side="left",padx=(18,4),pady=13)
        self.frm=tk.Entry(filt,width=12); self.frm.insert(0,self.from_date); self.frm.pack(side="left")
        tk.Label(filt,text="To",bg="#eef2f7",font=("Segoe UI",10,"bold")).pack(side="left",padx=(12,4))
        self.to=tk.Entry(filt,width=12); self.to.insert(0,self.to_date); self.to.pack(side="left")
        tk.Button(filt,text="UPDATE REPORT",command=self.refresh,font=("Segoe UI",10,"bold")).pack(side="left",padx=12)
        tk.Label(filt,text="A4-style preview • double-check dates before printing",fg="#52606d",bg="#eef2f7",font=("Segoe UI",9)).pack(side="right",padx=18)

        outer=tk.Frame(self,bg="#d9dee5"); outer.pack(fill="both",expand=True)
        self.canvas=tk.Canvas(outer,bg="#d9dee5",highlightthickness=0)
        vs=ttk.Scrollbar(outer,orient="vertical",command=self.canvas.yview); vs.pack(side="right",fill="y")
        self.canvas.configure(yscrollcommand=vs.set); self.canvas.pack(side="left",fill="both",expand=True)
        self.page=tk.Frame(self.canvas,bg="white",width=794,height=1123,bd=0)
        self.window_id=self.canvas.create_window((20,20),window=self.page,anchor="nw")
        self.canvas.bind("<Configure>",lambda e:self._center_page(e.width))
        self.page.grid_propagate(False)
        self.bind("<Escape>",lambda e:self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _close(self):
        try:
            self.grab_release()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in professional_reports.py", exc_info=exc)
        parent = getattr(self, "parent", None)
        try:
            self.destroy()
        finally:
            try:
                if parent is not None and parent.winfo_exists():
                    parent.focus_force()
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in professional_reports.py", exc_info=exc)

    def _center_page(self,w):
        x=max(20,(w-794)//2)
        self.canvas.coords(self.window_id,x,20)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _clear_page(self):
        for w in self.page.winfo_children(): w.destroy()

    def _header(self, subtitle):
        tk.Label(self.page,text=get_store_name(),font=("Georgia",20,"bold"),bg="white",fg="#17202a").pack(pady=(34,2))
        tk.Label(self.page,text=subtitle.upper(),font=("Segoe UI",13,"bold"),bg="white",fg="#34495e").pack()
        tk.Frame(self.page,bg="#17202a",height=2,width=690).pack(pady=12)
        tk.Label(self.page,text=f"Period: {self.frm.get()}  to  {self.to.get()}    •    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                 font=("Segoe UI",8),bg="white",fg="#667085").pack()
    def _section(self,title):
        tk.Label(self.page,text=title,font=("Segoe UI",11,"bold"),bg="white",fg="#243447",anchor="w").pack(fill="x",padx=52,pady=(18,6))
    def _table(self,headers,data,widths=None):
        frame=tk.Frame(self.page,bg="white"); frame.pack(fill="x",padx=52)
        if widths is None: widths=[max(12,min(38,len(str(h))+8)) for h in headers]
        for j,h in enumerate(headers):
            tk.Label(frame,text=str(h),font=("Segoe UI",8,"bold"),bg="#e9eef3",fg="#243447",
                     anchor="w",padx=6,pady=6,width=widths[j]).grid(row=0,column=j,sticky="ew")
        for i,row in enumerate(data,1):
            for j,val in enumerate(row):
                bg="#ffffff" if i%2 else "#f7f9fb"
                tk.Label(frame,text=str(val),font=("Segoe UI",8),bg=bg,fg="#1f2933",
                         anchor="w",padx=6,pady=5,width=widths[j]).grid(row=i,column=j,sticky="ew")
        return frame
    def _metric_grid(self, metrics):
        f=tk.Frame(self.page,bg="white"); f.pack(fill="x",padx=52,pady=12)
        for i,(k,v) in enumerate(metrics):
            c=tk.Frame(f,bg="#f7f9fb",bd=1,relief="solid"); c.grid(row=i//2,column=i%2,padx=4,pady=4,sticky="ew")
            f.grid_columnconfigure(i%2,weight=1)
            tk.Label(c,text=k,font=("Segoe UI",8,"bold"),bg="#f7f9fb",fg="#667085").pack(anchor="w",padx=10,pady=(8,0))
            tk.Label(c,text=v,font=("Segoe UI",13,"bold"),bg="#f7f9fb",fg="#17202a").pack(anchor="w",padx=10,pady=(1,8))
    def _footer(self):
        tk.Frame(self.page,bg="#17202a",height=1,width=690).pack(pady=(24,6))
        tk.Label(self.page,text=f"System-generated report • {get_store_name()} POS",font=("Segoe UI",8),bg="white",fg="#7b8794").pack()

    def _dates(self):
        return validate_report_period(self.frm.get(), self.to.get())

    def refresh(self):
        try:
            a,b=self._dates()
            self._clear_page()
            builders={"sales":self._sales,"general":self._general,"advanced":self._advanced,
                      "returns":self._returns,"financial":self._financial,"stock":self._stock,
                      "cashup":self._cashup,"lifecycle":self._lifecycle,"tax":self._tax}
            builders.get(self.report_type,self._sales)(a,b)
            self.canvas.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception as e:
            messagebox.showerror("Report",f"Unable to build report:\n{e}",parent=self)

    def _sales_data(self,a,b):
        c=db()
        # Net sales = completed sales less return notes, excluding voids.
        gross=c.execute("SELECT COALESCE(SUM(total_amount),0) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ? AND COALESCE(voided,0)=0",(a,b)).fetchone()[0]
        returns=c.execute("SELECT COALESCE(SUM(total_amount),0) FROM return_history WHERE date(timestamp) BETWEEN ? AND ?",(a,b)).fetchone()[0]
        net=gross-returns
        tx=c.execute("SELECT COUNT(*) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ? AND COALESCE(voided,0)=0",(a,b)).fetchone()[0]
        cash=c.execute("SELECT COALESCE(SUM(cash_amount),0) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ? AND COALESCE(voided,0)=0",(a,b)).fetchone()[0]
        card=c.execute("SELECT COALESCE(SUM(card_amount),0) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ? AND COALESCE(voided,0)=0",(a,b)).fetchone()[0]
        rows=c.execute("""SELECT id,timestamp,total_amount,payment_type,cashier FROM sales_history
                         WHERE date(timestamp) BETWEEN ? AND ? AND COALESCE(voided,0)=0
                         ORDER BY timestamp DESC LIMIT 35""",(a,b)).fetchall()
        c.close()
        return gross,returns,net,tx,cash,card,rows
    def _sales(self,a,b):
        self._header("Sales Report")
        gross,ret,net,tx,cash,card,rows=self._sales_data(a,b)
        vat=net*15/115
        self._metric_grid([("Gross Sales",money(gross)),("Credit Notes / Returns",money(ret)),
                           ("Net Sales",money(net)),("VAT Included",money(vat)),
                           ("Transactions",str(tx)),("Cash",money(cash)),("Card",money(card))])
        self._section("Transaction Detail")
        self._table(["Invoice","Date / Time","Amount","Payment","Cashier"],
                    [(f"#{r[0]:03d}",r[1],money(r[2]),r[3] or "-",r[4] or "-") for r in rows],[10,23,16,16,18])
        self._footer()

    def _general(self,a,b):
        self._header("Management Report")
        c=db()
        gross=c.execute("SELECT COALESCE(SUM(total_amount),0) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ? AND COALESCE(voided,0)=0",(a,b)).fetchone()[0]
        ret=c.execute("SELECT COALESCE(SUM(total_amount),0) FROM return_history WHERE date(timestamp) BETWEEN ? AND ?",(a,b)).fetchone()[0]
        cost=c.execute("SELECT COALESCE(SUM(total_cost),0) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ? AND COALESCE(voided,0)=0",(a,b)).fetchone()[0]
        stock=c.execute("SELECT COALESCE(SUM(soh*cost_price),0) FROM products").fetchone()[0]
        low=c.execute("SELECT COUNT(*) FROM products WHERE COALESCE(active,1)=1 AND COALESCE(soh,0)<=COALESCE(min_stock,0)").fetchone()[0]
        c.close()
        net=gross-ret
        self._metric_grid([("Gross Sales",money(gross)),("Returns",money(ret)),("Net Sales",money(net)),
                           ("Cost of Sales",money(cost)),("Estimated Profit",money(net-cost)),
                           ("Current Stock Value",money(stock)),("Low / Reorder Items",str(low))])
        self._section("Report Notes")
        self._table(["Control","Result"],[
            ("VAT included in net sales",money(net*15/115)),
            ("Sales less credit notes",money(net)),
            ("Stock valuation",money(stock)),
            ("Low stock items",str(low))],[34,28])
        self._footer()

    def _advanced(self,a,b):
        self._header("Advanced Sales & Profit Report")
        c=db()
        gross=c.execute("SELECT COALESCE(SUM(total_amount),0) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ? AND COALESCE(voided,0)=0",(a,b)).fetchone()[0]
        cost=c.execute("SELECT COALESCE(SUM(total_cost),0) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ? AND COALESCE(voided,0)=0",(a,b)).fetchone()[0]
        ret=c.execute("SELECT COALESCE(SUM(total_amount),0) FROM return_history WHERE date(timestamp) BETWEEN ? AND ?",(a,b)).fetchone()[0]
        top=c.execute("""SELECT description,SUM(qty),SUM(value) FROM sale_items s JOIN sales_history h ON h.id=s.sale_id
                      WHERE date(h.timestamp) BETWEEN ? AND ? AND COALESCE(h.voided,0)=0
                      GROUP BY barcode,description ORDER BY SUM(qty) DESC LIMIT 15""",(a,b)).fetchall()
        c.close()
        net=gross-ret; profit=net-cost
        self._metric_grid([("Gross Sales",money(gross)),("Credit Notes",money(ret)),("Net Sales",money(net)),
                           ("Cost",money(cost)),("Profit After Returns",money(profit)),("Margin",f"{(profit/net*100 if net else 0):.2f}%")])
        self._section("Top Selling Products")
        self._table(["Product","Units","Sales Value"],[(r[0],f"{r[1]:g}",money(r[2])) for r in top],[46,14,22])
        self._footer()

    def _returns(self,a,b):
        self._header("Returns & Credit Notes Report")
        c=db()
        total=c.execute("SELECT COALESCE(SUM(total_amount),0) FROM return_history WHERE date(timestamp) BETWEEN ? AND ?",(a,b)).fetchone()[0]
        count=c.execute("SELECT COUNT(*) FROM return_history WHERE date(timestamp) BETWEEN ? AND ?",(a,b)).fetchone()[0]
        rows=c.execute("""SELECT r.id,r.timestamp,r.original_sale_id,r.total_amount,r.refund_type,r.cashier,r.reason
                          FROM return_history r WHERE date(r.timestamp) BETWEEN ? AND ? ORDER BY r.timestamp DESC LIMIT 40""",(a,b)).fetchall()
        c.close()
        self._metric_grid([("Credit Notes",str(count)),("Total Credited",money(total)),
                           ("VAT Portion",money(total*15/115))])
        self._section("Credit Note Detail")
        self._table(["CN #","Date","Original Invoice","Amount","Type","Cashier","Reason"],
                    [(r[0],r[1],f"#{r[2]:03d}",money(r[3]),r[4] or "-",r[5] or "-",r[6] or "-") for r in rows],
                    [8,18,14,14,14,14,24])
        self._footer()

    def _financial(self,a,b):
        self._header("Financial Control Report")
        c=db(); x=tax_profit_stock_audit(c,start_date=a,end_date=b); c.close()
        s=x["sales"]; e=x["expenses"]
        self._metric_grid([("Gross Sales incl VAT",money(s["gross_inclusive"])),
                           ("Returns / Credit Notes",money(s["returns_inclusive"])),
                           ("Net Sales ex VAT",money(s["net_sales_ex_vat"])),
                           ("Output VAT",money(s["output_vat"])),
                           ("COGS ex VAT",money(x["cogs_ex_vat"])),
                           ("Gross Profit ex VAT",money(x["gross_profit_ex_vat"])),
                           ("Net Profit ex VAT",money(x["net_profit_ex_vat"])),
                           ("VAT Payable*",money(x["vat_payable_before_adjustments"]))])
        self._section("VAT / Profit Reconciliation")
        self._table(["Control","Amount"],[
            ("Output VAT on net sales",money(s["output_vat"])),
            ("Less input VAT on purchases",money(x["purchases"]["input_vat"])),
            ("Add supplier-credit VAT reversal",money(x["purchases"]["supplier_credit_vat"])),
            ("Less expense VAT",money(e["expense_vat"])),
            ("VAT payable before adjustments",money(x["vat_payable_before_adjustments"])),
            ("Net sales ex VAT",money(s["net_sales_ex_vat"])),
            ("COGS ex VAT",money(x["cogs_ex_vat"])),
            ("Gross profit ex VAT",money(x["gross_profit_ex_vat"])),
            ("Operating expenses ex VAT",money(e["expenses_ex_vat"])),
            ("Net profit ex VAT",money(x["net_profit_ex_vat"]))],[42,28])
        self._section("Stock Control")
        self._table(["Control","Amount"],[
            ("Global stock value",money(x["stock"]["global_value"])),
            ("Branch stock value",money(x["stock"]["branch_value"])),
            ("Stock value difference",money(x["stock"]["value_difference"])),
            ("Global units",f'{x["stock"]["global_units"]:g}'),
            ("Branch units",f'{x["stock"]["branch_units"]:g}'),
            ("Stock units difference",f'{x["stock"]["units_difference"]:g}'),
            ("Status", "BALANCED" if x["stock_balanced"] else "CHECK REQUIRED")
        ],[42,28])
        self._footer()

    def _tax(self,a,b):
        self._header("VAT, Profit & Stock Reconciliation")
        c=db(); x=tax_profit_stock_audit(c,start_date=a,end_date=b); c.close()
        s,p,e,st=x["sales"],x["purchases"],x["expenses"],x["stock"]
        self._metric_grid([("Net Sales ex VAT",money(s["net_sales_ex_vat"])),
                           ("Output VAT",money(s["output_vat"])),
                           ("Input VAT",money(p["input_vat"])),
                           ("Expense VAT",money(e["expense_vat"])),
                           ("VAT Payable*",money(x["vat_payable_before_adjustments"])),
                           ("Gross Profit ex VAT",money(x["gross_profit_ex_vat"])),
                           ("Net Profit ex VAT",money(x["net_profit_ex_vat"])),
                           ("Stock Value",money(st["global_value"]))])
        self._section("Detailed Controls")
        self._table(["Control","Amount"],[
            ("Gross sales incl VAT",money(s["gross_inclusive"])),
            ("Less returns",money(s["returns_inclusive"])),
            ("Net sales incl VAT",money(s["net_inclusive"])),
            ("Net sales ex VAT",money(s["net_sales_ex_vat"])),
            ("Output VAT",money(s["output_vat"])),
            ("Purchase input VAT",money(p["input_vat"])),
            ("Supplier credit VAT reversal",money(p["supplier_credit_vat"])),
            ("Expense VAT",money(e["expense_vat"])),
            ("VAT payable before adjustments",money(x["vat_payable_before_adjustments"])),
            ("Recorded COGS (VAT-inclusive basis)",money(x["recorded_cogs_inclusive"])),
            ("COGS ex VAT",money(x["cogs_ex_vat"])),
            ("Gross profit ex VAT",money(x["gross_profit_ex_vat"])),
            ("Operating expenses ex VAT",money(e["expenses_ex_vat"])),
            ("Net profit ex VAT",money(x["net_profit_ex_vat"])),
            ("Global stock value",money(st["global_value"])),
            ("Branch stock value",money(st["branch_value"])),
            ("Stock value difference",money(st["value_difference"])),
            ("Stock units difference",f'{st["units_difference"]:g}'),
            ("Stock status", "BALANCED" if x["stock_balanced"] else "CHECK REQUIRED")
        ],[46,28])
        self._section("Valuation Method")
        self._table(["Method","Description"],[("Current-cost valuation",st["valuation_method"])],[46,28])
        self._footer()

    def _stock(self,a,b):
        self._header("Stock Reconciliation Report")
        c=db()
        stock=c.execute("SELECT COALESCE(SUM(soh*cost_price),0) FROM products").fetchone()[0]
        rows=c.execute("""SELECT barcode,description,soh,cost_price,soh*cost_price
                          FROM products ORDER BY description LIMIT 60""").fetchall()
        mov=c.execute("""SELECT movement_type,COALESCE(SUM(qty),0) FROM stock_movements
                         WHERE date(timestamp) BETWEEN ? AND ? GROUP BY movement_type ORDER BY movement_type""",(a,b)).fetchall()
        c.close()
        self._metric_grid([("Current Stock Value",money(stock)),("Products Listed",str(len(rows))),
                           ("Movement Types",str(len(mov)))])
        self._section("Stock Movement Summary")
        self._table(["Movement","Signed Qty"],[(r[0],f"{r[1]:g}") for r in mov],[42,28])
        self._section("Current Stock Valuation")
        self._table(["Barcode","Description","SOH","Cost","Value"],
                    [(r[0],r[1],f"{r[2]:g}",money(r[3]),money(r[4])) for r in rows],
                    [18,34,12,16,20])
        self._footer()

    def _cashup(self,a,b):
        self._header("Cash-Up & Reconciliation Report")
        c=db()
        rows=c.execute("""SELECT cashier,COALESCE(SUM(cash_amount),0),COALESCE(SUM(card_amount),0),
                          COUNT(*) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ? AND COALESCE(voided,0)=0
                          GROUP BY cashier ORDER BY cashier""",(a,b)).fetchall()
        c.close()
        total_cash=sum(r[1] for r in rows); total_card=sum(r[2] for r in rows)
        self._metric_grid([("Expected Cash",money(total_cash)),("Card",money(total_card)),("Cashiers",str(len(rows)))])
        self._section("Cashier Reconciliation")
        self._table(["Cashier","Expected Cash","Card","Transactions"],
                    [(r[0] or "Unknown",money(r[1]),money(r[2]),r[3]) for r in rows],[28,24,24,18])
        self._section("Cash-Up Status")
        self._table(["Instruction","Result"],[
            ("Expected cash",money(total_cash)),
            ("Actual cash", "Enter counted cash in Cash-Up screen"),
            ("Difference", "Calculated when cash-up is submitted")
        ],[38,38])
        self._footer()

    def _lifecycle(self,a,b):
        self._header("Invoice Lifecycle Report")
        c=db()
        rows=c.execute("""SELECT id,timestamp,total_amount,payment_type,cashier,
                          CASE WHEN COALESCE(voided,0)=1 THEN 'VOIDED' ELSE 'CONFIRMED' END
                          FROM sales_history WHERE date(timestamp) BETWEEN ? AND ? ORDER BY timestamp DESC LIMIT 60""",(a,b)).fetchall()
        c.close()
        self._section("Invoice Status")
        self._table(["Invoice","Date","Amount","Payment","Cashier","Status"],
                    [(f"#{r[0]:03d}",r[1],money(r[2]),r[3] or "-",r[4] or "-",r[5]) for r in rows],
                    [10,22,17,17,18,15])
        self._footer()


    def view_in_jasperviewer(self):
        try:
            from jasper_reports.report_viewer import open_table_report
            lines=[]
            def walk(w):
                for child in w.winfo_children():
                    if isinstance(child, tk.Label):
                        t=child.cget("text")
                        if t: lines.append(str(t))
                    walk(child)
            walk(self.page)
            open_table_report(self.title, ["Report"], [(x,) for x in lines], period=f"{self.frm.get()} to {self.to.get()}", parent=self)
        except Exception as exc:
            messagebox.showerror("JasperViewer", str(exc), parent=self)

    def _render_pdf(self,path):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER
        except Exception as e:
            raise RuntimeError("PDF support is unavailable: "+str(e))
        # Create a clean PDF from the current preview's key metrics/tables.
        styles=getSampleStyleSheet()
        title=ParagraphStyle("Title2",parent=styles["Title"],fontName="Helvetica-Bold",fontSize=18,alignment=TA_CENTER,spaceAfter=5)
        sub=ParagraphStyle("Sub",parent=styles["Normal"],fontSize=9,alignment=TA_CENTER,textColor=colors.HexColor("#667085"))
        story=[Paragraph(get_store_name(),title),
               Paragraph(self.title.upper(),styles["Heading2"]),
               Paragraph(f"Period: {self.frm.get()} to {self.to.get()} | Generated {datetime.now():%Y-%m-%d %H:%M}",sub),
               Spacer(1,14)]
        # Extract visible labels in page order into a simple text report.
        for w in self.page.winfo_children():
            try:
                text=w.cget("text")
            except Exception:
                continue
            if text and text not in (get_store_name(),):
                story.append(Paragraph(str(text).replace("&","&amp;"),styles["BodyText"]))
                story.append(Spacer(1,4))
        doc=SimpleDocTemplate(path,pagesize=A4,rightMargin=35,leftMargin=35,topMargin=35,bottomMargin=35)
        doc.build(story)

    def export_pdf(self):
        try:
            a, b = self._dates()
        except ValueError as exc:
            messagebox.showerror("Report Dates", str(exc), parent=self)
            return
        p=filedialog.asksaveasfilename(parent=self,defaultextension=".pdf",
                                       filetypes=[("PDF document","*.pdf")],
                                       initialfile=report_filename(self.report_type, a, b))
        if not p:return
        try:
            self._render_pdf(p)
            messagebox.showinfo("PDF Ready",f"Report saved as:\n{p}",parent=self)
        except Exception as e: messagebox.showerror("PDF Export",str(e),parent=self)

    def print_report(self):
        import tempfile, subprocess, os
        try:
            p=os.path.join(tempfile.gettempdir(),f"pos_{self.report_type}_report.pdf")
            self._render_pdf(p)
            os.startfile(p,"print")
        except Exception as e:
            messagebox.showerror("Print Report",f"Could not send the report to the Windows printer:\n{e}",parent=self)

def open_professional_report(parent, report_type="sales", title=None):
    return ProfessionalReportWindow(parent,report_type,title)

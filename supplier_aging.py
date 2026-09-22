import tkinter as tk
from tkinter import ttk
from datetime import date,datetime
from supplier_ledger import db,ensure_schema,suppliers,purchase_rows,payment_rows,credit_rows
class SupplierAgingWindow(tk.Toplevel):
 def __init__(self,parent):
  super().__init__(parent); self.title('Supplier Aging'); self.geometry('1250x680'); self.configure(bg='#eef2f7'); self.transient(parent); c=db(); ensure_schema(c); self._build(); self.refresh(); self.bind('<Escape>',lambda e:self.destroy())
 def _build(self):
  tk.Label(self,text='SUPPLIER AGING',font=('Arial',21,'bold'),bg='#172033',fg='white',pady=16).pack(fill='x'); f=tk.Frame(self,bg='white'); f.pack(fill='both',expand=True,padx=15,pady=15); self.tree=ttk.Treeview(f,columns=('supplier','current','d30','d60','d90','over90','total'),show='headings');
  for c,h,w in zip(('supplier','current','d30','d60','d90','over90','total'),('SUPPLIER','CURRENT','1–30','31–60','61–90','90+','OUTSTANDING'),[260,135,135,135,135,135,150]): self.tree.heading(c,text=h); self.tree.column(c,width=w,anchor='e' if c!='supplier' else 'w')
  self.tree.pack(fill='both',expand=True,padx=10,pady=10); tk.Button(self,text='VIEW IN JASPER VIEWER',command=self.view_in_jasperviewer,bg='#2b6cb0',fg='white',bd=0,padx=18,pady=8).pack(side='left',padx=15,pady=(0,12)); tk.Button(self,text='REFRESH',command=self.refresh,bg='#475569',fg='white',bd=0,padx=18,pady=8).pack(side='left',padx=15,pady=(0,12)); tk.Button(self,text='CLOSE  ESC',command=self.destroy,bg='#172033',fg='white',bd=0,padx=18,pady=8).pack(side='right',padx=15,pady=(0,12))
 def view_in_jasperviewer(self):
  try:
   from jasper_reports.report_viewer import open_table_report
   rows=[self.tree.item(i,'values') for i in self.tree.get_children()]
   open_table_report("Supplier Aging",["Supplier","Current","1-30","31-60","61-90","90+","Outstanding"],rows,parent=self)
  except Exception as exc: from tkinter import messagebox; messagebox.showerror("JasperViewer",str(exc),parent=self)
 def refresh(self):
  self.tree.delete(*self.tree.get_children()); c=db(); ensure_schema(c); today=date.today()
  for sid,acc,name in suppliers(c):
   purchases=purchase_rows(c,sid,acc,name); payments=payment_rows(c,sid); credits=credit_rows(c,sid)
   buckets=[0.0]*5
   for _,_,d,amt in purchases:
    try: dt=datetime.fromisoformat(str(d).replace('Z','')).date()
    except: dt=today
    age=max(0,(today-dt).days); idx=0 if age==0 else 1 if age<=30 else 2 if age<=60 else 3 if age<=90 else 4; buckets[idx]+=float(amt or 0)
   reductions=sum(float(x[3] or 0) for x in payments)+sum(float(x[4] or 0) for x in credits)
   # Allocate payments/credits against oldest buckets first.
   for i in range(5): take=min(buckets[i],reductions); buckets[i]-=take; reductions-=take
   total=sum(buckets)
   if total>0.005:self.tree.insert('','end',values=(name,*[f'R {v:,.2f}' for v in buckets],f'R {total:,.2f}'))
  c.close()

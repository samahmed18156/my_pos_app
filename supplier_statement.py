import tkinter as tk
from tkinter import ttk, messagebox
from supplier_ledger import db,ensure_schema,suppliers,purchase_rows,payment_rows,credit_rows
class SupplierStatementWindow(tk.Toplevel):
 def __init__(self,parent):
  super().__init__(parent); self.title('Supplier Statements'); self.geometry('1350x760'); self.configure(bg='#eef2f7'); self.transient(parent)
  c=db(); ensure_schema(c); self.rows=suppliers(c); c.close(); self._build(); self.combo['values']=[f'{r[1]}  •  {r[2]}' if r[1] else r[2] for r in self.rows]; self.bind('<Escape>',lambda e:self.destroy())
 def _build(self):
  tk.Label(self,text='SUPPLIER STATEMENTS',font=('Arial',21,'bold'),bg='#172033',fg='white',pady=16).pack(fill='x')
  top=tk.Frame(self,bg='white'); top.pack(fill='x',padx=15,pady=12); tk.Label(top,text='SUPPLIER',bg='white',font=('Arial',10,'bold')).pack(side='left',padx=10); self.combo=ttk.Combobox(top,state='readonly',font=('Arial',13),width=55); self.combo.pack(side='left',pady=9); self.combo.bind('<<ComboboxSelected>>',self.refresh); self.summary=tk.StringVar(value='Select a supplier'); tk.Label(top,textvariable=self.summary,bg='white',font=('Arial',11,'bold')).pack(side='right',padx=12)
  f=tk.Frame(self,bg='white'); f.pack(fill='both',expand=True,padx=15,pady=(0,12)); self.tree=ttk.Treeview(f,columns=('date','doc','type','desc','debit','credit','balance'),show='headings')
  for c,h,w in zip(('date','doc','type','desc','debit','credit','balance'),('DATE','DOCUMENT','TYPE','DESCRIPTION','DEBIT','CREDIT','BALANCE'),(120,160,130,430,140,140,150)): self.tree.heading(c,text=h); self.tree.column(c,width=w,anchor='e' if c in ('debit','credit','balance') else 'w')
  self.tree.pack(fill='both',expand=True,padx=10,pady=10); self.tree.bind('<Double-1>', self.view_selected_document); tk.Button(self,text='VIEW SELECTED DOCUMENT',command=self.view_selected_document,bg='#2b6cb0',fg='white',bd=0,padx=18,pady=8).pack(anchor='e',padx=15,pady=(0,6)); tk.Button(self,text='CLOSE  ESC',command=self.destroy,bg='#172033',fg='white',bd=0,padx=20,pady=8).pack(anchor='e',padx=15,pady=(0,12))

 def view_selected_document(self,event=None):
  sel=self.tree.selection()
  if not sel:
   messagebox.showinfo('Document Viewer','Select a GRN/Purchase transaction first.',parent=self)
   return
  vals=self.tree.item(sel[0],'values')
  doc=str(vals[1] or '')
  typ=str(vals[2] or '').upper()
  if typ=='PURCHASE' and doc:
   try:
    c=db(); ensure_schema(c)
    row=c.execute("SELECT id FROM grn_headers WHERE grn_no=? LIMIT 1",(doc,)).fetchone()
    c.close()
    if not row:
     raise ValueError(f'GRN {doc} could not be found.')
    from document_viewer import _open
    _open('GRN',int(row[0]),parent=self)
   except Exception as exc:
    messagebox.showerror('Document Viewer',str(exc),parent=self)
  else:
   messagebox.showinfo('Document Viewer','Only purchase/GRN transactions have an original document viewer at this time.',parent=self)
 def refresh(self,e=None):
  i=self.combo.current(); self.tree.delete(*self.tree.get_children());
  if i<0:return
  sid,acc,name=self.rows[i]; c=db(); ensure_schema(c); entries=[]
  for rid,no,d,amt in purchase_rows(c,sid,acc,name): entries.append((d,no,'PURCHASE','GRN / Goods received',float(amt or 0),0))
  for rid,no,d,amt,method,ref in payment_rows(c,sid): entries.append((d,no,'PAYMENT',f'{method or ""} {ref or ""}'.strip(),0,float(amt or 0)))
  for rid,no,d,amt,reason,ref in credit_rows(c,sid): entries.append((d,no,'SUPPLIER CREDIT',f'{reason or "Stock returned"} {ref or ""}'.strip(),0,float(amt or 0)))
  running=0
  for d,no,typ,desc,debit,credit in sorted(entries,key=lambda z:(z[0] or '',z[1] or '')):
   running+=debit-credit; self.tree.insert('','end',values=(d,no,typ,desc,f'R {debit:,.2f}' if debit else '—',f'R {credit:,.2f}' if credit else '—',f'R {running:,.2f}'))
  self.summary.set(f'{name}  •  Purchases R {sum(x[4] for x in entries):,.2f}  •  Payments R {sum(x[5] for x in entries if x[2]=="PAYMENT"):,.2f}  •  Outstanding R {max(0,running):,.2f}'); c.close()

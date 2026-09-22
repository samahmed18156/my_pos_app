import sqlite3, tkinter as tk
from tkinter import ttk
DB_NAME='pos_store.db';BG='#eef2f7';NAVY='#172033';WHITE='white'
def db():return sqlite3.connect(DB_NAME)
class SupplierPurchaseHistoryWindow(tk.Toplevel):
 def __init__(self,parent):
  super().__init__(parent);self.title('Supplier Purchase History');self.geometry('1250x740');self.configure(bg=BG);self.transient(parent);self._build();self._load();self.bind('<Escape>',lambda e:self.destroy())
 def _build(self):
  h=tk.Frame(self,bg=NAVY);h.pack(fill='x');tk.Label(h,text='SUPPLIER PURCHASE HISTORY',font=('Arial',21,'bold'),bg=NAVY,fg=WHITE).pack(anchor='w',padx=20,pady=(15,2));tk.Label(h,text='GRN and supplier invoice history, separate from supplier account balances.',font=('Arial',10),bg=NAVY,fg='#cbd5e1').pack(anchor='w',padx=20,pady=(0,14));top=tk.Frame(self,bg=WHITE);top.pack(fill='x',padx=15,pady=12);tk.Label(top,text='SUPPLIER',bg=WHITE,font=('Arial',10,'bold')).pack(side='left',padx=10);self.combo=ttk.Combobox(top,state='readonly',font=('Arial',12),width=45);self.combo.pack(side='left',padx=5,pady=9);self.combo.bind('<<ComboboxSelected>>',self.refresh);self.total=tk.StringVar(value='');tk.Label(top,textvariable=self.total,bg=WHITE,fg=NAVY,font=('Arial',11,'bold')).pack(side='right',padx=12)
  tf=tk.Frame(self,bg=WHITE,bd=1,relief='solid');tf.pack(fill='both',expand=True,padx=15,pady=(0,12));self.tree=ttk.Treeview(tf,columns=('date','grn','invoice','ref','subtotal','vat','total'),show='headings');
  for c,t,w in [('date','DATE',120),('grn','GRN NO.',150),('invoice','SUPPLIER INVOICE',220),('ref','REFERENCE',180),('subtotal','SUBTOTAL',125),('vat','VAT',105),('total','TOTAL',130)]:self.tree.heading(c,text=t);self.tree.column(c,width=w,anchor='e' if c in ('subtotal','vat','total') else 'w')
  self.tree.pack(fill='both',expand=True,padx=10,pady=10);tk.Button(self,text='CLOSE  ESC',command=self.destroy,bg=NAVY,fg=WHITE,bd=0,font=('Arial',10,'bold'),padx=18,pady=8).pack(anchor='e',padx=15,pady=(0,12))
 def _load(self):
  c=db();self.rows=c.execute("SELECT id,supplier_account_no,name FROM accounts WHERE type='Supplier' ORDER BY name COLLATE NOCASE").fetchall();c.close();self.combo['values']=[f'{r[1]}  •  {r[2]}' for r in self.rows]
 def refresh(self,e=None):
  i=self.combo.current();self.tree.delete(*self.tree.get_children());
  if i<0:return
  acc,name=self.rows[i][1],self.rows[i][2];c=db();rows=c.execute("SELECT created_at,grn_no,supplier_invoice,reference,subtotal,vat,total FROM grn_headers WHERE supplier_account=? OR supplier_name=? ORDER BY id DESC",(acc,name)).fetchall();c.close();s=0
  for r in rows:s+=float(r[6] or 0);self.tree.insert('','end',values=(r[0],r[1],r[2] or '',r[3] or '',f'R {float(r[4] or 0):,.2f}',f'R {float(r[5] or 0):,.2f}',f'R {float(r[6] or 0):,.2f}'))
  self.total.set(f'TOTAL PURCHASES: R {s:,.2f}')

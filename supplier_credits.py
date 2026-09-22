import tkinter as tk
from tkinter import ttk,messagebox
from datetime import date,datetime
from supplier_ledger import db,ensure_schema,suppliers,credit_stock_available,supplier_balance

class SupplierCreditsWindow(tk.Toplevel):
 def __init__(self,parent,preselect_account='',preselect_name=''):
  super().__init__(parent); self.parent=parent; self.title('Supplier Credits / Stock Credit Notes'); self.geometry('1400x800'); self.minsize(1150,680); self.configure(bg='#eef2f7'); self.transient(parent)
  c=db(); ensure_schema(c); self.rows=suppliers(c); c.close(); self.sid=None; self.acc=''; self.name=''; self.items=[]; self._build(); self.combo['values']=[f'{r[1]}  •  {r[2]}' if r[1] else r[2] for r in self.rows]; self.bind('<Escape>',lambda e:self.destroy()); self._preselect_supplier(preselect_account,preselect_name)
 def _build(self):
  tk.Label(self,text='SUPPLIER CREDIT NOTES / STOCK RETURNS',font=('Arial',21,'bold'),bg='#172033',fg='white',pady=16).pack(fill='x')
  tk.Label(self,text='Select the supplier and the actual stock being returned. Credit value is calculated from stock quantity × supplier cost.',font=('Arial',10),bg='#172033',fg='#cbd5e1').pack(fill='x',pady=(0,14))
  top=tk.Frame(self,bg='white'); top.pack(fill='x',padx=15,pady=12); tk.Label(top,text='SUPPLIER',bg='white',font=('Arial',10,'bold')).pack(side='left',padx=10); self.combo=ttk.Combobox(top,state='readonly',font=('Arial',13),width=55); self.combo.pack(side='left',pady=9); self.combo.bind('<<ComboboxSelected>>',self.select_supplier); self.balance=tk.StringVar(value='Select supplier'); tk.Label(top,textvariable=self.balance,bg='white',fg='#172033',font=('Arial',11,'bold')).pack(side='right',padx=12)
  f=tk.Frame(self,bg='white',bd=1,relief='solid'); f.pack(fill='both',expand=True,padx=15,pady=(0,12)); tk.Label(f,text='STOCK AVAILABLE FROM THIS SUPPLIER',font=('Arial',13,'bold'),bg='white',fg='#172033').pack(anchor='w',padx=12,pady=10)
  cols=('grn','date','barcode','description','received','already','available','cost','return_qty','credit_value'); self.tree=ttk.Treeview(f,columns=cols,show='headings',selectmode='browse')
  heads={'grn':'GRN NO.','date':'DATE','barcode':'BARCODE','description':'DESCRIPTION','received':'RECEIVED','already':'ALREADY CREDITED','available':'AVAILABLE','cost':'SUPPLIER COST','return_qty':'RETURN QTY','credit_value':'CREDIT VALUE'}
  widths={'grn':130,'date':120,'barcode':130,'description':300,'received':90,'already':120,'available':100,'cost':120,'return_qty':110,'credit_value':130}
  for c in cols:self.tree.heading(c,text=heads[c]);self.tree.column(c,width=widths[c],anchor='e' if c not in ('grn','date','barcode','description') else 'w')
  self.tree.pack(fill='both',expand=True,padx=10,pady=8); self.tree.bind('<Double-1>',self.edit_qty); self.tree.bind('<Return>',self.edit_qty)
  act=tk.Frame(self,bg='#eef2f7'); act.pack(fill='x',padx=15,pady=(0,12)); self.reason=ttk.Combobox(act,values=['Damaged Stock','General Return','Expired Stock','Incorrect Delivery','Other'],state='readonly',font=('Arial',12),width=22); self.reason.set('Damaged Stock'); self.ref=tk.Entry(act,font=('Arial',12),width=24); self.dt=tk.Entry(act,font=('Arial',12),width=12); self.dt.insert(0,date.today().isoformat());
  for lab,w in [('RETURN REASON',self.reason),('REFERENCE',self.ref),('DATE',self.dt)]: tk.Label(act,text=lab,bg='#eef2f7',font=('Arial',9,'bold')).pack(side='left',padx=(8,4)); w.pack(side='left',padx=(0,10),ipady=5)
  self.total=tk.StringVar(value='Credit Value: R 0.00'); tk.Label(act,textvariable=self.total,bg='#eef2f7',font=('Arial',14,'bold')).pack(side='right',padx=12); tk.Button(act,text='POST CREDIT NOTE',command=self.post,bg='#b45309',fg='white',font=('Arial',11,'bold'),bd=0,padx=18,pady=10).pack(side='right',padx=5); tk.Button(act,text='SELECTED QTY',command=self.edit_qty,bg='#475569',fg='white',font=('Arial',10,'bold'),bd=0,padx=14,pady=10).pack(side='right',padx=5)
 def _preselect_supplier(self,account,name):
  if not self.rows:return
  idx=-1
  for i,r in enumerate(self.rows):
   if account and str(r[1] or '')==str(account): idx=i; break
   if name and str(r[2] or '').strip().lower()==str(name).strip().lower(): idx=i; break
  if idx>=0:
   self.combo.current(idx); self.select_supplier()

 def select_supplier(self,e=None):
  i=self.combo.current();
  if i<0:return
  self.sid,self.acc,self.name=self.rows[i]; self.load_items()
 def load_items(self):
  self.tree.delete(*self.tree.get_children()); self.items=[]; c=db(); ensure_schema(c); rows=credit_stock_available(c,self.sid,self.acc,self.name); c.close()
  for r in rows:
   iid,grnid,grn,d,barcode,desc,received,cost,credited=r; available=max(0,float(received or 0)-float(credited or 0));
   if available<=0:continue
   item={'grn_item_id':iid,'grn_id':grnid,'grn':grn,'date':d,'barcode':barcode,'description':desc,'received':float(received or 0),'already':float(credited or 0),'available':available,'cost':float(cost or 0),'qty':0.0}; self.items.append(item); self.tree.insert('','end',iid=str(len(self.items)-1),values=(grn,d,barcode,desc,f'{item["received"]:g}',f'{item["already"]:g}',f'{available:g}',f'R {item["cost"]:,.2f}','0', 'R 0.00'))
  self.recalculate(); self.update_balance()
 def update_balance(self):
  if not self.sid:return
  c=db(); p,pay,cr,bal=supplier_balance(c,self.sid,self.acc,self.name); c.close(); self.balance.set(f'Outstanding before this credit: R {max(0,bal):,.2f}')
 def edit_qty(self,event=None):
  sel=self.tree.selection();
  if not sel:return
  i=int(sel[0]); x=self.items[i]
  from tkinter import simpledialog
  q=simpledialog.askfloat('Return Stock',f"Return quantity for {x['description']}\nAvailable from this GRN: {x['available']:g}\nSupplier cost: R {x['cost']:,.2f}",initialvalue=x['qty'],minvalue=0,maxvalue=x['available'],parent=self)
  if q is None:return
  x['qty']=float(q); self.tree.item(str(i),values=(x['grn'],x['date'],x['barcode'],x['description'],f"{x['received']:g}",f"{x['already']:g}",f"{x['available']:g}",f"R {x['cost']:,.2f}",f"{x['qty']:g}",f"R {x['qty']*x['cost']:,.2f}")); self.recalculate()
 def recalculate(self):self.total.set(f'Credit Value: R {sum(x["qty"]*x["cost"] for x in self.items):,.2f}')
 def post(self):
  selected=[x for x in self.items if x['qty']>0.000001]
  if not self.sid:return messagebox.showwarning('Supplier Required','Select a supplier first.',parent=self)
  if not selected:return messagebox.showwarning('Stock Required','Enter a return quantity for at least one stock item.',parent=self)
  total=sum(x['qty']*x['cost'] for x in selected); no='SCN-'+datetime.now().strftime('%Y%m%d%H%M%S%f'); reason=self.reason.get().strip() or 'Stock returned to supplier'
  if not messagebox.askyesno('Confirm Supplier Credit',f'Credit Note: {no}\n\nStock returned: {sum(x["qty"] for x in selected):g} units\nCredit value: R {total:,.2f}\n\nThis quantity will be deducted from branch stock and the supplier liability will be reduced.',parent=self):return
  c=db(); ensure_schema(c)
  try:
   from services.supplier_credit_service import post_supplier_stock_credit
   result=post_supplier_stock_credit(c, supplier_id=self.sid,
      items=[{'grn_item_id':x['grn_item_id'],'qty':x['qty']} for x in selected],
      branch_id=getattr(self.parent,'current_branch_id',1), credit_no=no,
      credit_date=self.dt.get().strip() or date.today().isoformat(), reason=reason,
      reference=self.ref.get().strip(), created_by=getattr(self.parent,'cashier_username','Unknown'))
   c.commit(); messagebox.showinfo('Supplier Credit Completed',f"{result['credit_no']}\n\nStock returned: {result['stock_returned']:g} units\nSupplier credit: R {result['amount']:,.2f}\n\nThe stock and creditor transaction were committed together.",parent=self); self.load_items(); self.reason.set('Damaged Stock'); self.ref.delete(0,'end')
  except Exception as e:c.rollback(); messagebox.showerror('Credit Note Failed',str(e),parent=self)
  finally:c.close()

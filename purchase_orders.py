import sqlite3, tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from core.config import DB_PATH
from ui.window_polish import polish_window
from services.purchase_order_service import ensure_schema, create_purchase_order, set_status
DB_NAME=DB_PATH

def conn(): return sqlite3.connect(DB_NAME)

class PurchaseOrderWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); polish_window(self); self.parent=parent; self.title('Purchase Orders'); self.geometry('1280x820'); self.configure(bg='#eef2f7'); self.transient(parent); self.grab_set(); self.rows=[]; self.selected_id=None
        c=conn(); ensure_schema(c); c.commit(); c.close(); self.build(); self.new_order(); self.refresh_history()
    def build(self):
        tk.Label(self,text='PURCHASE ORDERS',font=('Arial',20,'bold'),bg='#1f4e78',fg='white',pady=13).pack(fill='x')
        top=tk.Frame(self,bg='white',padx=15,pady=12); top.pack(fill='x',padx=15,pady=10)
        self.fields={}
        specs=[('PO Number','po','readonly'),('Supplier','supplier','combo'),('Expected Delivery','expected','normal'),('Notes','notes','normal')]
        for i,(lab,key,kind) in enumerate(specs):
            tk.Label(top,text=lab,bg='white',font=('Arial',9,'bold')).grid(row=i//2*2,column=(i%2)*2,sticky='w',padx=8,pady=3)
            if key=='supplier':
                e=ttk.Combobox(top,state='readonly',font=('Arial',11),width=42)
            elif key=='notes': e=tk.Entry(top,font=('Arial',11),width=55)
            else: e=tk.Entry(top,font=('Arial',11),width=38)
            e.grid(row=i//2*2+1,column=(i%2)*2+1,sticky='ew',padx=8,pady=(0,7)); self.fields[key]=e
        top.grid_columnconfigure(1,weight=1); top.grid_columnconfigure(3,weight=1)
        entry=tk.LabelFrame(self,text='  ADD ORDER ITEM  ',bg='#eef2f7',font=('Arial',10,'bold'),fg='#1f4e78',padx=10,pady=8); entry.pack(fill='x',padx=15)
        for i,(lab,key,w) in enumerate([('Barcode','code',18),('Quantity','qty',10),('Unit Cost','cost',12)]):
            tk.Label(entry,text=lab,bg='#eef2f7',font=('Arial',9,'bold')).grid(row=0,column=i*2,sticky='w',padx=6); e=tk.Entry(entry,font=('Arial',12),width=w); e.grid(row=1,column=i*2,padx=6); setattr(self,key,e)
        tk.Button(entry,text='F3 PRODUCT LOOKUP',bg='#2563eb',fg='white',font=('Arial',10,'bold'),command=self.lookup_product).grid(row=1,column=6,padx=6)
        tk.Button(entry,text='ADD ITEM',bg='#16803c',fg='white',font=('Arial',10,'bold'),command=self.add_item).grid(row=1,column=7,padx=6)
        self.code.bind('<F3>',self.lookup_product); self.cost.bind('<Return>',lambda e:self.add_item()); self.qty.bind('<Return>',lambda e:self.cost.focus_set())
        box=tk.Frame(self,bg='white',padx=10,pady=10); box.pack(fill='both',expand=True,padx=15,pady=10)
        self.tree=ttk.Treeview(box,columns=('code','desc','qty','received','cost','value'),show='headings')
        for c,h,w,a in [('code','Barcode',150, 'w'),('desc','Description',380,'w'),('qty','Ordered',100,'e'),('received','Received',100,'e'),('cost','Unit Cost',120,'e'),('value','Value',140,'e')]: self.tree.heading(c,text=h); self.tree.column(c,width=w,anchor=a)
        self.tree.pack(fill='both',expand=True)
        self.total=tk.Label(self,text='TOTAL: R 0.00',font=('Arial',14,'bold'),bg='white',anchor='e',padx=20,pady=10); self.total.pack(fill='x',padx=15)
        b=tk.Frame(self,bg='#eef2f7'); b.pack(fill='x',padx=15,pady=8)
        for t,cmd,bgc in [('SAVE DRAFT',self.save,'#16803c'),('MARK ORDERED',lambda:self.change_status('ORDERED'),'#2563eb'),('CREATE GRN FROM PO',self.create_grn,'#b45309'),('NEW PO',self.new_order,'#64748b')]: tk.Button(b,text=t,command=cmd,bg=bgc,fg='white',font=('Arial',10,'bold'),padx=12,pady=8).pack(side='left',padx=4)
        tk.Button(b,text='VIEW PO IN JASPERVIEWER',command=self.view_jasper,bg='#334155',fg='white',font=('Arial',10,'bold'),padx=12,pady=8).pack(side='right',padx=4)
        tk.Button(b,text='CLOSE',command=self.destroy,padx=15,pady=8).pack(side='right',padx=4)
        hist=tk.LabelFrame(self,text='  PURCHASE ORDER HISTORY  ',bg='#eef2f7',fg='#1f4e78',font=('Arial',10,'bold')); hist.pack(fill='x',padx=15,pady=(0,12))
        self.history=ttk.Treeview(hist,columns=('po','date','supplier','expected','status','total'),show='headings',height=6)
        for c,h,w in [('po','PO No.',120),('date','Date',110),('supplier','Supplier',270),('expected','Expected',110),('status','Status',170),('total','Total',130)]: self.history.heading(c,text=h); self.history.column(c,width=w,anchor='e' if c=='total' else 'w')
        self.history.pack(fill='x',padx=8,pady=8); self.history.bind('<<TreeviewSelect>>',self.load_history)
    def suppliers(self):
        c=conn(); rows=c.execute("SELECT id,supplier_account_no,name FROM accounts WHERE type='Supplier' AND COALESCE(active,1)=1 ORDER BY name COLLATE NOCASE").fetchall(); c.close(); return rows
    def refresh_suppliers(self):
        rows=self.suppliers(); self.supplier_rows=rows; self.fields['supplier']['values']=[f'{r[1]} — {r[2]}' for r in rows]
    def new_order(self):
        self.selected_id=None; self.rows=[]; self.refresh_suppliers()
        self.fields['po'].configure(state='normal'); self.fields['po'].delete(0,'end'); self.fields['po'].insert(0,'NEW'); self.fields['po'].configure(state='readonly')
        self.fields['supplier'].set(''); self.fields['expected'].delete(0,'end'); self.fields['expected'].insert(0,datetime.now().strftime('%Y-%m-%d')); self.fields['notes'].delete(0,'end'); self.refresh_tree()
    def add_item(self):
        code=self.code.get().strip()
        try: qty=float(self.qty.get()); cost=float(self.cost.get())
        except Exception: messagebox.showerror('Invalid','Enter a valid product, quantity and unit cost.',parent=self); return
        c=conn(); r=c.execute('SELECT description FROM products WHERE barcode=?',(code,)).fetchone(); c.close()
        if not r or qty<=0 or cost<0: messagebox.showwarning('Invalid Item','Select an existing product and enter a positive quantity.',parent=self); return
        self.rows.append((code,r[0] or code,qty,cost,round(qty*cost,2),0)); self.refresh_tree(); self.code.delete(0,'end'); self.qty.delete(0,'end'); self.qty.insert(0,'1'); self.cost.delete(0,'end')
    def refresh_tree(self):
        for x in self.tree.get_children(): self.tree.delete(x)
        total=0
        for r in self.rows: total+=r[4]; self.tree.insert('','end',values=(r[0],r[1],f'{r[2]:g}',f'{r[5]:g}',f'R {r[3]:,.2f}',f'R {r[4]:,.2f}'))
        self.total.config(text=f'TOTAL: R {total:,.2f}')
    def save(self):
        if self.selected_id: messagebox.showinfo('Purchase Order','Use a new PO for changes to preserve the original order history.',parent=self); return
        sel=self.fields['supplier'].current()
        if sel<0: messagebox.showwarning('Supplier','Select a supplier.',parent=self); return
        s=self.supplier_rows[sel]
        try:
            c=conn(); result=create_purchase_order(c,supplier_id=s[0],supplier_account=s[1],supplier_name=s[2],items=[{'barcode':r[0],'description':r[1],'qty':r[2],'cost':r[3]} for r in self.rows],expected_date=self.fields['expected'].get().strip(),notes=self.fields['notes'].get().strip(),created_by=getattr(self.parent,'cashier_username','Unknown')); c.commit(); c.close()
            self.selected_id=result['po_id']; self.fields['po'].configure(state='normal'); self.fields['po'].delete(0,'end'); self.fields['po'].insert(0,result['po_no']); self.fields['po'].configure(state='readonly'); messagebox.showinfo('PO Saved',f"{result['po_no']} saved as DRAFT.\n\nTotal: R {result['total']:,.2f}",parent=self); self.refresh_history()
        except Exception as e: messagebox.showerror('PO Error',str(e),parent=self)
    def change_status(self,status):
        if not self.selected_id: messagebox.showwarning('Purchase Order','Save the PO first.',parent=self); return
        c=conn()
        try: set_status(c,self.selected_id,status); c.commit(); messagebox.showinfo('Purchase Order',f'PO marked {status}.',parent=self); self.refresh_history()
        except Exception as e: c.rollback(); messagebox.showerror('Status Error',str(e),parent=self)
        finally:c.close()
    def refresh_history(self):
        c=conn(); rows=c.execute('SELECT id,po_no,order_date,supplier_name,expected_date,status,total FROM purchase_orders ORDER BY id DESC LIMIT 100').fetchall(); c.close()
        for x in self.history.get_children(): self.history.delete(x)
        for r in rows: self.history.insert('','end',iid=str(r[0]),values=(r[1],r[2],r[3],r[4] or '',r[5],f'R {float(r[6] or 0):,.2f}'))
    def load_history(self,event=None):
        sel=self.history.selection()
        if not sel:return
        pid=int(sel[0]); c=conn(); h=c.execute('SELECT po_no,supplier_account,supplier_name,expected_date,notes,status FROM purchase_orders WHERE id=?',(pid,)).fetchone(); items=c.execute('SELECT barcode,description,ordered_qty,unit_cost,value,received_qty FROM purchase_order_items WHERE po_id=?',(pid,)).fetchall(); c.close()
        if not h:return
        self.selected_id=pid; self.rows=items; self.fields['po'].configure(state='normal'); self.fields['po'].delete(0,'end'); self.fields['po'].insert(0,h[0]); self.fields['po'].configure(state='readonly'); self.refresh_suppliers(); self.fields['supplier'].set(next((f'{r[1]} — {r[2]}' for r in self.supplier_rows if r[1]==h[1]),f'{h[1]} — {h[2]}')); self.fields['expected'].delete(0,'end'); self.fields['expected'].insert(0,h[3] or ''); self.fields['notes'].delete(0,'end'); self.fields['notes'].insert(0,h[4] or ''); self.refresh_tree()
    def lookup_product(self,event=None):
        w=tk.Toplevel(self); w.title('Product Lookup'); w.geometry('900x600'); w.transient(self); w.grab_set(); search=tk.Entry(w,font=('Arial',12)); search.pack(fill='x',padx=12,pady=10); tree=ttk.Treeview(w,columns=('code','desc','cost'),show='headings');
        for c,h,wd in [('code','Barcode',180),('desc','Description',480),('cost','Current Cost',140)]: tree.heading(c,text=h);tree.column(c,width=wd)
        tree.pack(fill='both',expand=True,padx=12)
        def load():
            for x in tree.get_children():tree.delete(x)
            q=search.get().strip(); c=conn(); rows=c.execute("SELECT barcode,description,COALESCE(cost_price,0) FROM products WHERE COALESCE(active,1)=1 AND (barcode LIKE ? OR description LIKE ?) ORDER BY description",(f'%{q}%',f'%{q}%')).fetchall(); c.close()
            for r in rows:tree.insert('','end',values=(r[0],r[1],f'R {float(r[2]):,.2f}'))
            if tree.get_children():tree.selection_set(tree.get_children()[0])
        def choose(e=None):
            s=tree.selection()
            if not s:return
            v=tree.item(s[0],'values');self.code.delete(0,'end');self.code.insert(0,v[0]);self.cost.delete(0,'end');self.cost.insert(0,v[2].replace('R ','').replace(',',''));w.destroy();self.qty.focus_set()
        search.bind('<KeyRelease>',lambda e:load());tree.bind('<Double-1>',choose);tree.bind('<Return>',choose);w.bind('<Escape>',lambda e:w.destroy());load();search.focus_set()
    def create_grn(self):
        if not self.selected_id: messagebox.showwarning('Purchase Order','Select a saved PO first.',parent=self); return
        c=conn(); h=c.execute('SELECT po_no,supplier_account,supplier_name,supplier_id,supplier_invoice FROM purchase_orders po LEFT JOIN accounts a ON a.id=po.supplier_id WHERE po.id=?',(self.selected_id,)).fetchone(); items=c.execute('SELECT barcode,description,ordered_qty,unit_cost,received_qty FROM purchase_order_items WHERE po_id=?',(self.selected_id,)).fetchall(); c.close()
        if not h:return
        if h[0] and any(float(x[4] or 0)>=float(x[2]) for x in items):
            pass
        try:
            from professional_grn import ProfessionalGRNWindow
            w=ProfessionalGRNWindow(self.parent); w._set_entry(w.fields['account'],h[1]); w._set_entry(w.fields['supplier'],h[2]); w._set_entry(w.fields['ref'],h[0]); w._set_entry(w.fields['invoice'],h[4] or '')
            w.rows=[]
            for code,desc,ordered,cost,received in items:
                remaining=max(0,float(ordered)-float(received or 0))
                if remaining>0: w.rows.append((code,desc,0,remaining,float(cost),round(remaining*float(cost),2)))
            w.refresh_tree(); w.update_total(); w.po_no=h[0]; w.status.config(text=f'RECEIVING AGAINST {h[0]}'); self.destroy()
        except Exception as e: messagebox.showerror('Create GRN',str(e),parent=self)
    def view_jasper(self):
        sel=self.history.selection()
        pid=int(sel[0]) if sel else self.selected_id
        if not pid: messagebox.showinfo('JasperViewer','Select a purchase order first.',parent=self); return
        c=conn(); h=c.execute('SELECT po_no,order_date,supplier_name,expected_date,status,total FROM purchase_orders WHERE id=?',(pid,)).fetchone(); rows=c.execute('SELECT barcode,description,ordered_qty,received_qty,unit_cost,value FROM purchase_order_items WHERE po_id=?',(pid,)).fetchall(); c.close()
        try:
            from jasper_reports.report_viewer import open_table_report
            open_table_report(f'Purchase Order {h[0]}',['Barcode','Description','Ordered','Received','Unit Cost','Value'],rows,summary=[('Supplier',h[2]),('Order Date',h[1]),('Expected',h[3] or ''),('Status',h[4]),('Total',f'R {float(h[5] or 0):,.2f}')],parent=self)
        except Exception as e: messagebox.showerror('JasperViewer',str(e),parent=self)

from core.logger import logger as _bkpos_logger
from store_settings import get_store_name
import sqlite3, tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
DB_NAME='pos_store.db'
CATS=[('Premises','Rent'),('Premises','Rates & Taxes'),('Premises','Electricity'),('Premises','Water'),('Premises','Refuse/Waste'),('Premises','Cleaning'),('Premises','Security'),('Premises','Property Maintenance'),('Staff','Salaries & Wages'),('Staff','Overtime'),('Staff','Staff Benefits'),('Staff','Staff Meals'),('Staff','Staff Uniforms'),('Staff','Training'),('Staff','Recruitment'),('Operations','Repairs & Maintenance'),('Operations','Equipment Maintenance'),('Operations','Refrigeration Maintenance'),('Operations','Vehicle Maintenance'),('Operations','Fuel'),('Operations','Transport'),('Operations','Delivery Costs'),('Operations','Packaging'),('Operations','Cleaning Supplies'),('Operations','Office Supplies'),('Operations','Stationery'),('Operations','Printing'),('Technology','Internet'),('Technology','Telephone'),('Technology','POS Software'),('Technology','Software Subscriptions'),('Technology','Computer Equipment'),('Technology','Printer Supplies'),('Technology','IT Support'),('Banking & Finance','Bank Charges'),('Banking & Finance','Card Machine Fees'),('Banking & Finance','Interest'),('Banking & Finance','Loan Costs'),('Banking & Finance','Accounting Fees'),('Banking & Finance','Audit Fees'),('Banking & Finance','Professional Fees'),('Sales & Marketing','Advertising'),('Sales & Marketing','Promotions'),('Sales & Marketing','Flyers'),('Sales & Marketing','Signage'),('Sales & Marketing','Marketing'),('Sales & Marketing','Customer Loyalty Costs'),('Insurance & Legal','Insurance'),('Insurance & Legal','Legal Fees'),('Insurance & Legal','Licences & Permits'),('Insurance & Legal','Compliance Costs'),('Vehicles','Vehicle Finance'),('Vehicles','Fuel'),('Vehicles','Insurance'),('Vehicles','Licensing'),('Vehicles','Repairs'),('Vehicles','Tyres'),('Vehicles','Parking/Tolls'),('General','Security Deposits'),('General','Donations'),('General','Entertainment'),('General','Bank/Cash Differences'),('General','Miscellaneous')]
def init_db():
 c=sqlite3.connect(DB_NAME); q=c.cursor()
 q.execute('CREATE TABLE IF NOT EXISTS expense_categories(id INTEGER PRIMARY KEY AUTOINCREMENT,department TEXT NOT NULL,name TEXT UNIQUE NOT NULL,active INTEGER DEFAULT 1)')
 q.execute('''CREATE TABLE IF NOT EXISTS budgets(id INTEGER PRIMARY KEY AUTOINCREMENT,budget_year INTEGER NOT NULL,period TEXT NOT NULL DEFAULT 'Monthly',month INTEGER,category TEXT NOT NULL,amount REAL NOT NULL DEFAULT 0,branch_id INTEGER DEFAULT 1,notes TEXT DEFAULT '',created_at DATETIME DEFAULT CURRENT_TIMESTAMP,created_by TEXT DEFAULT 'Unknown')''')
 q.execute('''CREATE TABLE IF NOT EXISTS operating_expenses(id INTEGER PRIMARY KEY AUTOINCREMENT,expense_date TEXT NOT NULL,reference TEXT,payee TEXT,category TEXT NOT NULL,description TEXT,amount_ex_vat REAL DEFAULT 0,vat_amount REAL DEFAULT 0,total_amount REAL NOT NULL DEFAULT 0,payment_method TEXT DEFAULT 'Bank Transfer',branch_id INTEGER DEFAULT 1,department TEXT,invoice_reference TEXT,notes TEXT DEFAULT '',captured_by TEXT DEFAULT 'Unknown',created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
 for d,n in CATS:
  q.execute('INSERT OR IGNORE INTO expense_categories(department,name) VALUES(?,?)',(d,n))
 c.commit(); c.close()
def cats():
 c=sqlite3.connect(DB_NAME); r=c.execute('SELECT department,name FROM expense_categories WHERE active=1 ORDER BY department,name').fetchall(); c.close(); return r
def user(p): return getattr(p,'current_user',None) or getattr(p,'username',None) or 'Unknown'
class BudgetWindow(tk.Toplevel):
 def __init__(self,p):
  super().__init__(p); self.parent=p; self.title('Budget Capture'); self.geometry('650x520'); self.configure(bg='#eef2f7'); tk.Label(self,text='BUDGET CAPTURE',font=('Arial',18,'bold'),bg='#243447',fg='white',pady=12).pack(fill='x'); f=tk.Frame(self,bg='#eef2f7',padx=25,pady=20); f.pack(fill='both',expand=True)
  self.year=self.field(f,'Financial Year',0); self.year.insert(0,str(date.today().year)); self.month=self.field(f,'Month (1-12, blank = annual)',1); self.cat=tk.StringVar(); tk.Label(f,text='Category',bg='#eef2f7').grid(row=2,column=0,sticky='w',pady=8); self.cb=ttk.Combobox(f,textvariable=self.cat,width=40,state='readonly'); self.cb.grid(row=2,column=1); self.cb['values']=[n for _,n in cats()]; self.cb.current(0) if self.cb['values'] else None; self.amount=self.field(f,'Budget Amount (R)',3); self.notes=self.field(f,'Notes',4); tk.Button(f,text='SAVE BUDGET',font=('Arial',11,'bold'),command=self.save).grid(row=5,column=1,sticky='w',pady=18)
 def field(self,f,l,r): tk.Label(f,text=l,bg='#eef2f7').grid(row=r,column=0,sticky='w',pady=8); e=tk.Entry(f,width=43); e.grid(row=r,column=1); return e
 def save(self):
  try:
   y=int(self.year.get()); m=self.month.get().strip(); m=int(m) if m else None; a=float(self.amount.get()); assert a>=0 and (m is None or 1<=m<=12)
   c=sqlite3.connect(DB_NAME); c.execute('INSERT INTO budgets(budget_year,period,month,category,amount,notes,created_by) VALUES(?,?,?,?,?,?,?)',(y,'Monthly' if m else 'Annual',m,self.cat.get(),a,self.notes.get(),user(self.parent))); c.commit(); c.close(); messagebox.showinfo('Budget','Budget captured successfully.',parent=self); self.destroy()
  except Exception as e: messagebox.showerror('Budget','Please check the year, month and amount.\n'+str(e),parent=self)
class ExpenseWindow(tk.Toplevel):
 def __init__(self,p):
  super().__init__(p); self.parent=p; self.title('Expense Capture'); self.geometry('760x680'); self.configure(bg='#eef2f7'); tk.Label(self,text='EXPENSE CAPTURE',font=('Arial',18,'bold'),bg='#243447',fg='white',pady=12).pack(fill='x'); f=tk.Frame(self,bg='#eef2f7',padx=25,pady=15); f.pack(fill='both',expand=True)
  self.dt=self.field(f,'Expense Date',0); self.dt.insert(0,date.today().isoformat()); self.ref=self.field(f,'Expense Number / Reference',1); self.payee=self.field(f,'Supplier / Payee',2); self.cat=tk.StringVar(); tk.Label(f,text='Category',bg='#eef2f7').grid(row=3,column=0,sticky='w',pady=6); self.cb=ttk.Combobox(f,textvariable=self.cat,width=43,state='readonly'); self.cb.grid(row=3,column=1); self.cb['values']=[n for _,n in cats()]; self.cb.current(0) if self.cb['values'] else None; self.desc=self.field(f,'Description',4); self.ex=self.field(f,'Amount Ex VAT',5); self.vat=self.field(f,'VAT',6); self.total=self.field(f,'Total Amount',7); self.ex.bind('<KeyRelease>',self.calc); self.vat.bind('<KeyRelease>',self.calc); self.pm=tk.StringVar(value='Bank Transfer'); tk.Label(f,text='Payment Method',bg='#eef2f7').grid(row=8,column=0,sticky='w',pady=6); ttk.Combobox(f,textvariable=self.pm,values=['Cash','Card','Bank Transfer','Other'],width=43,state='readonly').grid(row=8,column=1); self.dept=self.field(f,'Department (optional)',9); self.inv=self.field(f,'Supplier Invoice / Reference',10); self.notes=self.field(f,'Notes',11); tk.Button(f,text='CAPTURE EXPENSE',font=('Arial',11,'bold'),command=self.save).grid(row=12,column=1,sticky='w',pady=18)
 def field(self,f,l,r): tk.Label(f,text=l,bg='#eef2f7').grid(row=r,column=0,sticky='w',pady=6); e=tk.Entry(f,width=46); e.grid(row=r,column=1); return e
 def calc(self,e=None):
  try: self.total.delete(0,'end'); self.total.insert(0,f'{float(self.ex.get() or 0)+float(self.vat.get() or 0):.2f}')
  except BaseException as exc:
      _bkpos_logger.warning("Suppressed exception in budget_expenses.py", exc_info=exc)
 def save(self):
  try:
   datetime.strptime(self.dt.get().strip(),'%Y-%m-%d'); ex=float(self.ex.get() or 0); vat=float(self.vat.get() or 0); total=float(self.total.get() or 0); assert min(ex,vat,total)>=0
   c=sqlite3.connect(DB_NAME); c.execute('''INSERT INTO operating_expenses(expense_date,reference,payee,category,description,amount_ex_vat,vat_amount,total_amount,payment_method,department,invoice_reference,notes,captured_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(self.dt.get(),self.ref.get(),self.payee.get(),self.cat.get(),self.desc.get(),ex,vat,total,self.pm.get(),self.dept.get(),self.inv.get(),self.notes.get(),user(self.parent))); c.commit(); c.close(); messagebox.showinfo('Expense','Expense captured successfully.',parent=self); self.destroy()
  except Exception as e: messagebox.showerror('Expense','Please check the date and amounts.\n'+str(e),parent=self)
class Categories(tk.Toplevel):
 def __init__(self,p):
  super().__init__(p); self.title('Expense Categories'); self.geometry('620x600'); self.tree=ttk.Treeview(self,columns=('dept','cat'),show='headings'); self.tree.heading('dept',text='Department'); self.tree.heading('cat',text='Expense Category'); self.tree.pack(fill='both',expand=True,padx=12,pady=12); f=tk.Frame(self); f.pack(fill='x',padx=12,pady=8); self.d=tk.Entry(f,width=20); self.d.pack(side='left'); self.n=tk.Entry(f,width=28); self.n.pack(side='left',padx=5); tk.Button(f,text='ADD CATEGORY',command=self.add).pack(side='left'); self.refresh()
 def refresh(self): self.tree.delete(*self.tree.get_children()); [self.tree.insert('', 'end',values=r) for r in cats()]
 def add(self):
  d,n=self.d.get().strip(),self.n.get().strip()
  if not d or not n:return
  try:
   c=sqlite3.connect(DB_NAME); c.execute('INSERT INTO expense_categories(department,name) VALUES(?,?)',(d,n)); c.commit(); c.close(); self.refresh(); self.d.delete(0,'end'); self.n.delete(0,'end')
  except Exception as e: messagebox.showerror('Category',str(e),parent=self)
class ExpenseReport(tk.Toplevel):
 def __init__(self,p,kind):
  super().__init__(p); self.title('Professional Expense Report'); self.geometry('1000x780'); self.kind=kind; self.configure(bg='#dfe5ec'); self.build(); self.run()
 def build(self):
  t=tk.Frame(self,bg='#243447'); t.pack(fill='x'); tk.Label(t,text=get_store_name(),font=('Arial',18,'bold'),bg='#243447',fg='white').pack(side='left',padx=18,pady=12); tk.Button(t,text='CLOSE',command=self.destroy).pack(side='right',padx=10,pady=10); f=tk.Frame(self,bg='#dfe5ec',pady=8); f.pack(fill='x'); tk.Label(f,text='From',bg='#dfe5ec').pack(side='left'); self.a=tk.Entry(f,width=12); self.a.insert(0,date.today().replace(day=1).isoformat()); self.a.pack(side='left',padx=5); tk.Label(f,text='To',bg='#dfe5ec').pack(side='left'); self.b=tk.Entry(f,width=12); self.b.insert(0,date.today().isoformat()); self.b.pack(side='left',padx=5); tk.Button(f,text='RUN REPORT',command=self.run).pack(side='left',padx=8); tk.Button(f,text='VIEW IN JASPER VIEWER',command=self.view_in_jasperviewer).pack(side='left',padx=6); o=tk.Frame(self,bg='#dfe5ec'); o.pack(fill='both',expand=True,padx=18); self.cv=tk.Canvas(o,bg='#aeb7c2',highlightthickness=0); self.cv.pack(side='left',fill='both',expand=True); sb=ttk.Scrollbar(o,orient='vertical',command=self.cv.yview); sb.pack(side='right',fill='y'); self.cv.configure(yscrollcommand=sb.set); self.page=tk.Frame(self.cv,bg='white',width=760); self.cv.create_window((20,20),window=self.page,anchor='nw'); self.page.bind('<Configure>',lambda e:self.cv.configure(scrollregion=self.cv.bbox('all')))
 def view_in_jasperviewer(self):
  try:
   from jasper_reports.report_viewer import open_table_report
   rows=[]
   for w in self.page.winfo_children():
    if isinstance(w,tk.Label) and w.cget("text"): rows.append((w.cget("text"),))
   open_table_report(self.title,["Report"],rows,period=f"{self.a.get()} to {self.b.get()}",parent=self)
  except Exception as exc: messagebox.showerror("JasperViewer",str(exc),parent=self)
 def run(self):
  for w in self.page.winfo_children():w.destroy()
  a,b=self.a.get(),self.b.get(); datetime.strptime(a,'%Y-%m-%d'); datetime.strptime(b,'%Y-%m-%d'); c=sqlite3.connect(DB_NAME); title={'vs':'BUDGET VS ACTUAL','sum':'EXPENSE SUMMARY','detail':'EXPENSE DETAIL','month':'MONTHLY EXPENSE TREND'}[self.kind]; tk.Label(self.page,text=title,font=('Arial',21,'bold'),bg='white').pack(pady=(35,5)); tk.Label(self.page,text=f'Period: {a} to {b}',bg='white',fg='#666').pack(); tk.Label(self.page,text=f'Generated: {datetime.now():%Y-%m-%d %H:%M}',bg='white',fg='#777').pack(pady=(3,18))
  if self.kind=='vs':
   # Match annual budgets to the selected year and monthly budgets only to
   # months that overlap the selected date range.
   y1, y2 = int(a[:4]), int(b[:4])
   rows=c.execute('''SELECT b.category,
       COALESCE(SUM(CASE
         WHEN b.period='Annual' AND b.budget_year BETWEEN ? AND ? THEN b.amount
         WHEN b.period='Monthly' AND b.budget_year BETWEEN ? AND ?
              AND b.month IS NOT NULL
              AND date(printf('%04d-%02d-01',b.budget_year,b.month)) <= date(?)
              AND date(printf('%04d-%02d-01',b.budget_year,b.month),'start of month','+1 month','-1 day') >= date(?)
         THEN b.amount ELSE 0 END),0),
       COALESCE((SELECT SUM(e.total_amount) FROM operating_expenses e
                 WHERE e.category=b.category AND e.expense_date BETWEEN ? AND ?),0)
       FROM budgets b
       WHERE b.budget_year BETWEEN ? AND ?
       GROUP BY b.category ORDER BY b.category''',
       (y1,y2,y1,y2,b,a,a,b,y1,y2)).fetchall()
   headers=['Category','Budget','Actual','Variance','Status']; data=[]; totalb=totala=0
  elif self.kind=='sum': rows=c.execute('SELECT category,SUM(total_amount),COUNT(*) FROM operating_expenses WHERE expense_date BETWEEN ? AND ? GROUP BY category ORDER BY category',(a,b)).fetchall(); headers=['Category','Actual Expense','Entries']; data=[[r[0],f'R {r[1]:,.2f}',r[2]] for r in rows]; total=sum(r[1] for r in rows)
  elif self.kind=='month': rows=c.execute("SELECT substr(expense_date,1,7),SUM(total_amount),COUNT(*) FROM operating_expenses WHERE expense_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 1",(a,b)).fetchall(); headers=['Month','Expense','Entries']; data=[[r[0],f'R {r[1]:,.2f}',r[2]] for r in rows]; total=sum(r[1] for r in rows)
  else: rows=c.execute('SELECT expense_date,reference,payee,category,description,total_amount,payment_method,captured_by FROM operating_expenses WHERE expense_date BETWEEN ? AND ? ORDER BY expense_date DESC,id DESC',(a,b)).fetchall(); headers=['Date','Ref','Payee','Category','Description','Total','Payment','Captured By']; data=[[r[0],r[1] or '',r[2] or '',r[3],r[4] or '',f'R {r[5]:,.2f}',r[6],r[7]] for r in rows]; total=sum(r[5] for r in rows)
  if self.kind=='vs':
   for cat,bud,act in rows:
    bud=float(bud or 0); act=float(act or 0); totalb+=bud; totala+=act; v=bud-act; data.append([cat,f'R {bud:,.2f}',f'R {act:,.2f}',f'R {abs(v):,.2f}','UNDER' if v>=0 else 'OVER'])
   total=totala; tk.Label(self.page,text=f'Budget: R {totalb:,.2f}    Actual: R {totala:,.2f}    Difference: R {abs(totalb-totala):,.2f}',font=('Arial',12,'bold'),bg='white').pack(pady=(4,12))
  if self.kind!='vs': tk.Label(self.page,text=f'Total Expenses: R {total:,.2f}',font=('Arial',12,'bold'),bg='white').pack(pady=(4,12))
  table=tk.Frame(self.page,bg='white'); table.pack(fill='x',padx=25)
  for j,h in enumerate(headers): tk.Label(table,text=h,font=('Arial',9,'bold'),bg='#e8edf2',padx=6,pady=7).grid(row=0,column=j,sticky='nsew')
  for i,row in enumerate(data,1):
   for j,v in enumerate(row): tk.Label(table,text=v,font=('Arial',9),bg='white' if i%2 else '#f6f8fa',padx=6,pady=5,anchor='w').grid(row=i,column=j,sticky='nsew')
  c.close()
class Center(tk.Toplevel):
 def __init__(self,p):
  super().__init__(p); self.title('Budget & Expense Management'); self.geometry('760x580'); self.configure(bg='#eef2f7'); tk.Label(self,text='BUDGET & EXPENSE MANAGEMENT',font=('Arial',20,'bold'),bg='#243447',fg='white',pady=14).pack(fill='x'); f=tk.Frame(self,bg='#eef2f7',padx=30,pady=25); f.pack(fill='both',expand=True); items=[('CAPTURE BUDGET',lambda:BudgetWindow(p)),('CAPTURE EXPENSE',lambda:ExpenseWindow(p)),('EXPENSE CATEGORIES',lambda:Categories(p)),('BUDGET VS ACTUAL',lambda:ExpenseReport(p,'vs')),('EXPENSE SUMMARY',lambda:ExpenseReport(p,'sum')),('EXPENSE DETAIL',lambda:ExpenseReport(p,'detail')),('MONTHLY EXPENSE TREND',lambda:ExpenseReport(p,'month'))]; [tk.Button(f,text=t,font=('Arial',10,'bold'),width=27,height=2,command=cmd).grid(row=i//2,column=i%2,padx=10,pady=9) for i,(t,cmd) in enumerate(items)]; tk.Button(f,text='CLOSE',command=self.destroy).grid(row=4,column=0,columnspan=2,pady=15)
def install(app_cls):
 init_db(); original=app_cls.create_menu_bar
 def menu(self):
  original(self); mb=self.nametowidget(self['menu']);
  for i in range(mb.index('end')+1):
   try:
    if mb.type(i)=='cascade' and mb.entrycget(i,'label')=='Utility':
     u=mb.nametowidget(mb.entrycget(i,'menu')); u.add_separator(); u.add_command(label='Budget & Expense Management',command=lambda:Center(self)); break
   except BaseException as exc:
       _bkpos_logger.warning("Suppressed exception in budget_expenses.py", exc_info=exc)
 app_cls.create_menu_bar=menu; return app_cls

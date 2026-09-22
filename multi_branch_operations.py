"""UI for multi-branch operations, transfers and safe synchronization."""
from __future__ import annotations
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
from core.config import DB_PATH
from services import multi_branch_service as svc

class MultiBranchOperationsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent=parent; self.title("BKPOS - Multi-Branch Operations"); self.geometry("1120x700"); self.minsize(980,620)
        self.configure(bg="#f4f6f8")
        self._build()
        self.refresh()

    def conn(self): return sqlite3.connect(DB_PATH)
    def _build(self):
        tk.Label(self,text="Multi-Branch Operations & Synchronization",font=("Segoe UI",17,"bold"),bg="#243447",fg="white",pady=12).pack(fill=tk.X)
        bar=tk.Frame(self,bg="#f4f6f8"); bar.pack(fill=tk.X,padx=12,pady=10)
        ttk.Button(bar,text="Refresh",command=self.refresh).pack(side=tk.LEFT,padx=4)
        ttk.Button(bar,text="Export Branch Bundle",command=self.export).pack(side=tk.LEFT,padx=4)
        ttk.Button(bar,text="Import Bundle (Stage)",command=self.import_bundle).pack(side=tk.LEFT,padx=4)
        ttk.Button(bar,text="Transfer Stock",command=self.transfer).pack(side=tk.LEFT,padx=4)
        ttk.Button(bar,text="Reconciliation",command=self.reconcile).pack(side=tk.LEFT,padx=4)
        self.status=tk.StringVar(value="Ready")
        tk.Label(bar,textvariable=self.status,bg="#f4f6f8",fg="#4a5568").pack(side=tk.RIGHT)
        nb=ttk.Notebook(self); nb.pack(fill=tk.BOTH,expand=True,padx=12,pady=(0,12))
        f1=tk.Frame(nb,bg="white"); nb.add(f1,text="Branches")
        self.branch_tree=self._tree(f1,("id","name","code","status","products","units"),(60,240,110,100,100,120))
        f2=tk.Frame(nb,bg="white"); nb.add(f2,text="Transfers")
        self.transfer_tree=self._tree(f2,("no","from","to","barcode","description","qty","status","cashier","time"),(110,80,80,110,220,70,90,100,150))
        f3=tk.Frame(nb,bg="white"); nb.add(f3,text="Sync Conflicts")
        self.conflict_tree=self._tree(f3,("batch","branch","barcode","description","remote","local","variance","imported"),(170,70,110,220,90,90,90,150))

    def _tree(self,parent,cols,widths):
        box=tk.Frame(parent,bg="white"); box.pack(fill=tk.BOTH,expand=True,padx=8,pady=8)
        t=ttk.Treeview(box,columns=cols,show="headings")
        for c,w in zip(cols,widths): t.heading(c,text=c.replace("_"," ").title()); t.column(c,width=w,anchor="center")
        sy=ttk.Scrollbar(box,orient="vertical",command=t.yview); t.configure(yscrollcommand=sy.set); t.pack(side=tk.LEFT,fill=tk.BOTH,expand=True); sy.pack(side=tk.RIGHT,fill=tk.Y)
        return t

    def refresh(self):
        try:
            c=self.conn()
            branches=svc.branch_overview(c); transfers=svc.transfer_history(c,limit=250); conflicts=svc.staged_conflicts(c)
            c.close()
            for t in (self.branch_tree,self.transfer_tree,self.conflict_tree):
                for x in t.get_children(): t.delete(x)
            for r in branches: self.branch_tree.insert("",tk.END,values=(r['id'],r['name'],r['code'],r['status'],r['products'],f"{r['units']:g}"))
            for r in transfers: self.transfer_tree.insert("",tk.END,values=(r[1],f"{r[3] or r[2]}",f"{r[5] or r[4]}",r[6],r[7],f"{r[8]:g}",r[9],r[10],r[11]))
            for r in conflicts: self.conflict_tree.insert("",tk.END,values=(r[0],r[1],r[2],r[3],f"{r[4]:g}","—" if r[5] is None else f"{r[5]:g}","—" if r[6] is None else f"{r[6]:g}",r[7]))
            self.status.set(f"{len(branches)} branches • {len(transfers)} transfers • {len(conflicts)} staged conflicts")
        except Exception as e: messagebox.showerror("Multi-Branch Error",str(e),parent=self)

    def _selected_branch(self):
        sel=self.branch_tree.selection()
        if not sel: raise ValueError("Select a branch first.")
        return int(self.branch_tree.item(sel[0],"values")[0])

    def export(self):
        try: bid=self._selected_branch()
        except ValueError as e: messagebox.showwarning("Branch",str(e),parent=self); return
        p=filedialog.asksaveasfilename(parent=self,defaultextension=".json",filetypes=[("BKPOS Sync Bundle","*.json")])
        if not p:return
        try:
            c=self.conn(); batch=svc.export_bundle(c,bid,p); c.close(); self.refresh(); messagebox.showinfo("Exported",f"Branch bundle exported.\nBatch: {batch}",parent=self)
        except Exception as e: messagebox.showerror("Export Failed",str(e),parent=self)

    def import_bundle(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[("BKPOS Sync Bundle","*.json")])
        if not p:return
        try:
            c=self.conn(); result=svc.import_bundle(c,p); c.close(); self.refresh()
            messagebox.showinfo("Bundle Staged",f"Rows staged: {result['rows']}\nConflicts: {result['conflicts']}\n\nNo live stock was overwritten.",parent=self)
        except Exception as e: messagebox.showerror("Import Failed",str(e),parent=self)

    def transfer(self):
        win=tk.Toplevel(self); win.title("Transfer Stock"); win.geometry("430x300"); win.transient(self); win.grab_set()
        fields=[("From branch",tk.StringVar(value="1")),("To branch",tk.StringVar(value="2")),("Barcode",tk.StringVar()),("Quantity",tk.StringVar())]
        for i,(label,var) in enumerate(fields): tk.Label(win,text=label).grid(row=i,column=0,sticky="w",padx=15,pady=10); ttk.Entry(win,textvariable=var,width=28).grid(row=i,column=1,padx=15,pady=10)
        def post():
            try:
                c=self.conn(); svc.transfer(c,int(fields[0][1].get()),int(fields[1][1].get()),fields[2][1].get().strip(),float(fields[3][1].get()),"Multi-Branch"); c.commit(); c.close(); win.destroy(); self.refresh(); messagebox.showinfo("Posted","Stock transfer posted successfully.",parent=self)
            except Exception as e: messagebox.showerror("Transfer Failed",str(e),parent=win)
        ttk.Button(win,text="Post Transfer",command=post).grid(row=5,column=0,columnspan=2,pady=15)

    def reconcile(self):
        try: bid=self._selected_branch()
        except ValueError as e: messagebox.showwarning("Branch",str(e),parent=self); return
        c=self.conn(); issues=svc.reconciliation(c,bid); c.close()
        if issues:
            text="\n".join(f"{x['barcode']}: global={x['global_soh']:g}, branches={x['branch_total']:g}, variance={x['variance']:g}" for x in issues[:30])
            messagebox.warning if False else None
            messagebox.showwarning("Reconciliation Differences",f"{len(issues)} SKU(s) differ between global and branch totals.\n\n{text}",parent=self)
        else: messagebox.showinfo("Reconciliation","No stock-total differences found for this branch.",parent=self)

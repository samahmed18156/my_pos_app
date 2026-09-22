
import os,sqlite3,shutil,glob,tkinter as tk
from tkinter import messagebox,filedialog
from datetime import datetime
from core.config import DB_PATH, BACKUP_DIR
from services.production_hardening import backup_database, restore_database, integrity_check, prune_backups
DB_NAME=DB_PATH
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
def verify_database(path):
    try:
        return integrity_check(path)
    except Exception:
        return False

def make_backup(target=None):
    if not os.path.exists(DB_NAME):
        raise FileNotFoundError(DB_NAME)
    if target is None:
        os.makedirs(BACKUP_DIR,exist_ok=True)
        target=os.path.join(BACKUP_DIR,f"pos_store_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    result=backup_database(DB_NAME,target)
    prune_backups(BACKUP_DIR, keep=30)
    return result
class DisasterRecoveryWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent);self.parent=parent;self.title("Disaster Recovery Center");self.geometry("720x520");self.configure(bg="#eef2f7");self.build();self.refresh()
    def build(self):
        tk.Label(self,text="DISASTER RECOVERY CENTER",font=("Arial",19,"bold"),bg="#2c5282",fg="white",pady=12).pack(fill="x")
        tk.Label(self,text="Verified backups • safe restore • backup retention",font=("Arial",11),bg="#eef2f7").pack(pady=15)
        for text,cmd in [("CREATE VERIFIED BACKUP",self.backup),("RESTORE FROM BACKUP",self.restore),("OPEN BACKUP FOLDER",self.open_folder)]:
            tk.Button(self,text=text,font=("Arial",11,"bold"),width=30,height=2,command=cmd).pack(pady=7)
        self.status=tk.Label(self,text="",bg="#eef2f7",justify="left");self.status.pack(pady=12)
    def refresh(self):
        files=sorted(glob.glob(os.path.join(BACKUP_DIR,"*.db")),key=os.path.getmtime,reverse=True) if os.path.isdir(BACKUP_DIR) else []
        good=sum(verify_database(x) for x in files[:20]);self.status.config(text=f"Backups found: {len(files)}\nVerified recent backups: {good}\nAutomatic backups are retained by the existing POS backup system.")
    def backup(self):
        try:p=make_backup();self.refresh();messagebox.showinfo("Backup",f"Verified backup created:\n{p}",parent=self)
        except Exception as e:messagebox.showerror("Backup",str(e),parent=self)
    def restore(self):
        p=filedialog.askopenfilename(title="Select POS backup",initialdir=BACKUP_DIR,filetypes=[("Database","*.db")])
        if not p:return
        if not verify_database(p):messagebox.showerror("Restore","This backup failed integrity verification.",parent=self);return
        if not messagebox.askyesno("Confirm Restore","The POS database will be replaced. A safety backup will be created first.\n\nContinue?",parent=self):return
        try:
            safety=restore_database(p,DB_NAME,os.path.join(BACKUP_DIR,f"pos_store_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"));self.refresh();messagebox.showinfo("Restore",f"Restore completed.\nSafety backup:\n{safety}\n\nRestart the POS after restoring.",parent=self)
        except Exception as e:messagebox.showerror("Restore",str(e),parent=self)
    def open_folder(self):
        os.makedirs(BACKUP_DIR,exist_ok=True);os.startfile(BACKUP_DIR)

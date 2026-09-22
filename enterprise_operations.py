"""Phase 5 Enterprise Operations & Resilience control center.

Read-only operational diagnostics plus safe, verified backup creation.  The
module intentionally does not post sales, stock, accounting, or audit changes.
"""
from __future__ import annotations

import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from core.config import DB_PATH, BACKUP_DIR
from services.production_hardening import integrity_check, backup_database, prune_backups


def database_snapshot(path=DB_PATH):
    """Return lightweight, read-only database health metrics."""
    if not os.path.isfile(path):
        return {"exists": False, "integrity": False, "size_bytes": 0, "tables": 0,
                "sales": 0, "users": 0, "branches": 0}
    result = {"exists": True, "integrity": integrity_check(path),
              "size_bytes": os.path.getsize(path), "tables": 0,
              "sales": 0, "users": 0, "branches": 0}
    con = sqlite3.connect(path)
    try:
        result["tables"] = con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        for key, table in (("sales", "sales_history"), ("users", "users"), ("branches", "branches")):
            try:
                result[key] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.DatabaseError:
                result[key] = 0
    finally:
        con.close()
    return result


def backup_snapshot(directory=BACKUP_DIR):
    """Return backup count, newest timestamp and verified count."""
    if not os.path.isdir(directory):
        return {"count": 0, "verified": 0, "newest": None}
    files = sorted((os.path.join(directory, n) for n in os.listdir(directory)
                    if n.lower().endswith(".db") and os.path.isfile(os.path.join(directory, n))),
                   key=os.path.getmtime, reverse=True)
    verified = sum(1 for p in files[:20] if integrity_check(p))
    newest = datetime.fromtimestamp(os.path.getmtime(files[0])).strftime("%Y-%m-%d %H:%M:%S") if files else None
    return {"count": len(files), "verified": verified, "newest": newest}


def audit_snapshot(path=DB_PATH):
    """Return recent audit activity and counts of sensitive actions."""
    result = {"events": 0, "today": 0, "voids": 0, "transfers": 0, "log_available": False}
    if not os.path.isfile(path):
        return result
    con = sqlite3.connect(path)
    try:
        try:
            result["log_available"] = True
            result["events"] = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
            result["today"] = con.execute("SELECT COUNT(*) FROM audit_log WHERE date(timestamp)=date('now')").fetchone()[0]
            result["voids"] = con.execute("SELECT COUNT(*) FROM audit_log WHERE upper(action) LIKE '%VOID%'").fetchone()[0]
            result["transfers"] = con.execute("SELECT COUNT(*) FROM audit_log WHERE upper(action) LIKE '%TRANSFER%'").fetchone()[0]
        except sqlite3.DatabaseError:
            result["log_available"] = False
    finally:
        con.close()
    return result


def operational_exceptions(path=DB_PATH):
    """Find high-value read-only exceptions requiring management attention."""
    issues = []
    if not os.path.isfile(path):
        return ["Database file is missing."]
    con = sqlite3.connect(path)
    try:
        checks = [
            ("negative_stock", "SELECT COUNT(*) FROM products WHERE COALESCE(soh,0) < 0", "product(s) have negative stock"),
            ("inactive_users", "SELECT COUNT(*) FROM users WHERE COALESCE(active,1)=0", "inactive user account(s) exist"),
        ]
        for _, sql, msg in checks:
            try:
                count = int(con.execute(sql).fetchone()[0] or 0)
                if count: issues.append(f"{count} {msg}.")
            except sqlite3.DatabaseError:
                continue
        try:
            orphan = int(con.execute("SELECT COUNT(*) FROM sale_items si LEFT JOIN sales_history sh ON sh.id=si.sale_id WHERE sh.id IS NULL").fetchone()[0])
            if orphan: issues.append(f"{orphan} orphan sale-item row(s).")
        except sqlite3.DatabaseError:
            issues.append("Sale-item relationship check unavailable.")
    finally:
        con.close()
    return issues


class EnterpriseOperationsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("BKPOS Enterprise Operations & Resilience")
        self.geometry("1080x680")
        self.minsize(900, 580)
        self.configure(bg="#eef2f7")
        self.transient(parent)
        self.grab_set()
        self._build()
        self.refresh()

    def _build(self):
        tk.Label(self, text="ENTERPRISE OPERATIONS & RESILIENCE", font=("Arial", 19, "bold"),
                 bg="#2c5282", fg="white", pady=12).pack(fill="x")
        tk.Label(self, text="System health • backup verification • audit activity • operational exceptions",
                 bg="#eef2f7", font=("Arial", 10)).pack(pady=10)
        bar = tk.Frame(self, bg="#eef2f7")
        bar.pack(fill="x", padx=15)
        for text, cmd in (("REFRESH", self.refresh), ("CREATE VERIFIED BACKUP", self.create_backup), ("OPEN DISASTER RECOVERY", self.open_dr)):
            tk.Button(bar, text=text, command=cmd, font=("Arial", 10, "bold")).pack(side="left", padx=4)
        self.tree = ttk.Treeview(self, columns=("area", "metric", "value", "status"), show="headings")
        for c, h, w in (("area", "Area", 220), ("metric", "Metric", 300), ("value", "Value", 180), ("status", "Status", 180)):
            self.tree.heading(c, text=h); self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=15, pady=12)
        self.summary = tk.Label(self, text="", bg="#eef2f7", font=("Arial", 11, "bold"), anchor="w")
        self.summary.pack(fill="x", padx=15, pady=(0, 12))

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        db = database_snapshot()
        bk = backup_snapshot()
        au = audit_snapshot()
        issues = operational_exceptions()
        rows = [
            ("Database", "Integrity", "PASS" if db["integrity"] else "CHECK", "READY" if db["integrity"] else "CHECK"),
            ("Database", "Size", f"{db['size_bytes']/1024/1024:.2f} MB", "INFO"),
            ("Database", "Tables", db["tables"], "INFO"),
            ("Database", "Recorded sales", db["sales"], "INFO"),
            ("Backups", "Backup files", bk["count"], "READY" if bk["count"] else "ACTION NEEDED"),
            ("Backups", "Verified recent backups", bk["verified"], "READY" if bk["verified"] else "ACTION NEEDED"),
            ("Backups", "Newest backup", bk["newest"] or "None", "INFO"),
            ("Audit", "Total events", au["events"], "READY" if au["log_available"] else "CHECK"),
            ("Audit", "Today's events", au["today"], "INFO"),
            ("Audit", "Voids recorded", au["voids"], "INFO"),
            ("Audit", "Transfers recorded", au["transfers"], "INFO"),
            ("Exceptions", "Management exceptions", len(issues), "READY" if not issues else "REVIEW"),
        ]
        for row in rows: self.tree.insert("", "end", values=row)
        self.summary.config(text="SYSTEM STATUS: " + ("READY" if db["integrity"] and not issues else "REVIEW NEEDED") +
                            f"   |   Exceptions: {len(issues)}")

    def create_backup(self):
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target = os.path.join(BACKUP_DIR, f"pos_store_phase5_{stamp}.db")
            backup_database(DB_PATH, target)
            prune_backups(BACKUP_DIR, keep=30)
            self.refresh()
            messagebox.showinfo("Backup", f"Verified backup created:\n{target}", parent=self)
        except Exception as exc:
            messagebox.showerror("Backup", str(exc), parent=self)

    def open_dr(self):
        try:
            from disaster_recovery import DisasterRecoveryWindow
            DisasterRecoveryWindow(self.parent)
        except Exception as exc:
            messagebox.showerror("Disaster Recovery", str(exc), parent=self)

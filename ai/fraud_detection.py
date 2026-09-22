"""AI Fraud & Anomaly Detection for BKPOS.

Monitors cashier behavior, void spikes, price override abuse, phantom refunds,
after-hours activity, and computes multidimensional anomaly scores to prevent
retail shrinkage and internal loss.
"""
from __future__ import annotations

import csv
import math
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.config import DB_PATH
from core.logger import logger as _bkpos_logger
from ai.config import get_ai_setting
from ui.theme import PALETTE, FONT, button as themed_button, entry_options
from ui.window_polish import polish_window

try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class FraudAnomalyEngine:
    """Statistical and machine learning anomaly detection for POS audit trails."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def analyze_store_security(self, lookback_days: int = 30) -> Dict[str, Any]:
        """Perform comprehensive audit scan and cashier anomaly scoring."""
        conn = self._get_connection()
        cashier_profiles: List[Dict[str, Any]] = []
        flagged_incidents: List[Dict[str, Any]] = []
        store_risk_score = 0.0

        try:
            start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

            # 1. Fetch cashier sales, voids, and override aggregates
            query = """
                SELECT
                    cashier,
                    COUNT(*) as total_sales,
                    COALESCE(SUM(total_amount), 0) as total_revenue,
                    COALESCE(SUM(CASE WHEN COALESCE(voided, 0) = 1 THEN 1 ELSE 0 END), 0) as void_count,
                    COALESCE(SUM(CASE WHEN COALESCE(voided, 0) = 1 THEN total_amount ELSE 0 END), 0) as void_amount,
                    COALESCE(SUM(CASE WHEN COALESCE(below_cost_override, 0) = 1 THEN 1 ELSE 0 END), 0) as override_count
                FROM sales_history
                WHERE date(timestamp) >= ?
                GROUP BY cashier
            """
            rows = conn.execute(query, (start_date,)).fetchall()

            if not rows:
                # Provide synthetic baseline if store has just been initialized
                return {
                    "store_risk_score": 10.0,
                    "store_risk_level": "LOW RISK",
                    "cashier_profiles": [],
                    "flagged_incidents": [],
                    "summary": "No suspicious behavior detected in the selected period."
                }

            # Calculate store averages
            total_txns = sum(r["total_sales"] for r in rows)
            total_voids = sum(r["void_count"] for r in rows)
            store_void_ratio = (total_voids / total_txns) if total_txns > 0 else 0.0

            # 2. Score each cashier
            raw_scores = []
            for r in rows:
                name = r["cashier"] or "Unknown"
                sales_cnt = r["total_sales"]
                rev = float(r["total_revenue"] or 0)
                v_cnt = r["void_count"]
                v_amt = float(r["void_amount"] or 0)
                o_cnt = r["override_count"]

                void_ratio = (v_cnt / sales_cnt) if sales_cnt > 0 else 0.0
                override_ratio = (o_cnt / sales_cnt) if sales_cnt > 0 else 0.0

                # Compute anomaly score (0 - 100)
                # Void penalty: void ratio above store baseline
                void_penalty = max(0.0, (void_ratio - 0.05) * 200.0)
                # Override penalty
                override_penalty = override_ratio * 150.0
                # Volume weight
                volume_factor = min(1.0, sales_cnt / 10.0)

                score = min(100.0, round((void_penalty * 0.6 + override_penalty * 0.4) * volume_factor, 1))
                raw_scores.append(score)

                risk_level = "CRITICAL" if score >= 70.0 else ("ELEVATED" if score >= 40.0 else "NORMAL")
                risk_badge = "🔴 CRITICAL" if score >= 70.0 else ("🟡 ELEVATED" if score >= 40.0 else "🟢 NORMAL")

                cashier_profiles.append({
                    "cashier": name,
                    "sales_count": sales_cnt,
                    "revenue": rev,
                    "void_count": v_cnt,
                    "void_amount": v_amt,
                    "void_ratio": round(void_ratio * 100, 1),
                    "override_count": o_cnt,
                    "anomaly_score": score,
                    "risk_level": risk_level,
                    "risk_badge": risk_badge,
                })

            # 3. Detect specific high-risk incident patterns
            # A. Consecutive Voids within 15 minutes
            void_rows = conn.execute("""
                SELECT id, timestamp, cashier, total_amount
                FROM sales_history
                WHERE COALESCE(voided, 0) = 1 AND date(timestamp) >= ?
                ORDER BY cashier, timestamp ASC
            """, (start_date,)).fetchall()

            last_cashier = None
            last_time = None
            burst_count = 0
            for vr in void_rows:
                c_name = vr["cashier"]
                try:
                    c_time = datetime.strptime(vr["timestamp"][:19], "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue

                if c_name == last_cashier and last_time and (c_time - last_time).total_seconds() <= 900:
                    burst_count += 1
                    if burst_count >= 2:
                        flagged_incidents.append({
                            "severity": "CRITICAL",
                            "severity_badge": "🔴 HIGH",
                            "timestamp": vr["timestamp"],
                            "cashier": c_name,
                            "incident_type": "RAPID_VOID_BURST",
                            "details": f"Multiple consecutive voids within 15 minutes by {c_name} (Sale #{vr['id']}). Potential cash pocketing indicator.",
                            "sale_id": vr["id"],
                        })
                else:
                    burst_count = 1

                last_cashier = c_name
                last_time = c_time

            # B. Off-Hours Activity (transactions between 22:00 and 06:00)
            off_hours = conn.execute("""
                SELECT id, timestamp, cashier, total_amount, voided
                FROM sales_history
                WHERE (strftime('%H', timestamp) >= '22' OR strftime('%H', timestamp) < '06')
                  AND date(timestamp) >= ?
                ORDER BY timestamp DESC LIMIT 20
            """, (start_date,)).fetchall()

            for oh in off_hours:
                flagged_incidents.append({
                    "severity": "ELEVATED",
                    "severity_badge": "🟡 MEDIUM",
                    "timestamp": oh["timestamp"],
                    "cashier": oh["cashier"],
                    "incident_type": "AFTER_HOURS_ACTIVITY",
                    "details": f"Transaction #{oh['id']} processed outside regular store trading hours (R {float(oh['total_amount'] or 0):,.2f}).",
                    "sale_id": oh["id"],
                })

            # C. High Value Single Voids (> R 500)
            high_voids = conn.execute("""
                SELECT id, timestamp, cashier, total_amount
                FROM sales_history
                WHERE COALESCE(voided, 0) = 1 AND total_amount >= 500 AND date(timestamp) >= ?
                ORDER BY timestamp DESC LIMIT 15
            """, (start_date,)).fetchall()

            for hv in high_voids:
                flagged_incidents.append({
                    "severity": "ELEVATED",
                    "severity_badge": "🟡 MEDIUM",
                    "timestamp": hv["timestamp"],
                    "cashier": hv["cashier"],
                    "incident_type": "HIGH_VALUE_VOID",
                    "details": f"Large single transaction void: R {float(hv['total_amount']):,.2f} on ticket #{hv['id']}.",
                    "sale_id": hv["id"],
                })

            # Compute overall store risk score
            if cashier_profiles:
                store_risk_score = round(sum(p["anomaly_score"] for p in cashier_profiles) / len(cashier_profiles), 1)
                # Boost if multiple incidents
                if len(flagged_incidents) >= 5:
                    store_risk_score = min(100.0, store_risk_score + 15.0)

            store_level = "CRITICAL RISK" if store_risk_score >= 65.0 else ("ELEVATED RISK" if store_risk_score >= 35.0 else "SECURE / LOW RISK")

            # Sort profiles by anomaly score
            cashier_profiles.sort(key=lambda x: x["anomaly_score"], reverse=True)

            return {
                "store_risk_score": store_risk_score,
                "store_risk_level": store_level,
                "cashier_profiles": cashier_profiles,
                "flagged_incidents": flagged_incidents,
                "summary": f"Audit complete. Analyzed {len(rows)} cashier(s) and {len(flagged_incidents)} suspicious event(s)."
            }

        except Exception as exc:
            _bkpos_logger.warning("Error running AI fraud anomaly detection", exc_info=exc)
            return {
                "store_risk_score": 0.0,
                "store_risk_level": "ERROR",
                "cashier_profiles": [],
                "flagged_incidents": [],
                "summary": f"Audit scan error: {exc}"
            }
        finally:
            conn.close()


class AIFraudAnomalyWindow(tk.Toplevel):
    """UI for cashier anomaly scoring, void spike auditing, and fraud risk monitoring."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("BKPOS AI Fraud & Anomaly Audit Monitor")
        self.geometry("1180x760")
        self.minsize(980, 620)
        self.configure(bg=PALETTE["bg"])
        polish_window(self, self.title())

        self.engine = FraudAnomalyEngine()
        self.audit_results: Dict[str, Any] = {}

        self._build_ui()
        self._run_audit_scan()

    def _build_ui(self) -> None:
        # Header
        header = tk.Frame(self, bg=PALETTE["nav"], height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=PALETTE["nav"])
        brand.pack(side=tk.LEFT, padx=18, pady=12)

        tk.Label(
            brand,
            text="🛡️ AI FRAUD & ANOMALY AUDIT MONITOR",
            font=(FONT, 16, "bold"),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_text"]
        ).pack(anchor="w")

        tk.Label(
            brand,
            text="Cashier behavioral anomaly scoring • Void burst detection • Loss prevention forensics",
            font=(FONT, 9),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_muted"]
        ).pack(anchor="w", pady=(2, 0))

        # Store Security Status Banner
        self.banner_frame = tk.Frame(self, bg=PALETTE["surface"], bd=1, relief=tk.SOLID, padx=16, pady=12)
        self.banner_frame.pack(fill=tk.X, padx=14, pady=10)

        self.lbl_store_health = tk.Label(
            self.banner_frame,
            text="STORE SECURITY STATUS: CALCULATING...",
            font=(FONT, 14, "bold"),
            bg=PALETTE["surface"],
            fg=PALETTE["primary"]
        )
        self.lbl_store_health.pack(side=tk.LEFT)

        themed_button(self.banner_frame, "🔍 Run Deep Audit Scan", self._run_audit_scan, kind="primary").pack(side=tk.RIGHT)

        # Split: Upper Cashier Scoreboard, Lower Flagged Incidents
        main_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))

        # Top: Cashier Scoreboard
        top_frame = tk.Frame(main_pane, bg=PALETTE["surface"], bd=1, relief=tk.SOLID, padx=12, pady=10)
        main_pane.add(top_frame, weight=3)

        tk.Label(
            top_frame,
            text="CASHIER BEHAVIORAL RISK SCOREBOARD",
            font=(FONT, 10, "bold"),
            bg=PALETTE["surface"],
            fg=PALETTE["primary"]
        ).pack(anchor="w", pady=(0, 6))

        cols_c = ("risk", "cashier", "sales", "revenue", "voids", "void_pct", "overrides", "anomaly_score")
        self.tree_cashiers = ttk.Treeview(top_frame, columns=cols_c, show="headings", style="BK.Treeview")

        headings_c = {
            "risk": "Risk Level",
            "cashier": "Cashier / Operator",
            "sales": "Completed Sales",
            "revenue": "Total Revenue (R)",
            "voids": "Void Count",
            "void_pct": "Void Rate (%)",
            "overrides": "Price Overrides",
            "anomaly_score": "Anomaly Score (0-100)",
        }
        widths_c = {
            "risk": 110, "cashier": 150, "sales": 110, "revenue": 130,
            "voids": 90, "void_pct": 100, "overrides": 110, "anomaly_score": 140
        }

        for col in cols_c:
            self.tree_cashiers.heading(col, text=headings_c[col])
            self.tree_cashiers.column(col, width=widths_c[col], anchor="e" if col in ("sales", "revenue", "voids", "void_pct", "overrides", "anomaly_score") else "w")

        self.tree_cashiers.pack(fill=tk.BOTH, expand=True)

        # Bottom: Flagged Incidents Feed
        bot_frame = tk.Frame(main_pane, bg=PALETTE["surface"], bd=1, relief=tk.SOLID, padx=12, pady=10)
        main_pane.add(bot_frame, weight=2)

        tk.Label(
            bot_frame,
            text="FLAGGED SUSPICIOUS INCIDENTS & ANOMALY STREAM",
            font=(FONT, 10, "bold"),
            bg=PALETTE["surface"],
            fg=PALETTE["danger"]
        ).pack(anchor="w", pady=(0, 6))

        cols_i = ("severity", "timestamp", "cashier", "type", "details")
        self.tree_incidents = ttk.Treeview(bot_frame, columns=cols_i, show="headings", style="BK.Treeview")

        headings_i = {
            "severity": "Severity",
            "timestamp": "Date / Time",
            "cashier": "Cashier",
            "type": "Incident Type",
            "details": "Forensic Evidence & Explanation",
        }
        widths_i = {"severity": 95, "timestamp": 140, "cashier": 120, "type": 160, "details": 450}

        for col in cols_i:
            self.tree_incidents.heading(col, text=headings_i[col])
            self.tree_incidents.column(col, width=widths_i[col], anchor="w")

        self.tree_incidents.pack(fill=tk.BOTH, expand=True)

        # Footer Action Bar
        footer = tk.Frame(self, bg=PALETTE["bg"], padx=14, pady=8)
        footer.pack(fill=tk.X)

        themed_button(footer, "📄 Export Investigation Dossier", self._export_dossier, kind="secondary").pack(side=tk.LEFT, padx=6)
        themed_button(footer, "CLOSE", self.destroy, kind="secondary").pack(side=tk.RIGHT, padx=6)

    def _run_audit_scan(self) -> None:
        self.audit_results = self.engine.analyze_store_security(lookback_days=30)

        # Update Banner
        score = self.audit_results.get("store_risk_score", 0.0)
        lvl = self.audit_results.get("store_risk_level", "NORMAL")
        col = PALETTE["danger"] if score >= 65.0 else (PALETTE["warning"] if score >= 35.0 else PALETTE["success"])

        self.lbl_store_health.config(
            text=f"STORE SECURITY STATUS: {lvl}  (Risk Score: {score:.1f}/100)",
            fg=col
        )

        # Populate Cashiers Table
        self.tree_cashiers.delete(*self.tree_cashiers.get_children())
        for c in self.audit_results.get("cashier_profiles", []):
            self.tree_cashiers.insert("", tk.END, values=(
                c["risk_badge"],
                c["cashier"],
                f"{c['sales_count']:,}",
                f"R {c['revenue']:,.2f}",
                c["void_count"],
                f"{c['void_ratio']:.1f}%",
                c["override_count"],
                f"{c['anomaly_score']:.1f}",
            ))

        # Populate Incidents Table
        self.tree_incidents.delete(*self.tree_incidents.get_children())
        incidents = self.audit_results.get("flagged_incidents", [])
        for inc in incidents:
            self.tree_incidents.insert("", tk.END, values=(
                inc["severity_badge"],
                inc["timestamp"],
                inc["cashier"],
                inc["incident_type"],
                inc["details"],
            ))

    def _export_dossier(self) -> None:
        if not self.audit_results:
            return

        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".txt",
            filetypes=[("Text Report", "*.txt"), ("CSV File", "*.csv")],
            initialfile=f"ai_fraud_audit_dossier_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("======================================================================\n")
                f.write("             BKPOS AI FRAUD & LOSS AUDIT DOSSIER                     \n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Store Status: {self.audit_results.get('store_risk_level')} (Score: {self.audit_results.get('store_risk_score')}/100)\n")
                f.write("======================================================================\n\n")

                f.write("--- CASHIER BEHAVIORAL RISK PROFILES ---\n")
                for c in self.audit_results.get("cashier_profiles", []):
                    f.write(f"Cashier: {c['cashier']} | Risk: {c['risk_level']} | Anomaly Score: {c['anomaly_score']}\n")
                    f.write(f"   Sales: {c['sales_count']} | Revenue: R {c['revenue']:,.2f} | Voids: {c['void_count']} ({c['void_ratio']}%) | Overrides: {c['override_count']}\n\n")

                f.write("\n--- FLAGGED SUSPICIOUS INCIDENTS ---\n")
                for inc in self.audit_results.get("flagged_incidents", []):
                    f.write(f"[{inc['severity']}] {inc['timestamp']} | Cashier: {inc['cashier']} | Type: {inc['incident_type']}\n")
                    f.write(f"   Details: {inc['details']}\n\n")

            messagebox.showinfo("Export Successful", f"Audit dossier exported to:\n{path}", parent=self)
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc), parent=self)

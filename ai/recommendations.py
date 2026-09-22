"""AI Market Basket & Upsell Engine for BKPOS.

Provides:
- MarketBasketEngine: Association rule mining (co-occurrence frequency, confidence, lift)
- Default high-margin convenience & grocery pairing rules
- Real-time basket recommendation querying for checkout cashiers
- UpsellManagementWindow: Interactive rule manager and offline association mining
"""
from __future__ import annotations

from collections import defaultdict
import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, List, Optional, Tuple

from core.config import DB_PATH
from core.logger import logger as _bkpos_logger
from ui.theme import PALETTE, FONT, button as themed_button
from ui.window_polish import polish_window

# Default supermarket seed pairs (antecedent_barcode, consequent_barcode, reason, confidence, lift)
DEFAULT_SUPERMARKET_RULES: List[Tuple[str, str, str, float, float]] = [
    ("1001", "1002", "Customers buying milk frequently need sandwich bread", 0.78, 2.4),
    ("1002", "1003", "Offer butter with freshly sliced bread", 0.65, 2.1),
    ("1002", "1004", "Cross-sell sweet strawberry jam with sandwich bread", 0.52, 1.8),
    ("1005", "1006", "Offer brown sugar sweetener with roasted coffee", 0.71, 2.3),
    ("1001", "1005", "Suggest premium roasted coffee with fresh milk", 0.45, 1.6),
    ("1007", "1003", "Butter pairs with bulk rice and side preparations", 0.42, 1.5),
]


class MarketBasketEngine:
    """Mines purchase affinity associations and returns smart checkout upsells."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS upsell_rules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        antecedent_barcode TEXT NOT NULL,
                        antecedent_name TEXT,
                        consequent_barcode TEXT NOT NULL,
                        consequent_name TEXT,
                        confidence REAL NOT NULL,
                        lift REAL NOT NULL,
                        support REAL NOT NULL,
                        reason TEXT DEFAULT 'Frequently bought together',
                        is_active INTEGER DEFAULT 1,
                        is_custom INTEGER DEFAULT 0,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(antecedent_barcode, consequent_barcode)
                    )
                """)
                count = conn.execute("SELECT COUNT(*) FROM upsell_rules").fetchone()[0]
                if count == 0:
                    for a_code, c_code, reason, conf, lift in DEFAULT_SUPERMARKET_RULES:
                        conn.execute("""
                            INSERT OR IGNORE INTO upsell_rules
                            (antecedent_barcode, consequent_barcode, confidence, lift, support, reason, is_active, is_custom)
                            VALUES (?, ?, ?, ?, 0.15, ?, 1, 0)
                        """, (a_code, c_code, conf, lift, reason))
                    conn.commit()
        except Exception as exc:
            _bkpos_logger.warning("Error ensuring upsell_rules schema", exc_info=exc)

    def mine_rules_from_sales(
        self,
        min_support: float = 0.02,
        min_confidence: float = 0.25,
        min_support_count: Optional[int] = None
    ) -> int:
        """Mine association rules from historical sales transactions."""
        conn = self._get_connection()
        rules_found = 0
        try:
            # Check which items table exists (sale_items or sales_items)
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            items_table = "sale_items" if "sale_items" in tables else ("sales_items" if "sales_items" in tables else None)
            if not items_table:
                return 0

            # Inspect columns of items table
            cols = [c[1] for c in conn.execute(f"PRAGMA table_info({items_table})").fetchall()]
            barcode_col = "barcode" if "barcode" in cols else "product_code"

            # Query sales items grouped by sale_id
            rows = conn.execute(f"""
                SELECT si.sale_id, si.{barcode_col} as barcode, si.description
                FROM {items_table} si
                JOIN sales_history s ON (s.id = si.sale_id OR s.sale_id = si.sale_id)
                WHERE COALESCE(s.voided, 0) = 0
                ORDER BY si.sale_id
            """).fetchall()

            baskets: Dict[Any, List[Tuple[str, str]]] = defaultdict(list)
            item_names: Dict[str, str] = {}
            item_counts: Dict[str, int] = defaultdict(int)

            for r in rows:
                sid = r["sale_id"]
                code = str(r["barcode"])
                name = r["description"] or code
                item_names[code] = name
                baskets[sid].append((code, name))
                item_counts[code] += 1

            total_baskets = len(baskets)
            if total_baskets < 2:
                return 0

            if min_support_count is not None:
                min_support = min_support_count / total_baskets

            # Count pairs
            pair_counts: Dict[Tuple[str, str], int] = defaultdict(int)
            for items in baskets.values():
                unique_codes = list(set(code for code, _ in items))
                for i in range(len(unique_codes)):
                    for j in range(len(unique_codes)):
                        if i != j:
                            pair_counts[(unique_codes[i], unique_codes[j])] += 1

            # Generate rules
            for (a_code, c_code), pair_freq in pair_counts.items():
                supp = pair_freq / total_baskets
                if supp < min_support:
                    continue

                a_freq = item_counts[a_code]
                c_freq = item_counts[c_code]
                conf = pair_freq / max(1, a_freq)
                lift = (conf / (c_freq / total_baskets)) if c_freq > 0 else 1.0

                if conf >= min_confidence and lift >= 1.0:
                    conn.execute("""
                        INSERT INTO upsell_rules
                        (antecedent_barcode, antecedent_name, consequent_barcode, consequent_name, confidence, lift, support, reason, is_active, is_custom)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'Frequently bought together based on store sales', 1, 0)
                        ON CONFLICT(antecedent_barcode, consequent_barcode) DO UPDATE SET
                            confidence = excluded.confidence,
                            lift = excluded.lift,
                            support = excluded.support,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        a_code, item_names.get(a_code, a_code),
                        c_code, item_names.get(c_code, c_code),
                        round(conf, 2), round(lift, 2), round(supp, 2)
                    ))
                    rules_found += 1

            conn.commit()
        except Exception as exc:
            _bkpos_logger.warning("Error mining association rules from sales", exc_info=exc)
        finally:
            conn.close()

        return rules_found

    def get_recommendations(self, cart_barcodes: List[str], limit: int = 3) -> List[Dict[str, Any]]:
        """Given barcodes currently in the cashier cart, return the highest-value upsell items."""
        if not cart_barcodes:
            return []

        conn = self._get_connection()
        try:
            cart_str = [str(c) for c in cart_barcodes if c]
            if not cart_str:
                return []

            placeholders = ",".join("?" for _ in cart_str)
            # Inspect products columns for price/selling_price
            p_cols = [c[1] for c in conn.execute("PRAGMA table_info(products)").fetchall()] if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'").fetchone() else []
            price_col = "selling_price" if "selling_price" in p_cols else ("price" if "price" in p_cols else "0")
            cost_col = "cost_price" if "cost_price" in p_cols else "0"

            query = f"""
                SELECT r.consequent_barcode,
                       COALESCE(p.description, r.consequent_name) as name,
                       COALESCE(p.{price_col}, 0) as price,
                       COALESCE(p.{cost_col}, 0) as cost,
                       r.confidence, r.lift, r.reason,
                       COALESCE(p.soh, 0) as soh
                FROM upsell_rules r
                LEFT JOIN products p ON p.barcode = r.consequent_barcode
                WHERE r.antecedent_barcode IN ({placeholders})
                  AND r.is_active = 1
                  AND r.consequent_barcode NOT IN ({placeholders})
                ORDER BY r.lift DESC, r.confidence DESC
                LIMIT ?
            """
            rows = conn.execute(query, cart_str + cart_str + [limit]).fetchall()
            results = []
            for row in rows:
                results.append({
                    "barcode": row["consequent_barcode"],
                    "code": row["consequent_barcode"],
                    "name": row["name"] or row["consequent_barcode"],
                    "price": float(row["price"] or 0),
                    "cost": float(row["cost"] or 0),
                    "confidence": float(row["confidence"] or 0),
                    "lift": float(row["lift"] or 0),
                    "reason": row["reason"] or "Frequently bought together",
                    "soh": float(row["soh"] or 0),
                })
            return results
        except Exception as exc:
            _bkpos_logger.warning("Error querying upsell recommendations", exc_info=exc)
            return []
        finally:
            conn.close()

    def get_recommendation(self, cart_barcodes: List[str]) -> Optional[Dict[str, Any]]:
        """Return the top upsell recommendation or None."""
        recs = self.get_recommendations(cart_barcodes, limit=1)
        return recs[0] if recs else None

    def get_all_rules(self) -> List[Dict[str, Any]]:
        """Retrieve all active and inactive association rules."""
        conn = self._get_connection()
        try:
            rows = conn.execute("""
                SELECT id, antecedent_barcode, antecedent_name,
                       consequent_barcode, consequent_name,
                       confidence, lift, support, reason, is_active, is_custom
                FROM upsell_rules
                ORDER BY lift DESC, confidence DESC
            """).fetchall()
            return [
                {
                    "id": r["id"],
                    "antecedent_barcode": r["antecedent_barcode"],
                    "trigger_barcode": r["antecedent_barcode"],
                    "antecedent_name": r["antecedent_name"] or r["antecedent_barcode"],
                    "consequent_barcode": r["consequent_barcode"],
                    "recommended_barcode": r["consequent_barcode"],
                    "consequent_name": r["consequent_name"] or r["consequent_barcode"],
                    "confidence": float(r["confidence"] or 0),
                    "lift": float(r["lift"] or 0),
                    "support": float(r["support"] or 0),
                    "reason": r["reason"] or "",
                    "is_active": bool(r["is_active"]),
                    "is_custom": bool(r["is_custom"]),
                }
                for r in rows
            ]
        finally:
            conn.close()

    def add_custom_rule(
        self,
        trigger_code: str,
        rec_code: str,
        confidence: float = 0.8,
        lift: float = 2.0,
        message: str = "Frequently bought together",
        trigger_name: str = "",
        rec_name: str = ""
    ) -> int:
        """Insert or update a custom cross-sell rule."""
        conn = self._get_connection()
        try:
            if not trigger_name:
                row = conn.execute("SELECT description FROM products WHERE barcode = ?", (trigger_code,)).fetchone()
                trigger_name = row[0] if row else trigger_code
            if not rec_name:
                row = conn.execute("SELECT description FROM products WHERE barcode = ?", (rec_code,)).fetchone()
                rec_name = row[0] if row else rec_code

            cur = conn.execute("""
                INSERT INTO upsell_rules
                (antecedent_barcode, antecedent_name, consequent_barcode, consequent_name,
                 confidence, lift, support, reason, is_active, is_custom)
                VALUES (?, ?, ?, ?, ?, ?, 0.20, ?, 1, 1)
                ON CONFLICT(antecedent_barcode, consequent_barcode) DO UPDATE SET
                    confidence = excluded.confidence,
                    lift = excluded.lift,
                    reason = excluded.reason,
                    is_active = 1,
                    is_custom = 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (trigger_code, trigger_name, rec_code, rec_name, confidence, lift, message))
            conn.commit()
            row = conn.execute(
                "SELECT id FROM upsell_rules WHERE antecedent_barcode = ? AND consequent_barcode = ?",
                (trigger_code, rec_code)
            ).fetchone()
            return int(row[0]) if row else 1
        finally:
            conn.close()

    def toggle_rule_active(self, rule_id: int, active: bool) -> None:
        """Enable or disable a recommendation rule."""
        conn = self._get_connection()
        try:
            conn.execute("UPDATE upsell_rules SET is_active = ? WHERE id = ?", (1 if active else 0, rule_id))
            conn.commit()
        finally:
            conn.close()

    def delete_rule(self, rule_id: int) -> None:
        """Permanently delete an upsell rule."""
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM upsell_rules WHERE id = ?", (rule_id,))
            conn.commit()
        finally:
            conn.close()


class UpsellManagementWindow(tk.Toplevel):
    """Management interface for viewing and configuring AI upsell & cross-sell rules."""

    def __init__(self, parent: tk.Widget, db_path: str = DB_PATH) -> None:
        super().__init__(parent)
        self.parent = parent
        self.db_path = db_path
        self.title("BKPOS AI Market Basket & Upsell Rules")
        self.geometry("1100x680")
        self.minsize(920, 560)
        self.configure(bg=PALETTE["bg"])
        polish_window(self, self.title())

        self.engine = MarketBasketEngine(self.db_path)
        self.search_var = tk.StringVar()
        self._build_ui()
        self._load_rules()

    def _build_ui(self) -> None:
        # Header
        header = tk.Frame(self, bg=PALETTE["nav"], height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=PALETTE["nav"])
        brand.pack(side=tk.LEFT, padx=18, pady=12)

        tk.Label(
            brand,
            text="🛒 AI MARKET BASKET & UP-SELL RULES",
            font=(FONT, 16, "bold"),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_text"]
        ).pack(anchor="w")

        tk.Label(
            brand,
            text="Customer affinity association mining • Frequently bought together rules • Checkout up-selling",
            font=(FONT, 9),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_muted"]
        ).pack(anchor="w", pady=(2, 0))

        # Action Bar with Search
        action_bar = tk.Frame(self, bg=PALETTE["surface_alt"], bd=1, relief=tk.SOLID, padx=14, pady=10)
        action_bar.pack(fill=tk.X, padx=14, pady=10)

        themed_button(action_bar, "🧠 Mine Rules from Sales History", self._run_mining, kind="primary").pack(side=tk.LEFT, padx=(0, 8))
        themed_button(action_bar, "＋ Add Custom Cross-Sell Rule", self._add_custom_rule, kind="success").pack(side=tk.LEFT, padx=4)
        themed_button(action_bar, "🗑️ Delete Selected Rule", self._delete_rule, kind="danger").pack(side=tk.LEFT, padx=4)

        # Search field on right
        search_box = tk.Frame(action_bar, bg=PALETTE["surface_alt"])
        search_box.pack(side=tk.RIGHT, padx=4)
        tk.Label(search_box, text="Filter:", font=(FONT, 9, "bold"), bg=PALETTE["surface_alt"], fg=PALETTE["text"]).pack(side=tk.LEFT, padx=4)
        e_search = tk.Entry(search_box, textvariable=self.search_var, font=(FONT, 9), width=18)
        e_search.pack(side=tk.LEFT, padx=4)
        e_search.bind("<KeyRelease>", lambda e: self._filter_rules())

        # Rules Treeview
        tree_frame = tk.Frame(self, bg=PALETTE["surface"], bd=1, relief=tk.SOLID, padx=10, pady=10)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))

        cols = ("id", "antecedent", "consequent", "confidence", "lift", "reason", "type")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", style="BK.Treeview")

        headings = {
            "id": "#",
            "antecedent": "Trigger Item (When Customer Buys)",
            "consequent": "Recommended Item (Suggest to Customer)",
            "confidence": "Affinity / Confidence",
            "lift": "Lift Factor",
            "reason": "Recommendation Note",
            "type": "Rule Origin",
        }
        widths = {"id": 45, "antecedent": 220, "consequent": 220, "confidence": 120, "lift": 90, "reason": 260, "type": 95}

        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="e" if col in ("confidence", "lift", "id") else "w")

        tree_scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set)

        self.tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

    def _load_rules(self) -> None:
        self.tree.delete(*self.tree.get_children())
        rules = self.engine.get_all_rules()
        q = self.search_var.get().lower().strip()

        for r in rules:
            a_text = f"{r['antecedent_name']} ({r['antecedent_barcode']})"
            c_text = f"{r['consequent_name']} ({r['consequent_barcode']})"
            if q and q not in a_text.lower() and q not in c_text.lower() and q not in r["reason"].lower():
                continue

            r_type = "⭐ CUSTOM" if r["is_custom"] else "🤖 AI MINED"
            self.tree.insert("", tk.END, values=(
                r["id"],
                a_text,
                c_text,
                f"{int(r['confidence'] * 100)}%",
                f"{r['lift']:.2f}x",
                r["reason"],
                r_type
            ))

    def _filter_rules(self) -> None:
        self._load_rules()

    def _run_mining(self) -> None:
        count = self.engine.mine_rules_from_sales()
        messagebox.showinfo(
            "Market Basket Mining Complete",
            f"Successfully analyzed sales transactions and updated {count} association rule(s)!",
            parent=self
        )
        self._load_rules()

    # Alias for programmatic test and menu access
    _mine_rules = _run_mining

    def _add_custom_rule(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("Add Custom Cross-Sell Rule")
        dlg.geometry("500x340")
        dlg.configure(bg=PALETTE["bg"])
        dlg.transient(self)
        dlg.grab_set()

        form = tk.Frame(dlg, bg=PALETTE["surface"], padx=18, pady=16, bd=1, relief=tk.SOLID)
        form.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        tk.Label(form, text="Trigger Item Barcode:", font=(FONT, 9, "bold"), bg=PALETTE["surface"]).grid(row=0, column=0, sticky="w", pady=6)
        e_trigger = tk.Entry(form, font=(FONT, 10), width=28)
        e_trigger.grid(row=0, column=1, sticky="w", pady=6)

        tk.Label(form, text="Recommend Barcode:", font=(FONT, 9, "bold"), bg=PALETTE["surface"]).grid(row=1, column=0, sticky="w", pady=6)
        e_rec = tk.Entry(form, font=(FONT, 10), width=28)
        e_rec.grid(row=1, column=1, sticky="w", pady=6)

        tk.Label(form, text="Confidence (0.1 - 1.0):", font=(FONT, 9, "bold"), bg=PALETTE["surface"]).grid(row=2, column=0, sticky="w", pady=6)
        e_conf = tk.Entry(form, font=(FONT, 10), width=10)
        e_conf.insert(0, "0.75")
        e_conf.grid(row=2, column=1, sticky="w", pady=6)

        tk.Label(form, text="Lift Factor (e.g. 2.0):", font=(FONT, 9, "bold"), bg=PALETTE["surface"]).grid(row=3, column=0, sticky="w", pady=6)
        e_lift = tk.Entry(form, font=(FONT, 10), width=10)
        e_lift.insert(0, "2.10")
        e_lift.grid(row=3, column=1, sticky="w", pady=6)

        tk.Label(form, text="Pitch Note / Reason:", font=(FONT, 9, "bold"), bg=PALETTE["surface"]).grid(row=4, column=0, sticky="w", pady=6)
        e_reason = tk.Entry(form, font=(FONT, 10), width=28)
        e_reason.insert(0, "Recommended complement item")
        e_reason.grid(row=4, column=1, sticky="w", pady=6)

        def _save():
            t_code = e_trigger.get().strip()
            r_code = e_rec.get().strip()
            if not t_code or not r_code:
                messagebox.showerror("Validation Error", "Both trigger and recommended barcodes are required.", parent=dlg)
                return
            try:
                conf = float(e_conf.get().strip() or 0.7)
                lift = float(e_lift.get().strip() or 1.5)
            except ValueError:
                messagebox.showerror("Validation Error", "Confidence and Lift must be valid numbers.", parent=dlg)
                return

            self.engine.add_custom_rule(
                trigger_code=t_code,
                rec_code=r_code,
                confidence=conf,
                lift=lift,
                message=e_reason.get().strip()
            )
            dlg.destroy()
            self._load_rules()

        btn_row = tk.Frame(form, bg=PALETTE["surface"])
        btn_row.grid(row=5, column=0, columnspan=2, pady=16)
        themed_button(btn_row, "Save Cross-Sell Rule", _save, kind="success").pack(side=tk.LEFT, padx=6)
        themed_button(btn_row, "Cancel", dlg.destroy, kind="secondary").pack(side=tk.LEFT, padx=6)

    def _delete_rule(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select Rule", "Please select a rule from the table to delete.", parent=self)
            return

        rule_id = int(self.tree.item(sel[0])["values"][0])
        if messagebox.askyesno("Confirm Delete", f"Delete cross-sell rule #{rule_id}?", parent=self):
            self.engine.delete_rule(rule_id)
            self._load_rules()

"""AI Store Copilot / Natural Language Assistant for BKPOS.

Provides intelligent natural language querying, text-to-SQL translation,
conversational store performance analysis, and automated insights.
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.config import DB_PATH
from core.logger import logger as _bkpos_logger
from ai.config import get_ai_setting, AISettingsDialog
from ui.theme import PALETTE, FONT, button as themed_button, entry_options
from ui.window_polish import polish_window

FORBIDDEN_SQL_PATTERNS = [
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|EXEC|ATTACH|DETACH|PRAGMA)\b",
    r";",  # Prevent multiple chained queries
    r"--",  # Prevent comments that bypass clauses
    r"/\*",
]


class StoreCopilotEngine:
    """Natural Language processing engine for BKPOS store intelligence."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def validate_sql(self, sql: str) -> bool:
        """Strict validation ensuring SQL query is read-only and safe."""
        clean = sql.strip().strip(";").strip()
        upper = clean.upper()

        if not (upper.startswith("SELECT") or upper.startswith("WITH")):
            return False

        for pattern in FORBIDDEN_SQL_PATTERNS:
            if re.search(pattern, upper, re.IGNORECASE):
                return False

        return True

    def process_query(self, user_text: str) -> Dict[str, Any]:
        """Process user text and return conversational answer, SQL, and tabular data."""
        text = user_text.strip().lower()
        if not text:
            return {
                "answer": "Please ask a question regarding your store, inventory, sales, customers, or performance.",
                "sql": "",
                "columns": [],
                "rows": [],
                "total_count": 0,
            }

        # Try rule-based NLP engine first
        result = self._try_rule_based_nlp(text)
        if result is not None:
            return result

        # Check if external LLM provider is configured
        provider = get_ai_setting("llm_provider", "local")
        if provider in ("openai", "anthropic", "ollama"):
            llm_result = self._try_llm_query(user_text, provider)
            if llm_result is not None:
                return llm_result

        # Fallback keyword search
        return self._fallback_keyword_search(user_text)

    def _try_rule_based_nlp(self, text: str) -> Optional[Dict[str, Any]]:
        """Intelligent pattern-matching engine covering core retail POS workflows."""
        conn = self._get_connection()
        try:
            # 1. Low stock / Out of stock / Reorder items
            if any(k in text for k in ["low stock", "out of stock", "reorder", "stockout", "shortage"]):
                threshold = 10
                m = re.search(r"under\s+(\d+)|below\s+(\d+)|less than\s+(\d+)", text)
                if m:
                    threshold = int(m.group(1) or m.group(2) or m.group(3))

                sql = (
                    "SELECT barcode, description, soh, selling_price, cost_price, "
                    "COALESCE(category, 'General') as category "
                    "FROM products WHERE COALESCE(active, 1)=1 AND soh <= ? "
                    "ORDER BY soh ASC LIMIT 50"
                )
                cur = conn.execute(sql, (threshold,))
                rows = [list(r) for r in cur.fetchall()]
                cols = ["Barcode", "Product Description", "SOH", "Sell Price", "Cost Price", "Category"]

                if not rows:
                    answer = f"All inventory levels are healthy! No active products currently have stock at or below {threshold} units."
                else:
                    zero_count = sum(1 for r in rows if float(r[2] or 0) <= 0)
                    answer = (
                        f"Found **{len(rows)} products** with stock at or below {threshold} units. "
                        f"⚠️ **{zero_count} items** are completely out of stock."
                    )
                return {"answer": answer, "sql": sql.replace("?", str(threshold)), "columns": cols, "rows": rows, "total_count": len(rows)}

            # 2. Sales / Revenue Today
            if any(k in text for k in ["today's sale", "sales today", "sell today", "today revenue", "today's revenue"]):
                sql = (
                    "SELECT COUNT(*) as txn_count, "
                    "COALESCE(SUM(total_amount), 0) as total_sales, "
                    "COALESCE(SUM(total_cost), 0) as total_cost, "
                    "COALESCE(SUM(total_amount - total_cost), 0) as gross_profit "
                    "FROM sales_history "
                    "WHERE date(timestamp) = date('now', 'localtime') AND COALESCE(voided, 0) = 0"
                )
                row = conn.execute(sql).fetchone()
                txns = int(row["txn_count"] or 0)
                sales = float(row["total_sales"] or 0)
                profit = float(row["gross_profit"] or 0)
                margin = (profit / sales * 100) if sales > 0 else 0.0

                # Also get breakdown by payment type
                p_sql = (
                    "SELECT payment_type, COUNT(*) as count, SUM(total_amount) as total "
                    "FROM sales_history "
                    "WHERE date(timestamp) = date('now', 'localtime') AND COALESCE(voided, 0) = 0 "
                    "GROUP BY payment_type"
                )
                p_rows = [list(r) for r in conn.execute(p_sql).fetchall()]

                answer = (
                    f"**Today's Performance Summary:**\n"
                    f"• **Total Sales:** R {sales:,.2f}\n"
                    f"• **Transactions:** {txns:,}\n"
                    f"• **Gross Profit:** R {profit:,.2f} ({margin:.1f}% margin)\n"
                    f"• **Average Basket:** R {(sales / txns):,.2f}" if txns > 0 else
                    f"No sales recorded yet today."
                )
                return {
                    "answer": answer,
                    "sql": sql,
                    "columns": ["Payment Method", "Transactions", "Total Amount (R)"],
                    "rows": [[r[0], r[1], f"R {float(r[2] or 0):,.2f}"] for r in p_rows],
                    "total_count": txns
                }

            # 3. Top selling / Best sellers / Popular products
            if any(k in text for k in ["top sell", "best seller", "best-selling", "top product", "popular item", "most sold"]):
                limit = 5
                m = re.search(r"top\s+(\d+)", text)
                if m:
                    limit = int(m.group(1))

                sql = (
                    "SELECT si.barcode, si.description, SUM(si.qty) as total_qty, "
                    "ROUND(SUM(si.value), 2) as total_revenue, "
                    "ROUND(SUM(si.value - (si.qty * COALESCE(si.cost_price, 0))), 2) as est_profit "
                    "FROM sale_items si "
                    "JOIN sales_history s ON s.id = si.sale_id "
                    "WHERE COALESCE(s.voided, 0) = 0 "
                    "GROUP BY si.barcode, si.description "
                    "ORDER BY total_qty DESC LIMIT ?"
                )
                rows = [list(r) for r in conn.execute(sql, (limit,)).fetchall()]
                cols = ["Barcode", "Description", "Units Sold", "Total Revenue (R)", "Gross Profit (R)"]

                if rows:
                    top_name = rows[0][1]
                    top_qty = rows[0][2]
                    answer = f"The **#{1} Best Seller** is **{top_name}** with **{top_qty:g} units sold**. Here are the top {len(rows)} products:"
                else:
                    answer = "No sales history records available to rank best-selling products."

                return {"answer": answer, "sql": sql.replace("?", str(limit)), "columns": cols, "rows": rows, "total_count": len(rows)}

            # 4. Debtors / Customer Accounts / Who owes money
            if any(k in text for k in ["debtor", "owe", "outstanding", "unpaid customer", "customer balance"]):
                sql = (
                    "SELECT a.account_number, a.name, a.telephone, "
                    "ROUND(COALESCE(SUM(cat.debit - cat.credit), 0), 2) as balance, "
                    "a.credit_limit "
                    "FROM accounts a "
                    "LEFT JOIN customer_account_transactions cat ON cat.account_id = a.id "
                    "WHERE a.type = 'Customer' AND COALESCE(a.active, 1) = 1 "
                    "GROUP BY a.id, a.account_number, a.name "
                    "HAVING balance > 0 "
                    "ORDER BY balance DESC"
                )
                try:
                    rows = [list(r) for r in conn.execute(sql).fetchall()]
                except sqlite3.OperationalError:
                    # Alternative schema fallback
                    sql = (
                        "SELECT id, name, telephone, balance, credit_limit "
                        "FROM customers WHERE balance > 0 ORDER BY balance DESC"
                    )
                    rows = [list(r) for r in conn.execute(sql).fetchall()]

                cols = ["Account #", "Customer Name", "Contact", "Outstanding Balance (R)", "Credit Limit (R)"]
                total_owed = sum(float(r[3] or 0) for r in rows)

                if rows:
                    answer = (
                        f"There are **{len(rows)} customer accounts** with outstanding balances.\n"
                        f"• **Total Debtors Outstanding:** R {total_owed:,.2f}\n"
                        f"• **Highest Balance:** {rows[0][1]} (R {float(rows[0][3]):,.2f})"
                    )
                else:
                    answer = "Great news! There are currently **no outstanding debtor balances**."

                return {"answer": answer, "sql": sql, "columns": cols, "rows": rows, "total_count": len(rows)}

            # 5. Suppliers / Creditors / Accounts Payable
            if any(k in text for k in ["creditor", "supplier balance", "who we owe", "accounts payable"]):
                sql = (
                    "SELECT a.account_number, a.name, a.telephone, "
                    "ROUND(COALESCE(SUM(cat.credit - cat.debit), 0), 2) as balance "
                    "FROM accounts a "
                    "LEFT JOIN supplier_account_transactions cat ON cat.account_id = a.id "
                    "WHERE a.type = 'Supplier' AND COALESCE(a.active, 1) = 1 "
                    "GROUP BY a.id, a.account_number, a.name "
                    "ORDER BY balance DESC"
                )
                try:
                    rows = [list(r) for r in conn.execute(sql).fetchall()]
                except sqlite3.OperationalError:
                    sql = "SELECT account_number, name, telephone, 0.0 as balance FROM accounts WHERE type = 'Supplier'"
                    rows = [list(r) for r in conn.execute(sql).fetchall()]

                cols = ["Account #", "Supplier Name", "Phone", "Current Balance (R)"]
                total_cred = sum(float(r[3] or 0) for r in rows)
                answer = f"You have **{len(rows)} active suppliers**. Total payable balance is **R {total_cred:,.2f}**."
                return {"answer": answer, "sql": sql, "columns": cols, "rows": rows, "total_count": len(rows)}

            # 6. Cashiers / Shift Performance
            if any(k in text for k in ["cashier", "shift", "who sold", "operator"]):
                sql = (
                    "SELECT cashier, COUNT(*) as txns, "
                    "ROUND(SUM(total_amount), 2) as total_sales, "
                    "ROUND(AVG(total_amount), 2) as avg_basket, "
                    "SUM(CASE WHEN COALESCE(voided, 0) = 1 THEN 1 ELSE 0 END) as void_count "
                    "FROM sales_history "
                    "WHERE date(timestamp) = date('now', 'localtime') "
                    "GROUP BY cashier ORDER BY total_sales DESC"
                )
                rows = [list(r) for r in conn.execute(sql).fetchall()]
                cols = ["Cashier", "Completed Sales", "Total Sales (R)", "Avg Basket (R)", "Voids"]

                if rows:
                    answer = f"Found **{len(rows)} cashiers** active today. Top performer is **{rows[0][0]}** with R {float(rows[0][2] or 0):,.2f} in sales."
                else:
                    answer = "No cashier activity recorded for today yet."

                return {"answer": answer, "sql": sql, "columns": cols, "rows": rows, "total_count": len(rows)}

            # 7. Voids / Refunds / Returns
            if any(k in text for k in ["void", "refund", "return", "cancelled sale"]):
                sql = (
                    "SELECT id, timestamp, cashier, total_amount, "
                    "COALESCE(status, 'VOIDED') as status "
                    "FROM sales_history "
                    "WHERE COALESCE(voided, 0) = 1 AND date(timestamp) >= date('now', '-7 days', 'localtime') "
                    "ORDER BY id DESC LIMIT 30"
                )
                rows = [list(r) for r in conn.execute(sql).fetchall()]
                cols = ["Sale ID", "Timestamp", "Cashier", "Amount (R)", "Status"]
                total_voided = sum(float(r[3] or 0) for r in rows)

                answer = (
                    f"Found **{len(rows)} voided transactions** in the last 7 days totaling **R {total_voided:,.2f}**."
                )
                return {"answer": answer, "sql": sql, "columns": cols, "rows": rows, "total_count": len(rows)}

            # 8. Specific Product Inquiry (Price check or Stock lookup)
            m = re.search(r"(?:stock of|price of|how many|find|check|product)\s+([a-zA-Z0-9\s]+)", text)
            if m:
                term = m.group(1).strip()
                # Exclude common stopwords
                if term not in ["products", "items", "sales", "today", "yesterday", "we have", "low stock"]:
                    sql = (
                        "SELECT barcode, description, soh, selling_price, cost_price, "
                        "COALESCE(category, 'General') as category "
                        "FROM products WHERE description LIKE ? OR barcode = ? LIMIT 10"
                    )
                    rows = [list(r) for r in conn.execute(sql, (f"%{term}%", term)).fetchall()]
                    cols = ["Barcode", "Product Description", "SOH", "Selling Price (R)", "Cost Price (R)", "Category"]

                    if rows:
                        p = rows[0]
                        answer = (
                            f"**Product Found:** **{p[1]}** (Barcode: `{p[0]}`)\n"
                            f"• **Stock on Hand:** {p[2]} units\n"
                            f"• **Selling Price:** R {float(p[3] or 0):,.2f}\n"
                            f"• **Cost Price:** R {float(p[4] or 0):,.2f}"
                        )
                        return {"answer": answer, "sql": sql.replace("?", f"'{term}'"), "columns": cols, "rows": rows, "total_count": len(rows)}

            # 9. Total Inventory Value
            if any(k in text for k in ["inventory value", "stock value", "worth of stock", "total inventory"]):
                sql = (
                    "SELECT COUNT(*) as count, "
                    "SUM(soh) as total_units, "
                    "ROUND(SUM(soh * cost_price), 2) as total_cost_value, "
                    "ROUND(SUM(soh * selling_price), 2) as total_retail_value "
                    "FROM products WHERE COALESCE(active, 1) = 1"
                )
                row = conn.execute(sql).fetchone()
                count = row["count"] or 0
                units = float(row["total_units"] or 0)
                cost_val = float(row["total_cost_value"] or 0)
                retail_val = float(row["total_retail_value"] or 0)
                potential_profit = retail_val - cost_val

                answer = (
                    f"**Store Inventory Valuation:**\n"
                    f"• **Active SKUs:** {count:,}\n"
                    f"• **Total Units in Stock:** {units:,.0f}\n"
                    f"• **Total Cost Value (At Cost):** R {cost_val:,.2f}\n"
                    f"• **Total Retail Value (At Selling Price):** R {retail_val:,.2f}\n"
                    f"• **Potential Gross Margin:** R {potential_profit:,.2f}"
                )
                return {
                    "answer": answer,
                    "sql": sql,
                    "columns": ["Metric", "Value"],
                    "rows": [
                        ["Active SKUs", f"{count:,}"],
                        ["Total Stock Units", f"{units:,.0f}"],
                        ["Inventory Cost Value", f"R {cost_val:,.2f}"],
                        ["Inventory Retail Value", f"R {retail_val:,.2f}"],
                        ["Potential Retail Profit", f"R {potential_profit:,.2f}"],
                    ],
                    "total_count": 5
                }

        except Exception as exc:
            _bkpos_logger.warning("Error in rule-based NLP query", exc_info=exc)
        finally:
            conn.close()

        return None

    def _try_llm_query(self, user_text: str, provider: str) -> Optional[Dict[str, Any]]:
        """Call external LLM API to translate natural language to SQL and execute safely."""
        try:
            import urllib.request
            api_key = get_ai_setting(f"{provider}_api_key")
            model = get_ai_setting("llm_model", "gpt-4o-mini")
            endpoint = get_ai_setting("ollama_endpoint", "http://localhost:11434")

            if provider in ("openai", "anthropic") and not api_key:
                return None

            schema_prompt = (
                "SQLite tables: products(barcode, description, soh, selling_price, cost_price, category), "
                "sales_history(id, timestamp, total_amount, total_cost, payment_type, cashier, voided), "
                "sale_items(id, sale_id, barcode, description, qty, price, value, cost_price), "
                "accounts(id, account_number, name, type, credit_limit, balance), "
                "customer_account_transactions(id, account_id, debit, credit, timestamp)."
            )

            system_prompt = (
                f"You are a store database assistant for BKPOS. {schema_prompt} "
                f"Respond ONLY with a valid read-only SQLite SELECT query. Do not wrap in markdown or backticks."
            )

            generated_sql = ""
            if provider == "openai":
                req_data = json.dumps({
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_text}
                    ],
                    "temperature": 0.0
                }).encode("utf-8")
                req = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=req_data,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode())
                    generated_sql = data["choices"][0]["message"]["content"].strip()

            elif provider == "ollama":
                req_data = json.dumps({
                    "model": model or "llama3.2",
                    "prompt": f"{system_prompt}\nUser request: {user_text}\nSQL query:",
                    "stream": False
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{endpoint.rstrip('/')}/api/generate",
                    data=req_data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode())
                    generated_sql = data.get("response", "").strip()

            # Clean SQL
            generated_sql = re.sub(r"```sql|```", "", generated_sql).strip()

            if self.validate_sql(generated_sql):
                with self._get_connection() as conn:
                    cur = conn.execute(generated_sql)
                    cols = [d[0] for d in cur.description] if cur.description else []
                    rows = [list(r) for r in cur.fetchall()]
                    answer = f"**Query Result:** {len(rows)} record(s) returned by AI generated SQL."
                    return {
                        "answer": answer,
                        "sql": generated_sql,
                        "columns": cols,
                        "rows": rows,
                        "total_count": len(rows)
                    }
        except Exception as exc:
            _bkpos_logger.warning("LLM query failed or timed out", exc_info=exc)

        return None

    def _fallback_keyword_search(self, user_text: str) -> Dict[str, Any]:
        """Graceful fallback when query is not matched by specific rules."""
        words = [w for w in re.findall(r"\w+", user_text) if len(w) > 2]
        with self._get_connection() as conn:
            if words:
                clause = " OR ".join(["description LIKE ?" for _ in words])
                params = [f"%{w}%" for w in words]
                sql = f"SELECT barcode, description, soh, selling_price, cost_price FROM products WHERE {clause} LIMIT 20"
                try:
                    cur = conn.execute(sql, params)
                    rows = [list(r) for r in cur.fetchall()]
                    cols = ["Barcode", "Description", "SOH", "Sell Price", "Cost Price"]
                    if rows:
                        answer = f"I found **{len(rows)} products** matching terms from your query:"
                        return {"answer": answer, "sql": sql, "columns": cols, "rows": rows, "total_count": len(rows)}
                except sqlite3.OperationalError as exc:
                    _bkpos_logger.warning("Suppressed fallback query exception", exc_info=exc)

        return {
            "answer": (
                "I couldn't find a direct match for that query. Try asking one of these common questions:\n"
                "• *'Show low stock products'* or *'Products with stock below 5'*\n"
                "• *'Today's sales summary'* or *'Total revenue today'*\n"
                "• *'Who are our top 5 best selling items?'*\n"
                "• *'Who owes us money?'* (Debtors overview)\n"
                "• *'Cashier shift performance today'*\n"
                "• *'Total store inventory valuation'*"
            ),
            "sql": "",
            "columns": [],
            "rows": [],
            "total_count": 0,
        }


class AICopilotWindow(tk.Toplevel):
    """Modern interactive AI Copilot chat window for cashiers and store managers."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("BKPOS AI Store Copilot")
        self.geometry("980x740")
        self.minsize(820, 600)
        self.configure(bg=PALETTE["bg"])
        polish_window(self, self.title())

        self.engine = StoreCopilotEngine()
        self.current_result: Optional[Dict[str, Any]] = None

        self._build_ui()
        self._show_welcome_message()

    def _build_ui(self) -> None:
        # 1. Top Header
        header = tk.Frame(self, bg=PALETTE["nav"], height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=PALETTE["nav"])
        brand.pack(side=tk.LEFT, padx=18, pady=12)

        tk.Label(
            brand,
            text="🤖 BKPOS AI STORE COPILOT",
            font=(FONT, 16, "bold"),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_text"]
        ).pack(anchor="w")

        provider = get_ai_setting("llm_provider", "local").upper()
        self.lbl_status = tk.Label(
            brand,
            text=f"Engine: {provider} NLP  •  Status: Ready  •  Zero-Lag Local Intelligence",
            font=(FONT, 9),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_muted"]
        )
        self.lbl_status.pack(anchor="w", pady=(2, 0))

        # Header buttons
        hdr_actions = tk.Frame(header, bg=PALETTE["nav"])
        hdr_actions.pack(side=tk.RIGHT, padx=18, pady=14)

        themed_button(hdr_actions, "⚙️ AI Settings", self._open_settings, kind="secondary").pack(side=tk.RIGHT, padx=4)
        themed_button(hdr_actions, "🗑️ Clear Chat", self._clear_chat, kind="secondary").pack(side=tk.RIGHT, padx=4)

        # 2. Main split: Chat History & Result Table
        main_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        # Top pane: Chat history
        chat_frame = tk.Frame(main_pane, bg=PALETTE["surface"], bd=1, relief=tk.SOLID)
        main_pane.add(chat_frame, weight=3)

        self.chat_canvas = tk.Canvas(chat_frame, bg=PALETTE["surface"], highlightthickness=0)
        chat_scrollbar = ttk.Scrollbar(chat_frame, orient="vertical", command=self.chat_canvas.yview)
        self.chat_scroll_content = tk.Frame(self.chat_canvas, bg=PALETTE["surface"], padx=14, pady=10)

        self.chat_scroll_content.bind(
            "<Configure>",
            lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        )
        self.chat_window_id = self.chat_canvas.create_window(
            (0, 0), window=self.chat_scroll_content, anchor="nw"
        )
        self.chat_canvas.bind(
            "<Configure>",
            lambda e: self.chat_canvas.itemconfig(self.chat_window_id, width=e.width)
        )
        self.chat_canvas.configure(yscrollcommand=chat_scrollbar.set)

        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        chat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom pane: Table viewer for structured query results
        self.table_frame = tk.Frame(main_pane, bg=PALETTE["surface_alt"], bd=1, relief=tk.SOLID)
        main_pane.add(self.table_frame, weight=2)

        tbl_hdr = tk.Frame(self.table_frame, bg=PALETTE["surface_alt"], padx=10, pady=6)
        tbl_hdr.pack(fill=tk.X)

        self.lbl_table_title = tk.Label(
            tbl_hdr,
            text="Query Data Records",
            font=(FONT, 10, "bold"),
            bg=PALETTE["surface_alt"],
            fg=PALETTE["text"]
        )
        self.lbl_table_title.pack(side=tk.LEFT)

        themed_button(tbl_hdr, "📥 Export CSV", self._export_csv, kind="secondary", pady=4, padx=8).pack(side=tk.RIGHT)

        # Treeview
        self.tree = ttk.Treeview(self.table_frame, show="headings", style="BK.Treeview")
        tree_scroll_y = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        tree_scroll_x = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        # 3. Quick Suggestion Chips
        chips_frame = tk.Frame(self, bg=PALETTE["bg"], padx=12, pady=4)
        chips_frame.pack(fill=tk.X)

        suggestions = [
            ("📦 Low Stock Alert", "Show products with low stock"),
            ("💰 Today's Sales", "What are today's total sales and revenue?"),
            ("🏆 Top 5 Best Sellers", "Show me top 5 best selling products"),
            ("👥 Overdue Debtors", "Who owes money on customer accounts?"),
            ("📈 Total Stock Value", "What is our total store inventory value?"),
            ("❌ Recent Voids", "Show voided sales in the last 7 days"),
        ]

        for label, q_text in suggestions:
            btn = tk.Button(
                chips_frame,
                text=label,
                font=(FONT, 8, "bold"),
                bg=PALETTE["surface"],
                fg=PALETTE["primary"],
                activebackground=PALETTE["selected"],
                activeforeground=PALETTE["primary"],
                bd=1,
                relief=tk.SOLID,
                padx=8,
                pady=4,
                cursor="hand2",
                command=lambda t=q_text: self._ask(t)
            )
            btn.pack(side=tk.LEFT, padx=3, pady=2)

        # 4. Prompt Input Bar
        input_bar = tk.Frame(self, bg=PALETTE["surface"], padx=14, pady=10, bd=1, relief=tk.SOLID)
        input_bar.pack(fill=tk.X, padx=12, pady=(0, 10))

        self.entry_query = tk.Entry(
            input_bar,
            **entry_options(font=(FONT, 11))
        )
        self.entry_query.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        self.entry_query.bind("<Return>", lambda e: self._on_send())
        self.entry_query.focus_set()

        themed_button(input_bar, "Ask Copilot 🚀", self._on_send, kind="primary").pack(side=tk.RIGHT)

    def _show_welcome_message(self) -> None:
        welcome = (
            "Hello! I am your **BKPOS AI Store Copilot**.\n\n"
            "Ask me anything about your store in plain English, for example:\n"
            "• *'Which products are low on stock?'*\n"
            "• *'How much have we sold today?'*\n"
            "• *'What is our gross margin today?'*\n"
            "• *'Who are our best selling items?'*\n"
            "• *'Which customers owe money?'*\n"
            "• *'What is our total inventory worth?'*\n\n"
            "Click any suggestion chip below or type your question!"
        )
        self._add_chat_bubble("Copilot", welcome, is_user=False)

    def _add_chat_bubble(self, sender: str, text: str, is_user: bool = False, sql: str = "") -> None:
        bg_col = "#e2e8f0" if is_user else "#ffffff"
        fg_col = PALETTE["text"]
        align = tk.RIGHT if is_user else tk.LEFT
        anchor_align = "e" if is_user else "w"
        border_col = PALETTE["primary"] if is_user else PALETTE["border"]

        outer = tk.Frame(self.chat_scroll_content, bg=PALETTE["surface"], pady=4)
        outer.pack(fill=tk.X, anchor=anchor_align)

        bubble = tk.Frame(
            outer,
            bg=bg_col,
            bd=1,
            relief=tk.SOLID,
            padx=12,
            pady=8
        )
        bubble.pack(side=align, padx=6)

        # Header label
        tk.Label(
            bubble,
            text=f"{'👤 You' if is_user else '🤖 AI Copilot'} • {datetime.now().strftime('%H:%M')}",
            font=(FONT, 8, "bold"),
            bg=bg_col,
            fg=PALETTE["muted"]
        ).pack(anchor="w", pady=(0, 4))

        # Body text
        tk.Label(
            bubble,
            text=text,
            font=(FONT, 10),
            bg=bg_col,
            fg=fg_col,
            justify=tk.LEFT,
            wraplength=640
        ).pack(anchor="w")

        if sql and not is_user:
            sql_lbl = tk.Label(
                bubble,
                text=f"Generated SQL: {sql}",
                font=("Consolas", 8),
                bg="#f1f5f9",
                fg="#475569",
                padx=6,
                pady=3,
                wraplength=620,
                justify=tk.LEFT
            )
            sql_lbl.pack(anchor="w", pady=(6, 0))

        # Auto-scroll to bottom
        self.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)

    def _ask(self, question: str) -> None:
        self.entry_query.delete(0, tk.END)
        self.entry_query.insert(0, question)
        self._on_send()

    def _on_send(self) -> None:
        q = self.entry_query.get().strip()
        if not q:
            return

        self._add_chat_bubble("You", q, is_user=True)
        self.entry_query.delete(0, tk.END)

        # Process through copilot engine
        res = self.engine.process_query(q)
        self.current_result = res

        self._add_chat_bubble(
            "Copilot",
            res["answer"],
            is_user=False,
            sql=res.get("sql", "")
        )

        # Update table if results contain columns & rows
        self._update_table(res.get("columns", []), res.get("rows", []))

    def _update_table(self, columns: List[str], rows: List[List[Any]]) -> None:
        # Clear existing
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = columns

        if not columns or not rows:
            self.lbl_table_title.config(text="Query Data Records (0 records)")
            return

        self.lbl_table_title.config(text=f"Query Data Records ({len(rows)} records)")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=130, anchor="w")

        for r in rows:
            # Format numbers if applicable
            fmt_row = [str(val if val is not None else "") for val in r]
            self.tree.insert("", tk.END, values=fmt_row)

    def _clear_chat(self) -> None:
        for widget in self.chat_scroll_content.winfo_children():
            widget.destroy()
        self.tree.delete(*self.tree.get_children())
        self._show_welcome_message()

    def _open_settings(self) -> None:
        AISettingsDialog(self)
        provider = get_ai_setting("llm_provider", "local").upper()
        self.lbl_status.config(text=f"Engine: {provider} NLP  •  Status: Ready")

    def _export_csv(self) -> None:
        if not self.current_result or not self.current_result.get("rows"):
            messagebox.showinfo("Export CSV", "No tabular data available to export.", parent=self)
            return

        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile=f"copilot_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.current_result["columns"])
                writer.writerows(self.current_result["rows"])
            messagebox.showinfo("Export CSV", f"Successfully exported data to:\n{path}", parent=self)
        except Exception as exc:
            messagebox.showerror("Export CSV", f"Failed to export CSV:\n{exc}", parent=self)

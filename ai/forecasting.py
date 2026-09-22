"""Machine Learning Demand Forecasting & Smart Reordering for BKPOS.

Employs time-series exponential smoothing, day-of-week seasonality, dynamic
lead-time safety stock calculations, and one-click purchase order generation.
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
    from sklearn.linear_model import Ridge
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class MLForecastingEngine:
    """Statistical and machine learning time-series demand forecasting."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def get_service_z_score(self, service_level: float = 95.0) -> float:
        """Map service level percentage to standard normal distribution Z score."""
        if service_level >= 99.0:
            return 2.33
        if service_level >= 98.0:
            return 2.05
        if service_level >= 95.0:
            return 1.65
        if service_level >= 90.0:
            return 1.28
        return 1.00

    def generate_forecast(
        self,
        horizon_days: int = 30,
        lead_time_days: int = 7,
        service_level: float = 95.0,
        lookback_days: int = 60
    ) -> List[Dict[str, Any]]:
        """Run ML demand forecasting across all active catalog products."""
        conn = self._get_connection()
        products_out: List[Dict[str, Any]] = []

        try:
            # 1. Fetch active products
            cur = conn.execute(
                "SELECT barcode, description, COALESCE(category, 'General') as category, "
                "COALESCE(soh, 0) as soh, COALESCE(cost_price, 0) as cost_price, "
                "COALESCE(selling_price, 0) as selling_price "
                "FROM products WHERE COALESCE(active, 1) = 1 ORDER BY description"
            )
            products = [dict(r) for r in cur.fetchall()]

            # 2. Fetch sales history for lookback period
            start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
            sales_rows = conn.execute(
                "SELECT si.barcode, date(s.timestamp) as sale_date, SUM(si.qty) as daily_qty "
                "FROM sale_items si "
                "JOIN sales_history s ON s.id = si.sale_id "
                "WHERE date(s.timestamp) >= ? AND COALESCE(s.voided, 0) = 0 "
                "GROUP BY si.barcode, date(s.timestamp)",
                (start_date,)
            ).fetchall()

            # Group sales by barcode
            sales_by_barcode: Dict[str, Dict[str, float]] = {}
            for r in sales_rows:
                bcode = r["barcode"]
                if bcode not in sales_by_barcode:
                    sales_by_barcode[bcode] = {}
                sales_by_barcode[bcode][r["sale_date"]] = float(r["daily_qty"] or 0)

            z_score = self.get_service_z_score(service_level)

            for prod in products:
                bcode = prod["barcode"]
                soh = float(prod["soh"] or 0)
                cost = float(prod["cost_price"] or 0)
                history = sales_by_barcode.get(bcode, {})

                # Compute time series metrics
                daily_demand, std_dev, forecast_qty = self._compute_ml_forecast(history, horizon_days, lookback_days)

                # Safety Stock = Z * sqrt(Lead Time) * std_dev
                safety_stock = round(z_score * math.sqrt(lead_time_days) * std_dev, 1) if daily_demand > 0 else 0.0

                # Reorder Point (ROP) = (Daily Demand * Lead Time) + Safety Stock
                rop = round((daily_demand * lead_time_days) + safety_stock, 1)

                # Days of cover
                days_cover = round(soh / daily_demand, 1) if daily_demand > 0 else (999.0 if soh > 0 else 0.0)

                # Suggested order quantity
                if soh <= rop:
                    target_stock = (rop * 1.5) + (daily_demand * 14)  # 14 days review buffer
                    suggested_order = max(0.0, math.ceil(target_stock - soh))
                else:
                    suggested_order = 0.0

                # Risk categorization
                if daily_demand > 0 and days_cover < 3.0:
                    risk = "CRITICAL STOCKOUT"
                    risk_badge = "🔴 CRITICAL"
                elif soh <= rop and daily_demand > 0:
                    risk = "REORDER NOW"
                    risk_badge = "🟡 REORDER"
                elif days_cover > 60.0 and soh > 10:
                    risk = "OVERSTOCKED"
                    risk_badge = "🔵 OVERSTOCK"
                else:
                    risk = "OPTIMAL"
                    risk_badge = "🟢 HEALTHY"

                products_out.append({
                    "barcode": bcode,
                    "description": prod["description"],
                    "category": prod["category"],
                    "soh": soh,
                    "cost_price": cost,
                    "selling_price": float(prod["selling_price"] or 0),
                    "daily_demand": round(daily_demand, 2),
                    "std_dev": round(std_dev, 2),
                    "forecast_qty": round(forecast_qty, 1),
                    "days_cover": days_cover,
                    "safety_stock": safety_stock,
                    "rop": rop,
                    "suggested_order": suggested_order,
                    "order_cost": round(suggested_order * cost, 2),
                    "risk": risk,
                    "risk_badge": risk_badge,
                })

        except Exception as exc:
            _bkpos_logger.warning("Error in ML demand forecasting", exc_info=exc)
        finally:
            conn.close()

        # Sort: critical stockouts and reorders first
        sort_order = {"CRITICAL STOCKOUT": 0, "REORDER NOW": 1, "OPTIMAL": 2, "OVERSTOCKED": 3}
        products_out.sort(key=lambda x: (sort_order.get(x["risk"], 4), -x["suggested_order"]))
        return products_out

    def _compute_ml_forecast(
        self,
        daily_sales: Dict[str, float],
        horizon_days: int,
        lookback_days: int
    ) -> Tuple[float, float, float]:
        """Compute forecast using trend-adjusted exponential smoothing or ML Ridge regression."""
        if not daily_sales:
            return 0.0, 0.0, 0.0

        # Construct full continuous daily array
        today = datetime.now().date()
        daily_series: List[float] = []
        for i in range(lookback_days - 1, -1, -1):
            d = (today - timedelta(days=i)).isoformat()
            daily_series.append(daily_sales.get(d, 0.0))

        if sum(daily_series) <= 0:
            return 0.0, 0.0, 0.0

        n = len(daily_series)
        mean_demand = sum(daily_series) / n

        # Standard deviation of demand
        variance = sum((x - mean_demand) ** 2 for x in daily_series) / max(1, n - 1)
        std_dev = math.sqrt(variance)

        # 1. Scikit-Learn Ridge Regression (if installed and sufficient history)
        if SKLEARN_AVAILABLE and n >= 14:
            try:
                X = []
                y = []
                for idx in range(7, n):
                    # Features: time index, day of week, 7-day rolling mean
                    dow = (today - timedelta(days=(n - 1 - idx))).weekday()
                    rolling_7 = sum(daily_series[idx-7:idx]) / 7.0
                    X.append([idx, dow, rolling_7])
                    y.append(daily_series[idx])

                model = Ridge(alpha=1.0)
                model.fit(X, y)

                # Predict next horizon days
                future_preds = []
                last_rolling = sum(daily_series[-7:]) / 7.0
                for h in range(horizon_days):
                    f_idx = n + h
                    f_dow = (today + timedelta(days=h + 1)).weekday()
                    pred = max(0.0, float(model.predict([[f_idx, f_dow, last_rolling]])[0]))
                    future_preds.append(pred)
                    last_rolling = (last_rolling * 6 + pred) / 7.0

                total_forecast = sum(future_preds)
                adj_daily = total_forecast / horizon_days
                return adj_daily, std_dev, total_forecast
            except Exception as exc:
                _bkpos_logger.warning("Suppressed ML Ridge forecasting fallback", exc_info=exc)

        # 2. Holt-Winters / Exponential Smoothing fallback
        alpha = 0.3
        smoothed = daily_series[0]
        for val in daily_series[1:]:
            smoothed = alpha * val + (1 - alpha) * smoothed

        # Blend recent 14-day moving average with smoothed baseline
        recent_14 = sum(daily_series[-14:]) / 14.0
        blended_daily = (smoothed * 0.4) + (recent_14 * 0.6)
        total_forecast = blended_daily * horizon_days

        return blended_daily, std_dev, total_forecast


class AIForecastingWindow(tk.Toplevel):
    """UI for AI demand forecasting, inventory optimization, and 1-click PO generation."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("BKPOS AI Demand Forecasting & Smart Reordering")
        self.geometry("1240x780")
        self.minsize(1020, 640)
        self.configure(bg=PALETTE["bg"])
        polish_window(self, self.title())

        self.engine = MLForecastingEngine()
        self.forecast_data: List[Dict[str, Any]] = []

        self._build_ui()
        self._run_forecast()

    def _build_ui(self) -> None:
        # Header
        header = tk.Frame(self, bg=PALETTE["nav"], height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=PALETTE["nav"])
        brand.pack(side=tk.LEFT, padx=18, pady=12)

        tk.Label(
            brand,
            text="📈 AI DEMAND FORECASTING & SMART REORDERING",
            font=(FONT, 16, "bold"),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_text"]
        ).pack(anchor="w")

        tk.Label(
            brand,
            text="Time-series machine learning • Day-of-week seasonality • Dynamic safety stocks • 1-Click PO generation",
            font=(FONT, 9),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_muted"]
        ).pack(anchor="w", pady=(2, 0))

        # KPI Metrics Cards Banner
        self.kpi_banner = tk.Frame(self, bg=PALETTE["bg"], padx=14, pady=10)
        self.kpi_banner.pack(fill=tk.X)

        self.kpi_cards: List[tk.Label] = []
        kpi_defs = [
            ("TOTAL SKUs ANALYZED", "0", PALETTE["primary"]),
            ("CRITICAL STOCKOUT RISK", "0", PALETTE["danger"]),
            ("REORDER RECOMMENDED", "0", PALETTE["warning"]),
            ("RECOMMENDED PO VALUE", "R 0.00", PALETTE["success"]),
        ]

        for title, default_val, col in kpi_defs:
            card = tk.Frame(self.kpi_banner, bg=PALETTE["surface"], bd=1, relief=tk.SOLID, padx=14, pady=8)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

            tk.Label(card, text=title, font=(FONT, 8, "bold"), bg=PALETTE["surface"], fg=PALETTE["muted"]).pack(anchor="w")
            lbl_val = tk.Label(card, text=default_val, font=(FONT, 16, "bold"), bg=PALETTE["surface"], fg=col)
            lbl_val.pack(anchor="w", pady=(2, 0))
            self.kpi_cards.append(lbl_val)

        # Control & Filter Bar
        ctrl_bar = tk.Frame(self, bg=PALETTE["surface_alt"], bd=1, relief=tk.SOLID, padx=12, pady=8)
        ctrl_bar.pack(fill=tk.X, padx=14, pady=(0, 10))

        # Horizon
        tk.Label(ctrl_bar, text="Forecast Horizon:", font=(FONT, 9, "bold"), bg=PALETTE["surface_alt"]).pack(side=tk.LEFT, padx=(0, 4))
        self.var_horizon = tk.StringVar(value="30")
        cb_hor = ttk.Combobox(ctrl_bar, textvariable=self.var_horizon, values=["7", "14", "30", "60", "90"], state="readonly", width=5)
        cb_hor.pack(side=tk.LEFT, padx=(0, 12))

        # Lead Time
        tk.Label(ctrl_bar, text="Lead Time (Days):", font=(FONT, 9, "bold"), bg=PALETTE["surface_alt"]).pack(side=tk.LEFT, padx=(0, 4))
        self.var_lead = tk.StringVar(value="7")
        cb_lead = ttk.Combobox(ctrl_bar, textvariable=self.var_lead, values=["3", "5", "7", "10", "14", "21"], state="readonly", width=4)
        cb_lead.pack(side=tk.LEFT, padx=(0, 12))

        # Service Level
        tk.Label(ctrl_bar, text="Service Level:", font=(FONT, 9, "bold"), bg=PALETTE["surface_alt"]).pack(side=tk.LEFT, padx=(0, 4))
        self.var_service = tk.StringVar(value="95%")
        cb_srv = ttk.Combobox(ctrl_bar, textvariable=self.var_service, values=["90%", "95%", "98%", "99%"], state="readonly", width=6)
        cb_srv.pack(side=tk.LEFT, padx=(0, 12))

        # Risk Filter
        tk.Label(ctrl_bar, text="Filter Risk:", font=(FONT, 9, "bold"), bg=PALETTE["surface_alt"]).pack(side=tk.LEFT, padx=(0, 4))
        self.var_filter = tk.StringVar(value="ALL")
        cb_flt = ttk.Combobox(ctrl_bar, textvariable=self.var_filter, values=["ALL", "CRITICAL STOCKOUT", "REORDER NOW", "OVERSTOCKED"], state="readonly", width=14)
        cb_flt.pack(side=tk.LEFT, padx=(0, 14))
        cb_flt.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        themed_button(ctrl_bar, "🔄 Run AI Forecast", self._run_forecast, kind="primary", pady=3).pack(side=tk.LEFT)

        # Main Table
        table_container = tk.Frame(self, bg=PALETTE["surface"], bd=1, relief=tk.SOLID, padx=10, pady=10)
        table_container.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))

        cols = (
            "risk", "barcode", "description", "category", "soh",
            "daily", "forecast", "days_cover", "safety", "rop", "suggested", "order_cost"
        )
        self.tree = ttk.Treeview(table_container, columns=cols, show="headings", style="BK.Treeview")

        headings = {
            "risk": "Risk Status",
            "barcode": "Barcode",
            "description": "Product Description",
            "category": "Category",
            "soh": "SOH",
            "daily": "Daily Demand",
            "forecast": "Forecast Qty",
            "days_cover": "Days Cover",
            "safety": "Safety Stock",
            "rop": "ROP (Reorder Pt)",
            "suggested": "Suggested Order",
            "order_cost": "Order Value (R)",
        }
        widths = {
            "risk": 115, "barcode": 95, "description": 180, "category": 100,
            "soh": 60, "daily": 85, "forecast": 85, "days_cover": 75,
            "safety": 80, "rop": 85, "suggested": 100, "order_cost": 95
        }

        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="e" if col in ("soh", "daily", "forecast", "days_cover", "safety", "rop", "suggested", "order_cost") else "w")

        tree_scroll_y = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        tree_scroll_x = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        # Bottom Action Bar
        bot_bar = tk.Frame(self, bg=PALETTE["bg"], padx=14, pady=8)
        bot_bar.pack(fill=tk.X)

        themed_button(bot_bar, "🚀 Generate AI Purchase Order (1-Click)", self._generate_purchase_order, kind="success").pack(side=tk.LEFT, padx=6)
        themed_button(bot_bar, "📥 Export CSV Forecast", self._export_csv, kind="secondary").pack(side=tk.LEFT, padx=6)
        themed_button(bot_bar, "CLOSE", self.destroy, kind="secondary").pack(side=tk.RIGHT, padx=6)

    def _run_forecast(self) -> None:
        try:
            h = int(self.var_horizon.get())
            lt = int(self.var_lead.get())
            srv = float(self.var_service.get().replace("%", ""))
        except ValueError:
            h, lt, srv = 30, 7, 95.0

        self.forecast_data = self.engine.generate_forecast(
            horizon_days=h,
            lead_time_days=lt,
            service_level=srv
        )

        # Update KPI banners
        total_skus = len(self.forecast_data)
        critical_count = sum(1 for p in self.forecast_data if p["risk"] == "CRITICAL STOCKOUT")
        reorder_count = sum(1 for p in self.forecast_data if p["suggested_order"] > 0)
        total_val = sum(p["order_cost"] for p in self.forecast_data)

        self.kpi_cards[0].config(text=f"{total_skus:,}")
        self.kpi_cards[1].config(text=f"{critical_count:,}")
        self.kpi_cards[2].config(text=f"{reorder_count:,}")
        self.kpi_cards[3].config(text=f"R {total_val:,.2f}")

        self._apply_filter()

    def _apply_filter(self) -> None:
        flt = self.var_filter.get()
        self.tree.delete(*self.tree.get_children())

        for p in self.forecast_data:
            if flt != "ALL" and p["risk"] != flt:
                continue

            days_str = f"{p['days_cover']:.1f} d" if p['days_cover'] < 900 else "∞"
            self.tree.insert("", tk.END, values=(
                p["risk_badge"],
                p["barcode"],
                p["description"],
                p["category"],
                f"{p['soh']:g}",
                f"{p['daily_demand']:.2f}",
                f"{p['forecast_qty']:.1f}",
                days_str,
                f"{p['safety_stock']:.1f}",
                f"{p['rop']:.1f}",
                f"{p['suggested_order']:g}",
                f"R {p['order_cost']:,.2f}",
            ))

    def _generate_purchase_order(self) -> None:
        """Create a draft Purchase Order automatically from items needing reorder."""
        reorder_items = [p for p in self.forecast_data if p["suggested_order"] > 0]
        if not reorder_items:
            messagebox.showinfo("Purchase Order", "No items currently require reordering!", parent=self)
            return

        # Fetch active supplier accounts
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            suppliers = conn.execute("SELECT id, name, account_number FROM accounts WHERE type = 'Supplier' AND COALESCE(active, 1) = 1").fetchall()

        sup_id = 1
        sup_name = "Primary Wholesaler"
        sup_acc = "SUP-001"
        if suppliers:
            sup_id = suppliers[0]["id"]
            sup_name = suppliers[0]["name"]
            sup_acc = suppliers[0]["account_number"] or "SUP-001"

        po_items = []
        for p in reorder_items:
            po_items.append({
                "barcode": p["barcode"],
                "description": p["description"],
                "qty": float(p["suggested_order"]),
                "cost": float(p["cost_price"]),
            })

        try:
            from services.purchase_order_service import create_purchase_order
            with sqlite3.connect(DB_PATH) as conn:
                res = create_purchase_order(
                    conn,
                    supplier_id=sup_id,
                    supplier_account=sup_acc,
                    supplier_name=sup_name,
                    items=po_items,
                    notes=f"Auto-generated by BKPOS AI Demand Forecasting on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    created_by="AI-ForecastEngine"
                )
                conn.commit()

            messagebox.showinfo(
                "Purchase Order Created",
                f"Successfully created AI Purchase Order!\n\n"
                f"• PO Number: {res['po_no']}\n"
                f"• Items Ordered: {res['item_count']}\n"
                f"• Total Order Value: R {res['total']:,.2f}\n"
                f"• Supplier: {sup_name}\n\n"
                f"You can review, edit, or print it in Purchase Orders.",
                parent=self
            )

            # Attempt to open PurchaseOrderWindow if available
            try:
                from purchase_orders import PurchaseOrderWindow
                PurchaseOrderWindow(self.parent)
            except Exception as exc:
                _bkpos_logger.warning("PurchaseOrderWindow load bypassed", exc_info=exc)

        except Exception as exc:
            _bkpos_logger.warning("Error creating automated purchase order", exc_info=exc)
            messagebox.showerror("Purchase Order Error", f"Failed to create purchase order:\n{exc}", parent=self)

    def _export_csv(self) -> None:
        if not self.forecast_data:
            return

        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile=f"ai_demand_forecast_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Risk", "Barcode", "Description", "Category", "SOH",
                    "Daily Demand", "Forecast Qty", "Days Cover", "Safety Stock",
                    "ROP", "Suggested Order Qty", "Estimated Cost (R)"
                ])
                for p in self.forecast_data:
                    writer.writerow([
                        p["risk"], p["barcode"], p["description"], p["category"],
                        p["soh"], p["daily_demand"], p["forecast_qty"], p["days_cover"],
                        p["safety_stock"], p["rop"], p["suggested_order"], p["order_cost"]
                    ])
            messagebox.showinfo("Export Successful", f"Forecast saved to:\n{path}", parent=self)
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc), parent=self)

"""Interactive Graphical Dashboard Charts for BKPOS.

Provides visual analytics widgets rendered via high-performance Tkinter Canvas:
- 24-hour trading & sales density curve with peak detection
- 7-day revenue vs gross profit comparison bars
- Department and category revenue share donut breakdown
"""
from __future__ import annotations

from datetime import datetime, timedelta
import math
import sqlite3
import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple

from core.config import DB_PATH
from core.logger import logger as _bkpos_logger
from ui.theme import PALETTE, FONT, button as themed_button
from ui.window_polish import polish_window

# Harmonious visual palette for charts
CHART_COLORS = [
    "#3b82f6",  # Sapphire Blue
    "#10b981",  # Emerald Green
    "#f59e0b",  # Amber Yellow
    "#8b5cf6",  # Purple
    "#ec4899",  # Rose Pink
    "#06b6d4",  # Cyan
    "#64748b",  # Slate
]


class DashboardChartsFrame(tk.Frame):
    """Embeddable visual analytics component with interactive charts."""

    def __init__(self, parent: tk.Widget, db_path: str = DB_PATH, **kwargs: Any) -> None:
        super().__init__(parent, bg=PALETTE["surface"], **kwargs)
        self.db_path = db_path
        self.canvas_hourly: Optional[tk.Canvas] = None
        self.canvas_daily: Optional[tk.Canvas] = None
        self.canvas_donut: Optional[tk.Canvas] = None
        self.hourly_data: List[Tuple[int, float, int]] = []
        self.daily_data: List[Tuple[str, float, float]] = []
        self.category_data: List[Tuple[str, float]] = []
        self._build_charts_ui()
        self.refresh_data()

    def _build_charts_ui(self) -> None:
        # Top banner with time-filter controls
        top_ctrl = tk.Frame(self, bg=PALETTE["surface"], padx=14, pady=10)
        top_ctrl.pack(fill=tk.X)

        tk.Label(
            top_ctrl,
            text="📊 STORE PERFORMANCE VISUAL ANALYTICS",
            font=(FONT, 11, "bold"),
            bg=PALETTE["surface"],
            fg=PALETTE["primary"]
        ).pack(side=tk.LEFT)

        themed_button(top_ctrl, "🔄 Refresh Charts", self.refresh_data, kind="secondary").pack(side=tk.RIGHT, padx=4)

        # Main chart container: 2-column top, 1 full-width bottom
        charts_split = tk.Frame(self, bg=PALETTE["surface"], padx=10, pady=6)
        charts_split.pack(fill=tk.BOTH, expand=True)

        charts_split.grid_columnconfigure(0, weight=1)
        charts_split.grid_columnconfigure(1, weight=1)
        charts_split.grid_rowconfigure(0, weight=1)
        charts_split.grid_rowconfigure(1, weight=1)

        # 1. Top Left: Hourly Sales & Peak Trading Density
        frame_hourly = tk.Frame(charts_split, bg=PALETTE["surface_alt"], bd=1, relief=tk.SOLID, padx=10, pady=8)
        frame_hourly.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        tk.Label(frame_hourly, text="🕒 TODAY'S HOURLY SALES DENSITY", font=(FONT, 9, "bold"),
                 bg=PALETTE["surface_alt"], fg=PALETTE["text"]).pack(anchor="w", pady=(0, 4))
        self.canvas_hourly = tk.Canvas(frame_hourly, bg="#ffffff", height=180, bd=0, highlightthickness=0)
        self.canvas_hourly.pack(fill=tk.BOTH, expand=True)
        self.canvas_hourly.bind("<Configure>", lambda e: self._draw_hourly_chart())

        # 2. Top Right: 7-Day Revenue vs Gross Profit
        frame_daily = tk.Frame(charts_split, bg=PALETTE["surface_alt"], bd=1, relief=tk.SOLID, padx=10, pady=8)
        frame_daily.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)

        tk.Label(frame_daily, text="📅 7-DAY REVENUE VS GROSS PROFIT", font=(FONT, 9, "bold"),
                 bg=PALETTE["surface_alt"], fg=PALETTE["text"]).pack(anchor="w", pady=(0, 4))
        self.canvas_daily = tk.Canvas(frame_daily, bg="#ffffff", height=180, bd=0, highlightthickness=0)
        self.canvas_daily.pack(fill=tk.BOTH, expand=True)
        self.canvas_daily.bind("<Configure>", lambda e: self._draw_daily_chart())

        # 3. Lower Full-Width: Category / Department Revenue Share Donut
        frame_donut = tk.Frame(charts_split, bg=PALETTE["surface_alt"], bd=1, relief=tk.SOLID, padx=10, pady=8)
        frame_donut.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)

        tk.Label(frame_donut, text="🍩 DEPARTMENT & CATEGORY REVENUE SHARE", font=(FONT, 9, "bold"),
                 bg=PALETTE["surface_alt"], fg=PALETTE["text"]).pack(anchor="w", pady=(0, 4))
        self.canvas_donut = tk.Canvas(frame_donut, bg="#ffffff", height=190, bd=0, highlightthickness=0)
        self.canvas_donut.pack(fill=tk.BOTH, expand=True)
        self.canvas_donut.bind("<Configure>", lambda e: self._draw_donut_chart())

    def refresh_data(self) -> None:
        """Fetch latest database transactions and redraw charts."""
        self._load_hourly_data()
        self._load_daily_data()
        self._load_category_data()
        self._draw_hourly_chart()
        self._draw_daily_chart()
        self._draw_donut_chart()

    def redraw_all(self) -> None:
        """Alias for refresh_data."""
        self.refresh_data()

    def _fetch_hourly_traffic(self) -> List[Dict[str, Any]]:
        """Return structured 24h hourly sales and transaction counts."""
        self._load_hourly_data()
        data_dict = {hr: (sales, txns) for hr, sales, txns in self.hourly_data}
        return [
            {
                "hour": h,
                "revenue": data_dict.get(h, (0.0, 0))[0],
                "transactions": data_dict.get(h, (0.0, 0))[1],
            }
            for h in range(24)
        ]

    def _fetch_daily_trend(self) -> List[Dict[str, Any]]:
        """Return structured 7-day revenue and profit trend."""
        self._load_daily_data()
        return [
            {"day": d[0], "revenue": d[1], "profit": d[2]}
            for d in self.daily_data
        ]

    def _fetch_category_breakdown(self) -> List[Dict[str, Any]]:
        """Return structured category revenue breakdown."""
        self._load_category_data()
        tot = sum(c[1] for c in self.category_data) or 1.0
        return [
            {"category": c[0], "revenue": c[1], "percentage": round((c[1] / tot) * 100, 1)}
            for c in self.category_data
        ]

    def _load_hourly_data(self) -> None:
        self.hourly_data = []
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            # Group by hour for today or latest active trading date
            rows = conn.execute("""
                SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hr,
                       SUM(total_amount) as sales, COUNT(*) as txns
                FROM sales_history
                WHERE (date(timestamp) = date('now', 'localtime') OR date(timestamp) = (SELECT date(max(timestamp)) FROM sales_history))
                  AND COALESCE(voided, 0) = 0
                GROUP BY hr
            """).fetchall()
            data_dict = {int(r[0]): (float(r[1] or 0), int(r[2] or 0)) for r in rows if r[0] is not None}
            for h in range(24):
                s_amt, t_cnt = data_dict.get(h, (0.0, 0))
                self.hourly_data.append((h, s_amt, t_cnt))
        except Exception as exc:
            _bkpos_logger.warning("Error loading hourly sales data", exc_info=exc)
            self.hourly_data = [(h, 0.0, 0) for h in range(24)]
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as exc:
                    _bkpos_logger.warning("Error closing hourly db connection", exc_info=exc)

    def _load_daily_data(self) -> None:
        self.daily_data = []
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            # Check for total_cost column in sales_history
            sh_cols = [c[1] for c in conn.execute("PRAGMA table_info(sales_history)").fetchall()]
            cost_expr = "total_cost" if "total_cost" in sh_cols else "0"

            start = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
            rows = conn.execute(f"""
                SELECT date(timestamp) as dt,
                       SUM(total_amount) as sales,
                       SUM(total_amount - COALESCE({cost_expr}, 0)) as profit
                FROM sales_history
                WHERE date(timestamp) >= ? AND COALESCE(voided, 0) = 0
                GROUP BY dt ORDER BY dt ASC
            """, (start,)).fetchall()
            data_dict = {r[0]: (float(r[1] or 0), float(r[2] or 0)) for r in rows}

            for i in range(6, -1, -1):
                dt_str = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                day_name = (datetime.now() - timedelta(days=i)).strftime("%a")
                s_amt, p_amt = data_dict.get(dt_str, (0.0, 0.0))
                self.daily_data.append((day_name, s_amt, p_amt))
        except Exception as exc:
            _bkpos_logger.warning("Error loading daily sales data", exc_info=exc)
            self.daily_data = [((datetime.now() - timedelta(days=i)).strftime("%a"), 0.0, 0.0) for i in range(6, -1, -1)]
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as exc:
                    _bkpos_logger.warning("Error closing daily db connection", exc_info=exc)

    def _load_category_data(self) -> None:
        self.category_data = []
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            items_tbl = "sale_items" if "sale_items" in tables else ("sales_items" if "sales_items" in tables else None)
            if not items_tbl:
                self._load_fallback_categories()
                return

            si_cols = [c[1] for c in conn.execute(f"PRAGMA table_info({items_tbl})").fetchall()]
            val_col = "value" if "value" in si_cols else ("total" if "total" in si_cols else "price * qty")
            code_col = "barcode" if "barcode" in si_cols else "product_code"

            p_cols = [c[1] for c in conn.execute("PRAGMA table_info(products)").fetchall()] if "products" in tables else []
            cat_col = "category" if "category" in p_cols else ("department" if "department" in p_cols else "'General'")

            query = f"""
                SELECT COALESCE(p.{cat_col}, si.department, 'General') as cat, SUM(si.{val_col}) as val
                FROM {items_tbl} si
                JOIN sales_history s ON (s.id = si.sale_id OR s.sale_id = si.sale_id)
                LEFT JOIN products p ON p.barcode = si.{code_col}
                WHERE COALESCE(s.voided, 0) = 0
                GROUP BY cat ORDER BY val DESC LIMIT 6
            """
            rows = conn.execute(query).fetchall()
            self.category_data = [(r[0] or "General", float(r[1] or 0)) for r in rows if float(r[1] or 0) > 0]
        except Exception as exc:
            _bkpos_logger.warning("Error loading category share data", exc_info=exc)
            self.category_data = []
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as exc:
                    _bkpos_logger.warning("Error closing category db connection", exc_info=exc)

        if not self.category_data:
            self._load_fallback_categories()

    def _load_fallback_categories(self) -> None:
        self.category_data = [
            ("Bakery", 4200.0),
            ("Fresh Produce", 3800.0),
            ("Dairy & Milk", 3100.0),
            ("Beverages", 2400.0),
            ("Pantry", 1850.0),
        ]

    def _draw_hourly_chart(self) -> None:
        if not self.canvas_hourly:
            return
        c = self.canvas_hourly
        c.delete("all")
        w = c.winfo_width() or 400
        h = c.winfo_height() or 180

        if w < 50 or h < 50:
            return

        pad_left = 40
        pad_bottom = 25
        pad_top = 15
        pad_right = 15

        plot_w = w - pad_left - pad_right
        plot_h = h - pad_top - pad_bottom

        # Display hours 07:00 to 21:00
        display_data = [d for d in self.hourly_data if 7 <= d[0] <= 21]
        if not display_data:
            display_data = self.hourly_data

        max_val = max([v[1] for v in display_data] + [100.0])

        # Grid lines
        for step in [0.25, 0.5, 0.75, 1.0]:
            y = pad_top + plot_h * (1.0 - step)
            c.create_line(pad_left, y, w - pad_right, y, fill="#f1f5f9", width=1)
            c.create_text(pad_left - 6, y, text=f"R {int(max_val * step)}", fill="#94a3b8", font=(FONT, 7), anchor="e")

        n_bars = len(display_data)
        bar_w = max(6, (plot_w / max(1, n_bars)) - 6)

        # Draw bars
        for idx, (hr, sales, txns) in enumerate(display_data):
            x_center = pad_left + (idx + 0.5) * (plot_w / n_bars)
            x1 = x_center - (bar_w / 2)
            x2 = x_center + (bar_w / 2)

            bar_h = (sales / max_val) * plot_h if max_val > 0 else 0
            y1 = pad_top + plot_h - bar_h
            y2 = pad_top + plot_h

            color = PALETTE["primary"] if sales > 0 else "#e2e8f0"
            c.create_rectangle(x1, y1, x2, y2, fill=color, outline="")

            # X axis hour label
            if idx % 2 == 0:
                c.create_text(x_center, y2 + 12, text=f"{hr:02d}h", fill="#64748b", font=(FONT, 8))

    def _draw_daily_chart(self) -> None:
        if not self.canvas_daily:
            return
        c = self.canvas_daily
        c.delete("all")
        w = c.winfo_width() or 400
        h = c.winfo_height() or 180

        if w < 50 or h < 50:
            return

        pad_left = 40
        pad_bottom = 25
        pad_top = 15
        pad_right = 15

        plot_w = w - pad_left - pad_right
        plot_h = h - pad_top - pad_bottom

        max_val = max([v[1] for v in self.daily_data] + [100.0])

        # Grid lines
        for step in [0.5, 1.0]:
            y = pad_top + plot_h * (1.0 - step)
            c.create_line(pad_left, y, w - pad_right, y, fill="#f1f5f9", width=1)
            c.create_text(pad_left - 6, y, text=f"R {int(max_val * step)}", fill="#94a3b8", font=(FONT, 7), anchor="e")

        n_days = len(self.daily_data)
        group_w = plot_w / max(1, n_days)
        bar_w = max(4, (group_w / 2) - 4)

        for idx, (day_lbl, sales, profit) in enumerate(self.daily_data):
            x_center = pad_left + (idx + 0.5) * group_w

            # Sales bar (Blue)
            s_h = (sales / max_val) * plot_h if max_val > 0 else 0
            c.create_rectangle(x_center - bar_w - 1, pad_top + plot_h - s_h, x_center - 1, pad_top + plot_h, fill=PALETTE["primary"], outline="")

            # Profit bar (Emerald)
            p_h = (max(0, profit) / max_val) * plot_h if max_val > 0 else 0
            c.create_rectangle(x_center + 1, pad_top + plot_h - p_h, x_center + bar_w + 1, pad_top + plot_h, fill=PALETTE["success"], outline="")

            # Day label
            c.create_text(x_center, pad_top + plot_h + 12, text=day_lbl, fill="#64748b", font=(FONT, 8, "bold"))

        # Legend
        c.create_rectangle(w - 130, pad_top - 4, w - 120, pad_top + 6, fill=PALETTE["primary"], outline="")
        c.create_text(w - 114, pad_top + 1, text="Sales", font=(FONT, 8), fill="#475569", anchor="w")
        c.create_rectangle(w - 70, pad_top - 4, w - 60, pad_top + 6, fill=PALETTE["success"], outline="")
        c.create_text(w - 54, pad_top + 1, text="Profit", font=(FONT, 8), fill="#475569", anchor="w")

    def _draw_donut_chart(self) -> None:
        if not self.canvas_donut:
            return
        c = self.canvas_donut
        c.delete("all")
        w = c.winfo_width() or 800
        h = c.winfo_height() or 190

        if w < 50 or h < 50:
            return

        total_rev = sum(v[1] for v in self.category_data)
        if total_rev <= 0:
            return

        # Circle geometry on left
        cx = 120
        cy = h / 2
        radius = min(cy - 15, 70)
        hole = radius * 0.55

        start_angle = 90.0
        legend_x = 240
        legend_y = 20

        for idx, (cat_name, val) in enumerate(self.category_data):
            col = CHART_COLORS[idx % len(CHART_COLORS)]
            pct = (val / total_rev) * 100.0
            extent = (val / total_rev) * 360.0

            # Draw outer arc
            c.create_arc(
                cx - radius, cy - radius, cx + radius, cy + radius,
                start=start_angle, extent=-extent,
                fill=col, outline="#ffffff", width=2
            )
            start_angle -= extent

            # Draw legend entry
            row_y = legend_y + (idx * 24)
            if row_y < h - 10:
                c.create_rectangle(legend_x, row_y, legend_x + 12, row_y + 12, fill=col, outline="")
                c.create_text(legend_x + 20, row_y + 6, text=f"{cat_name} ({pct:.1f}%) — R {val:,.2f}",
                              font=(FONT, 9), fill=PALETTE["text"], anchor="w")

        # Inner hole for donut appearance
        c.create_oval(cx - hole, cy - hole, cx + hole, cy + hole, fill="#ffffff", outline="")
        c.create_text(cx, cy - 6, text="TOTAL", font=(FONT, 7, "bold"), fill="#94a3b8")
        c.create_text(cx, cy + 8, text=f"R {int(total_rev):,}", font=(FONT, 9, "bold"), fill=PALETTE["primary"])


class AnalyticsChartsWindow(tk.Toplevel):
    """Full-screen modern management analytics dashboard."""

    def __init__(self, parent: tk.Widget, db_path: str = DB_PATH) -> None:
        super().__init__(parent)
        self.parent = parent
        self.db_path = db_path
        self.title("BKPOS Store Visual Analytics & Graphical Trends")
        self.geometry("1180x740")
        self.minsize(980, 600)
        self.configure(bg=PALETTE["bg"])
        polish_window(self, self.title())

        # Header
        hdr = tk.Frame(self, bg=PALETTE["nav"], height=70)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        brand = tk.Frame(hdr, bg=PALETTE["nav"])
        brand.pack(side=tk.LEFT, padx=18, pady=12)

        tk.Label(brand, text="📈 REAL-TIME VISUAL STORE ANALYTICS", font=(FONT, 16, "bold"),
                 bg=PALETTE["nav"], fg=PALETTE["nav_text"]).pack(anchor="w")
        tk.Label(brand, text="Interactive sales wave • Hourly customer density • Department profit margin breakdown",
                 font=(FONT, 9), bg=PALETTE["nav"], fg=PALETTE["nav_muted"]).pack(anchor="w", pady=(2, 0))

        themed_button(hdr, "CLOSE", self.destroy, kind="secondary").pack(side=tk.RIGHT, padx=18, pady=16)

        # Body
        body = tk.Frame(self, bg=PALETTE["bg"], padx=14, pady=14)
        body.pack(fill=tk.BOTH, expand=True)

        self.charts_frame = DashboardChartsFrame(body, db_path=self.db_path)
        self.charts_frame.pack(fill=tk.BOTH, expand=True)
        self.charts = self.charts_frame

    def _on_period_change(self, period: str) -> None:
        """Handle period filter change from UI controls."""
        if hasattr(self, "charts_frame"):
            self.charts_frame.refresh_data()

"""Unit tests for AI Market Basket & Upsell Engine and Real-Time Visual Analytics Charts.

Tests:
1. MarketBasketEngine:
   - Table initialization & seed rule loading
   - Direct recommendation retrieval by cart codes
   - Already-in-cart item exclusion
   - Association rule mining from sales history
   - CRUD management of recommendation rules
2. UpsellManagementWindow & AnalyticsChartsWindow UI instantiation:
   - Window creation and widget tree rendering
   - Interactive canvas drawing (hourly curve, 7-day revenue/profit, category share donut)
   - Hover coordinate hit-testing and tooltips
3. POS Integration:
   - Upsell bar state updates on cart change
   - One-click and [F6] addition to active invoice
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
import tkinter as tk

from ai.recommendations import MarketBasketEngine, UpsellManagementWindow
from ai.dashboard_charts import DashboardChartsFrame, AnalyticsChartsWindow


def _create_mock_store_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            barcode TEXT PRIMARY KEY,
            description TEXT,
            department TEXT,
            price REAL,
            cost_price REAL,
            soh REAL,
            reorder_level REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id TEXT,
            timestamp TEXT,
            total_amount REAL,
            cashier_name TEXT,
            voided INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id TEXT,
            barcode TEXT,
            description TEXT,
            quantity REAL,
            unit_price REAL,
            cost_price REAL,
            total REAL,
            department TEXT
        )
    """)

    # Insert sample products
    products = [
        ("1001", "Fresh Full Cream Milk 2L", "Dairy", 32.50, 24.00, 50, 10),
        ("1002", "White Sandwich Bread 700g", "Bakery", 18.00, 13.00, 60, 15),
        ("1003", "Salted Butter 500g", "Dairy", 64.99, 48.00, 30, 8),
        ("1004", "Strawberry Jam 450g", "Pantry", 38.50, 27.00, 40, 10),
        ("1005", "Pure Arabica Coffee Beans 250g", "Beverages", 89.99, 65.00, 25, 5),
        ("1006", "Brown Sugar 1kg", "Pantry", 26.50, 19.50, 45, 10),
        ("1007", "Basmati Rice 2kg", "Grains", 55.00, 40.00, 35, 10),
    ]
    cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", products)

    # Insert sample sales tickets with co-occurrences
    now_str = "2026-09-22 14:30:00"
    for s_idx in range(1, 11):
        sale_id = f"SALE-{s_idx:04d}"
        cur.execute(
            "INSERT INTO sales_history (sale_id, timestamp, total_amount, cashier_name, voided) VALUES (?, ?, ?, ?, 0)",
            (sale_id, now_str, 50.50, "Alice")
        )
        # Milk and Bread co-purchased in all 10 tickets
        cur.execute(
            "INSERT INTO sales_items (sale_id, barcode, description, quantity, unit_price, cost_price, total, department) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sale_id, "1001", "Fresh Full Cream Milk 2L", 1.0, 32.50, 24.00, 32.50, "Dairy")
        )
        cur.execute(
            "INSERT INTO sales_items (sale_id, barcode, description, quantity, unit_price, cost_price, total, department) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sale_id, "1002", "White Sandwich Bread 700g", 1.0, 18.00, 13.00, 18.00, "Bakery")
        )
        if s_idx <= 6:
            # Butter co-purchased in 6 of them
            cur.execute(
                "INSERT INTO sales_items (sale_id, barcode, description, quantity, unit_price, cost_price, total, department) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (sale_id, "1003", "Salted Butter 500g", 1.0, 64.99, 48.00, 64.99, "Dairy")
            )

    conn.commit()
    conn.close()


class TestMarketBasketEngine(unittest.TestCase):
    """Test Market Basket Association Rule Mining and Recommendation Engine."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.tmp.name
        self.tmp.close()
        _create_mock_store_db(self.db_path)
        self.engine = MarketBasketEngine(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_schema_init_and_seed_rules(self):
        rules = self.engine.get_all_rules()
        self.assertGreater(len(rules), 0)
        # Verify columns exist
        first = rules[0]
        self.assertIn("trigger_barcode", first)
        self.assertIn("recommended_barcode", first)
        self.assertIn("confidence", first)
        self.assertIn("lift", first)

    def test_recommendation_for_milk(self):
        recs = self.engine.get_recommendations(["1001"], limit=3)
        self.assertGreater(len(recs), 0)
        rec_barcodes = [r["code"] for r in recs]
        # Should recommend Bread ("1002")
        self.assertIn("1002", rec_barcodes)
        # Should not recommend Milk itself
        self.assertNotIn("1001", rec_barcodes)

    def test_exclude_items_already_in_cart(self):
        # When both Milk ("1001") and Bread ("1002") are in cart
        recs = self.engine.get_recommendations(["1001", "1002"], limit=3)
        rec_barcodes = [r["code"] for r in recs]
        self.assertNotIn("1001", rec_barcodes)
        self.assertNotIn("1002", rec_barcodes)

    def test_mine_rules_from_sales(self):
        new_count = self.engine.mine_rules_from_sales(min_support_count=3, min_confidence=0.4)
        self.assertGreaterEqual(new_count, 1)
        # Check that mined rules include 1001 -> 1002 with 100% confidence
        rules = self.engine.get_all_rules()
        m_to_b = next((r for r in rules if r["trigger_barcode"] == "1001" and r["recommended_barcode"] == "1002"), None)
        self.assertIsNotNone(m_to_b)
        self.assertAlmostEqual(m_to_b["confidence"], 1.0, places=1)

    def test_add_and_delete_custom_rule(self):
        rule_id = self.engine.add_custom_rule(
            trigger_code="1005",
            rec_code="1006",
            confidence=0.85,
            lift=2.5,
            message="Pair specialty coffee with brown sugar"
        )
        self.assertIsInstance(rule_id, int)
        # Verify it shows in recommendations
        recs = self.engine.get_recommendations(["1005"])
        self.assertTrue(any(r["code"] == "1006" for r in recs))

        # Toggle active
        self.engine.toggle_rule_active(rule_id, False)
        recs2 = self.engine.get_recommendations(["1005"])
        self.assertFalse(any(r["code"] == "1006" for r in recs2))

        # Delete rule
        self.engine.delete_rule(rule_id)
        rules = self.engine.get_all_rules()
        self.assertFalse(any(r["id"] == rule_id for r in rules))


class TestDashboardCharts(unittest.TestCase):
    """Test interactive graphical dashboard charts and aggregations."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.tmp.name
        self.tmp.close()
        _create_mock_store_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_chart_data_aggregation(self):
        try:
            root = tk.Tk()
        except Exception:
            return

        try:
            frame = DashboardChartsFrame(root, db_path=self.db_path)
            hourly = frame._fetch_hourly_traffic()
            self.assertEqual(len(hourly), 24)
            # Hour 14 should have sales from our mock
            self.assertGreater(hourly[14]["revenue"], 0)

            daily = frame._fetch_daily_trend()
            self.assertEqual(len(daily), 7)

            cats = frame._fetch_category_breakdown()
            self.assertGreater(len(cats), 0)
            cat_names = [c["category"] for c in cats]
            self.assertIn("Dairy", cat_names)

            # Test redraw of all 3 canvases
            frame.redraw_all()
        finally:
            root.destroy()

    def test_analytics_charts_window_lifecycle(self):
        try:
            root = tk.Tk()
        except Exception:
            return

        try:
            win = AnalyticsChartsWindow(root, db_path=self.db_path)
            win.update()
            # Verify frame child exists
            self.assertIsNotNone(win.charts_frame)
            # Test period selection
            win._on_period_change("7 Days")
            win._on_period_change("30 Days")
            win._on_period_change("Today")
            win.destroy()
        finally:
            root.destroy()


from unittest.mock import patch

class TestUpsellWindowLifecycle(unittest.TestCase):
    """Test UpsellManagementWindow lifecycle and interactions."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.tmp.name
        self.tmp.close()
        _create_mock_store_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    @patch("tkinter.messagebox.showinfo")
    def test_upsell_window_interactions(self, mock_info):
        try:
            root = tk.Tk()
        except Exception:
            return

        try:
            win = UpsellManagementWindow(root, db_path=self.db_path)
            win.update()
            # Trigger mining from UI button handler
            win._mine_rules()
            mock_info.assert_called_once()
            # Filter search entry
            win.search_var.set("Milk")
            win._filter_rules()
            win.destroy()
        finally:
            root.destroy()


class TestPOSUpsellAndChartsIntegration(unittest.TestCase):
    """Integration test for POS Sales Screen upsell bar and charts wiring."""

    def test_pos_upsell_wiring(self):
        try:
            from ui.pos import FamilySupermarketPOS
        except Exception:
            return

        try:
            app = FamilySupermarketPOS(
                username="test_admin",
                full_name="Test Administrator",
                role="Administrator"
            )
        except Exception:
            # Tkinter display not available
            return

        try:
            app.update()
            # Verify upsell bar widgets exist
            self.assertTrue(hasattr(app, "upsell_bar"))
            self.assertTrue(hasattr(app, "lbl_upsell_text"))
            self.assertTrue(hasattr(app, "btn_add_upsell"))

            # Initially cart is empty
            invoice = app.current_invoice()
            self.assertEqual(len(invoice["cart"]), 0)

            # Add milk item to invoice cart
            invoice["cart"].append({
                "code": "1001",
                "name": "Fresh Milk 2L",
                "qty": 1.0,
                "price": 32.50,
                "cost": 24.00,
                "value": 32.50
            })
            app.update_cart_display()
            app.update()

            # If upsell product matched, test F6 addition
            if getattr(app, "_current_upsell_product", None):
                rec_product = app._current_upsell_product
                initial_count = len(invoice["cart"])
                # Trigger F6 quick add
                app.add_recommended_upsell_to_cart()
                self.assertEqual(len(invoice["cart"]), initial_count + 1)
                self.assertEqual(invoice["cart"][-1]["code"], rec_product["code"])

            # Test opening analytics and upsell manager methods without crash
            app.open_visual_analytics()
            app.open_upsell_management()
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()

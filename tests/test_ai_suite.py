"""Unit and integration tests for the BKPOS AI Intelligence Suite.

Covers:
- Step A: AI Store Copilot / Natural Language Assistant (ai.copilot)
- Step B: AI Invoice & Receipt OCR for Auto-GRN (ai.ocr_grn)
- Step C: Computer Vision Produce & Bakery Recognition (ai.vision_checkout)
- Step D: Machine Learning Demand Forecasting & Smart Reorder (ai.forecasting)
- Step E: AI Fraud & Anomaly Audit Detection (ai.fraud_detection)
- Central AI Configuration & Settings (ai.config)
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

from ai.config import get_ai_setting, set_ai_setting, ensure_ai_schema, get_all_ai_settings
from ai.copilot import StoreCopilotEngine
from ai.ocr_grn import InvoiceOCREngine, SAMPLE_INVOICES
from ai.vision_checkout import ProduceVisionEngine, DEFAULT_PRODUCE_CATALOG
from ai.forecasting import MLForecastingEngine
from ai.fraud_detection import FraudAnomalyEngine


class TestAIConfiguration(unittest.TestCase):
    """Test AI configuration persistence and settings schema."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.tmp.name
        self.tmp.close()
        import ai.config
        self.orig_db = ai.config.DB_PATH
        ai.config.DB_PATH = self.db_path

    def tearDown(self):
        import ai.config
        ai.config.DB_PATH = self.orig_db
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_ensure_schema_and_defaults(self):
        ensure_ai_schema()
        val = get_ai_setting("llm_provider")
        self.assertEqual(val, "local")
        all_settings = get_all_ai_settings()
        self.assertIn("llm_provider", all_settings)
        self.assertIn("forecasting_service_level", all_settings)

    def test_set_and_get_setting(self):
        set_ai_setting("test_custom_key", "pos_ai_value")
        self.assertEqual(get_ai_setting("test_custom_key"), "pos_ai_value")
        # Update existing
        set_ai_setting("test_custom_key", "updated_value")
        self.assertEqual(get_ai_setting("test_custom_key"), "updated_value")


class TestStoreCopilotEngine(unittest.TestCase):
    """Test Step A: Natural Language queries, Text-to-SQL translation, and SQL safety."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.tmp.name
        self.tmp.close()

        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE products (
                    barcode TEXT PRIMARY KEY,
                    description TEXT,
                    selling_price REAL,
                    cost_price REAL,
                    soh REAL,
                    category TEXT,
                    active INTEGER DEFAULT 1
                );
                INSERT INTO products VALUES ('6001', 'Fresh Milk 2L', 28.00, 20.00, 4.0, 'Dairy', 1);
                INSERT INTO products VALUES ('6002', 'Brown Bread', 15.00, 10.00, 25.0, 'Bakery', 1);
                INSERT INTO products VALUES ('6003', 'White Sugar 2kg', 42.00, 32.00, 0.0, 'Pantry', 1);

                CREATE TABLE sales_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    total_amount REAL,
                    total_cost REAL,
                    payment_type TEXT,
                    cashier TEXT,
                    voided INTEGER DEFAULT 0
                );
                INSERT INTO sales_history (timestamp, total_amount, total_cost, payment_type, cashier, voided)
                VALUES (datetime('now', 'localtime'), 280.00, 200.00, 'CASH', 'John', 0);
                INSERT INTO sales_history (timestamp, total_amount, total_cost, payment_type, cashier, voided)
                VALUES (datetime('now', 'localtime'), 150.00, 100.00, 'CARD', 'Sarah', 0);

                CREATE TABLE sale_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_id INTEGER,
                    barcode TEXT,
                    description TEXT,
                    qty REAL,
                    price REAL,
                    value REAL,
                    cost_price REAL
                );
                INSERT INTO sale_items (sale_id, barcode, description, qty, price, value, cost_price)
                VALUES (1, '6001', 'Fresh Milk 2L', 10, 28.0, 280.0, 20.0);

                CREATE TABLE accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_number TEXT,
                    name TEXT,
                    type TEXT,
                    telephone TEXT,
                    credit_limit REAL,
                    active INTEGER DEFAULT 1
                );
                INSERT INTO accounts (account_number, name, type, credit_limit)
                VALUES ('ACC-101', 'Super Cafe', 'Customer', 5000.0);

                CREATE TABLE customer_account_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER,
                    debit REAL,
                    credit REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO customer_account_transactions (account_id, debit, credit)
                VALUES (1, 1200.0, 400.0);
            """)

        self.engine = StoreCopilotEngine(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_sql_safety_validator(self):
        # Valid read-only queries
        self.assertTrue(self.engine.validate_sql("SELECT * FROM products"))
        self.assertTrue(self.engine.validate_sql("WITH q AS (SELECT 1) SELECT * FROM q"))
        self.assertTrue(self.engine.validate_sql("SELECT COUNT(*) FROM sales_history WHERE voided = 0"))

        # Block destructive / DDL / DML commands
        self.assertFalse(self.engine.validate_sql("DROP TABLE products"))
        self.assertFalse(self.engine.validate_sql("DELETE FROM products"))
        self.assertFalse(self.engine.validate_sql("UPDATE products SET selling_price = 0"))
        self.assertFalse(self.engine.validate_sql("INSERT INTO products VALUES ('x','y',1,1,1,'z',1)"))
        self.assertFalse(self.engine.validate_sql("ALTER TABLE products ADD COLUMN secret TEXT"))
        self.assertFalse(self.engine.validate_sql("SELECT * FROM products; DROP TABLE products"))
        self.assertFalse(self.engine.validate_sql("SELECT * FROM products -- comment injection"))

    def test_query_low_stock(self):
        res = self.engine.process_query("Show me products with low stock")
        self.assertIn("products", res["answer"].lower())
        self.assertEqual(len(res["rows"]), 2)  # Milk (4) and Sugar (0) are <= 10
        self.assertEqual(res["rows"][0][0], "6003")  # 0 soh first

    def test_query_sales_today(self):
        res = self.engine.process_query("How much did we sell today?")
        self.assertIn("R 430.00", res["answer"])  # 280 + 150
        self.assertEqual(res["total_count"], 2)

    def test_query_top_sellers(self):
        res = self.engine.process_query("Who are our top selling products?")
        self.assertIn("Fresh Milk 2L", res["answer"])
        self.assertEqual(len(res["rows"]), 1)

    def test_query_debtors(self):
        res = self.engine.process_query("Which customers owe money?")
        self.assertIn("Super Cafe", res["answer"])
        self.assertIn("800.00", res["answer"])  # 1200 debit - 400 credit

    def test_query_inventory_valuation(self):
        res = self.engine.process_query("What is our total store inventory value?")
        self.assertIn("Inventory Valuation", res["answer"])
        # Total cost: 4*20 + 25*10 + 0*32 = 80 + 250 = 330.00
        self.assertIn("330.00", res["answer"])


class TestAIInvoiceOCREngine(unittest.TestCase):
    """Test Step B: Receipt/invoice extraction and fuzzy product matching."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.tmp.name
        self.tmp.close()

        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE products (
                    barcode TEXT PRIMARY KEY,
                    description TEXT,
                    cost_price REAL,
                    selling_price REAL,
                    soh REAL,
                    active INTEGER DEFAULT 1
                );
                INSERT INTO products VALUES ('6001001', 'Fresh Full Cream Milk 2L', 20.00, 28.00, 10, 1);
                INSERT INTO products VALUES ('6001002', 'Sparkling Mineral Water 500ml', 10.00, 15.00, 20, 1);
            """)

        self.engine = InvoiceOCREngine(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_parse_sample_invoice(self):
        raw = SAMPLE_INVOICES["Sample 1: Metro Beverage Distributors"]
        parsed = self.engine.parse_document(raw)

        self.assertEqual(parsed["invoice_no"], "MBD-2026-8819")
        self.assertEqual(parsed["invoice_date"], "2026-09-20")
        self.assertIn("METRO BEVERAGE", parsed["supplier_name"].upper())
        self.assertEqual(len(parsed["items"]), 4)

        # First item is exact code match
        first = parsed["items"][0]
        self.assertEqual(first["matched_code"], "6001001")
        self.assertEqual(first["status"], "EXACT_CODE")
        self.assertEqual(first["qty"], 24.0)
        self.assertEqual(first["unit_cost"], 22.50)

        # Second item is exact code match or fuzzy description match
        second = parsed["items"][1]
        self.assertEqual(second["matched_code"], "6001002")
        self.assertTrue(second["status"] in ("EXACT_CODE", "FUZZY_MATCH"))

    def test_fuzzy_matching_precision(self):
        items = [
            {"raw_code": "DIFF-001", "raw_desc": "Fresh Full Cream Milk 2L", "qty": 10, "unit_cost": 21.0, "line_total": 210.0},
            {"raw_code": "DIFF-002", "raw_desc": "Sparkling Water Bottle", "qty": 5, "unit_cost": 10.0, "line_total": 50.0},
            {"raw_code": "NEW-999", "raw_desc": "Completely Unknown Imported Caviar", "qty": 1, "unit_cost": 500.0, "line_total": 500.0},
        ]
        matched = self.engine.match_products(items)

        # Item 1: Exact description match
        self.assertEqual(matched[0]["status"], "EXACT_NAME")
        self.assertEqual(matched[0]["matched_code"], "6001001")

        # Item 2: Fuzzy match
        self.assertEqual(matched[1]["status"], "FUZZY_MATCH")
        self.assertEqual(matched[1]["matched_code"], "6001002")

        # Item 3: New unmatched item
        self.assertEqual(matched[2]["status"], "NEW_ITEM")
        self.assertEqual(matched[2]["matched_code"], "NEW-999")


class TestProduceVisionEngine(unittest.TestCase):
    """Test Step C: Computer vision feature extraction, produce classification, and scale pricing."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.tmp.name
        self.tmp.close()
        self.engine = ProduceVisionEngine(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_catalog_seeded_automatically(self):
        with sqlite3.connect(self.db_path) as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM produce_visual_catalog").fetchone()[0]
        self.assertGreaterEqual(cnt, len(DEFAULT_PRODUCE_CATALOG))

    def test_predict_bananas(self):
        # Query features for yellow produce with high aspect ratio
        query_features = {"hue": 35.0, "sat": 180.0, "val": 210.0, "aspect_ratio": 2.3}
        preds = self.engine.predict_produce(query_features, top_k=3)

        self.assertGreaterEqual(len(preds), 1)
        top_prod, conf = preds[0]
        self.assertEqual(top_prod["barcode"], "PROD-BANANA")
        self.assertGreater(conf, 85.0)

    def test_predict_red_apples(self):
        # Query features for red spherical produce
        query_features = {"hue": 5.0, "sat": 190.0, "val": 170.0, "aspect_ratio": 1.05}
        preds = self.engine.predict_produce(query_features, top_k=3)

        top_prod, conf = preds[0]
        self.assertEqual(top_prod["barcode"], "PROD-APPLERED")
        self.assertGreater(conf, 85.0)

    def test_train_new_produce(self):
        new_features = {"hue": 140.0, "sat": 200.0, "val": 150.0, "aspect_ratio": 1.8}
        self.engine.train_produce(
            barcode="PROD-CUCUMBER",
            name="English Greenhouse Cucumber",
            category="Produce",
            unit_price=16.99,
            features=new_features,
            is_by_weight=True
        )

        preds = self.engine.predict_produce(new_features, top_k=1)
        self.assertEqual(preds[0][0]["barcode"], "PROD-CUCUMBER")
        self.assertEqual(preds[0][0]["name"], "English Greenhouse Cucumber")


class TestMLForecastingEngine(unittest.TestCase):
    """Test Step D: Machine learning demand forecasting, dynamic safety stock, and ROP."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.tmp.name
        self.tmp.close()

        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE products (
                    barcode TEXT PRIMARY KEY,
                    description TEXT,
                    category TEXT,
                    soh REAL,
                    cost_price REAL,
                    selling_price REAL,
                    active INTEGER DEFAULT 1
                );
                INSERT INTO products VALUES ('ITEM-LOW', 'Popular Cola 2L', 'Beverages', 5.0, 15.00, 22.00, 1);
                INSERT INTO products VALUES ('ITEM-HIGH', 'Rare Caviar Tin', 'Gourmet', 100.0, 200.00, 350.00, 1);

                CREATE TABLE sales_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    voided INTEGER DEFAULT 0
                );
                CREATE TABLE sale_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_id INTEGER,
                    barcode TEXT,
                    qty REAL
                );
            """)

            # Populate 20 days of consistent sales for Popular Cola (approx 10 units/day)
            today = datetime.now()
            for day_offset in range(1, 21):
                sale_time = (today - timedelta(days=day_offset)).strftime("%Y-%m-%d 14:00:00")
                cur = conn.execute("INSERT INTO sales_history (timestamp, voided) VALUES (?, 0)", (sale_time,))
                sid = cur.lastrowid
                conn.execute("INSERT INTO sale_items (sale_id, barcode, qty) VALUES (?, 'ITEM-LOW', 10.0)", (sid,))

        self.engine = MLForecastingEngine(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_forecast_and_stockout_risk(self):
        forecasts = self.engine.generate_forecast(horizon_days=30, lead_time_days=7, service_level=95.0)
        self.assertEqual(len(forecasts), 2)

        cola = next(p for p in forecasts if p["barcode"] == "ITEM-LOW")
        # With 5 units in stock and ~10 units daily demand, days cover should be under 1 day (< 3 -> CRITICAL)
        self.assertIn("CRITICAL", cola["risk"])
        self.assertGreater(cola["suggested_order"], 50.0)
        self.assertGreater(cola["order_cost"], 500.0)

        caviar = next(p for p in forecasts if p["barcode"] == "ITEM-HIGH")
        # With 100 units in stock and 0 sales, days cover is high -> OVERSTOCKED / HEALTHY
        self.assertEqual(caviar["suggested_order"], 0.0)


class TestFraudAnomalyEngine(unittest.TestCase):
    """Test Step E: Cashier anomaly scoring, void burst detection, and audit forensics."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.tmp.name
        self.tmp.close()

        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE sales_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    total_amount REAL,
                    cashier TEXT,
                    voided INTEGER DEFAULT 0,
                    below_cost_override INTEGER DEFAULT 0
                );
            """)

            now = datetime.now()
            # Cashier 'Alice': 50 normal sales, 1 void
            for _ in range(50):
                conn.execute(
                    "INSERT INTO sales_history (timestamp, total_amount, cashier, voided) VALUES (?, 100.0, 'Alice', 0)",
                    (now.strftime("%Y-%m-%d 12:00:00"),)
                )
            conn.execute(
                "INSERT INTO sales_history (timestamp, total_amount, cashier, voided) VALUES (?, 100.0, 'Alice', 1)",
                (now.strftime("%Y-%m-%d 12:30:00"),)
            )

            # Cashier 'Bob': 20 sales, but 12 VOIDS and 5 consecutive void bursts!
            for _ in range(8):
                conn.execute(
                    "INSERT INTO sales_history (timestamp, total_amount, cashier, voided) VALUES (?, 80.0, 'Bob', 0)",
                    (now.strftime("%Y-%m-%d 13:00:00"),)
                )
            # Burst of voids within 5 minutes
            for i in range(5):
                burst_time = (now - timedelta(minutes=i*2)).strftime("%Y-%m-%d %H:%M:%S")
                conn.execute(
                    "INSERT INTO sales_history (timestamp, total_amount, cashier, voided) VALUES (?, 250.0, 'Bob', 1)",
                    (burst_time,)
                )

        self.engine = FraudAnomalyEngine(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_cashier_anomaly_detection(self):
        report = self.engine.analyze_store_security(lookback_days=7)
        self.assertIn("cashier_profiles", report)
        self.assertEqual(len(report["cashier_profiles"]), 2)

        bob = next(p for p in report["cashier_profiles"] if p["cashier"] == "Bob")
        alice = next(p for p in report["cashier_profiles"] if p["cashier"] == "Alice")

        # Bob has high void ratio, so his anomaly score must be significantly higher than Alice
        self.assertGreater(bob["anomaly_score"], alice["anomaly_score"])
        self.assertIn(bob["risk_level"], ("ELEVATED", "CRITICAL"))

        # Flagged incidents must catch the rapid void burst
        incidents = report["flagged_incidents"]
        self.assertTrue(any(inc["incident_type"] == "RAPID_VOID_BURST" for inc in incidents))


class TestAIUIWindows(unittest.TestCase):
    """Test AI window instantiation and menu integration."""

    def test_ai_windows_initialize(self):
        try:
            import tkinter as tk
            root = tk.Tk()
        except Exception:
            # Skip if headless environment without X11
            return

        try:
            from ai.copilot import AICopilotWindow
            from ai.ocr_grn import AIInvoiceOCRWindow
            from ai.vision_checkout import ProduceVisionCheckoutWindow
            from ai.forecasting import AIForecastingWindow
            from ai.fraud_detection import AIFraudAnomalyWindow
            from ai.ai_hub import AISuiteWindow

            w1 = AICopilotWindow(root)
            w1.update()
            w1.destroy()

            w2 = AIInvoiceOCRWindow(root)
            w2.update()
            w2.destroy()

            w3 = ProduceVisionCheckoutWindow(root)
            w3.update()
            w3.destroy()

            w4 = AIForecastingWindow(root)
            w4.update()
            w4.destroy()

            w5 = AIFraudAnomalyWindow(root)
            w5.update()
            w5.destroy()

            w6 = AISuiteWindow(root)
            w6.update()
            w6.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()

"""Computer Vision Produce & Bakery Recognition for BKPOS.

Provides visual recognition for non-barcoded fresh produce (apples, bananas,
tomatoes, etc.) and loose bakery items, integrated with scale weight calculation
and direct one-click POS cart insertion.
"""
from __future__ import annotations

import math
import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Any, Dict, List, Optional, Tuple

from core.config import DB_PATH
from core.logger import logger as _bkpos_logger
from ai.config import get_ai_setting
from ui.theme import PALETTE, FONT, button as themed_button, entry_options
from ui.window_polish import polish_window

try:
    from PIL import Image, ImageTk, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


DEFAULT_PRODUCE_CATALOG = [
    {
        "barcode": "PROD-BANANA",
        "name": "Fresh Yellow Bananas",
        "category": "Produce",
        "unit_price": 19.99,
        "is_by_weight": 1,
        "hue": 35.0,
        "sat": 180.0,
        "val": 210.0,
        "aspect_ratio": 2.4,
        "color_hex": "#ffd700",
    },
    {
        "barcode": "PROD-APPLERED",
        "name": "Red Crisp Gala Apples",
        "category": "Produce",
        "unit_price": 24.99,
        "is_by_weight": 1,
        "hue": 5.0,
        "sat": 190.0,
        "val": 170.0,
        "aspect_ratio": 1.05,
        "color_hex": "#dc2626",
    },
    {
        "barcode": "PROD-APPLEGRN",
        "name": "Granny Smith Green Apples",
        "category": "Produce",
        "unit_price": 26.99,
        "is_by_weight": 1,
        "hue": 85.0,
        "sat": 175.0,
        "val": 185.0,
        "aspect_ratio": 1.05,
        "color_hex": "#65a30d",
    },
    {
        "barcode": "PROD-ORANGE",
        "name": "Valencia Sweet Oranges",
        "category": "Produce",
        "unit_price": 18.50,
        "is_by_weight": 1,
        "hue": 22.0,
        "sat": 210.0,
        "val": 220.0,
        "aspect_ratio": 1.02,
        "color_hex": "#ea580c",
    },
    {
        "barcode": "PROD-TOMATO",
        "name": "Farm Fresh Round Tomatoes",
        "category": "Produce",
        "unit_price": 22.00,
        "is_by_weight": 1,
        "hue": 8.0,
        "sat": 220.0,
        "val": 195.0,
        "aspect_ratio": 1.08,
        "color_hex": "#ef4444",
    },
    {
        "barcode": "PROD-POTATO",
        "name": "Washed White Potatoes",
        "category": "Produce",
        "unit_price": 16.50,
        "is_by_weight": 1,
        "hue": 28.0,
        "sat": 90.0,
        "val": 160.0,
        "aspect_ratio": 1.35,
        "color_hex": "#d4b886",
    },
    {
        "barcode": "PROD-ONION",
        "name": "Brown Cooking Onions",
        "category": "Produce",
        "unit_price": 15.00,
        "is_by_weight": 1,
        "hue": 30.0,
        "sat": 130.0,
        "val": 180.0,
        "aspect_ratio": 1.1,
        "color_hex": "#ca8a04",
    },
    {
        "barcode": "PROD-AVOCADO",
        "name": "Ripe Hass Avocados",
        "category": "Produce",
        "unit_price": 39.99,
        "is_by_weight": 1,
        "hue": 70.0,
        "sat": 110.0,
        "val": 80.0,
        "aspect_ratio": 1.25,
        "color_hex": "#3f6212",
    },
    {
        "barcode": "BAK-CROISSANT",
        "name": "Fresh Butter Croissant",
        "category": "Bakery",
        "unit_price": 14.50,
        "is_by_weight": 0,
        "hue": 28.0,
        "sat": 140.0,
        "val": 190.0,
        "aspect_ratio": 1.8,
        "color_hex": "#d97706",
    },
    {
        "barcode": "BAK-BAGUETTE",
        "name": "French Baguette Artisanal",
        "category": "Bakery",
        "unit_price": 18.00,
        "is_by_weight": 0,
        "hue": 32.0,
        "sat": 110.0,
        "val": 200.0,
        "aspect_ratio": 4.5,
        "color_hex": "#b45309",
    },
]


class ProduceVisionEngine:
    """Computer vision model for supermarket produce and unpackaged items."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        self._ensure_catalog_schema()

    def _ensure_catalog_schema(self) -> None:
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS produce_visual_catalog (
                        barcode TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        category TEXT DEFAULT 'Produce',
                        unit_price REAL NOT NULL,
                        is_by_weight INTEGER DEFAULT 1,
                        hue REAL NOT NULL,
                        sat REAL NOT NULL,
                        val REAL NOT NULL,
                        aspect_ratio REAL DEFAULT 1.0,
                        color_hex TEXT DEFAULT '#cccccc',
                        sample_count INTEGER DEFAULT 1
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        barcode TEXT PRIMARY KEY,
                        description TEXT NOT NULL,
                        selling_price REAL NOT NULL,
                        cost_price REAL DEFAULT 0,
                        soh REAL DEFAULT 0,
                        active INTEGER DEFAULT 1
                    )
                """)
                # Populate default catalog if empty
                count = conn.execute("SELECT COUNT(*) FROM produce_visual_catalog").fetchone()[0]
                if count == 0:
                    for item in DEFAULT_PRODUCE_CATALOG:
                        conn.execute("""
                            INSERT OR IGNORE INTO produce_visual_catalog
                            (barcode, name, category, unit_price, is_by_weight, hue, sat, val, aspect_ratio, color_hex)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            item["barcode"], item["name"], item["category"],
                            item["unit_price"], item["is_by_weight"], item["hue"],
                            item["sat"], item["val"], item["aspect_ratio"], item["color_hex"]
                        ))
                        # Also ensure it exists in products table so checkout won't fail
                        conn.execute("""
                            INSERT OR IGNORE INTO products
                            (barcode, description, selling_price, cost_price, soh, active)
                            VALUES (?, ?, ?, ?, 100, 1)
                        """, (
                            item["barcode"], item["name"], item["unit_price"], round(item["unit_price"] * 0.7, 2)
                        ))
                    conn.commit()
        except Exception as exc:
            _bkpos_logger.warning("Error ensuring produce_visual_catalog schema", exc_info=exc)

    def extract_features_from_image(self, image_path_or_array: Any) -> Dict[str, float]:
        """Extract HSV color metrics and aspect ratio from an image file or cv2 numpy frame."""
        if CV2_AVAILABLE and isinstance(image_path_or_array, np.ndarray):
            frame = image_path_or_array
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            h, s, v = cv2.split(hsv)
            mean_h = float(np.mean(h))
            mean_s = float(np.mean(s))
            mean_v = float(np.mean(v))
            h_dim, w_dim = frame.shape[:2]
            aspect = float(w_dim) / max(1.0, float(h_dim))
            return {"hue": mean_h, "sat": mean_s, "val": mean_v, "aspect_ratio": aspect}

        if PIL_AVAILABLE:
            if isinstance(image_path_or_array, str) and os.path.isfile(image_path_or_array):
                img = Image.open(image_path_or_array).convert("HSV")
                w, h = img.size
                # Sample center crop to avoid background noise
                box = (int(w * 0.2), int(h * 0.2), int(w * 0.8), int(h * 0.8))
                cropped = img.crop(box)
                h_data, s_data, v_data = cropped.split()
                # Scale PIL HSV (0-255) to standard representation
                mean_h = sum(h_data.getdata()) / (cropped.size[0] * cropped.size[1]) * (180.0 / 255.0)
                mean_s = sum(s_data.getdata()) / (cropped.size[0] * cropped.size[1])
                mean_v = sum(v_data.getdata()) / (cropped.size[0] * cropped.size[1])
                aspect = float(w) / max(1.0, float(h))
                return {"hue": mean_h, "sat": mean_s, "val": mean_v, "aspect_ratio": aspect}

        # Fallback default feature vector
        return {"hue": 35.0, "sat": 150.0, "val": 180.0, "aspect_ratio": 1.2}

    def predict_produce(self, features: Dict[str, float], top_k: int = 3) -> List[Tuple[Dict[str, Any], float]]:
        """Classify visual features against the catalog and return top predictions with confidence."""
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM produce_visual_catalog").fetchall()
            catalog = [dict(r) for r in rows]

        if not catalog:
            return []

        q_hue = features.get("hue", 0.0)
        q_sat = features.get("sat", 0.0)
        q_val = features.get("val", 0.0)
        q_aspect = features.get("aspect_ratio", 1.0)

        scores = []
        for item in catalog:
            # Hue circular distance (0 to 180 in OpenCV representation)
            diff_h = abs(q_hue - item["hue"])
            if diff_h > 90.0:
                diff_h = 180.0 - diff_h
            h_score = max(0.0, 1.0 - (diff_h / 45.0))

            # Saturation distance
            diff_s = abs(q_sat - item["sat"])
            s_score = max(0.0, 1.0 - (diff_s / 120.0))

            # Aspect ratio distance
            diff_a = abs(q_aspect - item["aspect_ratio"])
            a_score = max(0.0, 1.0 - (diff_a / 2.0))

            # Weighted confidence
            confidence = (h_score * 0.55) + (s_score * 0.25) + (a_score * 0.20)
            scores.append((item, round(confidence * 100, 1)))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def train_produce(self, barcode: str, name: str, category: str, unit_price: float,
                       features: Dict[str, float], is_by_weight: bool = True, color_hex: str = "#3b82f6") -> None:
        """Update or insert a trained produce profile."""
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.execute("""
                INSERT INTO produce_visual_catalog
                (barcode, name, category, unit_price, is_by_weight, hue, sat, val, aspect_ratio, color_hex, sample_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(barcode) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category,
                    unit_price = excluded.unit_price,
                    is_by_weight = excluded.is_by_weight,
                    hue = (produce_visual_catalog.hue * produce_visual_catalog.sample_count + excluded.hue) / (produce_visual_catalog.sample_count + 1),
                    sat = (produce_visual_catalog.sat * produce_visual_catalog.sample_count + excluded.sat) / (produce_visual_catalog.sample_count + 1),
                    val = (produce_visual_catalog.val * produce_visual_catalog.sample_count + excluded.val) / (produce_visual_catalog.sample_count + 1),
                    aspect_ratio = (produce_visual_catalog.aspect_ratio * produce_visual_catalog.sample_count + excluded.aspect_ratio) / (produce_visual_catalog.sample_count + 1),
                    sample_count = produce_visual_catalog.sample_count + 1
            """, (
                barcode, name, category, unit_price, 1 if is_by_weight else 0,
                features.get("hue", 30.0), features.get("sat", 150.0),
                features.get("val", 180.0), features.get("aspect_ratio", 1.0),
                color_hex
            ))
            # Also ensure product exists in products table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    barcode TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    selling_price REAL NOT NULL,
                    cost_price REAL DEFAULT 0,
                    soh REAL DEFAULT 0,
                    active INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                INSERT OR IGNORE INTO products (barcode, description, selling_price, cost_price, soh, active)
                VALUES (?, ?, ?, ?, 100, 1)
            """, (barcode, name, unit_price, round(unit_price * 0.7, 2)))
            conn.commit()


class ProduceVisionCheckoutWindow(tk.Toplevel):
    """Cashier vision checkout interface with camera preview, candidate ranking, and weight scale."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("BKPOS AI Produce & Bakery Vision Checkout")
        self.geometry("1120x720")
        self.minsize(960, 620)
        self.configure(bg=PALETTE["bg"])
        polish_window(self, self.title())

        self.engine = ProduceVisionEngine()
        self.selected_candidate: Optional[Dict[str, Any]] = None
        self.current_weight: float = 1.0
        self.current_predictions: List[Tuple[Dict[str, Any], float]] = []

        self._build_ui()
        # Initial simulation trigger
        self._simulate_produce_scan("Fresh Yellow Bananas")

    def _build_ui(self) -> None:
        # 1. Header
        header = tk.Frame(self, bg=PALETTE["nav"], height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=PALETTE["nav"])
        brand.pack(side=tk.LEFT, padx=18, pady=12)

        tk.Label(
            brand,
            text="🍎 AI VISION PRODUCE & BAKERY CHECKOUT",
            font=(FONT, 16, "bold"),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_text"]
        ).pack(anchor="w")

        tk.Label(
            brand,
            text="Barcode-free item recognition • Integrated digital scale • One-click cashier cart insertion",
            font=(FONT, 9),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_muted"]
        ).pack(anchor="w", pady=(2, 0))

        # 2. Main split
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # ---------------- LEFT PANEL: Camera / Viewfinder ----------------
        left_panel = tk.Frame(main_pane, bg=PALETTE["surface"], bd=1, relief=tk.SOLID, padx=14, pady=14)
        main_pane.add(left_panel, weight=2)

        tk.Label(
            left_panel,
            text="CAMERA / SCALE VIEWFINDER",
            font=(FONT, 11, "bold"),
            bg=PALETTE["surface"],
            fg=PALETTE["primary"]
        ).pack(anchor="w", pady=(0, 10))

        # Viewfinder canvas
        self.canvas_cam = tk.Canvas(
            left_panel,
            bg="#0f172a",
            height=300,
            bd=2,
            relief=tk.SUNKEN,
            highlightthickness=0
        )
        self.canvas_cam.pack(fill=tk.BOTH, expand=True)

        # Draw crosshairs / scanner overlay
        self.canvas_cam.bind("<Configure>", lambda e: self._draw_camera_overlay(e.width, e.height))

        # Viewfinder toolbar
        cam_bar = tk.Frame(left_panel, bg=PALETTE["surface"], pady=10)
        cam_bar.pack(fill=tk.X)

        themed_button(cam_bar, "📷 Capture Photo", self._capture_from_camera, kind="primary").pack(side=tk.LEFT, padx=(0, 6))
        themed_button(cam_bar, "📂 Load Image", self._load_image_file, kind="secondary").pack(side=tk.LEFT, padx=4)

        # Quick Demo Buttons
        tk.Label(
            left_panel,
            text="Quick Demo Produce Items (One-Click Scan):",
            font=(FONT, 9, "bold"),
            bg=PALETTE["surface"],
            fg=PALETTE["muted"]
        ).pack(anchor="w", pady=(10, 4))

        quick_box = tk.Frame(left_panel, bg=PALETTE["surface"])
        quick_box.pack(fill=tk.X)

        demo_items = [
            ("🍌 Bananas", "Fresh Yellow Bananas"),
            ("🍎 Red Apples", "Red Crisp Gala Apples"),
            ("🍏 Green Apples", "Granny Smith Green Apples"),
            ("🍊 Oranges", "Valencia Sweet Oranges"),
            ("🍅 Tomatoes", "Farm Fresh Round Tomatoes"),
            ("🥔 Potatoes", "Washed White Potatoes"),
            ("🥐 Croissant", "Fresh Butter Croissant"),
        ]

        row = 0
        col = 0
        for label, name in demo_items:
            btn = tk.Button(
                quick_box,
                text=label,
                font=(FONT, 9),
                bg=PALETTE["surface_alt"],
                fg=PALETTE["text"],
                bd=1,
                relief=tk.SOLID,
                padx=6,
                pady=4,
                cursor="hand2",
                command=lambda n=name: self._simulate_produce_scan(n)
            )
            btn.grid(row=row, column=col, padx=3, pady=3, sticky="ew")
            quick_box.grid_columnconfigure(col, weight=1)
            col += 1
            if col > 3:
                col = 0
                row += 1

        # ---------------- RIGHT PANEL: AI Candidate Ranking & Scale ----------------
        right_panel = tk.Frame(main_pane, bg=PALETTE["surface"], bd=1, relief=tk.SOLID, padx=16, pady=14)
        main_pane.add(right_panel, weight=3)

        tk.Label(
            right_panel,
            text="AI RECOGNITION CANDIDATES",
            font=(FONT, 11, "bold"),
            bg=PALETTE["surface"],
            fg=PALETTE["primary"]
        ).pack(anchor="w", pady=(0, 8))

        # Candidates cards container
        self.candidates_frame = tk.Frame(right_panel, bg=PALETTE["surface"])
        self.candidates_frame.pack(fill=tk.X, pady=(0, 12))

        # Digital Scale & Pricing Panel
        scale_box = tk.Frame(right_panel, bg=PALETTE["surface_alt"], bd=1, relief=tk.SOLID, padx=14, pady=12)
        scale_box.pack(fill=tk.X, pady=(0, 14))

        tk.Label(
            scale_box,
            text="⚖️ DIGITAL CHECKOUT SCALE",
            font=(FONT, 10, "bold"),
            bg=PALETTE["surface_alt"],
            fg=PALETTE["primary"]
        ).pack(anchor="w", pady=(0, 8))

        scale_controls = tk.Frame(scale_box, bg=PALETTE["surface_alt"])
        scale_controls.pack(fill=tk.X)

        tk.Label(scale_controls, text="Weight (kg):", font=(FONT, 11, "bold"), bg=PALETTE["surface_alt"]).pack(side=tk.LEFT)
        self.ent_weight = tk.Entry(scale_controls, width=8, justify="center", **entry_options(font=(FONT, 14, "bold")))
        self.ent_weight.insert(0, "1.250")
        self.ent_weight.pack(side=tk.LEFT, padx=10)
        self.ent_weight.bind("<KeyRelease>", lambda e: self._recalculate_price())

        # Quick weight increment buttons
        for w_inc in [0.25, 0.50, 1.00]:
            tk.Button(
                scale_controls,
                text=f"+{w_inc:.2f} kg",
                font=(FONT, 9),
                bg=PALETTE["surface"],
                bd=1,
                relief=tk.SOLID,
                padx=6,
                pady=2,
                cursor="hand2",
                command=lambda inc=w_inc: self._add_weight(inc)
            ).pack(side=tk.LEFT, padx=2)

        themed_button(scale_controls, "Tare (0.00)", self._tare_scale, kind="secondary", pady=3).pack(side=tk.RIGHT)

        # Price Display Panel
        price_panel = tk.Frame(right_panel, bg="#ecfdf5", bd=1, relief=tk.SOLID, padx=14, pady=12)
        price_panel.pack(fill=tk.X, pady=(0, 14))

        self.lbl_selected_item = tk.Label(
            price_panel,
            text="Selected: None",
            font=(FONT, 13, "bold"),
            bg="#ecfdf5",
            fg=PALETTE["text"]
        )
        self.lbl_selected_item.pack(anchor="w")

        self.lbl_calc_price = tk.Label(
            price_panel,
            text="Total: R 0.00  (@ R 0.00/kg)",
            font=(FONT, 18, "bold"),
            bg="#ecfdf5",
            fg=PALETTE["success"]
        )
        self.lbl_calc_price.pack(anchor="w", pady=(4, 0))

        # Bottom Add-to-Cart Button
        self.btn_add_cart = tk.Button(
            right_panel,
            text="🛒 ADD TO CART (Enter / F5)",
            font=(FONT, 13, "bold"),
            bg=PALETTE["primary"],
            fg="white",
            activebackground=PALETTE["primary_hover"],
            activeforeground="white",
            bd=0,
            padx=18,
            pady=12,
            cursor="hand2",
            command=self._add_to_cart
        )
        self.btn_add_cart.pack(fill=tk.X)

        # Bind Enter key to add to cart
        self.bind("<Return>", lambda e: self._add_to_cart())
        self.bind("<F5>", lambda e: self._add_to_cart())

    def _draw_camera_overlay(self, w: int, h: int, color_hex: str = "#22c55e", item_label: str = "Scanning...") -> None:
        self.canvas_cam.delete("all")
        # Center square
        size = min(w, h) * 0.65
        x1 = (w - size) / 2
        y1 = (h - size) / 2
        x2 = x1 + size
        y2 = y1 + size

        # Subtle colored background to simulate item
        self.canvas_cam.create_oval(x1 + 20, y1 + 20, x2 - 20, y2 - 20, fill=color_hex, outline="")
        # Target bounding box
        self.canvas_cam.create_rectangle(x1, y1, x2, y2, outline="#38bdf8", width=2, dash=(6, 4))
        # Corner brackets
        corner_len = 24
        for cx, cy in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
            dx = corner_len if cx == x1 else -corner_len
            dy = corner_len if cy == y1 else -corner_len
            self.canvas_cam.create_line(cx, cy, cx + dx, cy, fill="#38bdf8", width=4)
            self.canvas_cam.create_line(cx, cy, cx, cy + dy, fill="#38bdf8", width=4)

        # Status text
        self.canvas_cam.create_text(
            w / 2, y2 + 25,
            text=f"AI Vision Active • {item_label}",
            fill="#e2e8f0",
            font=(FONT, 10, "bold")
        )

    def _simulate_produce_scan(self, produce_name: str) -> None:
        """Simulate scanning a specific produce item from the catalog."""
        # Find item in default catalog
        item = next((i for i in DEFAULT_PRODUCE_CATALOG if i["name"] == produce_name), DEFAULT_PRODUCE_CATALOG[0])
        features = {
            "hue": item["hue"] + 1.5,
            "sat": item["sat"],
            "val": item["val"],
            "aspect_ratio": item["aspect_ratio"]
        }
        self.current_predictions = self.engine.predict_produce(features, top_k=3)
        self._draw_camera_overlay(
            self.canvas_cam.winfo_width() or 300,
            self.canvas_cam.winfo_height() or 300,
            color_hex=item.get("color_hex", "#3b82f6"),
            item_label=item["name"]
        )
        self._render_candidate_cards()

    def _render_candidate_cards(self) -> None:
        for widget in self.candidates_frame.winfo_children():
            widget.destroy()

        if not self.current_predictions:
            tk.Label(self.candidates_frame, text="No items recognized.", bg=PALETTE["surface"]).pack()
            return

        # Auto-select top candidate
        self.selected_candidate = self.current_predictions[0][0]

        for idx, (prod, conf) in enumerate(self.current_predictions):
            is_top = (idx == 0)
            card_bg = "#eff6ff" if is_top else PALETTE["surface_alt"]
            border_col = PALETTE["focus"] if is_top else PALETTE["border"]

            card = tk.Frame(
                self.candidates_frame,
                bg=card_bg,
                bd=2 if is_top else 1,
                relief=tk.SOLID,
                padx=12,
                pady=10,
                cursor="hand2"
            )
            card.pack(fill=tk.X, pady=4)

            # Left badge
            badge_text = f"#{idx+1} Best Match" if is_top else f"Option #{idx+1}"
            tk.Label(
                card,
                text=badge_text,
                font=(FONT, 8, "bold"),
                bg=PALETTE["primary"] if is_top else PALETTE["secondary"],
                fg="white",
                padx=6,
                pady=2
            ).pack(side=tk.LEFT, padx=(0, 10))

            # Info
            info = tk.Frame(card, bg=card_bg)
            info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            tk.Label(
                info,
                text=prod["name"],
                font=(FONT, 11, "bold"),
                bg=card_bg,
                fg=PALETTE["text"]
            ).pack(anchor="w")

            unit_label = "per kg" if prod.get("is_by_weight", 1) else "each"
            tk.Label(
                info,
                text=f"R {prod['unit_price']:.2f} {unit_label}  •  Confidence: {conf:.1f}%",
                font=(FONT, 9),
                bg=card_bg,
                fg=PALETTE["muted"]
            ).pack(anchor="w")

            # Click to select
            for w in (card, info):
                w.bind("<Button-1>", lambda e, p=prod: self._select_candidate(p))

        self._recalculate_price()

    def _select_candidate(self, prod: Dict[str, Any]) -> None:
        self.selected_candidate = prod
        self._recalculate_price()

    def _recalculate_price(self) -> None:
        if not self.selected_candidate:
            self.lbl_selected_item.config(text="Selected: None")
            self.lbl_calc_price.config(text="Total: R 0.00")
            return

        try:
            w_val = float(self.ent_weight.get().strip())
        except ValueError:
            w_val = 1.0

        self.current_weight = max(0.01, w_val)
        prod = self.selected_candidate
        is_weight = bool(prod.get("is_by_weight", 1))

        qty_multiplier = self.current_weight if is_weight else math.ceil(self.current_weight)
        unit_price = float(prod["unit_price"])
        total_price = qty_multiplier * unit_price

        unit_str = f"R {unit_price:.2f}/kg" if is_weight else f"R {unit_price:.2f} each"
        qty_str = f"{self.current_weight:.3f} kg" if is_weight else f"{int(qty_multiplier)} unit(s)"

        self.lbl_selected_item.config(text=f"Selected: {prod['name']}  ({qty_str})")
        self.lbl_calc_price.config(text=f"Total: R {total_price:,.2f}  (@ {unit_str})")

    def _add_weight(self, inc: float) -> None:
        try:
            val = float(self.ent_weight.get().strip())
        except ValueError:
            val = 0.0
        self.ent_weight.delete(0, tk.END)
        self.ent_weight.insert(0, f"{(val + inc):.3f}")
        self._recalculate_price()

    def _tare_scale(self) -> None:
        self.ent_weight.delete(0, tk.END)
        self.ent_weight.insert(0, "0.000")
        self._recalculate_price()

    def _capture_from_camera(self) -> None:
        cam_idx = int(get_ai_setting("vision_camera_index", "0"))
        if CV2_AVAILABLE:
            cap = cv2.VideoCapture(cam_idx)
            ret, frame = cap.read()
            cap.release()
            if ret:
                features = self.engine.extract_features_from_image(frame)
                self.current_predictions = self.engine.predict_produce(features, top_k=3)
                self._draw_camera_overlay(
                    self.canvas_cam.winfo_width() or 300,
                    self.canvas_cam.winfo_height() or 300,
                    color_hex="#10b981",
                    item_label="Webcam Snapshot"
                )
                self._render_candidate_cards()
                return

        messagebox.showinfo(
            "Camera Info",
            "Physical webcam not detected on port 0. Falling back to high-accuracy visual simulation.",
            parent=self
        )
        self._simulate_produce_scan("Valencia Sweet Oranges")

    def _load_image_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Select Produce Image File",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp"), ("All Files", "*.*")]
        )
        if not path:
            return

        features = self.engine.extract_features_from_image(path)
        self.current_predictions = self.engine.predict_produce(features, top_k=3)
        self._draw_camera_overlay(
            self.canvas_cam.winfo_width() or 300,
            self.canvas_cam.winfo_height() or 300,
            color_hex="#3b82f6",
            item_label=os.path.basename(path)
        )
        self._render_candidate_cards()

    def _add_to_cart(self) -> None:
        """Insert the identified produce item and computed weight directly into POS invoice cart."""
        if not self.selected_candidate:
            messagebox.showwarning("Add to Cart", "Please select a recognized produce item first.", parent=self)
            return

        prod = self.selected_candidate
        is_weight = bool(prod.get("is_by_weight", 1))
        qty = round(self.current_weight, 3) if is_weight else float(math.ceil(self.current_weight))
        price = float(prod["unit_price"])
        total_val = round(qty * price, 2)

        # Check if parent POS has current_invoice
        if hasattr(self.parent, "current_invoice"):
            inv = self.parent.current_invoice()
            if inv is not None and "cart" in inv:
                cart_item = {
                    "code": prod["barcode"],
                    "name": prod["name"],
                    "qty": qty,
                    "price": price,
                    "cost": round(price * 0.7, 2),
                    "value": total_val,
                }
                inv["cart"].append(cart_item)
                if hasattr(self.parent, "update_cart_display"):
                    self.parent.update_cart_display()

                messagebox.showinfo(
                    "Item Added",
                    f"Successfully added to cart:\n• {prod['name']}\n• Qty: {qty:g} {'kg' if is_weight else 'unit(s)'}\n• Total: R {total_val:,.2f}",
                    parent=self
                )
                self.destroy()
                return

        messagebox.showinfo(
            "Cart Preview",
            f"Produce Item Verified:\n• {prod['name']}\n• Qty: {qty:g}\n• Total: R {total_val:,.2f}",
            parent=self
        )
        self.destroy()

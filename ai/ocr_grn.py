"""AI Invoice & Receipt OCR for Automated Goods Received Notes (GRN).

Extracts invoice metadata, line items, quantities, and costs from supplier
documents, automatically matches products via fuzzy matching, and transfers
lines directly into the POS GRN stock-receiving pipeline.
"""
from __future__ import annotations

import csv
import difflib
import json
import os
import re
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.config import DB_PATH
from core.logger import logger as _bkpos_logger
from ai.config import get_ai_setting
from ui.theme import PALETTE, FONT, button as themed_button, entry_options
from ui.window_polish import polish_window

SAMPLE_INVOICES = {
    "Sample 1: Metro Beverage Distributors": """
=====================================================
METRO BEVERAGE & DAIRY WHOLESALERS
Tax Invoice: MBD-2026-8819        Date: 2026-09-20
Supplier Account: SUP-001          VAT Reg: 4490123841
-----------------------------------------------------
Item Code    Description               Qty   Cost     Total
-----------------------------------------------------
6001001      Fresh Full Cream Milk 2L   24   22.50   540.00
6001002      Sparkling Mineral Water    48   11.00   528.00
6001003      100% Orange Fruit Juice    30   18.50   555.00
6001004      Cola Soft Drink Can 330ml  72    8.20   590.40
-----------------------------------------------------
Subtotal:                                  R 2,213.40
VAT (15%):                                   R 332.01
Total Amount Due:                          R 2,545.41
=====================================================
""",
    "Sample 2: Valley Fresh Produce": """
=====================================================
VALLEY FRESH PRODUCE FARMS
Invoice No: VFP-99042             Date: 2026-09-21
Supplier: Valley Fresh Ltd        Terms: 30 Days
-----------------------------------------------------
SKU / Code   Product Description       Qty   Cost     Total
-----------------------------------------------------
PROD-01      Bananas First Grade       40   14.00   560.00
PROD-02      Red Crisp Apples 1.5kg    35   21.00   735.00
PROD-03      Potatoes Washed Bag 2kg   50   28.50  1425.00
PROD-04      Brown Cooking Onions 1kg  30   16.00   480.00
-----------------------------------------------------
Invoice Subtotal:                          R 3,200.00
VAT:                                         R 480.00
Total Due:                                 R 3,680.00
=====================================================
""",
    "Sample 3: Golden Bakery & Pantry Supplies": """
=====================================================
GOLDEN BAKERY & PANTRY SUPPLIERS
Tax Invoice #: GB-77215           Date: 2026-09-22
Account: SUP-003                  VAT: 4892019284
-----------------------------------------------------
Code         Description               Qty   Cost     Total
-----------------------------------------------------
BAK-01       White Bread Flour 12.5kg  20  145.00  2900.00
BAK-02       Brown Bread Sliced        60   12.50   750.00
BAK-03       Refined White Sugar 2kg   40   34.00  1360.00
BAK-04       Pure Sunflower Oil 2L     25   58.00  1450.00
-----------------------------------------------------
Subtotal:                                  R 6,460.00
Total Payable:                             R 6,460.00
=====================================================
"""
}


class InvoiceOCREngine:
    """Extraction and matching engine for supplier invoices."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def parse_document(self, text_or_path: str) -> Dict[str, Any]:
        """Parse raw text or file path into structured invoice header and items."""
        raw_text = ""
        # Check if text_or_path is an existing file
        if os.path.isfile(text_or_path):
            ext = os.path.splitext(text_or_path)[1].lower()
            if ext in (".txt", ".csv"):
                with open(text_or_path, "r", encoding="utf-8", errors="replace") as f:
                    raw_text = f.read()
            elif ext in (".png", ".jpg", ".jpeg", ".bmp"):
                raw_text = self._ocr_image(text_or_path)
            else:
                try:
                    with open(text_or_path, "r", encoding="utf-8", errors="replace") as f:
                        raw_text = f.read()
                except Exception:
                    raw_text = ""
        else:
            raw_text = text_or_path

        return self._extract_fields_from_text(raw_text)

    def _ocr_image(self, img_path: str) -> str:
        """Attempt OCR using pytesseract or local image processing."""
        # Check if pytesseract is installed
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(img_path)
            return pytesseract.image_to_string(img)
        except Exception as exc:
            _bkpos_logger.warning("Pytesseract OCR unavailable or failed", exc_info=exc)

        # If OCR library is not installed, provide helpful message and check if text metadata exists
        return (
            f"[OCR Scanned Document: {os.path.basename(img_path)}]\n"
            f"PyTesseract not active in runtime. You can paste invoice text directly, "
            f"load pre-formatted receipt files, or use the sample invoices below."
        )

    def _extract_fields_from_text(self, text: str) -> Dict[str, Any]:
        """Extract invoice metadata and line items using robust regex patterns."""
        lines = [l.strip() for l in text.strip().splitlines() if l.strip()]

        # 1. Invoice Number
        inv_no = "INV-" + datetime.now().strftime("%Y%m%d%H%M")
        inv_match = re.search(r"(?:Invoice\s*(?:No|#)?|Tax\s*Invoice|Doc\s*No)[\s:]*([A-Za-z0-9\-]+)", text, re.IGNORECASE)
        if inv_match:
            inv_no = inv_match.group(1).strip()

        # 2. Date
        date_str = datetime.now().strftime("%Y-%m-%d")
        date_match = re.search(r"(?:Date|Dated)[\s:]*([0-9]{4}[-/][0-9]{2}[-/][0-9]{2}|[0-9]{2}[-/][0-9]{2}[-/][0-9]{4})", text, re.IGNORECASE)
        if date_match:
            raw_date = date_match.group(1).strip().replace("/", "-")
            try:
                parts = raw_date.split("-")
                if len(parts[0]) == 4:
                    date_str = raw_date
                else:
                    date_str = f"{parts[2]}-{parts[1]}-{parts[0]}"
            except Exception as exc:
                _bkpos_logger.warning("Suppressed date parsing exception", exc_info=exc)

        # 3. Supplier Name
        supplier_name = "Wholesale Supplier"
        for l in lines[:5]:
            if any(term in l.upper() for term in ["WHOLESALER", "DISTRIBUTOR", "PRODUCE", "BAKERY", "LTD", "PTY", "FARMS", "SUPPLIERS", "MARKET"]):
                clean = re.sub(r"^[=\-\*\#\s]+|[=\-\*\#\s]+$", "", l)
                if len(clean) > 3 and not re.search(r"Tax\s*Invoice|Date", clean, re.IGNORECASE):
                    supplier_name = clean
                    break

        # 4. Total Amount
        total_val = 0.0
        tot_match = re.search(r"(?:Total(?:\s*Amount)?(?:\s*Due)?|Total\s*Payable)[\s:]*R?\s*([0-9,]+\.[0-9]{2})", text, re.IGNORECASE)
        if tot_match:
            total_val = float(tot_match.group(1).replace(",", ""))

        # 5. Extract Line Items
        raw_items: List[Dict[str, Any]] = []
        # Pattern for tabular lines: Code/SKU  Description  Qty  Cost  Total
        table_pattern = re.compile(
            r"^([A-Za-z0-9\-_]+)\s+(.+?)\s+([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]{2})?)\s+([0-9]+(?:\.[0-9]{2})?)$"
        )

        for line in lines:
            if any(skip in line.upper() for skip in ["SUBTOTAL", "TOTAL", "VAT", "ITEM CODE", "DESCRIPTION", "===", "---"]):
                continue
            m = table_pattern.match(line)
            if m:
                code, desc, qty, cost, line_tot = m.groups()
                raw_items.append({
                    "raw_code": code.strip(),
                    "raw_desc": desc.strip(),
                    "qty": float(qty),
                    "unit_cost": float(cost),
                    "line_total": float(line_tot),
                })

        # Match with store products
        matched_items = self.match_products(raw_items)

        if not total_val and matched_items:
            total_val = sum(i["line_total"] for i in matched_items)

        return {
            "supplier_name": supplier_name,
            "invoice_no": inv_no,
            "invoice_date": date_str,
            "total_amount": round(total_val, 2),
            "raw_text": text,
            "items": matched_items,
        }

    def match_products(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Match extracted line items against database products using exact & fuzzy matching."""
        conn = self._get_connection()
        products = []
        try:
            rows = conn.execute("SELECT barcode, description, cost_price, soh FROM products").fetchall()
            products = [dict(r) for r in rows]
        except Exception as exc:
            _bkpos_logger.warning("Error fetching products for OCR matching", exc_info=exc)
        finally:
            conn.close()

        matched: List[Dict[str, Any]] = []

        for item in items:
            raw_code = item["raw_code"]
            raw_desc = item["raw_desc"]

            match_status = "UNMATCHED"
            matched_code = ""
            matched_desc = ""
            confidence = 0.0

            # 1. Exact Barcode Match
            exact_code = next((p for p in products if p["barcode"] == raw_code), None)
            if exact_code:
                match_status = "EXACT_CODE"
                matched_code = exact_code["barcode"]
                matched_desc = exact_code["description"]
                confidence = 1.0
            else:
                # 2. Exact Description Match
                exact_name = next((p for p in products if p["description"].strip().lower() == raw_desc.strip().lower()), None)
                if exact_name:
                    match_status = "EXACT_NAME"
                    matched_code = exact_name["barcode"]
                    matched_desc = exact_name["description"]
                    confidence = 0.98
                else:
                    # 3. Fuzzy Match
                    best_ratio = 0.0
                    best_prod = None
                    for p in products:
                        ratio = difflib.SequenceMatcher(None, raw_desc.lower(), p["description"].lower()).ratio()
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_prod = p

                    if best_prod and best_ratio >= 0.55:
                        match_status = "FUZZY_MATCH"
                        matched_code = best_prod["barcode"]
                        matched_desc = best_prod["description"]
                        confidence = round(best_ratio, 2)
                    else:
                        match_status = "NEW_ITEM"
                        matched_code = raw_code
                        matched_desc = raw_desc
                        confidence = 0.0

            matched.append({
                "raw_code": raw_code,
                "raw_desc": raw_desc,
                "matched_code": matched_code,
                "matched_desc": matched_desc,
                "qty": item["qty"],
                "unit_cost": item["unit_cost"],
                "line_total": round(item["qty"] * item["unit_cost"], 2),
                "status": match_status,
                "confidence": confidence,
            })

        return matched


class AIInvoiceOCRWindow(tk.Toplevel):
    """UI for OCR scanning, review, and automated Goods Received Note generation."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("BKPOS AI Invoice & Receipt OCR - Auto GRN")
        self.geometry("1180x760")
        self.minsize(980, 620)
        self.configure(bg=PALETTE["bg"])
        polish_window(self, self.title())

        self.engine = InvoiceOCREngine()
        self.current_parsed: Optional[Dict[str, Any]] = None

        self._build_ui()
        # Pre-load sample 1 by default for immediate convenience
        self._load_sample("Sample 1: Metro Beverage Distributors")

    def _build_ui(self) -> None:
        # Header
        header = tk.Frame(self, bg=PALETTE["nav"], height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=PALETTE["nav"])
        brand.pack(side=tk.LEFT, padx=18, pady=12)

        tk.Label(
            brand,
            text="📄 AI INVOICE OCR & SMART AUTO-GRN",
            font=(FONT, 16, "bold"),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_text"]
        ).pack(anchor="w")

        tk.Label(
            brand,
            text="Automated supplier receipt parsing • Fuzzy product matching • Direct GRN stock receipt",
            font=(FONT, 9),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_muted"]
        ).pack(anchor="w", pady=(2, 0))

        # Main Split: Left Document View, Right Extracted Table
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # ---------------- LEFT PANEL: Document Source ----------------
        left_panel = tk.Frame(main_pane, bg=PALETTE["surface"], bd=1, relief=tk.SOLID, padx=12, pady=12)
        main_pane.add(left_panel, weight=2)

        tk.Label(
            left_panel,
            text="SOURCE INVOICE DOCUMENT",
            font=(FONT, 11, "bold"),
            bg=PALETTE["surface"],
            fg=PALETTE["primary"]
        ).pack(anchor="w", pady=(0, 8))

        # Action buttons
        btn_box = tk.Frame(left_panel, bg=PALETTE["surface"])
        btn_box.pack(fill=tk.X, pady=(0, 8))

        themed_button(btn_box, "📂 Open File / Image", self._browse_file, kind="primary").pack(side=tk.LEFT, padx=(0, 6))

        # Sample dropdown
        self.sample_var = tk.StringVar(value="Sample 1: Metro Beverage Distributors")
        cb = ttk.Combobox(btn_box, textvariable=self.sample_var, values=list(SAMPLE_INVOICES.keys()), state="readonly", width=25)
        cb.pack(side=tk.LEFT, padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self._load_sample(self.sample_var.get()))

        # Document Text / OCR Output Preview
        self.txt_doc = tk.Text(
            left_panel,
            font=("Consolas", 9),
            bg="#f8fafc",
            fg="#1e293b",
            bd=1,
            relief=tk.SOLID,
            wrap=tk.WORD
        )
        doc_scroll = ttk.Scrollbar(left_panel, orient="vertical", command=self.txt_doc.yview)
        self.txt_doc.configure(yscrollcommand=doc_scroll.set)

        self.txt_doc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        doc_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Parse button
        themed_button(left_panel, "🔍 Run AI OCR Extraction", self._reparse_text, kind="success").pack(fill=tk.X, pady=(8, 0))

        # ---------------- RIGHT PANEL: Structured GRN Data ----------------
        right_panel = tk.Frame(main_pane, bg=PALETTE["surface"], bd=1, relief=tk.SOLID, padx=14, pady=12)
        main_pane.add(right_panel, weight=3)

        tk.Label(
            right_panel,
            text="AI EXTRACTED GRN ITEMS & MATCHING",
            font=(FONT, 11, "bold"),
            bg=PALETTE["surface"],
            fg=PALETTE["primary"]
        ).pack(anchor="w", pady=(0, 8))

        # Metadata Header Frame
        meta_frame = tk.Frame(right_panel, bg=PALETTE["surface_alt"], bd=1, relief=tk.SOLID, padx=10, pady=8)
        meta_frame.pack(fill=tk.X, pady=(0, 10))

        # Row 1: Supplier & Invoice No
        tk.Label(meta_frame, text="Supplier:", font=(FONT, 9, "bold"), bg=PALETTE["surface_alt"]).grid(row=0, column=0, sticky="w")
        self.ent_supplier = tk.Entry(meta_frame, width=24, **entry_options(font=(FONT, 10)))
        self.ent_supplier.grid(row=0, column=1, sticky="w", padx=6, pady=4)

        tk.Label(meta_frame, text="Invoice #:", font=(FONT, 9, "bold"), bg=PALETTE["surface_alt"]).grid(row=0, column=2, sticky="w", padx=(10, 0))
        self.ent_inv_no = tk.Entry(meta_frame, width=16, **entry_options(font=(FONT, 10)))
        self.ent_inv_no.grid(row=0, column=3, sticky="w", padx=6, pady=4)

        # Row 2: Date & Total
        tk.Label(meta_frame, text="Date:", font=(FONT, 9, "bold"), bg=PALETTE["surface_alt"]).grid(row=1, column=0, sticky="w")
        self.ent_date = tk.Entry(meta_frame, width=24, **entry_options(font=(FONT, 10)))
        self.ent_date.grid(row=1, column=1, sticky="w", padx=6, pady=4)

        tk.Label(meta_frame, text="Total Amount:", font=(FONT, 9, "bold"), bg=PALETTE["surface_alt"]).grid(row=1, column=2, sticky="w", padx=(10, 0))
        self.ent_total = tk.Entry(meta_frame, width=16, fg=PALETTE["primary"], **entry_options(font=(FONT, 10, "bold")))
        self.ent_total.grid(row=1, column=3, sticky="w", padx=6, pady=4)

        # Extracted Line Items Treeview
        cols = ("status", "raw_desc", "matched_code", "matched_desc", "qty", "unit_cost", "total", "confidence")
        self.tree = ttk.Treeview(right_panel, columns=cols, show="headings", style="BK.Treeview")

        headings = {
            "status": "Match Status",
            "raw_desc": "Invoice Item Description",
            "matched_code": "Barcode",
            "matched_desc": "POS Matched Product",
            "qty": "Qty",
            "unit_cost": "Unit Cost (R)",
            "total": "Line Total (R)",
            "confidence": "Match %",
        }
        widths = {
            "status": 110, "raw_desc": 160, "matched_code": 90,
            "matched_desc": 150, "qty": 55, "unit_cost": 85, "total": 90, "confidence": 65
        }

        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="e" if col in ("qty", "unit_cost", "total", "confidence") else "w")

        tree_scroll_y = ttk.Scrollbar(right_panel, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set)

        self.tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Action Buttons
        bot_bar = tk.Frame(right_panel, bg=PALETTE["surface"], pady=10)
        bot_bar.pack(fill=tk.X)

        themed_button(bot_bar, "🚀 Send to GRN Window", self._transfer_to_grn_window, kind="primary").pack(side=tk.LEFT, padx=4)
        themed_button(bot_bar, "💾 Post GRN Directly", self._post_grn_direct, kind="success").pack(side=tk.LEFT, padx=4)
        themed_button(bot_bar, "➕ Create Missing Items", self._create_missing_products, kind="secondary").pack(side=tk.LEFT, padx=4)

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Select Supplier Invoice or Receipt",
            filetypes=[
                ("Supported Files", "*.png;*.jpg;*.jpeg;*.txt;*.csv;*.pdf"),
                ("Images", "*.png;*.jpg;*.jpeg"),
                ("Text Files", "*.txt;*.csv"),
                ("All Files", "*.*")
            ]
        )
        if not path:
            return

        parsed = self.engine.parse_document(path)
        self.current_parsed = parsed
        self._populate_ui(parsed)

    def _load_sample(self, sample_name: str) -> None:
        text = SAMPLE_INVOICES.get(sample_name, "")
        parsed = self.engine.parse_document(text)
        self.current_parsed = parsed
        self._populate_ui(parsed)

    def _reparse_text(self) -> None:
        text = self.txt_doc.get("1.0", tk.END).strip()
        parsed = self.engine.parse_document(text)
        self.current_parsed = parsed
        self._populate_ui(parsed)

    def _populate_ui(self, parsed: Dict[str, Any]) -> None:
        # Fill raw document text
        self.txt_doc.delete("1.0", tk.END)
        self.txt_doc.insert("1.0", parsed.get("raw_text", ""))

        # Fill metadata
        self.ent_supplier.delete(0, tk.END)
        self.ent_supplier.insert(0, parsed.get("supplier_name", ""))

        self.ent_inv_no.delete(0, tk.END)
        self.ent_inv_no.insert(0, parsed.get("invoice_no", ""))

        self.ent_date.delete(0, tk.END)
        self.ent_date.insert(0, parsed.get("invoice_date", ""))

        self.ent_total.delete(0, tk.END)
        self.ent_total.insert(0, f"R {parsed.get('total_amount', 0):,.2f}")

        # Fill treeview
        self.tree.delete(*self.tree.get_children())
        items = parsed.get("items", [])
        for i in items:
            status_badge = (
                "🟢 EXACT" if i["status"].startswith("EXACT")
                else ("🟡 FUZZY" if i["status"] == "FUZZY_MATCH" else "🔴 NEW")
            )
            conf_str = f"{int(i['confidence'] * 100)}%" if i['confidence'] > 0 else "0%"
            self.tree.insert("", tk.END, values=(
                status_badge,
                i["raw_desc"],
                i["matched_code"],
                i["matched_desc"],
                f"{i['qty']:g}",
                f"{i['unit_cost']:.2f}",
                f"{i['line_total']:.2f}",
                conf_str
            ))

    def _transfer_to_grn_window(self) -> None:
        """Transfer extracted lines to an open ProfessionalGRNWindow."""
        if not self.current_parsed or not self.current_parsed.get("items"):
            messagebox.showwarning("Auto GRN", "No items to transfer.", parent=self)
            return

        try:
            from professional_grn import ProfessionalGRNWindow
            grn_win = ProfessionalGRNWindow(self.parent)

            # Fill header fields
            if hasattr(grn_win, "inv_no"):
                grn_win.inv_no.delete(0, tk.END)
                grn_win.inv_no.insert(0, self.ent_inv_no.get().strip())

            if hasattr(grn_win, "supplier_name"):
                grn_win.supplier_name.delete(0, tk.END)
                grn_win.supplier_name.insert(0, self.ent_supplier.get().strip())

            # Populate rows
            grn_rows = []
            for item in self.current_parsed["items"]:
                code = item["matched_code"]
                desc = item["matched_desc"] or item["raw_desc"]
                qty = float(item["qty"])
                cost = float(item["unit_cost"])
                tot = float(item["line_total"])
                # ProfessionalGRNWindow expects: (barcode, description, soh, qty, unit_cost, total)
                grn_rows.append((code, desc, 0.0, qty, cost, tot))

            grn_win.rows = grn_rows
            if hasattr(grn_win, "refresh_tree"):
                grn_win.refresh_tree()
            if hasattr(grn_win, "update_total"):
                grn_win.update_total()

            messagebox.showinfo(
                "Transfer Successful",
                f"Successfully transferred {len(grn_rows)} item(s) to Goods Received Note window!",
                parent=self
            )
            self.destroy()
        except Exception as exc:
            _bkpos_logger.warning("Error transferring to GRN window", exc_info=exc)
            messagebox.showerror("Transfer Failed", f"Could not launch GRN window:\n{exc}", parent=self)

    def _post_grn_direct(self) -> None:
        """Post GRN directly using services.grn_service."""
        if not self.current_parsed or not self.current_parsed.get("items"):
            messagebox.showwarning("Post GRN", "No items to post.", parent=self)
            return

        supplier = self.ent_supplier.get().strip()
        inv_no = self.ent_inv_no.get().strip()
        if not supplier:
            messagebox.showerror("Missing Information", "Supplier name is required.", parent=self)
            return

        items = []
        for i in self.current_parsed["items"]:
            items.append({
                "barcode": i["matched_code"],
                "description": i["matched_desc"] or i["raw_desc"],
                "qty": float(i["qty"]),
                "cost": float(i["unit_cost"]),
            })

        try:
            from services.grn_service import post_grn
            with sqlite3.connect(DB_PATH) as conn:
                res = post_grn(
                    conn,
                    supplier_name=supplier,
                    supplier_invoice=inv_no,
                    items=items,
                    cashier="AI-AutoGRN"
                )
                conn.commit()

            messagebox.showinfo(
                "GRN Posted",
                f"Goods Received Note posted successfully!\nGRN Number: {res.get('grn_no', 'N/A')}\n"
                f"Total: R {res.get('total', 0):,.2f}",
                parent=self
            )
            self.destroy()
        except Exception as exc:
            _bkpos_logger.warning("Error posting GRN directly", exc_info=exc)
            messagebox.showerror("Post Failed", f"Could not post GRN:\n{exc}", parent=self)

    def _create_missing_products(self) -> None:
        """Create new entries in Product Master for unmatched invoice items."""
        if not self.current_parsed:
            return

        unmatched = [i for i in self.current_parsed.get("items", []) if i["status"] == "NEW_ITEM"]
        if not unmatched:
            messagebox.showinfo("Product Master", "All invoice items are already matched to existing products!", parent=self)
            return

        created = 0
        with sqlite3.connect(DB_PATH) as conn:
            for item in unmatched:
                code = item["matched_code"]
                desc = item["raw_desc"]
                cost = float(item["unit_cost"])
                selling = round(cost * 1.35, 2)  # default 35% margin
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO products (barcode, description, cost_price, selling_price, soh, active) "
                        "VALUES (?, ?, ?, ?, 0, 1)",
                        (code, desc, cost, selling)
                    )
                    created += 1
                except Exception as exc:
                    _bkpos_logger.warning("Suppressed product insertion exception", exc_info=exc)
            conn.commit()

        messagebox.showinfo(
            "Products Created",
            f"Successfully created {created} new product(s) in Product Master!\nRe-running matching...",
            parent=self
        )
        self._reparse_text()

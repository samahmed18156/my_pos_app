"""JasperReports/JasperViewer bridge for MiPOS.

MiPOS remains the source of truth for sales and invoice data.  This module only
builds a JRPXML (filled JasperPrint XML) document and, when a JasperReports
runtime is available, launches the standard JasperViewer against it.

JasperReports supports JRPXML as a human-readable representation of a filled
JasperPrint document, and JasperViewer can display XML reports.
"""
from __future__ import annotations
from core.logger import logger as _bkpos_logger

import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from core.config import APP_BASE_DIR, GENERATED_REPORT_DIR, DATA_DIR
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

NS = "http://jasperreports.sourceforge.net/jasperreports/print"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
XSD = "http://jasperreports.sourceforge.net/xsd/jasperprint.xsd"

ROOT = Path(__file__).resolve().parent
REPORT_DIR = Path(GENERATED_REPORT_DIR)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _uid():
    return str(uuid.uuid4())


def _money(v):
    return f"R {float(v or 0):,.2f}"


def _fmt_qty(v):
    f = float(v or 0)
    return f"{f:g}"


def _esc_text(value):
    return escape(str(value if value is not None else ""))


def _text(parent, text, x, y, width, height, style="normal", align="Left", key="text"):
    node = ET.SubElement(parent, "text", {
        "textAlignment": align,
        "textHeight": str(max(1, height - 2)),
        "lineSpacingFactor": "1.2578125",
        "leadingOffset": "-2.1972656",
    })
    ET.SubElement(node, "reportElement", {
        "uuid": _uid(), "key": key, "style": style,
        "x": str(int(x)), "y": str(int(y)),
        "width": str(int(width)), "height": str(int(height)),
        "origin": "0", "srcId": "1",
    })
    content = ET.SubElement(node, "textContent")
    content.text = text
    return node


def _line(parent, x, y, width):
    node = ET.SubElement(parent, "line")
    ET.SubElement(node, "reportElement", {
        "uuid": _uid(), "x": str(int(x)), "y": str(int(y)),
        "width": str(int(width)), "height": "0", "origin": "0", "srcId": "1",
    })
    return node


def build_jrpxml(*, items, total, payment_type, cashier="", invoice_number="",
                 customer_name="Cash Sale", store_name="FAMILY SUPERMARKET",
                 store_address="", store_phone="", vat_number="", payment_info=None,
                 sale_datetime=None):
    """Return JRPXML bytes for a compact 80mm-style receipt."""
    payment_info = payment_info or {}
    sale_datetime = sale_datetime or datetime.now()

    gross = float(total or 0)
    vat = gross * 15 / 115
    net = gross - vat

    # 80mm paper: Jasper uses report units roughly equivalent to screen points.
    page_w = 226
    left = 10
    content_w = page_w - 2 * left
    row_h = 18
    y = 10

    # Estimate height so longer carts still fit on one continuous receipt page.
    item_height = sum(row_h * (2 if len(str(i.get("name", i.get("description", "")))) > 28 else 1) + 18
                      for i in items)
    page_h = max(420, y + 205 + item_height + 110)

    root = ET.Element("jasperPrint", {
        "xmlns": NS,
        "xmlns:xsi": XSI,
        "xsi:schemaLocation": f"{NS} {XSD}",
        "name": "MiPOS Cash Sale Receipt",
        "pageWidth": str(page_w), "pageHeight": str(page_h),
        "topMargin": "0", "leftMargin": "0", "bottomMargin": "0", "rightMargin": "0",
        "locale": "en_ZA",
    })
    ET.SubElement(root, "property", {"name": "net.sf.jasperreports.export.xml.start.page.index", "value": "0"})
    ET.SubElement(root, "property", {"name": "net.sf.jasperreports.export.xml.end.page.index", "value": "0"})
    ET.SubElement(root, "property", {"name": "net.sf.jasperreports.export.xml.page.count", "value": "1"})
    ET.SubElement(root, "origin", {"band": "detail"})

    ET.SubElement(root, "style", {"name": "normal", "forecolor": "#111111", "fontName": "SansSerif", "fontSize": "9"})
    ET.SubElement(root, "style", {"name": "small", "forecolor": "#111111", "fontName": "SansSerif", "fontSize": "8"})
    ET.SubElement(root, "style", {"name": "bold", "forecolor": "#111111", "fontName": "SansSerif", "fontSize": "9", "isBold": "true"})
    ET.SubElement(root, "style", {"name": "title", "forecolor": "#111111", "fontName": "SansSerif", "fontSize": "12", "isBold": "true"})
    ET.SubElement(root, "style", {"name": "total", "forecolor": "#111111", "fontName": "SansSerif", "fontSize": "10", "isBold": "true"})

    page = ET.SubElement(root, "page")

    # Header closely follows the friend's screenshot.
    _text(page, _esc_text(store_name), left, y, content_w, 22, "title", "Center", "store")
    y += 24
    if store_address:
        _text(page, _esc_text(store_address), left, y, content_w, 14, "small", "Center", "address")
        y += 14
    if store_phone:
        _text(page, _esc_text(store_phone), left, y, content_w, 14, "small", "Center", "phone")
        y += 14
    if vat_number:
        _text(page, _esc_text(f"VAT No: {vat_number}"), left, y + 2, content_w, 14, "small", "Center", "vat")
        y += 18

    y += 8
    _text(page, _esc_text(f"Date: {sale_datetime:%Y-%m-%d %H:%M:%S}"), left, y, content_w, 15, "bold", "Left", "date")
    y += 16
    _text(page, _esc_text(f"Invoice No: {invoice_number}"), left, y, content_w, 15, "bold", "Left", "invoice")
    y += 16
    _text(page, _esc_text(f"Customer: {customer_name or 'Cash Sale'}"), left, y, content_w, 15, "bold", "Left", "customer")
    y += 16
    if cashier:
        _text(page, _esc_text(f"Salesperson: {cashier}"), left, y, content_w, 15, "bold", "Left", "cashier")
        y += 18

    _text(page, "CODE", left, y, 80, 14, "bold", "Left", "h_code")
    _text(page, "QTY", 90, y, 35, 14, "bold", "Right", "h_qty")
    _text(page, "PRICE", 128, y, 42, 14, "bold", "Right", "h_price")
    _text(page, "VALUE", 171, y, 45, 14, "bold", "Right", "h_value")
    y += 16
    _line(page, left, y, content_w)
    y += 4

    total_qty = 0.0
    for idx, item in enumerate(items):
        code = str(item.get("code", item.get("barcode", "")))
        name = str(item.get("name", item.get("description", "")))
        qty = float(item.get("qty", 0) or 0)
        price = float(item.get("price", 0) or 0)
        value = float(item.get("value", qty * price) or 0)
        total_qty += qty

        # Screenshot shows the code as the main line, so keep that visual style.
        _text(page, _esc_text(code or name[:20]), left, y, 80, 15, "bold", "Left", f"code_{idx}")
        _text(page, _esc_text(_fmt_qty(qty)), 90, y, 35, 15, "small", "Right", f"qty_{idx}")
        _text(page, _esc_text(f"{price:.2f}"), 128, y, 42, 15, "small", "Right", f"price_{idx}")
        _text(page, _esc_text(f"{value:.2f}"), 171, y, 45, 15, "small", "Right", f"value_{idx}")
        y += 16
        if name and name != code:
            _text(page, _esc_text(name[:34]), left, y, content_w, 14, "small", "Left", f"name_{idx}")
            y += 14
        _line(page, left, y, content_w)
        y += 4

    y += 2
    _text(page, _esc_text(f"TOTAL QTY: {_fmt_qty(total_qty)}"), left, y, content_w, 16, "bold", "Left", "total_qty")
    y += 22
    _text(page, "VAT Incl:", 110, y, 60, 15, "bold", "Right", "vat_label")
    _text(page, _esc_text(f"{vat:.2f}"), 171, y, 45, 15, "bold", "Right", "vat")
    y += 20
    _text(page, "Total:", 110, y, 60, 16, "total", "Right", "total_label")
    _text(page, _esc_text(f"{gross:.2f}"), 171, y, 45, 16, "total", "Right", "total")
    y += 30

    if payment_type == "Cash":
        tendered = float(payment_info.get("amount_tendered", 0) or 0)
        change = float(payment_info.get("change", 0) or 0)
        _text(page, "Paid:", 110, y, 60, 15, "bold", "Right", "paid_label")
        _text(page, _esc_text(f"{tendered:.2f}"), 171, y, 45, 15, "bold", "Right", "paid")
        y += 20
        _text(page, "Change:", 110, y, 60, 15, "bold", "Right", "change_label")
        _text(page, _esc_text(f"{change:.2f}"), 171, y, 45, 15, "bold", "Right", "change")
        y += 20
    elif payment_type == "Split Payment":
        cash = float(payment_info.get("cash", 0) or 0)
        card = float(payment_info.get("card", 0) or 0)
        _text(page, "Cash:", 110, y, 60, 15, "bold", "Right", "cash_label")
        _text(page, _esc_text(f"{cash:.2f}"), 171, y, 45, 15, "bold", "Right", "cash")
        y += 18
        _text(page, "Card:", 110, y, 60, 15, "bold", "Right", "card_label")
        _text(page, _esc_text(f"{card:.2f}"), 171, y, 45, 15, "bold", "Right", "card")
        y += 20

    _text(page, _esc_text(f"PAYMENT TYPE: {payment_type.upper()}"), left, y, content_w, 16, "bold", "Center", "payment_type")
    y += 24
    _text(page, "THANK YOU FOR SHOPPING WITH US", left, y, content_w, 18, "bold", "Center", "thanks")

    # A text barcode placeholder keeps the report dependency-free.  A real
    # Code128 image can be added later without changing the sales workflow.
    y += 24
    _text(page, _esc_text("||||| ||||| || ||||| ||| ||||"), left, y, content_w, 22, "small", "Center", "barcode")

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_jrpxml(**kwargs):
    invoice = str(kwargs.get("invoice_number") or "receipt")
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in invoice)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"mipos_receipt_{safe}_{stamp}.jrpxml"
    path.write_bytes(build_jrpxml(**kwargs))
    return path


def get_branch_info(db_name=None):
    """Return display information for the default/main branch when available."""
    import sqlite3
    try:
        if not db_name:
            from core.config import DB_PATH
            db_name = DB_PATH
        conn = sqlite3.connect(db_name)
        row = conn.execute(
            "SELECT name, COALESCE(address,''), COALESCE(phone,'') FROM branches ORDER BY id LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            return {"name": row[0] or "", "address": row[1] or "", "phone": row[2] or ""}
    except Exception as exc:
        _bkpos_logger.warning("Suppressed exception in jasper_reports/jasper_receipt.py", exc_info=exc)
    return {"name": "", "address": "", "phone": ""}


CONFIG_FILE = Path(DATA_DIR) / "mipos_jasper_config.json"
LOCAL_RUNTIME_DIRS = (
    Path(APP_BASE_DIR) / "jasper_runtime",
    ROOT / "runtime",
    ROOT.parent / "jasper",
)

WINDOWS_JASPERSTARTER_DIRS = (
    Path(os.environ.get("ProgramFiles", "")) / "JasperStarter",
    Path(os.environ.get("ProgramFiles(x86)", "")) / "JasperStarter",
    Path(os.environ.get("LOCALAPPDATA", "")) / "JasperStarter",
    Path(os.environ.get("ProgramFiles", "")) / "JasperStarter-3.6",
    Path(os.environ.get("ProgramFiles(x86)", "")) / "JasperStarter-3.6",
)


def _read_jasper_config():
    try:
        import json
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return str(data.get("home", "")).strip()
    except Exception:
        return ""


def _java_executable():
    """Find Java, preferring the bundled MiPOS Java runtime."""
    app_dir = Path(APP_BASE_DIR)
    for rel in ("jre8/bin/java.exe", "jre/bin/java.exe", "java/bin/java.exe"):
        candidate = app_dir / rel
        if candidate.exists():
            return str(candidate)
    # Development/configured Java locations.
    try:
        import json
        if CONFIG_FILE.exists():
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            configured = str(cfg.get("java", "")).strip()
            if configured and Path(configured).exists():
                return configured
    except Exception as exc:
        _bkpos_logger.warning("Suppressed exception in jasper_reports/jasper_receipt.py", exc_info=exc)
    found = shutil.which("java")
    if found:
        return found
    java_home = os.environ.get("JAVA_HOME", "").strip()
    if java_home:
        for name in ("java.exe", "java"):
            p = Path(java_home) / "bin" / name
            if p.exists():
                return str(p)
    # Common Windows JDK/JRE locations. This is harmless on non-Windows.
    for base in (
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
        os.environ.get("LOCALAPPDATA", ""),
    ):
        if not base:
            continue
        root = Path(base)
        for pattern in (
            "Java/*/bin/java.exe",
            "Eclipse Adoptium/*/bin/java.exe",
            "Eclipse Foundation/*/bin/java.exe",
            "Microsoft/*/bin/java.exe",
            "Temurin/*/bin/java.exe",
        ):
            matches = sorted(root.glob(pattern), reverse=True)
            if matches:
                return str(matches[0])
    return None


def _runtime_homes():
    seen = set()
    values = []
    for raw in (
        os.environ.get("MIPOS_JASPER_HOME", ""),
        _read_jasper_config(),
        *(str(p) for p in LOCAL_RUNTIME_DIRS),
        *(str(p) for p in WINDOWS_JASPERSTARTER_DIRS if str(p) not in (".", "")),
    ):
        raw = str(raw or "").strip()
        if not raw:
            continue
        p = Path(raw).expanduser()
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            seen.add(key); values.append(p)
    return values


def _jasper_core_jar(jars):
    """Return a JasperReports jar that actually contains JasperViewer."""
    import zipfile
    target = "net/sf/jasperreports/view/JasperViewer.class"
    for jar in jars:
        try:
            with zipfile.ZipFile(jar) as zf:
                if target in zf.namelist():
                    return jar
        except Exception:
            continue
    return None


def _jars_for_home(home):
    if not home.exists():
        return []
    jars = []
    # Search a few levels so Jaspersoft Studio and extracted Jasper runtimes
    # are found without forcing the user to configure an environment variable.
    for pattern in ("*.jar", "lib/*.jar", "**/*.jar"):
        for p in home.glob(pattern):
            if p.is_file() and p not in jars:
                jars.append(p)
    return jars


def _jasper_candidates():
    """Return JasperViewer launch commands, auto-discovering local runtimes."""
    java = _java_executable()

    env_cp = os.environ.get("MIPOS_JASPER_CLASSPATH", "").strip()
    if env_cp and java:
        yield [java, "-cp", env_cp, "net.sf.jasperreports.view.JasperViewer"]

    if java:
        for home in _runtime_homes():
            jars = _jars_for_home(home)
            if _jasper_core_jar(jars):
                cp = os.pathsep.join(str(x) for x in jars)
                yield [java, "-cp", cp, "net.sf.jasperreports.view.JasperViewer"]

    # Allow a directly supplied JasperViewer/JasperReports launcher.
    for exe in ("jasperviewer.bat", "jasperviewer.cmd", "jasperviewer.exe"):
        found = shutil.which(exe)
        if found:
            yield [found]


def find_jasper_viewer():
    for command in _jasper_candidates():
        return command
    return None


def jasper_viewer_status():
    """Return a user-friendly diagnostic without launching anything."""
    java = _java_executable()
    homes = _runtime_homes()
    core = []
    for home in homes:
        jars = _jars_for_home(home)
        if _jasper_core_jar(jars):
            core.append(str(home))
    if not java:
        return False, "Java was not found. Install a Java runtime/JDK, then restart MiPOS."
    if not core:
        return False, (
            "Java was found, but JasperReports/JasperViewer was not found. "
            "Put the JasperReports runtime in the MiPOS 'jasper_runtime' folder "
            "or run CONFIGURE_JASPER_VIEWER.bat."
        )
    return True, f"JasperViewer ready. Java: {java}\nRuntime: {core[0]}"


def open_in_jasperviewer(jrpxml_path):
    """Launch the standard JasperViewer in a separate process."""
    command = find_jasper_viewer()
    if not command:
        ok, status = jasper_viewer_status()
        return False, status
    try:
        subprocess.Popen(command + ["-F" + str(jrpxml_path), "-XML"], cwd=str(ROOT))
        return True, "JasperViewer opened."
    except Exception as exc:
        return False, f"JasperViewer could not be started: {exc}"

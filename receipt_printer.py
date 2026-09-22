"""
FAMILY SUPERMARKET POS
DIRECT THERMAL RECEIPT PRINTER

Uses Windows printing and sends ESC/POS directly
to the configured Epson thermal printer.

Configured printer:
    POS-80C (Windows queue for TT-70)
"""
from core.logger import logger as _bkpos_logger
from store_settings import get_store_name

import os
import textwrap
from datetime import datetime


# ============================================================
# PRINTER
# ============================================================

PRINTER_NAME = os.environ.get("BKPOS_RECEIPT_PRINTER", "POS-80C").strip() or "POS-80C"


# ============================================================
# WINDOWS PRINTING
# ============================================================

try:
    import win32print
except ImportError:
    win32print = None


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(value):
    """
    Convert text into something suitable for
    a thermal ESC/POS printer.
    """

    if value is None:
        return ""

    text = str(value)

    replacements = {
        "–": "-",
        "—": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "•": "*",
        "×": "x",
        "é": "e",
        "è": "e",
        "ê": "e",
        "á": "a",
        "à": "a",
        "â": "a",
        "ä": "a",
        "í": "i",
        "ì": "i",
        "î": "i",
        "ï": "i",
        "ó": "o",
        "ò": "o",
        "ô": "o",
        "ö": "o",
        "ú": "u",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ñ": "n",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


# ============================================================
# ESC/POS COMMANDS
# ============================================================

ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"

ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
ALIGN_RIGHT = ESC + b"a\x02"

BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"

DOUBLE_HEIGHT_ON = ESC + b"!\x10"
DOUBLE_HEIGHT_OFF = ESC + b"!\x00"

# Full cut
CUT_PAPER = GS + b"V\x00"

# Cash drawer pulse
OPEN_DRAWER = ESC + b"p\x00\x19\xfa"


# ============================================================
# ENCODING
# ============================================================

def encode_text(text):
    """
    Encode text for common ESC/POS printers.
    """

    text = clean_text(text)

    try:
        return text.encode(
            "cp437",
            errors="replace"
        )

    except Exception:
        return text.encode(
            "ascii",
            errors="replace"
        )


# ============================================================
# PRINTER INFORMATION
# ============================================================

def get_printer_name():
    """
    Return configured printer name.
    """

    return PRINTER_NAME


def get_default_printer():
    """
    Return the Windows default printer.
    """

    if win32print is None:
        return None

    try:
        return win32print.GetDefaultPrinter()

    except Exception:
        return None


def get_installed_printers():
    """
    Return installed Windows printers.
    """

    if win32print is None:
        return []

    printers = []

    try:

        flags = (
            win32print.PRINTER_ENUM_LOCAL
            | win32print.PRINTER_ENUM_CONNECTIONS
        )

        for printer in win32print.EnumPrinters(
            flags
        ):

            if len(printer) >= 3:
                printers.append(
                    printer[2]
                )

    except Exception:
        return []

    return printers


def printer_exists(
    printer_name=PRINTER_NAME
):
    """
    Check whether a printer exists in Windows.
    """

    if win32print is None:
        return False

    try:

        printers = get_installed_printers()

        return printer_name in printers

    except Exception:
        return False


# ============================================================
# RAW PRINTING
# ============================================================

def send_raw_to_printer(
    raw_data,
    printer_name=PRINTER_NAME
):
    """
    Send raw ESC/POS bytes directly to a Windows printer.

    Returns:
        True when the Windows print job was accepted.
    """

    if win32print is None:

        raise RuntimeError(
            "pywin32 is not installed.\n\n"
            "Please run:\n"
            "pip install pywin32"
        )

    if not printer_name:
        printer_name = PRINTER_NAME

    if not printer_exists(
        printer_name
    ):

        raise RuntimeError(
            "Printer was not found in Windows:\n\n"
            f"{printer_name}"
        )

    handle = None

    try:

        handle = win32print.OpenPrinter(
            printer_name
        )

        job = win32print.StartDocPrinter(
            handle,
            1,
            (
                f"{get_store_name()} Receipt",
                None,
                "RAW"
            )
        )

        try:

            win32print.StartPagePrinter(
                handle
            )

            win32print.WritePrinter(
                handle,
                raw_data
            )

            win32print.EndPagePrinter(
                handle
            )

        finally:

            win32print.EndDocPrinter(
                handle
            )

    except Exception as exc:

        raise RuntimeError(
            "Windows could not send the receipt "
            "to the printer.\n\n"
            f"Printer: {printer_name}\n\n"
            f"Error: {exc}"
        )

    finally:

        if handle is not None:

            try:
                win32print.ClosePrinter(
                    handle
                )
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in receipt_printer.py", exc_info=exc)

    return True


# ============================================================
# TEST RECEIPT
# ============================================================

def build_test_receipt():
    """
    Build a simple thermal printer test receipt.
    """

    data = bytearray()

    data += INIT

    # Header
    data += ALIGN_CENTER
    data += BOLD_ON
    data += DOUBLE_HEIGHT_ON

    data += encode_text(
        get_store_name()
    )

    data += b"\n"

    data += DOUBLE_HEIGHT_OFF
    data += BOLD_OFF

    data += encode_text(
        "THERMAL PRINTER TEST"
    )

    data += b"\n"
    data += b"\n"

    # Information
    data += ALIGN_LEFT

    data += encode_text(
        "--------------------------------"
    )

    data += b"\n"

    data += encode_text(
        f"Printer: {PRINTER_NAME}"
    )

    data += b"\n"

    data += encode_text(
        "Connection: Windows Printer Queue"
    )

    data += b"\n"

    data += encode_text(
        f"Date: {datetime.now():%Y-%m-%d %H:%M}"
    )

    data += b"\n"

    data += encode_text(
        "--------------------------------"
    )

    data += b"\n"

    data += ALIGN_CENTER

    data += BOLD_ON

    data += encode_text(
        "PRINT TEST SUCCESSFUL"
    )

    data += b"\n"

    data += BOLD_OFF

    data += b"\n"

    data += encode_text(
        "Thank you"
    )

    data += b"\n"
    data += b"\n"
    data += b"\n"

    data += CUT_PAPER

    return bytes(data)


def test_printer(
    printer_name=PRINTER_NAME
):
    """
    Send a test receipt.
    """

    if not printer_exists(
        printer_name
    ):

        raise RuntimeError(
            "Printer was not found in Windows:\n\n"
            f"{printer_name}"
        )

    receipt = build_test_receipt()

    return send_raw_to_printer(
        receipt,
        printer_name
    )


# ============================================================
# RECEIPT BUILDER
# ============================================================

def build_receipt(
    items,
    total,
    payment_type,
    cashier="",
    invoice_number="",
    customer_name="Cash Sale",
    subtotal=None,
    vat=None,
    amount_tendered=0,
    change=0,
    cash_amount=0,
    card_amount=0
):
    """
    Build a complete ESC/POS receipt.

    Expected item format:

        {
            "code": "...",
            "name": "...",
            "qty": 1,
            "price": 10.00,
            "value": 10.00
        }
    """

    data = bytearray()

    # Calculate subtotal/VAT when not supplied.
    total = float(total)

    # Selling prices are VAT-inclusive.
    # R115 gross = R100 ex-VAT + R15 VAT.
    if subtotal is None:
        subtotal = total / 1.15

    if vat is None:
        vat = total - float(subtotal)

    subtotal = float(subtotal)
    vat = float(vat)

    # --------------------------------------------------------
    # INITIALIZE
    # --------------------------------------------------------

    data += INIT

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    data += ALIGN_CENTER

    data += BOLD_ON
    data += DOUBLE_HEIGHT_ON

    data += encode_text(
        get_store_name()
    )

    data += b"\n"

    data += DOUBLE_HEIGHT_OFF
    data += BOLD_OFF

    data += encode_text(
        "Thank you for shopping with us"
    )

    data += b"\n"
    data += b"\n"

    # --------------------------------------------------------
    # SALE INFORMATION
    # --------------------------------------------------------

    data += ALIGN_LEFT

    data += encode_text(
        "--------------------------------"
    )

    data += b"\n"

    if invoice_number:

        data += encode_text(
            f"Invoice: {invoice_number}"
        )

        data += b"\n"

    if cashier:

        data += encode_text(
            f"Cashier: {cashier}"
        )

        data += b"\n"

    if customer_name:

        data += encode_text(
            f"Customer: {customer_name}"
        )

        data += b"\n"

    data += encode_text(
        f"Date: {datetime.now():%Y-%m-%d %H:%M}"
    )

    data += b"\n"

    data += encode_text(
        "--------------------------------"
    )

    data += b"\n"

    # --------------------------------------------------------
    # ITEMS
    # --------------------------------------------------------

    for item in items:

        name = clean_text(
            item.get(
                "name",
                item.get(
                    "description",
                    ""
                )
            )
        )

        qty = float(
            item.get(
                "qty",
                0
            ) or 0
        )

        price = float(
            item.get(
                "price",
                0
            ) or 0
        )

        value = float(
            item.get(
                "value",
                qty * price
            ) or 0
        )

        # Product code
        code = clean_text(
            item.get(
                "code",
                item.get(
                    "barcode",
                    ""
                )
            )
        )

        if code:

            data += encode_text(
                code
            )

            data += b"\n"

        # Product description
        wrapped = textwrap.wrap(
            name,
            width=32
        )

        if not wrapped:
            wrapped = [""]

        data += encode_text(
            wrapped[0]
        )

        data += b"\n"

        for extra_line in wrapped[1:]:

            data += encode_text(
                extra_line
            )

            data += b"\n"

        # Quantity / price / value
        item_line = (
            f"{qty:g} x R {price:.2f}"
        )

        value_text = (
            f"R {value:.2f}"
        )

        spacing = (
            32
            - len(item_line)
            - len(value_text)
        )

        if spacing < 1:
            spacing = 1

        data += encode_text(
            item_line
            + (" " * spacing)
            + value_text
        )

        data += b"\n"

    # --------------------------------------------------------
    # TOTALS
    # --------------------------------------------------------

    data += encode_text(
        "--------------------------------"
    )

    data += b"\n"

    data += ALIGN_RIGHT

    data += encode_text(
        f"Subtotal: R {float(subtotal):.2f}"
    )

    data += b"\n"

    data += encode_text(
        f"VAT (15%): R {float(vat):.2f}"
    )

    data += b"\n"

    data += BOLD_ON
    data += DOUBLE_HEIGHT_ON

    data += encode_text(
        f"TOTAL: R {total:.2f}"
    )

    data += b"\n"

    data += DOUBLE_HEIGHT_OFF
    data += BOLD_OFF

    data += ALIGN_LEFT

    data += encode_text(
        f"Payment: {payment_type}"
    )

    data += b"\n"

    if payment_type == "Cash":
        data += encode_text(
            f"Amount tendered: R {float(amount_tendered):.2f}"
        )
        data += b"\n"
        data += encode_text(
            f"Change: R {float(change):.2f}"
        )
        data += b"\n"

    elif payment_type == "Split Payment":
        data += encode_text(
            f"Cash: R {float(cash_amount):.2f}"
        )
        data += b"\n"
        data += encode_text(
            f"Card: R {float(card_amount):.2f}"
        )
        data += b"\n"

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------

    data += b"\n"

    data += ALIGN_CENTER

    data += encode_text(
        "Please come again!"
    )

    data += b"\n"
    data += b"\n"
    data += b"\n"

    # Cut paper
    data += CUT_PAPER

    return bytes(data)


# ============================================================
# PRINT RECEIPT
# ============================================================

def print_receipt(
    items,
    total,
    payment_type,
    cashier="",
    invoice_number="",
    customer_name="Cash Sale",
    printer_name=PRINTER_NAME,
    subtotal=None,
    vat=None,
    amount_tendered=0,
    change=0,
    cash_amount=0,
    card_amount=0
):
    """
    Build and print a complete thermal receipt.
    """

    if not printer_exists(
        printer_name
    ):

        raise RuntimeError(
            "Printer not found in Windows:\n\n"
            f"{printer_name}"
        )

    receipt_data = build_receipt(
        items=items,
        total=total,
        payment_type=payment_type,
        cashier=cashier,
        invoice_number=invoice_number,
        customer_name=customer_name,
        subtotal=subtotal,
        vat=vat,
        amount_tendered=amount_tendered,
        change=change,
        cash_amount=cash_amount,
        card_amount=card_amount
    )

    return send_raw_to_printer(
        receipt_data,
        printer_name
    )


# ============================================================
# ALTERNATIVE FUNCTION NAME
# ============================================================

def print_thermal_receipt(
    items,
    total,
    payment_type,
    cashier="",
    invoice_number="",
    customer_name="Cash Sale",
    printer_name=PRINTER_NAME,
    subtotal=None,
    vat=None,
    amount_tendered=0,
    change=0,
    cash_amount=0,
    card_amount=0
):
    """
    Alias for print_receipt().
    """

    return print_receipt(
        items=items,
        total=total,
        payment_type=payment_type,
        cashier=cashier,
        invoice_number=invoice_number,
        customer_name=customer_name,
        printer_name=printer_name,
        subtotal=subtotal,
        vat=vat,
        amount_tendered=amount_tendered,
        change=change,
        cash_amount=cash_amount,
        card_amount=card_amount
    )


# ============================================================
# PDF COMPATIBILITY FUNCTION
# ============================================================

def print_pdf(
    pdf_path=None,
    printer_name=PRINTER_NAME,
    items=None,
    total=None,
    payment_type="Cash",
    cashier="",
    invoice_number="",
    customer_name="Cash Sale"
):
    """
    Compatibility function for older app.py code.

    IMPORTANT:
    The POS should use direct ESC/POS printing whenever
    receipt information is available.

    If items are supplied, this function prints the receipt
    directly to the Epson thermal printer.

    The pdf_path argument is accepted so older app.py code
    can import this function without crashing.
    """

    # --------------------------------------------------------
    # Preferred method:
    # Direct thermal printing
    # --------------------------------------------------------

    if items is not None and total is not None:

        return print_receipt(
            items=items,
            total=total,
            payment_type=payment_type,
            cashier=cashier,
            invoice_number=invoice_number,
            customer_name=customer_name,
            printer_name=printer_name
        )

    # --------------------------------------------------------
    # PDF-only compatibility
    # --------------------------------------------------------

    if pdf_path:

        if not os.path.exists(
            pdf_path
        ):

            raise RuntimeError(
                "Receipt PDF was not found:\n\n"
                f"{pdf_path}"
            )

        raise RuntimeError(
            "A PDF file was supplied to print_pdf(), "
            "but direct thermal printing requires the "
            "receipt items and total.\n\n"
            "Use print_receipt() or print_thermal_receipt() "
            "for the Epson thermal printer."
        )

    raise RuntimeError(
        "print_pdf() requires either receipt items and total "
        "or a valid PDF path."
    )


# ============================================================
# SIMPLE RECEIPT ALIAS
# ============================================================

def print_thermal(
    items,
    total,
    payment_type="Cash",
    cashier="",
    invoice_number="",
    customer_name="Cash Sale",
    printer_name=PRINTER_NAME
):
    """
    Short alias for direct thermal printing.
    """

    return print_receipt(
        items=items,
        total=total,
        payment_type=payment_type,
        cashier=cashier,
        invoice_number=invoice_number,
        customer_name=customer_name,
        printer_name=printer_name
    )


# ============================================================
# MAIN TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("======================================")
    print(" FAMILY SUPERMARKET RECEIPT PRINTER")
    print("======================================")
    print()

    print(
        f"Printer: {PRINTER_NAME}"
    )

    print(
        "Windows default printer: "
        f"{get_default_printer()}"
    )

    print()

    if win32print is None:

        print(
            "ERROR: pywin32 is not installed."
        )

        print()
        print(
            "Run:"
        )

        print(
            "pip install pywin32"
        )

    else:

        print(
            "Checking printer..."
        )

        if printer_exists():

            print(
                "Printer found in Windows."
            )

            print(
                "Sending test receipt..."
            )

            try:

                test_printer()

                print(
                    "Test receipt sent successfully."
                )

            except Exception as exc:

                print()
                print(
                    "PRINT ERROR:"
                )

                print(
                    exc
                )

        else:

            print(
                "Printer was NOT found."
            )

            print()
            print(
                "Configured printer:"
            )

            print(
                PRINTER_NAME
            )

            print()

            print(
                "Installed printers:"
            )

            for name in get_installed_printers():

                print(
                    f"  - {name}"
                )
from pathlib import Path
import shutil
import subprocess
import sys

BASE = Path(__file__).parent
APP = BASE / "app.py"
PRINTER = BASE / "receipt_printer.py"
BACKUP = BASE / "app_before_direct_receipt_print.py"

if not APP.exists():
    print("ERROR: app.py was not found.")
    raise SystemExit(1)

if not PRINTER.exists():
    print("ERROR: receipt_printer.py was not found.")
    raise SystemExit(1)

# Install pywin32 if needed.
try:
    import win32print  # noqa: F401
    print("OK: pywin32 is already installed.")
except ImportError:
    print("pywin32 is not installed. Installing it now...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "pywin32"],
        check=False
    )
    if result.returncode != 0:
        print("\nERROR: pywin32 installation failed.")
        print("Run this manually in PyCharm Terminal:")
        print("python -m pip install pywin32")
        raise SystemExit(1)
    print("OK: pywin32 installed.")

# Safety backup
shutil.copy2(APP, BACKUP)
text = APP.read_text(encoding="utf-8")

start_marker = "    def generate_pdf_receipt("
end_marker = "    def show_share_options("

start = text.find(start_marker)
end = text.find(end_marker, start)

if start == -1 or end == -1:
    print("ERROR: Could not locate generate_pdf_receipt() safely.")
    print("Your app.py was NOT changed.")
    raise SystemExit(1)

old_function = text[start:end]

# Keep the existing PDF receipt/share system, but replace the Windows
# os.startfile(..., "print") mechanism with direct ESC/POS printing.
needle = """            c.save()

            messagebox.showinfo(
                "Sale Complete!",
"""

replacement = """            c.save()

            # -------------------------------------------------
            # DIRECT THERMAL PRINTER
            # -------------------------------------------------
            # Send the receipt directly to the Epson Windows
            # printer queue. This does not require a PDF viewer
            # or a Windows PDF "Print" file association.
            try:

                from receipt_printer import print_receipt

                printed, print_message = print_receipt(
                    sold_items=sold_items,
                    total=total,
                    payment_type=payment_type,
                    cashier=self.cashier_name
                )

            except Exception as print_error:

                printed = False
                print_message = str(print_error)

            messagebox.showinfo(
                "Sale Complete!",
"""

if needle not in old_function:
    print("ERROR: Expected receipt code was not found.")
    print("Your app.py was NOT changed.")
    raise SystemExit(1)

new_function = old_function.replace(needle, replacement, 1)

# Replace the success message so it reports printer status.
old_tail = """                    f"Payment: {payment_type}\n"
                    "Stock has been updated.\n\n"
                    f"Receipt saved: {filename}"
"""

new_tail = """                    f"Payment: {payment_type}\n"
                    "Stock has been updated.\n\n"
                    f"Receipt saved: {filename}\n\n"
                    + (
                        "Printer: EPSON TM-T20 Receipt4\n"
                        "Status: Receipt sent to printer."
                        if printed
                        else
                        "Printer: EPSON TM-T20 Receipt4\n"
                        f"Status: Printer not reached.\\n{print_message}"
                    )
"""

if old_tail in new_function:
    new_function = new_function.replace(old_tail, new_tail, 1)
else:
    print("WARNING: Could not update the printer status text.")
    print("Direct printing code was still inserted.")

text = text[:start] + new_function + text[end:]
APP.write_text(text, encoding="utf-8")

print()
print("DIRECT RECEIPT PRINTING IS INSTALLED.")
print("------------------------------------")
print("Backup:", BACKUP.name)
print("Printer:", "EPSON TM-T20 Receipt4")
print()
print("You can now run:")
print("python app.py")
print()
print("No Windows PDF viewer is required for thermal printing.")

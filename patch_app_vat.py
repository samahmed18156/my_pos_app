from pathlib import Path
from datetime import datetime
import shutil

APP = Path("app.py")
if not APP.exists():
    raise SystemExit("Run this script from your my_pos_app folder.")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = APP.with_name(f"app_before_invoice_patch_{stamp}.py")
shutil.copy2(APP, backup)

text = APP.read_text(encoding="utf-8")

# Main cart and checkout: selling prices already include VAT.
old = '''        vat = subtotal * 0.15

        total = subtotal + vat
'''
new = '''        # Selling prices are VAT-inclusive.
        total = subtotal
        vat = total * 15 / 115
        subtotal = total - vat
'''
text = text.replace(old, new)

# PDF receipt: calculate VAT from the gross selling-price total.
old_pdf = '''            subtotal = sum(
                item["value"]
                for item in sold_items
            )

            vat = subtotal * 0.15
'''
new_pdf = '''            total = sum(
                item["value"]
                for item in sold_items
            )

            vat = total * 15 / 115
            subtotal = total - vat
'''
text = text.replace(old_pdf, new_pdf, 1)

APP.write_text(text, encoding="utf-8")

print("Patch completed.")
print(f"Backup: {backup}")

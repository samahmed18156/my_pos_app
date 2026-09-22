from pathlib import Path
import shutil
import re

app = Path(__file__).parent / "app.py"

if not app.exists():
    print("ERROR: app.py is not in the same folder as this fixer.")
    print("Extract this ZIP directly into your my_pos_app folder.")
    raise SystemExit(1)

backup = app.with_name("app_before_fix_20260902.py")
shutil.copy2(app, backup)

text = app.read_text(encoding="utf-8")
changes = []

# Fix the exact syntax error shown in PyCharm.
bad = 'HEADER_COLOR = "#2c5282"aq'
good = 'HEADER_COLOR = "#2c5282"'
if bad in text:
    text = text.replace(bad, good)
    changes.append("Removed accidental 'aq' from HEADER_COLOR.")

# Fix Treeview scrollbar warning if this exact form exists.
if "yscroll=scrollbar.set" in text:
    text = text.replace("yscroll=scrollbar.set", "yscrollcommand=scrollbar.set")
    changes.append("Changed yscroll to yscrollcommand.")

# Initialize f3_window if it is used but never initialized.
if "self.f3_window = None" not in text and "self.f3_window" in text:
    marker = "self.logout_requested = False"
    pos = text.find(marker)
    if pos != -1:
        end = text.find("\n", pos)
        if end == -1:
            end = len(text)
        text = text[:end+1] + "\n        self.f3_window = None\n" + text[end+1:]
        changes.append("Initialized self.f3_window.")

app.write_text(text, encoding="utf-8")

print("DONE")
print("Backup created:", backup.name)
if changes:
    for c in changes:
        print("OK:", c)
else:
    print("No matching fixes were found.")
print("\nNow run: python app.py")

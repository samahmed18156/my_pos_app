"""Configure JasperReports/JasperViewer for BKPOS on Windows or desktop Python."""
from __future__ import annotations
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from jasper_reports.jasper_receipt import CONFIG_FILE, jasper_viewer_status, _jasper_core_jar, _jars_for_home

ROOT = Path(__file__).resolve().parent


def main():
    current_ok, current_msg = jasper_viewer_status()
    if current_ok:
        print(current_msg)
        return 0
    root = tk.Tk(); root.withdraw()
    messagebox.showinfo(
        "BKPOS JasperViewer Setup",
        "BKPOS needs the JasperReports runtime folder.\n\n"
        "Select the folder that contains JasperReports .jar files "
        "(or a lib folder containing them).",
        parent=root,
    )
    selected = filedialog.askdirectory(title="Select JasperReports runtime folder", parent=root)
    if not selected:
        root.destroy(); return 1
    home = Path(selected)
    jars = _jars_for_home(home)
    if not _jasper_core_jar(jars):
        messagebox.showerror(
            "BKPOS JasperViewer Setup",
            "That folder does not contain a JasperReports jar with JasperViewer.\n\n"
            "Please select the JasperReports runtime/lib folder.",
            parent=root,
        )
        root.destroy(); return 2
    CONFIG_FILE.write_text(json.dumps({"home": str(home)}, indent=2), encoding="utf-8")
    messagebox.showinfo(
        "BKPOS JasperViewer Setup",
        "JasperViewer runtime saved successfully.\n\nRestart BKPOS and try View Selected Document again.",
        parent=root,
    )
    root.destroy()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

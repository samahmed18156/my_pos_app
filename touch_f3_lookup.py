"""Touch-optimized F3 product lookup for BKPOS.

Enhanced version of the F3 product lookup with:
- Larger touch targets and buttons
- Touch-friendly grid layout
- On-screen numeric keypad
- Visual feedback for touch interactions
- Improved spacing and sizing
"""
from core.logger import logger as _bkpos_logger

import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from touch_optimization import TouchButton, TouchKeypad, TouchListItem, create_shortcut_hint


from core.config import DB_PATH
DB_NAME = DB_PATH


class TouchF3LookupWindow(tk.Toplevel):
    """Touch-optimized product selector for the sales screen (F3)."""
    
    def __init__(self, parent, initial_query="", on_select_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.on_select_callback = on_select_callback
        self.title("Product Lookup • F3")
        self.geometry("1100x750")
        self.minsize(1000, 650)
        self.configure(bg="#eef2f6")
        self.transient(parent)
        self.grab_set()
        
        self.keypad_window = None
        self.rows = []
        
        self._build_ui()
        self._setup_bindings()
        self.filter_products()
        self.entry_search.focus_force()
    
    def _build_ui(self):
        """Build the touch-optimized UI."""
        # Header
        header = tk.Frame(self, bg="#243447", height=85)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text="PRODUCT LOOKUP", font=("Segoe UI", 20, "bold"),
                 fg="white", bg="#243447").pack(side="left", padx=25, pady=(15, 0))
        tk.Label(header, text="F3  •  Select a product to add to the current invoice",
                 font=("Segoe UI", 10), fg="#dbe7f3", bg="#243447").pack(side="left", padx=20, pady=(18, 0))
        
        # Search controls - larger for touch
        controls = tk.Frame(self, bg="white", bd=2, relief="solid")
        controls.pack(fill="x", padx=20, pady=(18, 12))
        
        tk.Label(controls, text="SEARCH", font=("Segoe UI", 11, "bold"),
                 fg="#344054", bg="white").pack(side="left", padx=(20, 12), pady=18)
        
        self.cmb_search_by = ttk.Combobox(controls, values=["Description", "Barcode"],
                                          width=16, state="readonly", font=("Segoe UI", 11))
        self.cmb_search_by.set("Description")
        self.cmb_search_by.pack(side="left", padx=(0, 12), pady=12)
        
        self.entry_search = tk.Entry(controls, font=("Segoe UI", 14), bd=2, relief="solid")
        self.entry_search.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=12, ipady=8)
        self.entry_search.insert(0, initial_query)
        
        # Touch-friendly search button
        search_btn = TouchButton(controls, text="SEARCH", command=self.filter_products,
                                 bg="#2c5282", fg="white", font=("Segoe UI", 11, "bold"))
        search_btn.pack(side="left", padx=(0, 8), pady=12)
        
        clear_btn = TouchButton(controls, text="CLEAR", command=self.clear_search,
                               bg="#edf2f7", fg="#243447", font=("Segoe UI", 11, "bold"))
        clear_btn.pack(side="left", padx=(0, 20), pady=12)
        
        # Keypad button
        keypad_btn = TouchButton(controls, text="🔢", command=self.show_keypad,
                                bg="#718096", fg="white", font=("Segoe UI", 14))
        keypad_btn.pack(side="left", padx=(0, 20), pady=12)
        
        # Results info
        info = tk.Frame(self, bg="#eef2f6")
        info.pack(fill="x", padx=20, pady=(0, 8))
        self.result_label = tk.Label(info, text="", font=("Segoe UI", 10),
                                     fg="#667085", bg="#eef2f6")
        self.result_label.pack(side="left")
        
        # Main content area with product list
        content_frame = tk.Frame(self, bg="#eef2f6")
        content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        
        # Product table
        table_frame = tk.Frame(content_frame, bg="white", bd=2, relief="solid")
        table_frame.pack(fill="both", expand=True)
        
        cols = ("barcode", "description", "category", "supplier", "retail", "soh")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        
        headings = {
            "barcode": "BARCODE",
            "description": "DESCRIPTION", 
            "category": "CATEGORY",
            "supplier": "SUPPLIER",
            "retail": "RETAIL PRICE",
            "soh": "SOH"
        }
        
        widths = {
            "barcode": 160,
            "description": 320,
            "category": 150,
            "supplier": 180,
            "retail": 130,
            "soh": 90
        }
        
        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="e" if col in ("retail", "soh") else "w")
        
        # Enhanced tree styling for touch
        style = ttk.Style(self)
        try:
            style.configure("TouchLookup.Treeview", font=("Segoe UI", 11), rowheight=40,
                            background="white", fieldbackground="white")
            style.configure("TouchLookup.Treeview.Heading", font=("Segoe UI", 10, "bold"))
            style.map("TouchLookup.Treeview", background=[("selected", "#dbeafe")],
                      foreground=[("selected", "#17202a")])
            self.tree.configure(style="TouchLookup.Treeview")
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in touch_f3_lookup.py", exc_info=exc)
        
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        
        # Touch-friendly action buttons
        footer = tk.Frame(self, bg="white", height=80, bd=2, relief="solid")
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        
        tk.Label(footer, text="Select a product to use its current selling price and stock information.",
                 font=("Segoe UI", 9), fg="#667085", bg="white").pack(side="left", padx=20)
        
        cancel_btn = TouchButton(footer, text="CANCEL", command=self.destroy,
                                bg="#e53e3e", fg="white", font=("Segoe UI", 11, "bold"))
        cancel_btn.pack(side="right", padx=(10, 20), pady=12)
        
        select_btn = TouchButton(footer, text="SELECT PRODUCT  ENTER", command=self.confirm_selection,
                                 bg="#38a169", fg="white", font=("Segoe UI", 11, "bold"))
        select_btn.pack(side="right", pady=12)
        
        # Touch shortcut hints
        shortcuts = {
            "ESC": "Close",
            "ENTER": "Select",
            "TAP": "Select"
        }
        create_shortcut_hint(self, shortcuts)
    
    def _setup_bindings(self):
        """Setup keyboard and touch bindings."""
        self.cmb_search_by.bind("<<ComboboxSelected>>", self.filter_products)
        
        # Keyboard bindings
        self.entry_search.bind("<KeyRelease>", self.filter_products)
        self.entry_search.bind("<Up>", lambda e: self.move_selection(-1))
        self.entry_search.bind("<Down>", lambda e: self.move_selection(1))
        self.entry_search.bind("<Return>", lambda e: self.confirm_selection())
        
        # Tree bindings
        self.tree.bind("<Return>", lambda e: self.confirm_selection())
        self.tree.bind("<Double-1>", lambda e: self.confirm_selection())
        self.tree.bind("<ButtonRelease-1>", self.on_mouse_click)
        
        # Escape to close
        self.bind("<Escape>", lambda e: self.destroy())
    
    def show_keypad(self):
        """Show on-screen numeric keypad."""
        if self.keypad_window and tk.Toplevel.winfo_exists(self.keypad_window):
            self.keypad_window.destroy()
        
        self.keypad_window = tk.Toplevel(self)
        self.keypad_window.title("Numeric Keypad")
        self.keypad_window.geometry("350x450")
        self.keypad_window.transient(self)
        self.keypad_window.grab_set()
        
        keypad = TouchKeypad(
            self.keypad_window,
            target_entry=self.entry_search,
            on_enter=lambda: self.keypad_window.destroy()
        )
        keypad.pack(fill=tk.BOTH, expand=True)
        
        # Position near search field
        try:
            x = self.entry_search.winfo_rootx()
            y = self.entry_search.winfo_rooty() + self.entry_search.winfo_height()
            self.keypad_window.geometry(f"+{x}+{y}")
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in touch_f3_lookup.py", exc_info=exc)
    
    def clear_search(self):
        """Clear search field and refresh results."""
        self.entry_search.delete(0, tk.END)
        self.filter_products()
        self.entry_search.focus_force()
    
    def filter_products(self, event=None):
        """Filter products based on search criteria."""
        # Don't filter when arrow keys are pressed
        if event and event.keysym in ("Up", "Down", "Left", "Right"):
            return
        
        query = self.entry_search.get().strip()
        
        # Clear current results
        for row in self.tree.get_children():
            self.tree.delete(row)
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        try:
            field = "description" if self.cmb_search_by.get() == "Description" else "barcode"
            cursor.execute(f"""
                SELECT barcode, description, category, supplier, selling_price, soh
                FROM products 
                WHERE {field} LIKE ? COLLATE NOCASE
                ORDER BY description ASC 
                LIMIT 250
            """, (f"%{query}%",))
            rows = cursor.fetchall()
        except Exception:
            cursor.execute("""
                SELECT barcode, description, '', '', selling_price, soh 
                FROM products
                WHERE description LIKE ? OR barcode LIKE ? 
                ORDER BY description LIMIT 250
            """, (f"%{query}%", f"%{query}%"))
            rows = cursor.fetchall()
        finally:
            conn.close()
        
        self.rows = rows
        
        # Populate tree with results
        for barcode, desc, cat, supplier, price, soh in rows:
            self.tree.insert("", tk.END, values=(
                barcode or "",
                desc or "",
                cat or "",
                supplier or "",
                f"R {float(price or 0):,.2f}",
                f"{float(soh or 0):g}"
            ))
        
        # Select first item if available
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])
            self.tree.see(children[0])
        
        self.result_label.config(text=f"{len(rows)} product(s) found")
    
    def move_selection(self, step):
        """Move product selection with arrow keys."""
        children = self.tree.get_children()
        if not children:
            return "break"
        
        selected = self.tree.selection()
        current_index = children.index(selected[0]) if selected else (-1 if step > 0 else 0)
        new_index = max(0, min(current_index + step, len(children) - 1))
        
        item_id = children[new_index]
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        self.tree.see(item_id)
        
        return "break"
    
    def on_mouse_click(self, event):
        """Handle mouse click on tree."""
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.tree.focus(row)
    
    def confirm_selection(self):
        """Confirm product selection and close window."""
        selected = self.tree.selection()
        if not selected:
            return "break"
        
        barcode = str(self.tree.item(selected[0])["values"][0])
        
        # Close the modal first
        try:
            self.grab_release()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in touch_f3_lookup.py", exc_info=exc)
        try:
            self.destroy()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in touch_f3_lookup.py", exc_info=exc)
        
        # Call callback with selected barcode
        if self.on_select_callback:
            try:
                self.on_select_callback(barcode)
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in touch_f3_lookup.py", exc_info=exc)
        
        return "break"


def install_touch_f3_lookup(app_cls):
    """Install touch-optimized F3 lookup into the main POS application."""
    
    # Store original F3 lookup method
    original_f3 = getattr(app_cls, 'open_f3_search', None)
    
    def touch_f3_search(self, event=None):
        """Open touch-optimized F3 product lookup."""
        initial_query = ""
        try:
            # Try to get current entry text as initial query
            if hasattr(self, 'code_entry'):
                initial_query = self.code_entry.get().strip()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in touch_f3_lookup.py", exc_info=exc)
        
        # Use touch-optimized window
        lookup = TouchF3LookupWindow(
            self,
            initial_query=initial_query,
            on_select_callback=self.add_product_by_barcode
        )
        
        # Keep reference to prevent garbage collection
        self.f3_window = lookup
    
    # Replace the F3 lookup method
    if original_f3:
        app_cls.open_f3_search = touch_f3_search
    
    return app_cls


if __name__ == "__main__":
    # Demo the touch F3 lookup
    root = tk.Tk()
    root.title("Touch F3 Lookup Demo")
    root.geometry("1200x800")
    
    def on_select(barcode):
        print(f"Selected product: {barcode}")
        messagebox.showinfo("Selection", f"You selected: {barcode}")
    
    lookup = TouchF3LookupWindow(root, on_select_callback=on_select)
    
    root.mainloop()
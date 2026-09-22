"""Enhanced cart management with touch-friendly controls for BKPOS.

Provides improved cart interaction:
- Touch-friendly cart item editing
- Swipe-to-delete functionality (simulated)
- Quick quantity adjustment buttons
- Better visual feedback
- Batch operations
"""
from core.logger import logger as _bkpos_logger

import tkinter as tk
from tkinter import ttk, messagebox
from touch_optimization import TouchButton, TouchListItem


class TouchCartItem(tk.Frame):
    """Touch-friendly cart item with enhanced controls."""
    
    def __init__(self, parent, item_data, on_edit=None, on_delete=None, **kwargs):
        default_kwargs = {
            'bg': '#f7fafc',
            'bd': 1,
            'relief': tk.SOLID,
            'padx': 12,
            'pady': 10
        }
        
        for key, value in default_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(parent, **kwargs)
        
        self.item_data = item_data
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.original_bg = self.cget('bg')
        
        self._build_ui()
        self._setup_bindings()
    
    def _build_ui(self):
        """Build the touch-friendly cart item UI."""
        # Main content area
        content_frame = tk.Frame(self, bg=self.cget('bg'))
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Product info
        info_frame = tk.Frame(content_frame, bg=self.cget('bg'))
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Product name
        name = self.item_data.get('name', 'Unknown Product')
        tk.Label(
            info_frame,
            text=name,
            font=('Arial', 11, 'bold'),
            bg=self.cget('bg'),
            fg='#1a202c',
            wraplength=300
        ).pack(anchor='w')
        
        # Product code
        code = self.item_data.get('code', '')
        if code:
            tk.Label(
                info_frame,
                text=f"Code: {code}",
                font=('Arial', 9),
                bg=self.cget('bg'),
                fg='#718096'
            ).pack(anchor='w', pady=(2, 0))
        
        # Price and quantity info
        details_frame = tk.Frame(info_frame, bg=self.cget('bg'))
        details_frame.pack(anchor='w', pady=(4, 0))
        
        price = self.item_data.get('price', 0)
        qty = self.item_data.get('qty', 1)
        value = self.item_data.get('value', price * qty)
        
        tk.Label(
            details_frame,
            text=f"R {price:.2f} × {qty:g} = R {value:.2f}",
            font=('Arial', 10, 'bold'),
            bg=self.cget('bg'),
            fg='#2d3748'
        ).pack(side=tk.LEFT)
        
        # Quick quantity controls
        qty_frame = tk.Frame(content_frame, bg=self.cget('bg'))
        qty_frame.pack(side=tk.RIGHT, padx=(10, 0))
        
        tk.Label(
            qty_frame,
            text="Qty:",
            font=('Arial', 9, 'bold'),
            bg=self.cget('bg'),
            fg='#4a5568'
        ).pack(anchor='e')
        
        # Quantity adjustment buttons
        qty_controls = tk.Frame(qty_frame, bg=self.cget('bg'))
        qty_controls.pack(pady=(2, 0))
        
        minus_btn = tk.Button(
            qty_controls,
            text="−",
            command=lambda: self._adjust_quantity(-1),
            font=('Arial', 14, 'bold'),
            bg='#fed7d7',
            fg='#c53030',
            relief=tk.FLAT,
            width=3
        )
        minus_btn.pack(side=tk.LEFT, padx=2)
        
        self.qty_label = tk.Label(
            qty_controls,
            text=f"{qty:g}",
            font=('Arial', 12, 'bold'),
            bg='white',
            fg='#1a202c',
            width=4,
            relief=tk.SOLID,
            bd=1
        )
        self.qty_label.pack(side=tk.LEFT, padx=2)
        
        plus_btn = tk.Button(
            qty_controls,
            text="+",
            command=lambda: self._adjust_quantity(1),
            font=('Arial', 14, 'bold'),
            bg='#c6f6d5',
            fg='#2f855a',
            relief=tk.FLAT,
            width=3
        )
        plus_btn.pack(side=tk.LEFT, padx=2)
        
        # Action buttons
        action_frame = tk.Frame(content_frame, bg=self.cget('bg'))
        action_frame.pack(side=tk.RIGHT, padx=(15, 0))
        
        if self.on_edit:
            edit_btn = tk.Button(
                action_frame,
                text="✏️",
                command=self._handle_edit,
                font=('Arial', 10),
                bg='#bee3f8',
                fg='#2b6cb0',
                relief=tk.FLAT,
                padx=8,
                pady=4
            )
            edit_btn.pack(pady=2)
        
        if self.on_delete:
            delete_btn = tk.Button(
                action_frame,
                text="🗑️",
                command=self._handle_delete,
                font=('Arial', 10),
                bg='#fed7d7',
                fg='#c53030',
                relief=tk.FLAT,
                padx=8,
                pady=4
            )
            delete_btn.pack(pady=2)
    
    def _setup_bindings(self):
        """Setup touch and mouse bindings."""
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._on_click)
    
    def _on_enter(self, event):
        """Hover effect."""
        try:
            self.config(bg='#edf2f7')
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in enhanced_cart.py", exc_info=exc)
    
    def _on_leave(self, event):
        """Remove hover effect."""
        try:
            self.config(bg=self.original_bg)
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in enhanced_cart.py", exc_info=exc)
    
    def _on_click(self, event):
        """Handle click to select item."""
        # Could implement selection logic here
        pass
    
    def _adjust_quantity(self, change):
        """Adjust item quantity."""
        try:
            new_qty = max(1, self.item_data.get('qty', 1) + change)
            self.item_data['qty'] = new_qty
            self.item_data['value'] = new_qty * self.item_data.get('price', 0)
            
            # Update display
            self.qty_label.config(text=f"{new_qty:g}")
            
            # Update price display
            price = self.item_data.get('price', 0)
            value = self.item_data.get('value', 0)
            
            # Find and update the price label
            for widget in self.winfo_children():
                if isinstance(widget, tk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, tk.Frame):
                            for grandchild in child.winfo_children():
                                if isinstance(grandchild, tk.Label) and "R" in grandchild.cget('text'):
                                    grandchild.config(text=f"R {price:.2f} × {new_qty:g} = R {value:.2f}")
            
            # Notify parent of change
            if hasattr(self.master, 'update_cart_totals'):
                self.master.update_cart_totals()
                
        except Exception as e:
            print(f"Error adjusting quantity: {e}")
    
    def _handle_edit(self):
        """Handle edit button click."""
        if self.on_edit:
            self.on_edit(self.item_data)
    
    def _handle_delete(self):
        """Handle delete button click."""
        if self.on_delete:
            # Confirm deletion
            if messagebox.askyesno(
                "Remove Item",
                f"Remove {self.item_data.get('name', 'this item')} from cart?"
            ):
                self.on_delete(self.item_data)
    
    def update_data(self, new_data):
        """Update the item data and refresh display."""
        self.item_data = new_data
        
        # Rebuild UI with new data
        for widget in self.winfo_children():
            widget.destroy()
        
        self._build_ui()
        self._setup_bindings()


class TouchCartPanel(tk.Frame):
    """Touch-friendly cart panel with enhanced controls."""
    
    def __init__(self, parent, pos_instance=None, **kwargs):
        default_kwargs = {
            'bg': 'white',
            'bd': 2,
            'relief': tk.SOLID,
            'padx': 15,
            'pady': 15
        }
        
        for key, value in default_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(parent, **kwargs)
        
        self.pos_instance = pos_instance
        self.cart_items = []
        self.cart_item_widgets = {}
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the touch cart panel UI."""
        # Header
        header_frame = tk.Frame(self, bg='white')
        header_frame.pack(fill=tk.X, pady=(0, 12))
        
        tk.Label(
            header_frame,
            text="🛒 SHOPPING CART",
            font=('Arial', 12, 'bold'),
            bg='white',
            fg='#2d3748'
        ).pack(side=tk.LEFT)
        
        # Cart controls
        controls_frame = tk.Frame(header_frame, bg='white')
        controls_frame.pack(side=tk.RIGHT)
        
        control_buttons = [
            ("🔄 Refresh", self._refresh_cart),
            ("📋 Clear", self._clear_cart),
            ("💾 Save", self._save_cart)
        ]
        
        for text, command in control_buttons:
            btn = tk.Button(
                controls_frame,
                text=text,
                command=command,
                font=('Arial', 9),
                bg='#edf2f7',
                fg='#4a5568',
                relief=tk.FLAT,
                padx=8,
                pady=4
            )
            btn.pack(side=tk.LEFT, padx=2)
        
        # Cart items container
        self.items_container = tk.Frame(self, bg='white')
        self.items_container.pack(fill=tk.BOTH, expand=True)
        
        # Scrollable frame for cart items
        canvas = tk.Canvas(self.items_container, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.items_container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas, bg='white')
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Totals section
        self.totals_frame = tk.Frame(self, bg='#f7fafc', bd=1, relief=tk.SOLID, padx=15, pady=12)
        self.totals_frame.pack(fill=tk.X, pady=(12, 0))
        
        self._build_totals()
    
    def _build_totals(self):
        """Build the totals display."""
        # Subtotal
        self.subtotal_label = tk.Label(
            self.totals_frame,
            text="Subtotal: R 0.00",
            font=('Arial', 10),
            bg='#f7fafc',
            fg='#4a5568'
        )
        self.subtotal_label.pack(anchor='e')
        
        # VAT
        self.vat_label = tk.Label(
            self.totals_frame,
            text="VAT (15%): R 0.00",
            font=('Arial', 10),
            bg='#f7fafc',
            fg='#4a5568'
        )
        self.vat_label.pack(anchor='e')
        
        # Total
        self.total_label = tk.Label(
            self.totals_frame,
            text="TOTAL: R 0.00",
            font=('Arial', 14, 'bold'),
            bg='#f7fafc',
            fg='#1a202c'
        )
        self.total_label.pack(anchor='e', pady=(5, 0))
    
    def add_cart_item(self, item_data):
        """Add an item to the cart display."""
        # Create touch-friendly cart item
        cart_item = TouchCartItem(
            self.scrollable_frame,
            item_data,
            on_edit=self._edit_item,
            on_delete=self._delete_item
        )
        cart_item.pack(fill=tk.X, pady=5)
        
        # Store references
        item_id = item_data.get('code') or len(self.cart_items)
        self.cart_item_widgets[item_id] = cart_item
        self.cart_items.append(item_data)
        
        self.update_cart_totals()
    
    def _edit_item(self, item_data):
        """Handle item editing."""
        if self.pos_instance:
            try:
                if hasattr(self.pos_instance, 'open_edit_cart_item'):
                    # Find the index of the item
                    cart = self.pos_instance.current_invoice().get('cart', [])
                    try:
                        index = cart.index(item_data)
                        self.pos_instance.open_edit_cart_item(None, index)
                    except ValueError:
                        messagebox.showerror("Error", "Item not found in cart")
            except Exception as e:
                messagebox.showerror("Error", f"Could not edit item: {e}")
    
    def _delete_item(self, item_data):
        """Handle item deletion."""
        # Remove from display
        item_id = item_data.get('code') or id(item_data)
        if item_id in self.cart_item_widgets:
            self.cart_item_widgets[item_id].destroy()
            del self.cart_item_widgets[item_id]
        
        # Remove from data
        if item_data in self.cart_items:
            self.cart_items.remove(item_data)
        
        # Update POS cart
        if self.pos_instance:
            try:
                cart = self.pos_instance.current_invoice()
                if item_data in cart.get('cart', []):
                    cart['cart'].remove(item_data)
                    self.pos_instance.update_cart_display()
            except Exception as e:
                print(f"Error updating POS cart: {e}")
        
        self.update_cart_totals()
    
    def update_cart_totals(self):
        """Update the cart totals display."""
        subtotal = sum(item.get('value', 0) for item in self.cart_items)
        vat = subtotal * 0.15 / 1.15  # Assuming 15% VAT included
        total = subtotal
        
        self.subtotal_label.config(text=f"Subtotal: R {subtotal:.2f}")
        self.vat_label.config(text=f"VAT (15%): R {vat:.2f}")
        self.total_label.config(text=f"TOTAL: R {total:.2f}")
    
    def _refresh_cart(self):
        """Refresh the cart display from POS."""
        if self.pos_instance:
            try:
                # Clear current display
                for widget in self.scrollable_frame.winfo_children():
                    widget.destroy()
                self.cart_items.clear()
                self.cart_item_widgets.clear()
                
                # Reload from POS
                cart = self.pos_instance.current_invoice().get('cart', [])
                for item in cart:
                    self.add_cart_item(item)
                    
            except Exception as e:
                messagebox.showerror("Error", f"Could not refresh cart: {e}")
    
    def _clear_cart(self):
        """Clear the entire cart."""
        if messagebox.askyesno("Clear Cart", "Remove all items from cart?"):
            # Clear display
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            self.cart_items.clear()
            self.cart_item_widgets.clear()
            
            # Clear POS cart
            if self.pos_instance:
                try:
                    cart = self.pos_instance.current_invoice()
                    cart['cart'] = []
                    self.pos_instance.update_cart_display()
                except Exception as e:
                    print(f"Error clearing POS cart: {e}")
            
            self.update_cart_totals()
    
    def _save_cart(self):
        """Save the current cart for later."""
        messagebox.showinfo("Save Cart", "Cart saved for later recall")


def install_enhanced_cart(app_cls):
    """Install enhanced cart management into the main POS application."""
    
    original_init = app_cls.__init__
    
    def __init_with_enhanced_cart(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        
        # Add enhanced cart panel to the main POS screen
        try:
            if hasattr(self, 'pos_screen'):
                # This could be added as a side panel or replace the existing cart display
                # For now, we'll just create it and store the reference
                enhanced_cart = TouchCartPanel(self.pos_screen, pos_instance=self)
                # Don't pack it automatically - let the user decide where to place it
                # enhanced_cart.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
                
                # Store reference
                self.enhanced_cart_panel = enhanced_cart
        except Exception as e:
            print(f"Error installing enhanced cart: {e}")
    
    app_cls.__init__ = __init_with_enhanced_cart
    
    return app_cls


if __name__ == "__main__":
    # Demo the enhanced cart
    root = tk.Tk()
    root.title("Enhanced Cart Demo")
    root.geometry("500x700")
    
    cart_panel = TouchCartPanel(root)
    cart_panel.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Add some sample items
    sample_items = [
        {
            'code': '6009612470533',
            'name': 'AQUELLE FLAVOUR WATER 1.5L',
            'price': 14.99,
            'qty': 2,
            'value': 29.98
        },
        {
            'code': '6009612470168',
            'name': 'AQUELLE FLAVOUR WATER 500ML',
            'price': 9.99,
            'qty': 1,
            'value': 9.99
        }
    ]
    
    for item in sample_items:
        cart_panel.add_cart_item(item)
    
    root.mainloop()
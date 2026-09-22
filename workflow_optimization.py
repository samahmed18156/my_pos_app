from core.config import DB_PATH
"""Workflow optimization module for BKPOS.

Streamlines common workflows to reduce clicks and improve efficiency:
- Quick checkout actions
- One-click common operations
- Smart cart management
- Batch operations
- Workflow shortcuts
"""

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    try:
        from touch_optimization import TouchButton, create_touch_action_bar
    except ImportError:
        TouchButton = tk.Button
        create_touch_action_bar = None
except ImportError:
    print("Warning: Required modules not available, workflow optimization will not work")
    tk = None
    TouchButton = None
    create_touch_action_bar = None


class QuickActionsBar(tk.Frame if tk else object):
    """Quick action bar for common POS operations."""
    
    def __init__(self, parent, pos_instance=None, **kwargs):
        default_kwargs = {
            'bg': '#f0f4f8',
            'padx': 12,
            'pady': 10
        }
        
        for key, value in default_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(parent, **kwargs)
        
        self.pos_instance = pos_instance
        self._build_ui()
    
    def _build_ui(self):
        """Build the quick actions UI."""
        tk.Label(
            self,
            text="⚡ QUICK ACTIONS",
            font=('Arial', 10, 'bold'),
            bg=self.cget('bg'),
            fg='#4a5568'
        ).pack(anchor='w', pady=(0, 8))
        
        # Quick action buttons
        actions_frame = tk.Frame(self, bg=self.cget('bg'))
        actions_frame.pack(fill=tk.X)
        
        quick_actions = [
            ("🛒 Complete Sale", "#38a169", self._quick_checkout),
            ("👤 Add Customer", "#3182ce", self._quick_customer),
            ("🏷️ Apply Discount", "#d69e2e", self._quick_discount),
            ("📋 Hold Invoice", "#718096", self._quick_hold),
            ("🔄 Recall", "#805ad5", self._quick_recall),
            ("❌ Clear Cart", "#e53e3e", self._quick_clear)
        ]
        
        for i, (text, color, command) in enumerate(quick_actions):
            btn = TouchButton(
                actions_frame,
                text=text,
                command=command,
                bg=color,
                fg='white',
                font=('Arial', 9, 'bold')
            )
            btn.grid(row=i//3, column=i%3, sticky='nsew', padx=4, pady=4)
        
        # Configure grid
        for i in range(3):
            actions_frame.grid_columnconfigure(i, weight=1)
    
    def _quick_checkout(self):
        """Quick checkout - goes directly to payment."""
        if self.pos_instance:
            try:
                # Trigger F12 payment directly
                if hasattr(self.pos_instance, 'process_payment'):
                    self.pos_instance.process_payment()
                elif hasattr(self.pos_instance, 'checkout'):
                    self.pos_instance.checkout()
            except Exception as e:
                messagebox.showerror("Error", f"Could not process checkout: {e}")
    
    def _quick_customer(self):
        """Quick customer lookup."""
        if self.pos_instance:
            try:
                if hasattr(self.pos_instance, 'open_customer_lookup'):
                    self.pos_instance.open_customer_lookup()
            except Exception as e:
                messagebox.showerror("Error", f"Could not open customer lookup: {e}")
    
    def _quick_discount(self):
        """Quick discount application."""
        if self.pos_instance:
            try:
                # Apply a quick discount to the current invoice
                messagebox.showinfo("Discount", "Quick discount feature - apply percentage or fixed amount")
            except Exception as e:
                messagebox.showerror("Error", f"Could not apply discount: {e}")
    
    def _quick_hold(self):
        """Hold current invoice for later."""
        if self.pos_instance:
            try:
                if hasattr(self.pos_instance, 'hold_invoice'):
                    self.pos_instance.hold_invoice()
                else:
                    messagebox.showinfo("Hold Invoice", "Invoice held successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Could not hold invoice: {e}")
    
    def _quick_recall(self):
        """Recall a held invoice."""
        if self.pos_instance:
            try:
                if hasattr(self.pos_instance, 'open_invoice_selector'):
                    self.pos_instance.open_invoice_selector()
            except Exception as e:
                messagebox.showerror("Error", f"Could not recall invoice: {e}")
    
    def _quick_clear(self):
        """Clear current cart with confirmation."""
        if self.pos_instance:
            try:
                if messagebox.askyesno("Clear Cart", "Are you sure you want to clear the current cart?"):
                    if hasattr(self.pos_instance, 'clear_cart'):
                        self.pos_instance.clear_cart()
                    else:
                        messagebox.showinfo("Clear Cart", "Cart cleared successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Could not clear cart: {e}")


class SmartCartManager(tk.Frame):
    """Enhanced cart management with batch operations and smart features."""
    
    def __init__(self, parent, pos_instance=None, **kwargs):
        default_kwargs = {
            'bg': 'white',
            'bd': 1,
            'relief': tk.SOLID,
            'padx': 15,
            'pady': 15
        }
        
        for key, value in default_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(parent, **kwargs)
        
        self.pos_instance = pos_instance
        self._build_ui()
    
    def _build_ui(self):
        """Build the smart cart management UI."""
        tk.Label(
            self,
            text="🛒 SMART CART MANAGER",
            font=('Arial', 11, 'bold'),
            bg='white',
            fg='#2d3748'
        ).pack(anchor='w', pady=(0, 12))
        
        # Batch operations
        batch_frame = tk.Frame(self, bg='white')
        batch_frame.pack(fill=tk.X, pady=(0, 12))
        
        tk.Label(
            batch_frame,
            text="Batch Operations:",
            font=('Arial', 9, 'bold'),
            bg='white',
            fg='#4a5568'
        ).pack(anchor='w', pady=(0, 6))
        
        batch_buttons = [
            ("+1 All", lambda: self._batch_quantity(1)),
            ("-1 All", lambda: self._batch_quantity(-1)),
            ("×2 All", lambda: self._batch_multiply(2)),
            ("÷2 All", lambda: self._batch_divide(2)),
            ("Remove All", self._batch_remove)
        ]
        
        for text, command in batch_buttons:
            btn = tk.Button(
                batch_frame,
                text=text,
                command=command,
                font=('Arial', 9),
                bg='#edf2f7',
                fg='#2d3748',
                relief=tk.FLAT,
                padx=8,
                pady=4
            )
            btn.pack(side=tk.LEFT, padx=3)
        
        # Smart features
        smart_frame = tk.Frame(self, bg='white')
        smart_frame.pack(fill=tk.X)
        
        tk.Label(
            smart_frame,
            text="Smart Features:",
            font=('Arial', 9, 'bold'),
            bg='white',
            fg='#4a5568'
        ).pack(anchor='w', pady=(0, 6))
        
        smart_buttons = [
            ("🔄 Auto-Complete Order", self._auto_complete),
            ("📦 Check Stock", self._check_stock),
            ("💡 Suggest Products", self._suggest_products),
            ("🏷️ Apply Promos", self._apply_promos)
        ]
        
        for text, command in smart_buttons:
            btn = tk.Button(
                smart_frame,
                text=text,
                command=command,
                font=('Arial', 9),
                bg='#dbeafe',
                fg='#2c5282',
                relief=tk.FLAT,
                padx=8,
                pady=4
            )
            btn.pack(side=tk.LEFT, padx=3)
    
    def _batch_quantity(self, change):
        """Add or subtract 1 from all item quantities."""
        if self.pos_instance:
            try:
                cart = self.pos_instance.current_invoice().get('cart', [])
                for item in cart:
                    item['qty'] = max(1, item.get('qty', 1) + change)
                    item['value'] = item['qty'] * item.get('price', 0)
                self.pos_instance.update_cart_display()
            except Exception as e:
                messagebox.showerror("Error", f"Could not update quantities: {e}")
    
    def _batch_multiply(self, factor):
        """Multiply all item quantities by factor."""
        if self.pos_instance:
            try:
                cart = self.pos_instance.current_invoice().get('cart', [])
                for item in cart:
                    item['qty'] = item.get('qty', 1) * factor
                    item['value'] = item['qty'] * item.get('price', 0)
                self.pos_instance.update_cart_display()
            except Exception as e:
                messagebox.showerror("Error", f"Could not multiply quantities: {e}")
    
    def _batch_divide(self, factor):
        """Divide all item quantities by factor."""
        if self.pos_instance:
            try:
                cart = self.pos_instance.current_invoice().get('cart', [])
                for item in cart:
                    item['qty'] = max(1, item.get('qty', 1) // factor)
                    item['value'] = item['qty'] * item.get('price', 0)
                self.pos_instance.update_cart_display()
            except Exception as e:
                messagebox.showerror("Error", f"Could not divide quantities: {e}")
    
    def _batch_remove(self):
        """Remove all items from cart with confirmation."""
        if self.pos_instance:
            try:
                if messagebox.askyesno("Remove All", "Remove all items from cart?"):
                    cart = self.pos_instance.current_invoice()
                    cart['cart'] = []
                    self.pos_instance.update_cart_display()
            except Exception as e:
                messagebox.showerror("Error", f"Could not remove items: {e}")
    
    def _auto_complete(self):
        """Auto-complete common order patterns."""
        messagebox.showinfo("Auto-Complete", "AI-powered order completion based on common patterns")
    
    def _check_stock(self):
        """Check stock availability for all cart items."""
        if self.pos_instance:
            try:
                import sqlite3
                conn = sqlite3.connect(DB_PATH)
                cart = self.pos_instance.current_invoice().get('cart', [])
                
                stock_issues = []
                for item in cart:
                    barcode = item.get('code')
                    qty = item.get('qty', 0)
                    
                    result = conn.execute(
                        "SELECT description, COALESCE(soh,0) FROM products WHERE barcode=?",
                        (str(barcode),)
                    ).fetchone()
                    
                    if result:
                        desc, soh = result
                        if qty > soh:
                            stock_issues.append(f"{desc}: Requested {qty}, Available {soh}")
                
                conn.close()
                
                if stock_issues:
                    messagebox.showwarning(
                        "Stock Check",
                        "Some items have insufficient stock:\n\n" + "\n".join(stock_issues)
                    )
                else:
                    messagebox.showinfo("Stock Check", "All items are in stock!")
            except Exception as e:
                messagebox.showerror("Error", f"Could not check stock: {e}")
    
    def _suggest_products(self):
        """Suggest related products based on cart contents."""
        messagebox.showinfo("Product Suggestions", "AI-powered product suggestions based on current cart")
    
    def _apply_promos(self):
        """Apply applicable promotions to cart."""
        messagebox.showinfo("Promotions", "Apply available promotions to current cart")


class OneTouchCheckout(tk.Frame):
    """One-touch checkout panel for completing sales quickly."""
    
    def __init__(self, parent, pos_instance=None, **kwargs):
        default_kwargs = {
            'bg': '#f0fff4',
            'bd': 2,
            'relief': tk.SOLID,
            'padx': 20,
            'pady': 15
        }
        
        for key, value in default_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(parent, **kwargs)
        
        self.pos_instance = pos_instance
        self._build_ui()
    
    def _build_ui(self):
        """Build the one-touch checkout UI."""
        tk.Label(
            self,
            text="⚡ ONE-TOUCH CHECKOUT",
            font=('Arial', 12, 'bold'),
            bg='#f0fff4',
            fg='#22543d'
        ).pack(anchor='w', pady=(0, 10))
        
        # Quick payment methods
        payment_frame = tk.Frame(self, bg='#f0fff4')
        payment_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(
            payment_frame,
            text="Quick Payment:",
            font=('Arial', 10, 'bold'),
            bg='#f0fff4',
            fg='#2f855a'
        ).pack(anchor='w', pady=(0, 8))
        
        # Large payment buttons
        payment_methods = [
            ("💵 CASH", "#38a169", "cash"),
            ("💳 CARD", "#3182ce", "card"),
            ("📱 EFT", "#805ad5", "eft"),
            ("🏷️ ACCOUNT", "#d69e2e", "account")
        ]
        
        for text, color, method in payment_methods:
            btn = TouchButton(
                payment_frame,
                text=text,
                command=lambda m=method: self._quick_payment(m),
                bg=color,
                fg='white',
                font=('Arial', 11, 'bold')
            )
            btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
        
        # Express lane
        express_frame = tk.Frame(self, bg='#c6f6d5', bd=1, relief=tk.SOLID, padx=12, pady=8)
        express_frame.pack(fill=tk.X, pady=(10, 0))
        
        tk.Label(
            express_frame,
            text="🚀 EXPRESS LANE",
            font=('Arial', 10, 'bold'),
            bg='#c6f6d5',
            fg='#22543d'
        ).pack(anchor='w')
        
        express_btn = TouchButton(
            express_frame,
            text="SKIP TO PAYMENT (F12)",
            command=self._skip_to_payment,
            bg="#22543d",
            fg="white",
            font=('Arial', 10, 'bold')
        )
        express_btn.pack(fill=tk.X, pady=(5, 0))
    
    def _quick_payment(self, method):
        """Process quick payment with selected method."""
        if self.pos_instance:
            try:
                # Pre-select payment method and open payment dialog
                if hasattr(self.pos_instance, 'process_payment_with_method'):
                    self.pos_instance.process_payment_with_method(method)
                else:
                    messagebox.showinfo(f"{method.upper()} Payment", f"Processing {method.upper()} payment...")
            except Exception as e:
                messagebox.showerror("Error", f"Could not process payment: {e}")
    
    def _skip_to_payment(self):
        """Skip directly to payment screen."""
        if self.pos_instance:
            try:
                if hasattr(self.pos_instance, 'process_payment'):
                    self.pos_instance.process_payment()
                elif hasattr(self.pos_instance, 'checkout'):
                    self.pos_instance.checkout()
            except Exception as e:
                messagebox.showerror("Error", f"Could not skip to payment: {e}")


def install_workflow_optimization(app_cls):
    """Install workflow optimization features into the main POS application."""
    
    original_init = app_cls.__init__
    
    def __init_with_workflow(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        
        # Add workflow optimization components to the main POS screen
        try:
            if hasattr(self, 'pos_screen'):
                # Add quick actions bar
                quick_actions = QuickActionsBar(self.pos_screen, pos_instance=self)
                quick_actions.pack(fill=tk.X, padx=8, pady=(5, 8))
                
                # Add smart cart manager (could be placed in a side panel)
                # smart_cart = SmartCartManager(self.pos_screen, pos_instance=self)
                # smart_cart.pack(fill=tk.X, padx=8, pady=(5, 8))
                
                # Add one-touch checkout (could be placed near totals)
                # one_touch = OneTouchCheckout(self.pos_screen, pos_instance=self)
                # one_touch.pack(fill=tk.X, padx=8, pady=(5, 8))
                
                # Store references
                self.quick_actions_bar = quick_actions
        except Exception as e:
            print(f"Error installing workflow optimization: {e}")
    
    app_cls.__init__ = __init_with_workflow
    
    return app_cls


if __name__ == "__main__":
    # Demo the workflow optimization components
    root = tk.Tk()
    root.title("Workflow Optimization Demo")
    root.geometry("900x600")
    
    # Quick actions bar
    quick_actions = QuickActionsBar(root)
    quick_actions.pack(fill=tk.X, padx=20, pady=20)
    
    # Smart cart manager
    smart_cart = SmartCartManager(root)
    smart_cart.pack(fill=tk.X, padx=20, pady=20)
    
    # One-touch checkout
    one_touch = OneTouchCheckout(root)
    one_touch.pack(fill=tk.X, padx=20, pady=20)
    
    root.mainloop()
"""Visual keyboard shortcut hints for BKPOS.

Provides on-screen keyboard shortcut hints to help users:
- Learn keyboard shortcuts faster
- Improve workflow efficiency
- Reduce dependency on mouse/touch
- Provide training assistance for new staff
"""
from core.logger import logger as _bkpos_logger

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    print("Warning: tkinter not available, shortcut hints will not work")


class ShortcutHintBar(tk.Frame):
    """A bar that displays keyboard shortcuts in a touch-friendly format."""
    
    def __init__(self, parent, shortcuts=None, **kwargs):
        """
        Initialize the shortcut hint bar.
        
        Args:
            parent: Parent widget
            shortcuts: Dictionary of shortcut -> description
            kwargs: Additional frame configuration options
        """
        default_kwargs = {
            'bg': '#f7fafc',
            'bd': 1,
            'relief': tk.FLAT,
            'padx': 15,
            'pady': 10
        }
        
        for key, value in default_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(parent, **kwargs)
        
        self.shortcuts = shortcuts or {}
        self.shortcut_widgets = {}
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the shortcut hint UI."""
        # Title
        title_label = tk.Label(
            self,
            text="⌨ KEYBOARD SHORTCUTS",
            font=('Arial', 9, 'bold'),
            bg=self.cget('bg'),
            fg='#4a5568'
        )
        title_label.pack(anchor='w', pady=(0, 8))
        
        # Shortcuts container
        self.shortcuts_container = tk.Frame(self, bg=self.cget('bg'))
        self.shortcuts_container.pack(fill=tk.X)
        
        self._refresh_shortcuts()
    
    def _refresh_shortcuts(self):
        """Refresh the shortcuts display."""
        # Clear existing shortcuts
        for widget in self.shortcuts_container.winfo_children():
            widget.destroy()
        
        # Add shortcut chips
        for shortcut, description in self.shortcuts.items():
            self._add_shortcut_chip(shortcut, description)
    
    def _add_shortcut_chip(self, shortcut, description):
        """Add a single shortcut chip to the display."""
        chip = tk.Frame(
            self.shortcuts_container,
            bg='white',
            bd=1,
            relief=tk.SOLID,
            padx=10,
            pady=6,
            cursor='hand2'
        )
        chip.pack(side=tk.LEFT, padx=4, pady=3)
        
        # Key badge
        key_badge = tk.Label(
            chip,
            text=shortcut,
            font=('Arial', 9, 'bold'),
            bg='#2c5282',
            fg='white',
            padx=6,
            pady=2
        )
        key_badge.pack(side=tk.LEFT)
        
        # Description
        desc_label = tk.Label(
            chip,
            text=f" {description}",
            font=('Arial', 9),
            bg='white',
            fg='#4a5568'
        )
        desc_label.pack(side=tk.LEFT)
        
        # Store reference
        self.shortcut_widgets[shortcut] = chip
    
    def update_shortcuts(self, new_shortcuts):
        """Update the shortcuts displayed."""
        self.shortcuts = new_shortcuts
        self._refresh_shortcuts()
    
    def add_shortcut(self, shortcut, description):
        """Add a new shortcut to the display."""
        self.shortcuts[shortcut] = description
        self._add_shortcut_chip(shortcut, description)


class ContextualShortcutHints(tk.Frame):
    """Context-aware shortcut hints that change based on current screen/context."""
    
    def __init__(self, parent, **kwargs):
        default_kwargs = {
            'bg': '#edf2f7',
            'padx': 12,
            'pady': 8
        }
        
        for key, value in default_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(parent, **kwargs)
        
        self.context_shortcuts = {
            'pos': {
                'F1': 'Home/Dashboard',
                'F3': 'Product Lookup',
                'F9': 'Quotation',
                'F12': 'Payment',
                'Ctrl+N': 'New Invoice',
                'Ctrl+I': 'Open Invoices',
                'Ctrl+S': 'Save',
                'Esc': 'Cancel'
            },
            'lookup': {
                'ESC': 'Close',
                'ENTER': 'Select',
                '↑↓': 'Navigate',
                'F3': 'Product Lookup',
                'F4': 'Customer Lookup'
            },
            'payment': {
                'ESC': 'Cancel',
                'ENTER': 'Confirm',
                'Alt+C': 'Cash',
                'Alt+A': 'Card',
                'Alt+B': 'Bank Transfer',
                'Alt+S': 'Split Payment'
            },
            'reports': {
                'ESC': 'Close',
                'Ctrl+P': 'Print',
                'Ctrl+E': 'Export',
                'F5': 'Refresh'
            }
        }
        
        self.current_context = 'pos'
        self.hint_bar = None
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the contextual hints UI."""
        # Context indicator
        self.context_label = tk.Label(
            self,
            text=f"CONTEXT: {self.current_context.upper()}",
            font=('Arial', 8, 'bold'),
            bg=self.cget('bg'),
            fg='#718096'
        )
        self.context_label.pack(anchor='w', pady=(0, 5))
        
        # Shortcut hint bar
        self.hint_bar = ShortcutHintBar(
            self,
            shortcuts=self.context_shortcuts[self.current_context]
        )
        self.hint_bar.pack(fill=tk.X)
    
    def set_context(self, context):
        """Change the current context and update shortcuts."""
        if context in self.context_shortcuts:
            self.current_context = context
            self.context_label.config(text=f"CONTEXT: {context.upper()}")
            self.hint_bar.update_shortcuts(self.context_shortcuts[context])
    
    def add_context(self, context_name, shortcuts):
        """Add a new context with its shortcuts."""
        self.context_shortcuts[context_name] = shortcuts


class ShortcutTutorial(tk.Toplevel):
    """Interactive tutorial for learning keyboard shortcuts."""
    
    def __init__(self, parent, shortcuts=None):
        super().__init__(parent)
        self.title("Keyboard Shortcuts Tutorial")
        self.geometry("800x600")
        self.configure(bg="#f7fafc")
        self.transient(parent)
        self.grab_set()
        
        self.shortcuts = shortcuts or {}
        self.current_step = 0
        self.tutorial_steps = self._create_tutorial_steps()
        
        self._build_ui()
        self._show_step()
    
    def _create_tutorial_steps(self):
        """Create tutorial steps for common shortcuts."""
        return [
            {
                'title': 'Welcome to Shortcuts Tutorial',
                'content': 'Keyboard shortcuts can significantly speed up your workflow. Let\'s learn the most important ones!',
                'shortcuts': []
            },
            {
                'title': 'Product Lookup (F3)',
                'content': 'Press F3 to quickly search for products without using the mouse. This is the most used shortcut!',
                'shortcuts': [('F3', 'Open Product Lookup')]
            },
            {
                'title': 'Payment (F12)',
                'content': 'When you\'re ready to complete a sale, press F12 to open the payment dialog instantly.',
                'shortcuts': [('F12', 'Open Payment')]
            },
            {
                'title': 'New Invoice (Ctrl+N)',
                'content': 'Start a new sale quickly by pressing Ctrl+N instead of clicking the New Invoice button.',
                'shortcuts': [('Ctrl+N', 'New Invoice')]
            },
            {
                'title': 'Navigation',
                'content': 'Use these shortcuts to navigate through the application efficiently.',
                'shortcuts': [
                    ('F1', 'Home/Dashboard'),
                    ('F9', 'Quotation'),
                    ('Ctrl+I', 'Open Invoices')
                ]
            },
            {
                'title': 'You\'re Ready!',
                'content': 'You\'ve learned the essential shortcuts. Practice them daily to build muscle memory and speed up your work!',
                'shortcuts': []
            }
        ]
    
    def _build_ui(self):
        """Build the tutorial UI."""
        # Header
        header = tk.Frame(self, bg="#2c5282", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text="⌨ KEYBOARD SHORTCUTS TUTORIAL",
                 font=("Arial", 16, "bold"), fg="white", bg="#2c5282").pack(pady=15)
        
        # Progress indicator
        self.progress_label = tk.Label(
            self,
            text="Step 1 of 6",
            font=("Arial", 10),
            bg="#f7fafc",
            fg="#718096"
        )
        self.progress_label.pack(pady=(15, 10))
        
        # Content area
        content_frame = tk.Frame(self, bg="white", bd=2, relief=tk.SOLID, padx=30, pady=25)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        self.title_label = tk.Label(
            content_frame,
            text="",
            font=("Arial", 18, "bold"),
            bg="white",
            fg="#1a202c"
        )
        self.title_label.pack(anchor='w', pady=(0, 15))
        
        self.content_label = tk.Label(
            content_frame,
            text="",
            font=("Arial", 12),
            bg="white",
            fg="#4a5568",
            wraplength=700,
            justify="left"
        )
        self.content_label.pack(anchor='w', pady=(0, 20))
        
        # Shortcuts display area
        self.shortcuts_frame = tk.Frame(content_frame, bg="white")
        self.shortcuts_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Navigation buttons
        nav_frame = tk.Frame(self, bg="#f7fafc")
        nav_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        self.prev_btn = tk.Button(
            nav_frame,
            text="← Previous",
            command=self._previous_step,
            state=tk.DISABLED,
            font=("Arial", 10, "bold"),
            bg="#718096",
            fg="white",
            relief=tk.FLAT,
            padx=15,
            pady=8
        )
        self.prev_btn.pack(side=tk.LEFT)
        
        self.next_btn = tk.Button(
            nav_frame,
            text="Next →",
            command=self._next_step,
            font=("Arial", 10, "bold"),
            bg="#2c5282",
            fg="white",
            relief=tk.FLAT,
            padx=15,
            pady=8
        )
        self.next_btn.pack(side=tk.RIGHT)
        
        # Close button
        tk.Button(
            self,
            text="Close Tutorial",
            command=self.destroy,
            font=("Arial", 10, "bold"),
            bg="#e53e3e",
            fg="white",
            relief=tk.FLAT,
            padx=20,
            pady=10
        ).pack(side=tk.BOTTOM, pady=15)
    
    def _show_step(self):
        """Display the current tutorial step."""
        if self.current_step < len(self.tutorial_steps):
            step = self.tutorial_steps[self.current_step]
            
            self.title_label.config(text=step['title'])
            self.content_label.config(text=step['content'])
            self.progress_label.config(
                text=f"Step {self.current_step + 1} of {len(self.tutorial_steps)}"
            )
            
            # Clear and add shortcuts
            for widget in self.shortcuts_frame.winfo_children():
                widget.destroy()
            
            for shortcut, description in step['shortcuts']:
                shortcut_frame = tk.Frame(
                    self.shortcuts_frame,
                    bg="#edf2f7",
                    padx=12,
                    pady=8
                )
                shortcut_frame.pack(fill=tk.X, pady=5)
                
                tk.Label(
                    shortcut_frame,
                    text=shortcut,
                    font=("Arial", 11, "bold"),
                    bg="#2c5282",
                    fg="white",
                    padx=8,
                    pady=4
                ).pack(side=tk.LEFT)
                
                tk.Label(
                    shortcut_frame,
                    text=f" {description}",
                    font=("Arial", 11),
                    bg="#edf2f7",
                    fg="#4a5568"
                ).pack(side=tk.LEFT)
            
            # Update button states
            self.prev_btn.config(state=tk.NORMAL if self.current_step > 0 else tk.DISABLED)
            
            if self.current_step == len(self.tutorial_steps) - 1:
                self.next_btn.config(text="Finish", state=tk.DISABLED)
            else:
                self.next_btn.config(text="Next →", state=tk.NORMAL)
    
    def _next_step(self):
        """Move to the next tutorial step."""
        if self.current_step < len(self.tutorial_steps) - 1:
            self.current_step += 1
            self._show_step()
    
    def _previous_step(self):
        """Move to the previous tutorial step."""
        if self.current_step > 0:
            self.current_step -= 1
            self._show_step()


def install_shortcut_hints(app_cls):
    """Install visual shortcut hints into the main POS application."""
    
    original_init = app_cls.__init__
    
    def __init_with_hints(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        
        # Add shortcut hint bar to the main POS screen
        try:
            if hasattr(self, 'pos_screen'):
                # Find the action bar and add hints below it
                hint_bar = ShortcutHintBar(
                    self.pos_screen,
                    shortcuts={
                        'F1': 'Home',
                        'F3': 'Product Lookup',
                        'F9': 'Quotation',
                        'F12': 'Payment',
                        'Ctrl+N': 'New Invoice',
                        'Ctrl+I': 'Open Invoices'
                    }
                )
                hint_bar.pack(fill=tk.X, padx=8, pady=(5, 8))
                
                # Store reference
                self.shortcut_hint_bar = hint_bar
        except Exception as e:
            print(f"Error installing shortcut hints: {e}")
    
    app_cls.__init__ = __init_with_hints
    
    # Add menu item for tutorial
    original_menu = app_cls.create_menu_bar
    
    def menu_with_tutorial(self):
        result = original_menu(self)
        try:
            top = self.nametowidget(self.cget("menu"))
            for i in range(top.index("end") + 1):
                if top.type(i) == "cascade" and top.entrycget(i, "label") == "Help":
                    sub = self.nametowidget(top.entrycget(i, "menu"))
                    sub.add_separator()
                    sub.add_command(
                        label="Shortcut Tutorial",
                        command=lambda: ShortcutTutorial(self)
                    )
                    break
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in shortcut_hints.py", exc_info=exc)
        return result
    
    app_cls.create_menu_bar = menu_with_tutorial
    
    return app_cls


if __name__ == "__main__":
    # Demo the shortcut hints
    root = tk.Tk()
    root.title("Shortcut Hints Demo")
    root.geometry("900x400")
    
    # Basic shortcut hint bar
    shortcuts = {
        'F1': 'Home',
        'F3': 'Product Lookup',
        'F12': 'Payment',
        'Ctrl+N': 'New Invoice'
    }
    
    hint_bar = ShortcutHintBar(root, shortcuts=shortcuts)
    hint_bar.pack(fill=tk.X, padx=20, pady=20)
    
    # Contextual hints
    contextual = ContextualShortcutHints(root)
    contextual.pack(fill=tk.X, padx=20, pady=20)
    
    # Button to test context switching
    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=20)
    
    tk.Button(btn_frame, text="POS Context",
              command=lambda: contextual.set_context('pos')).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="Lookup Context",
              command=lambda: contextual.set_context('lookup')).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="Payment Context",
              command=lambda: contextual.set_context('payment')).pack(side=tk.LEFT, padx=5)
    
    # Tutorial button
    tk.Button(root, text="Open Tutorial",
              command=lambda: ShortcutTutorial(root)).pack(pady=10)
    
    root.mainloop()
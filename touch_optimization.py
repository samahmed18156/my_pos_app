"""Touch optimization module for BKPOS.

Provides enhanced UI components and utilities for better touch experience:
- Larger touch targets (minimum 44x44 pixels)
- Touch-friendly button styles with visual feedback
- On-screen numeric keypad for faster data entry
- Enhanced spacing and sizing for touch interactions
- Visual feedback for touch states
"""
from core.logger import logger as _bkpos_logger

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    print("Warning: tkinter not available, touch optimization will not work")


class TouchButton(tk.Button):
    """Touch-optimized button with larger touch targets and visual feedback."""
    
    def __init__(self, parent, text="", command=None, **kwargs):
        # Set default touch-friendly properties
        default_kwargs = {
            'font': ('Arial', 11, 'bold'),
            'padx': 20,
            'pady': 12,
            'cursor': 'hand2',
            'relief': tk.FLAT,
            'bd': 0,
        }
        
        # Merge with user-provided kwargs
        for key, value in default_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(parent, text=text, command=command, **kwargs)
        
        # Store original colors for press effect
        self.original_bg = self.cget('bg')
        self.original_fg = self.cget('fg')
        self.pressed_bg = self._darker_color(self.original_bg)
        
        # Bind touch events
        self.bind('<ButtonPress-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)
        
    def _darker_color(self, hex_color, factor=0.8):
        """Create a darker version of a color for press effect."""
        try:
            # Remove # if present
            hex_color = hex_color.lstrip('#')
            # Convert to RGB
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            # Darken
            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)
            # Convert back to hex
            return f'#{r:02x}{g:02x}{b:02x}'
        except Exception:
            return hex_color
    
    def _on_press(self, event):
        """Visual feedback when button is pressed."""
        try:
            self.config(bg=self.pressed_bg)
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in touch_optimization.py", exc_info=exc)
    
    def _on_release(self, event):
        """Restore original appearance when button is released."""
        try:
            self.config(bg=self.original_bg)
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in touch_optimization.py", exc_info=exc)


class TouchKeypad(tk.Frame):
    """On-screen numeric keypad for touch-friendly data entry."""
    
    def __init__(self, parent, target_entry=None, on_enter=None, on_clear=None, **kwargs):
        default_kwargs = {
            'bg': '#f0f4f8',
            'padx': 10,
            'pady': 10
        }
        for key, value in default_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(parent, **kwargs)
        
        self.target_entry = target_entry
        self.on_enter = on_enter
        self.on_clear = on_clear
        
        self._build_keypad()
    
    def _build_keypad(self):
        """Build the numeric keypad layout."""
        # Button styles
        btn_style = {
            'font': ('Arial', 16, 'bold'),
            'padx': 15,
            'pady': 15,
            'cursor': 'hand2',
            'relief': tk.FLAT,
            'bd': 0
        }
        
        # Number buttons (7-9, 4-6, 1-3, 0)
        buttons = [
            ('7', 0, 0), ('8', 0, 1), ('9', 0, 2),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2),
            ('0', 3, 1)  # 0 is centered on bottom row
        ]
        
        for text, row, col in buttons:
            btn = TouchButton(
                self, 
                text=text,
                command=lambda t=text: self._insert_number(t),
                bg='white',
                fg='#2d3748',
                **btn_style
            )
            btn.grid(row=row, column=col, sticky='nsew', padx=3, pady=3)
        
        # Special buttons
        # Clear button
        clear_btn = TouchButton(
            self,
            text='C',
            command=self._clear,
            bg='#e53e3e',
            fg='white',
            **btn_style
        )
        clear_btn.grid(row=3, column=0, sticky='nsew', padx=3, pady=3)
        
        # Decimal point
        decimal_btn = TouchButton(
            self,
            text='.',
            command=lambda: self._insert_number('.'),
            bg='white',
            fg='#2d3748',
            **btn_style
        )
        decimal_btn.grid(row=3, column=2, sticky='nsew', padx=3, pady=3)
        
        # Enter button (spans two columns)
        enter_btn = TouchButton(
            self,
            text='⏎',
            command=self._handle_enter,
            bg='#38a169',
            fg='white',
            **btn_style
        )
        enter_btn.grid(row=4, column=0, columnspan=3, sticky='nsew', padx=3, pady=3)
        
        # Configure grid weights
        for i in range(3):
            self.grid_columnconfigure(i, weight=1)
        for i in range(5):
            self.grid_rowconfigure(i, weight=1)
    
    def _insert_number(self, text):
        """Insert number into target entry field."""
        if self.target_entry:
            try:
                current_text = self.target_entry.get()
                # Insert at cursor position or append
                cursor_pos = self.target_entry.index(tk.INSERT)
                new_text = current_text[:cursor_pos] + text + current_text[cursor_pos:]
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, new_text)
                # Move cursor after inserted text
                self.target_entry.icursor(cursor_pos + len(text))
            except Exception:
                # Fallback: just append
                self.target_entry.insert(tk.END, text)
    
    def _clear(self):
        """Clear the target entry field."""
        if self.target_entry:
            self.target_entry.delete(0, tk.END)
        if self.on_clear:
            self.on_clear()
    
    def _handle_enter(self):
        """Handle enter key press."""
        if self.on_enter:
            self.on_enter()


class TouchEntry(tk.Entry):
    """Touch-optimized entry field with larger touch target and optional keypad."""
    
    def __init__(self, parent, show_keypad_button=True, keypad_callback=None, **kwargs):
        # Set default touch-friendly properties
        default_kwargs = {
            'font': ('Arial', 14),
            'bd': 1,
            'relief': tk.SOLID,
            'justify': 'center'
        }
        
        for key, value in default_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(parent, **kwargs)
        
        self.show_keypad_button = show_keypad_button
        self.keypad_callback = keypad_callback
        self.keypad_window = None
        
        if show_keypad_button:
            self._add_keypad_button()
    
    def _add_keypad_button(self):
        """Add a keypad button next to the entry field."""
        # This would typically be used in a frame with the entry
        # The parent should handle the layout
        pass
    
    def show_keypad(self, parent=None):
        """Show on-screen keypad for this entry."""
        if self.keypad_window and tk.Toplevel.winfo_exists(self.keypad_window):
            self.keypad_window.destroy()
        
        if parent is None:
            parent = self.master
        
        self.keypad_window = tk.Toplevel(parent)
        self.keypad_window.title("Numeric Keypad")
        self.keypad_window.geometry("300x400")
        self.keypad_window.transient(parent)
        self.keypad_window.grab_set()
        
        keypad = TouchKeypad(
            self.keypad_window,
            target_entry=self,
            on_enter=lambda: self.keypad_window.destroy()
        )
        keypad.pack(fill=tk.BOTH, expand=True)
        
        # Position near the entry field
        try:
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height()
            self.keypad_window.geometry(f"+{x}+{y}")
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in touch_optimization.py", exc_info=exc)


class TouchCard(tk.Frame):
    """Touch-friendly card component for grouping related content."""
    
    def __init__(self, parent, title="", content_widget=None, **kwargs):
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
        
        if title:
            title_label = tk.Label(
                self,
                text=title,
                font=('Arial', 11, 'bold'),
                bg='white',
                fg='#2d3748'
            )
            title_label.pack(anchor='w', pady=(0, 10))
        
        if content_widget:
            content_widget.pack(fill=tk.BOTH, expand=True)


class TouchListItem(tk.Frame):
    """Touch-friendly list item with larger touch targets."""
    
    def __init__(self, parent, text="", subtext="", on_click=None, **kwargs):
        default_kwargs = {
            'bg': '#f7fafc',
            'bd': 1,
            'relief': tk.FLAT,
            'padx': 15,
            'pady': 12,
            'cursor': 'hand2'
        }
        
        for key, value in default_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(parent, **kwargs)
        
        self.on_click = on_click
        self.original_bg = self.cget('bg')
        
        # Content
        content_frame = tk.Frame(self, bg=self.cget('bg'))
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        if text:
            tk.Label(
                content_frame,
                text=text,
                font=('Arial', 11, 'bold'),
                bg=self.cget('bg'),
                fg='#1a202c'
            ).pack(anchor='w')
        
        if subtext:
            tk.Label(
                content_frame,
                text=subtext,
                font=('Arial', 9),
                bg=self.cget('bg'),
                fg='#718096'
            ).pack(anchor='w', pady=(2, 0))
        
        # Touch events
        if on_click:
            self.bind('<Button-1>', self._handle_click)
            content_frame.bind('<Button-1>', self._handle_click)
            
            # Add hover effect
            self.bind('<Enter>', self._on_enter)
            self.bind('<Leave>', self._on_leave)
    
    def _handle_click(self, event):
        """Handle click event."""
        if self.on_click:
            self.on_click()
    
    def _on_enter(self, event):
        """Hover effect."""
        try:
            self.config(bg='#edf2f7')
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in touch_optimization.py", exc_info=exc)
    
    def _on_leave(self, event):
        """Remove hover effect."""
        try:
            self.config(bg=self.original_bg)
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in touch_optimization.py", exc_info=exc)


def create_touch_action_bar(parent, actions):
    """
    Create a touch-friendly action bar with large buttons.
    
    Args:
        parent: Parent widget
        actions: List of tuples (text, command, color) where color is optional
    """
    action_frame = tk.Frame(parent, bg='#f0f4f8', padx=10, pady=10)
    action_frame.pack(fill=tk.X)
    
    for i, action in enumerate(actions):
        if len(action) == 2:
            text, command = action
            color = '#2c5282'  # Default blue
        else:
            text, command, color = action
        
        btn = TouchButton(
            action_frame,
            text=text,
            command=command,
            bg=color,
            fg='white'
        )
        btn.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
    
    return action_frame


def create_shortcut_hint(parent, shortcuts):
    """
    Create a touch-friendly shortcut hint display.
    
    Args:
        parent: Parent widget
        shortcuts: Dictionary of shortcut -> description
    """
    hint_frame = tk.Frame(parent, bg='#edf2f7', padx=12, pady=8)
    hint_frame.pack(fill=tk.X)
    
    tk.Label(
        hint_frame,
        text="KEYBOARD SHORTCUTS",
        font=('Arial', 9, 'bold'),
        bg='#edf2f7',
        fg='#4a5568'
    ).pack(anchor='w', pady=(0, 5))
    
    # Create shortcut chips
    shortcuts_frame = tk.Frame(hint_frame, bg='#edf2f7')
    shortcuts_frame.pack(fill=tk.X)
    
    for shortcut, description in shortcuts.items():
        chip = tk.Frame(
            shortcuts_frame,
            bg='white',
            bd=1,
            relief=tk.SOLID,
            padx=8,
            pady=4
        )
        chip.pack(side=tk.LEFT, padx=3, pady=2)
        
        tk.Label(
            chip,
            text=shortcut,
            font=('Arial', 9, 'bold'),
            bg='white',
            fg='#2c5282'
        ).pack(side=tk.LEFT)
        
        tk.Label(
            chip,
            text=f" {description}",
            font=('Arial', 9),
            bg='white',
            fg='#4a5568'
        ).pack(side=tk.LEFT)
    
    return hint_frame


if __name__ == "__main__":
    # Demo of touch components
    root = tk.Tk()
    root.title("Touch Optimization Demo")
    root.geometry("800x600")
    
    # Demo TouchButton
    demo_frame = tk.Frame(root, padx=20, pady=20)
    demo_frame.pack(fill=tk.BOTH, expand=True)
    
    tk.Label(demo_frame, text="Touch Components Demo", 
             font=('Arial', 16, 'bold')).pack(pady=(0, 20))
    
    # Touch buttons
    btn_frame = tk.Frame(demo_frame)
    btn_frame.pack(pady=10)
    
    TouchButton(btn_frame, text="Touch Button 1", 
                command=lambda: print("Button 1 clicked")).pack(side=tk.LEFT, padx=5)
    TouchButton(btn_frame, text="Touch Button 2", bg="#38a169",
                command=lambda: print("Button 2 clicked")).pack(side=tk.LEFT, padx=5)
    
    # Touch entry with keypad
    entry_frame = tk.Frame(demo_frame)
    entry_frame.pack(pady=20)
    
    tk.Label(entry_frame, text="Touch Entry:", font=('Arial', 10)).pack(side=tk.LEFT)
    touch_entry = TouchEntry(entry_frame, width=20)
    touch_entry.pack(side=tk.LEFT, padx=5)
    
    keypad_btn = tk.Button(entry_frame, text="🔢", 
                          command=lambda: touch_entry.show_keypad(),
                          font=('Arial', 12))
    keypad_btn.pack(side=tk.LEFT)
    
    # Touch card
    card = TouchCard(demo_frame, title="Touch Card Demo")
    card.pack(fill=tk.X, pady=20)
    
    tk.Label(card, text="This is a touch-friendly card component", 
             bg='white').pack()
    
    # Action bar
    actions = [
        ("Save", lambda: print("Save clicked"), "#38a169"),
        ("Cancel", lambda: print("Cancel clicked"), "#e53e3e"),
        ("Help", lambda: print("Help clicked"), "#3182ce")
    ]
    create_touch_action_bar(demo_frame, actions)
    
    # Shortcut hints
    shortcuts = {
        "F1": "Help",
        "F3": "Lookup", 
        "F12": "Payment",
        "Ctrl+N": "New"
    }
    create_shortcut_hint(demo_frame, shortcuts)
    
    root.mainloop()
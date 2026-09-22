"""Enhanced UI feedback system for BKPOS.

Provides better user experience through:
- Loading indicators for long operations
- Better error messages with helpful information
- Success notifications
- Progress indicators
- Visual feedback for user actions
"""
from core.logger import logger as _bkpos_logger

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time


class LoadingIndicator(tk.Frame):
    """Professional loading indicator for long-running operations."""
    
    def __init__(self, parent, message="Loading...", **kwargs):
        default_kwargs = {
            'bg': 'white',
            'bd': 2,
            'relief': tk.SOLID,
            'padx': 30,
            'pady': 20
        }
        
        for key, value in default_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(parent, **kwargs)
        
        self.message = message
        self.is_loading = False
        self.progress = 0
        self._build_ui()
    
    def _build_ui(self):
        """Build the loading indicator UI."""
        # Message
        self.message_label = tk.Label(
            self,
            text=self.message,
            font=('Arial', 12),
            bg='white',
            fg='#4a5568'
        )
        self.message_label.pack(pady=(0, 15))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(
            self,
            mode='indeterminate',
            length=300
        )
        self.progress_bar.pack(pady=(0, 10))
        
        # Status text
        self.status_label = tk.Label(
            self,
            text="Please wait...",
            font=('Arial', 10),
            bg='white',
            fg='#718096'
        )
        self.status_label.pack()
    
    def start(self, message=None):
        """Start the loading animation."""
        if message:
            self.message = message
            self.message_label.config(text=message)
        
        self.is_loading = True
        self.progress_bar.start(10)
        self.status_label.config(text="Processing...")
    
    def stop(self, message="Complete!"):
        """Stop the loading animation."""
        self.is_loading = False
        self.progress_bar.stop()
        self.status_label.config(text=message)
    
    def update_progress(self, value, maximum=100):
        """Update progress for determinate mode."""
        self.progress_bar.config(mode='determinate', maximum=maximum, value=value)
        percentage = (value / maximum) * 100
        self.status_label.config(text=f"Progress: {percentage:.0f}%")
    
    def set_message(self, message):
        """Update the message text."""
        self.message = message
        self.message_label.config(text=message)


class LoadingOverlay(tk.Toplevel):
    """Full-screen loading overlay for blocking operations."""
    
    def __init__(self, parent, message="Processing...", **kwargs):
        super().__init__(parent)
        
        self.title("Processing")
        self.geometry("400x200")
        self.configure(bg="#f7fafc")
        self.transient(parent)
        self.grab_set()
        self.overrideredirect(True)  # Remove window decorations
        
        # Center the window
        self.update_idletasks()
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() // 2) - 200
            y = parent.winfo_rooty() + (parent.winfo_height() // 2) - 100
            self.geometry(f"+{x}+{y}")
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in ui_feedback.py", exc_info=exc)
        
        self.indicator = LoadingIndicator(self, message)
        self.indicator.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        self.indicator.start()
    
    def close(self):
        """Close the overlay."""
        self.indicator.stop()
        self.destroy()


class BetterMessageDialog(tk.Toplevel):
    """Enhanced message dialog with better styling and user experience."""
    
    def __init__(self, parent, title, message, message_type="info", **kwargs):
        super().__init__(parent)
        
        self.title(title)
        self.geometry("500x300")
        self.configure(bg="#f7fafc")
        self.transient(parent)
        self.grab_set()
        
        # Style based on message type
        styles = {
            'info': {'bg': '#bee3f8', 'fg': '#2b6cb0', 'icon': 'ℹ️'},
            'success': {'bg': '#c6f6d5', 'fg': '#22543d', 'icon': '✅'},
            'warning': {'bg': '#fefcbf', 'fg': '#744210', 'icon': '⚠️'},
            'error': {'bg': '#fed7d7', 'fg': '#c53030', 'icon': '❌'}
        }
        
        style = styles.get(message_type, styles['info'])
        
        self._build_ui(title, message, style)
    
    def _build_ui(self, title, message, style):
        """Build the enhanced message dialog UI."""
        # Header with icon
        header = tk.Frame(self, bg=style['bg'], height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(
            header,
            text=style['icon'],
            font=('Arial', 32),
            bg=style['bg'],
            fg=style['fg']
        ).pack(side=tk.LEFT, padx=20, pady=15)
        
        tk.Label(
            header,
            text=title,
            font=('Arial', 16, 'bold'),
            bg=style['bg'],
            fg=style['fg']
        ).pack(side=tk.LEFT, padx=10, pady=20)
        
        # Message content
        content = tk.Frame(self, bg="white", padx=25, pady=20)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        message_label = tk.Label(
            content,
            text=message,
            font=('Arial', 11),
            bg="white",
            fg="#2d3748",
            wraplength=450,
            justify="left"
        )
        message_label.pack(anchor='w', fill=tk.BOTH, expand=True)
        
        # Action buttons
        button_frame = tk.Frame(self, bg="#f7fafc")
        button_frame.pack(fill=tk.X, padx=20, pady=20)
        
        ok_button = tk.Button(
            button_frame,
            text="OK",
            command=self.destroy,
            font=('Arial', 11, 'bold'),
            bg="#2c5282",
            fg="white",
            relief=tk.FLAT,
            padx=25,
            pady=10,
            cursor='hand2'
        )
        ok_button.pack(side=tk.RIGHT)
    
    def show(self):
        """Show the dialog and wait for response."""
        self.wait_window()
        return True


class ToastNotification(tk.Toplevel):
    """Temporary toast notification for non-intrusive alerts."""
    
    def __init__(self, parent, message, duration=3000, message_type="info"):
        super().__init__(parent)
        
        self.duration = duration
        self.configure(bg="#f7fafc")
        self.overrideredirect(True)  # Remove window decorations
        
        # Style based on message type
        styles = {
            'info': {'bg': '#bee3f8', 'fg': '#2b6cb0'},
            'success': {'bg': '#c6f6d5', 'fg': '#22543d'},
            'warning': {'bg': '#fefcbf', 'fg': '#744210'},
            'error': {'bg': '#fed7d7', 'fg': '#c53030'}
        }
        
        style = styles.get(message_type, styles['info'])
        
        # Build toast UI
        self._build_ui(message, style)
        
        # Position in corner of parent
        self._position_toast(parent)
        
        # Auto-close after duration
        self.after(duration, self.close)
    
    def _build_ui(self, message, style):
        """Build the toast notification UI."""
        content = tk.Frame(self, bg=style['bg'], padx=20, pady=15)
        content.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(
            content,
            text=message,
            font=('Arial', 10),
            bg=style['bg'],
            fg=style['fg']
        ).pack()
    
    def _position_toast(self, parent):
        """Position the toast in the corner of the parent window."""
        self.update_idletasks()
        try:
            x = parent.winfo_rootx() + parent.winfo_width() - self.winfo_width() - 20
            y = parent.winfo_rooty() + 20
            self.geometry(f"+{x}+{y}")
        except Exception:
            # Fallback to screen positioning
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = sw - self.winfo_width() - 20
            y = 20
            self.geometry(f"+{x}+{y}")
    
    def close(self):
        """Close the toast with fade effect."""
        self.destroy()


class ProgressBar(tk.Frame):
    """Enhanced progress bar with percentage and status."""
    
    def __init__(self, parent, **kwargs):
        default_kwargs = {
            'bg': 'white',
            'padx': 10,
            'pady': 10
        }
        
        for key, value in default_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(parent, **kwargs)
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the progress bar UI."""
        # Progress bar
        self.progress_bar = ttk.Progressbar(
            self,
            mode='determinate',
            length=400
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        # Status info
        status_frame = tk.Frame(self, bg=self.cget('bg'))
        status_frame.pack(fill=tk.X)
        
        self.percentage_label = tk.Label(
            status_frame,
            text="0%",
            font=('Arial', 9, 'bold'),
            bg=self.cget('bg'),
            fg='#4a5568'
        )
        self.percentage_label.pack(side=tk.LEFT)
        
        self.status_label = tk.Label(
            status_frame,
            text="Ready",
            font=('Arial', 9),
            bg=self.cget('bg'),
            fg='#718096'
        )
        self.status_label.pack(side=tk.RIGHT)
    
    def update(self, value, maximum=100, status=None):
        """Update progress bar."""
        self.progress_bar.config(maximum=maximum, value=value)
        percentage = (value / maximum) * 100
        self.percentage_label.config(text=f"{percentage:.0f}%")
        
        if status:
            self.status_label.config(text=status)
    
    def reset(self):
        """Reset progress bar to initial state."""
        self.progress_bar.config(value=0)
        self.percentage_label.config(text="0%")
        self.status_label.config(text="Ready")


def show_loading(parent, message="Processing..."):
    """Show a loading overlay and return the overlay object."""
    overlay = LoadingOverlay(parent, message)
    return overlay


def show_message(parent, title, message, message_type="info"):
    """Show an enhanced message dialog."""
    dialog = BetterMessageDialog(parent, title, message, message_type)
    dialog.show()


def show_toast(parent, message, duration=3000, message_type="info"):
    """Show a temporary toast notification."""
    toast = ToastNotification(parent, message, duration, message_type)


def with_loading(parent, message="Processing..."):
    """Decorator to show loading indicator during function execution."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            overlay = show_loading(parent, message)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                overlay.close()
        return wrapper
    return decorator


def handle_errors(parent, error_message="An error occurred"):
    """Decorator to handle errors with user-friendly messages."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                show_message(
                    parent,
                    "Error",
                    f"{error_message}\n\nDetails: {str(e)}",
                    "error"
                )
                return None
        return wrapper
    return decorator


class StatusIndicator(tk.Frame):
    """Small status indicator for showing operation status."""
    
    def __init__(self, parent, **kwargs):
        default_kwargs = {
            'bg': 'white',
            'width': 20,
            'height': 20
        }
        
        for key, value in default_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(parent, **kwargs)
        
        self._build_ui()
        self.set_status('ready')
    
    def _build_ui(self):
        """Build the status indicator UI."""
        self.canvas = tk.Canvas(
            self,
            width=20,
            height=20,
            bg=self.cget('bg'),
            highlightthickness=0
        )
        self.canvas.pack()
    
    def set_status(self, status):
        """Set the status indicator color."""
        colors = {
            'ready': '#a0aec0',
            'loading': '#4299e1',
            'success': '#48bb78',
            'error': '#f56565',
            'warning': '#ed8936'
        }
        
        color = colors.get(status, colors['ready'])
        
        self.canvas.delete("all")
        self.canvas.create_oval(
            2, 2, 18, 18,
            fill=color,
            outline=color
        )
    
    def animate_loading(self):
        """Animate the loading indicator."""
        if not hasattr(self, '_loading_animation'):
            self._loading_animation = True
            self._animate_step()
    
    def _animate_step(self):
        """Single step of loading animation."""
        if getattr(self, '_loading_animation', False):
            # Simple pulsing animation
            colors = ['#4299e1', '#63b3ed', '#90cdf4', '#63b3ed']
            if not hasattr(self, '_color_index'):
                self._color_index = 0
            
            color = colors[self._color_index]
            self.canvas.delete("all")
            self.canvas.create_oval(
                2, 2, 18, 18,
                fill=color,
                outline=color
            )
            
            self._color_index = (self._color_index + 1) % len(colors)
            self.after(200, self._animate_step)
    
    def stop_loading(self):
        """Stop the loading animation."""
        self._loading_animation = False


if __name__ == "__main__":
    # Demo the UI feedback components
    root = tk.Tk()
    root.title("UI Feedback Demo")
    root.geometry("600x500")
    
    # Test buttons
    button_frame = tk.Frame(root, padx=20, pady=20)
    button_frame.pack(fill=tk.X)
    
    tk.Button(button_frame, text="Show Loading Overlay",
              command=lambda: show_loading(root, "Demo loading...")).pack(side=tk.LEFT, padx=5)
    
    tk.Button(button_frame, text="Show Info Message",
              command=lambda: show_message(root, "Information", "This is an info message", "info")).pack(side=tk.LEFT, padx=5)
    
    tk.Button(button_frame, text="Show Success Message",
              command=lambda: show_message(root, "Success", "Operation completed successfully!", "success")).pack(side=tk.LEFT, padx=5)
    
    tk.Button(button_frame, text="Show Error Message",
              command=lambda: show_message(root, "Error", "An error occurred during operation.", "error")).pack(side=tk.LEFT, padx=5)
    
    tk.Button(button_frame, text="Show Toast",
              command=lambda: show_toast(root, "This is a toast notification")).pack(side=tk.LEFT, padx=5)
    
    # Progress bar demo
    progress_frame = tk.Frame(root, padx=20, pady=20)
    progress_frame.pack(fill=tk.X)
    
    progress = ProgressBar(progress_frame)
    progress.pack(fill=tk.X)
    
    def animate_progress():
        for i in range(101):
            progress.update(i, status=f"Processing item {i}/100")
            root.update()
            time.sleep(0.05)
    
    tk.Button(progress_frame, text="Animate Progress",
              command=animate_progress).pack(pady=10)
    
    # Status indicator demo
    status_frame = tk.Frame(root, padx=20, pady=20)
    status_frame.pack(fill=tk.X)
    
    status = StatusIndicator(status_frame)
    status.pack()
    
    def cycle_status():
        statuses = ['ready', 'loading', 'success', 'error', 'warning']
        if not hasattr(cycle_status, 'index'):
            cycle_status.index = 0
        
        status.set_status(statuses[cycle_status.index])
        if statuses[cycle_status.index] == 'loading':
            status.animate_loading()
        else:
            status._loading_animation = False
        
        cycle_status.index = (cycle_status.index + 1) % len(statuses)
    
    tk.Button(status_frame, text="Cycle Status",
              command=cycle_status).pack(pady=10)
    
    root.mainloop()
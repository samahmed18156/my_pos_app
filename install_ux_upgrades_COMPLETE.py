"""
Simple UX Upgrade Installer for BKPOS

This file makes it super easy to add all the new UX features to your POS system.
Just import this at the top of your app.py file!

USAGE:
1. Add this line at the TOP of your app.py file (after the imports):
   from install_ux_upgrades import install_all_ux_features

2. Then, at the END of your FamilySupermarketPOS class __init__ method, add:
   install_all_ux_features(self)

That's it! All the new UX features will be automatically added.
"""
from core.logger import logger as _bkpos_logger

import tkinter as tk

def install_all_ux_features(app_instance):
    """
    Install all UX upgrade features into the POS application.
    
    Args:
        app_instance: The main POS application instance (usually 'self' in the class)
    """
    print("🚀 Installing UX features...")
    
    try:
        # Import the UX modules
        from touch_optimization import TouchButton, TouchKeypad
        print("✅ Touch optimization module loaded")
    except ImportError as e:
        print(f"⚠️ Could not import touch_optimization: {e}")
    
    try:
        from shortcut_hints import ShortcutHintBar
        print("✅ Shortcut hints module loaded")
    except ImportError as e:
        print(f"⚠️ Could not import shortcut_hints: {e}")
        ShortcutHintBar = None
    
    try:
        from workflow_optimization import QuickActionsBar
        print("✅ Workflow optimization module loaded")
    except ImportError as e:
        print(f"⚠️ Could not import workflow_optimization: {e}")
        QuickActionsBar = None
    
    try:
        from ui_feedback import show_loading, show_message, show_toast
        print("✅ UI feedback module loaded")
    except ImportError as e:
        print(f"⚠️ Could not import ui_feedback: {e}")
        show_loading = show_message = show_toast = None
    
    # Install shortcut hints
    try:
        if ShortcutHintBar and hasattr(app_instance, 'pos_screen'):
            hint_bar = ShortcutHintBar(
                app_instance.pos_screen,
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
            app_instance.shortcut_hint_bar = hint_bar
            print("✅ Shortcut hints installed!")
    except Exception as e:
        print(f"⚠️ Could not install shortcut hints: {e}")
    
    # Install workflow optimization
    try:
        if QuickActionsBar and hasattr(app_instance, 'pos_screen'):
            quick_actions = QuickActionsBar(app_instance.pos_screen, pos_instance=app_instance)
            quick_actions.pack(fill=tk.X, padx=8, pady=(5, 8))
            app_instance.quick_actions_bar = quick_actions
            print("✅ Quick actions bar installed!")
    except Exception as e:
        print(f"⚠️ Could not install quick actions: {e}")
    
    # Add helper methods to the app instance
    try:
        if show_loading:
            app_instance.show_loading = lambda msg="Loading...": show_loading(app_instance, msg)
        if show_message:
            app_instance.show_message = lambda title, msg, type="info": show_message(app_instance, title, msg, type)
        if show_toast:
            app_instance.show_toast = lambda msg, duration=3000: show_toast(app_instance, msg, duration)
        print("✅ Helper methods added!")
    except Exception as e:
        print(f"⚠️ Could not add helper methods: {e}")
    
    print("🎉 UX features installation complete!")


# Alternative: Manual installation functions if you want more control

def install_shortcut_hints_only(app_instance):
    """Install only the shortcut hints feature."""
    try:
        from shortcut_hints import ShortcutHintBar
        
        if hasattr(app_instance, 'pos_screen'):
            hint_bar = ShortcutHintBar(
                app_instance.pos_screen,
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
            app_instance.shortcut_hint_bar = hint_bar
            print("✅ Shortcut hints installed!")
    except Exception as e:
        print(f"❌ Error installing shortcut hints: {e}")


def install_quick_actions_only(app_instance):
    """Install only the quick actions bar."""
    try:
        from workflow_optimization import QuickActionsBar
        
        if hasattr(app_instance, 'pos_screen'):
            quick_actions = QuickActionsBar(app_instance.pos_screen, pos_instance=app_instance)
            quick_actions.pack(fill=tk.X, padx=8, pady=(5, 8))
            app_instance.quick_actions_bar = quick_actions
            print("✅ Quick actions installed!")
    except Exception as e:
        print(f"❌ Error installing quick actions: {e}")


def install_touch_f3_lookup(app_instance):
    """Replace the F3 lookup with touch-optimized version."""
    try:
        # Store the original F3 method
        original_f3 = getattr(app_instance, 'open_f3_search', None)
        
        if original_f3:
            from touch_f3_lookup import TouchF3LookupWindow
            
            def touch_f3_search(self, event=None):
                """Open touch-optimized F3 product lookup."""
                initial_query = ""
                try:
                    if hasattr(self, 'code_entry'):
                        initial_query = self.code_entry.get().strip()
                except Exception as exc:
                    _bkpos_logger.warning("Suppressed exception in install_ux_upgrades_COMPLETE.py", exc_info=exc)
                
                lookup = TouchF3LookupWindow(
                    self,
                    initial_query=initial_query,
                    on_select_callback=self.add_product_by_barcode
                )
                self.f3_window = lookup
            
            # Replace the method
            app_instance.open_f3_search = touch_f3_search.__get__(app_instance, type(app_instance))
            print("✅ Touch F3 lookup installed!")
    except Exception as e:
        print(f"❌ Error installing touch F3 lookup: {e}")


if __name__ == "__main__":
    print("UX Upgrade Installer")
    print("=" * 40)
    print("This file helps install UX improvements to your POS system.")
    print("Import this file in your app.py and call install_all_ux_features(self)")
    print("in your FamilySupermarketPOS class __init__ method.")
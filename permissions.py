import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox


# ============================================================
# COLORS
# ============================================================

COLORS = {
    "bg": "#f0f4f8",
    "header": "#2b6cb0",
    "accent_green": "#38a169",
    "accent_red": "#e53e3e",
    "accent_blue": "#3182ce",
    "accent_purple": "#805ad5",
    "card_bg": "#ffffff",
    "text_primary": "#1a202c",
    "text_secondary": "#4a5568",
}


# ============================================================
# FONTS
# ============================================================

FONTS = {
    "title": ("Segoe UI", 14, "bold"),
    "heading": ("Segoe UI", 12, "bold"),
    "normal": ("Segoe UI", 11),
    "small": ("Segoe UI", 9),
}


# ============================================================
# DATABASE
# ============================================================

from core.config import DB_PATH
DB_NAME = DB_PATH


PERMISSION_COLUMNS = [
    "can_edit_price",
    "can_edit_qty",
    "can_delete_items",
    "can_view_reports",
    "can_access_stock",
    "can_access_debtors",
    "can_access_creditors",
    "can_access_utility",
    "can_void_sales",
    "can_issue_credit_notes",
    "can_manage_users",
    "can_manage_branches",
    "can_cashup",
    "can_manage_expenses",
]


def connect_database():
    """Open the POS database."""

    return sqlite3.connect(
        DB_NAME
    )


# ============================================================
# SETUP PERMISSION COLUMNS
# ============================================================

def setup_permission_columns():

    conn = connect_database()
    cursor = conn.cursor()

    try:

        # Check users table

        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name='users'
        """)

        users_table = cursor.fetchone()

        if not users_table:

            raise Exception(
                "The 'users' table does not exist in pos_store.db."
            )

        # Existing columns

        cursor.execute(
            "PRAGMA table_info(users)"
        )

        existing_columns = {
            row[1]
            for row in cursor.fetchall()
        }

        # Add missing columns

        for column in PERMISSION_COLUMNS:

            if column not in existing_columns:

                cursor.execute(
                    f"""
                    ALTER TABLE users
                    ADD COLUMN {column} INTEGER DEFAULT 0
                    """
                )

        conn.commit()

    finally:

        conn.close()


# ============================================================
# PERMISSION WINDOW
# ============================================================

class PermissionsWindow(tk.Toplevel):

    def __init__(
        self,
        parent,
        admin_user=None
    ):

        super().__init__(
            parent
        )

        self.parent = parent

        self.admin_user = admin_user

        self.title(
            "Cashier Permissions"
        )

        self.geometry(
            "700x550"
        )

        self.minsize(
            650,
            500
        )

        self.configure(
            bg=COLORS["bg"]
        )

        self.transient(
            parent
        )

        self.grab_set()

        self.users = []

        self.current_user = None

        # ====================================================
        # PREPARE DATABASE
        # ====================================================

        try:

            setup_permission_columns()

        except Exception as e:

            messagebox.showerror(
                "Database Error",
                f"Could not prepare permissions.\n\n{e}",
                parent=self
            )

            self.destroy()

            return

        # ====================================================
        # CENTER WINDOW
        # ====================================================

        self.update_idletasks()

        x = (
            self.winfo_screenwidth() // 2
            - 350
        )

        y = (
            self.winfo_screenheight() // 2
            - 275
        )

        self.geometry(
            f"700x550+{x}+{y}"
        )

        # ====================================================
        # CREATE INTERFACE
        # ====================================================

        self.create_widgets()

        self.load_users()

    # ========================================================
    # CREATE WIDGETS
    # ========================================================

    def create_widgets(self):

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        header = tk.Frame(
            self,
            bg=COLORS["header"],
            height=50
        )

        header.pack(
            fill=tk.X,
            side=tk.TOP
        )

        header.pack_propagate(
            False
        )

        tk.Label(
            header,
            text="🔑 Cashier Permissions",
            font=("Segoe UI", 14, "bold"),
            fg="white",
            bg=COLORS["header"]
        ).pack(
            pady=10
        )

        # ----------------------------------------------------
        # BODY
        # ----------------------------------------------------

        body = tk.Frame(
            self,
            bg=COLORS["bg"],
            padx=20,
            pady=15
        )

        body.pack(
            fill=tk.BOTH,
            expand=True
        )

        # ----------------------------------------------------
        # USER SELECTION
        # ----------------------------------------------------

        user_frame = tk.Frame(
            body,
            bg=COLORS["bg"]
        )

        user_frame.pack(
            fill=tk.X,
            pady=(0, 15)
        )

        tk.Label(
            user_frame,
            text="Select Cashier:",
            font=FONTS["heading"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"]
        ).pack(
            side=tk.LEFT,
            padx=(0, 10)
        )

        self.user_combo = ttk.Combobox(
            user_frame,
            font=FONTS["normal"],
            width=30,
            state="readonly"
        )

        self.user_combo.pack(
            side=tk.LEFT,
            padx=(0, 10)
        )

        self.user_combo.bind(
            "<<ComboboxSelected>>",
            self.on_user_selected
        )

        tk.Button(
            user_frame,
            text="🔄 Refresh",
            font=FONTS["small"],
            bg=COLORS["accent_blue"],
            fg="white",
            padx=12,
            pady=4,
            relief=tk.FLAT,
            command=self.load_users
        ).pack(
            side=tk.LEFT
        )

        # ----------------------------------------------------
        # PERMISSIONS FRAME
        # ----------------------------------------------------

        self.perms_frame = tk.LabelFrame(
            body,
            text="Permissions",
            font=FONTS["heading"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"],
            padx=15,
            pady=15
        )

        self.perms_frame.pack(
            fill=tk.BOTH,
            expand=True,
            pady=(0, 15)
        )

        # ----------------------------------------------------
        # PERMISSION LIST
        # ----------------------------------------------------

        permission_list = [

            (
                "can_edit_price",
                "💰 Edit Price"
            ),

            (
                "can_edit_qty",
                "📦 Edit Quantity"
            ),

            (
                "can_delete_items",
                "🗑️ Delete Items"
            ),

            (
                "can_view_reports",
                "📊 View Reports"
            ),

            (
                "can_access_stock",
                "📦 Access Stock"
            ),

            (
                "can_access_debtors",
                "👤 Access Debtors"
            ),

            (
                "can_access_creditors",
                "🏢 Access Creditors"
            ),

            (
                "can_access_utility",
                "⚙️ Access Utility"
            ),
        ]

        self.permissions = {}

        for i, (
            key,
            label
        ) in enumerate(permission_list):

            row = i // 2

            col = i % 2

            frame = tk.Frame(
                self.perms_frame,
                bg=COLORS["bg"]
            )

            frame.grid(
                row=row,
                column=col,
                sticky="w",
                padx=10,
                pady=8
            )

            var = tk.IntVar(
                value=0
            )

            cb = tk.Checkbutton(
                frame,
                text=label,
                variable=var,
                font=FONTS["normal"],
                bg=COLORS["bg"],
                fg=COLORS["text_secondary"],
                activebackground=COLORS["bg"],
                activeforeground=COLORS["text_primary"],
                selectcolor="white"
            )

            cb.pack(
                side=tk.LEFT
            )

            self.permissions[key] = {
                "var": var,
                "cb": cb
            }

        # ----------------------------------------------------
        # BUTTONS
        # ----------------------------------------------------

        button_frame = tk.Frame(
            body,
            bg=COLORS["bg"]
        )

        button_frame.pack(
            fill=tk.X
        )

        tk.Button(
            button_frame,
            text="💾 Save Permissions",
            font=FONTS["heading"],
            bg=COLORS["accent_green"],
            fg="white",
            padx=20,
            pady=8,
            relief=tk.FLAT,
            command=self.save_permissions
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Button(
            button_frame,
            text="❌ Close",
            font=FONTS["heading"],
            bg=COLORS["accent_red"],
            fg="white",
            padx=20,
            pady=8,
            relief=tk.FLAT,
            command=self.destroy
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.status_label = tk.Label(
            body,
            text="✅ Select a cashier to manage permissions",
            font=FONTS["small"],
            bg=COLORS["bg"],
            fg=COLORS["accent_green"]
        )

        self.status_label.pack(
            anchor="w",
            pady=(10, 0)
        )

    # ========================================================
    # LOAD USERS
    # ========================================================

    def load_users(self):

        try:

            conn = connect_database()

            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    id,
                    username,
                    full_name,
                    role
                FROM users
                WHERE LOWER(role) = 'cashier'
                ORDER BY username
            """)

            self.users = cursor.fetchall()

            conn.close()

            user_list = [
                f"{user[1]} - {user[2]}"
                for user in self.users
            ]

            self.user_combo["values"] = user_list

            if user_list:

                self.user_combo.current(
                    0
                )

                self.on_user_selected()

            else:

                self.current_user = None

                self.clear_permissions()

                self.status_label.config(
                    text="⚠️ No cashier users found.",
                    fg=COLORS["accent_red"]
                )

        except Exception as e:

            messagebox.showerror(
                "Database Error",
                f"Could not load cashiers.\n\n{e}",
                parent=self
            )

    # ========================================================
    # USER SELECTED
    # ========================================================

    def on_user_selected(
        self,
        event=None
    ):

        selection = self.user_combo.get()

        if not selection:

            return

        username = selection.split(
            " - ",
            1
        )[0]

        self.current_user = None

        for user in self.users:

            if user[1] == username:

                self.current_user = user

                break

        if not self.current_user:

            return

        try:

            conn = connect_database()

            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    can_edit_price,
                    can_edit_qty,
                    can_delete_items,
                    can_view_reports,
                    can_access_stock,
                    can_access_debtors,
                    can_access_creditors,
                    can_access_utility
                FROM users
                WHERE id = ?
            """, (
                self.current_user[0],
            ))

            perms = cursor.fetchone()

            conn.close()

            if perms:

                for i, key in enumerate(
                    PERMISSION_COLUMNS
                ):

                    value = perms[i]

                    if value is None:

                        value = 0

                    self.permissions[key]["var"].set(
                        int(value)
                    )

            self.status_label.config(
                text=(
                    f"✅ Editing permissions for: "
                    f"{self.current_user[2]}"
                ),
                fg=COLORS["accent_green"]
            )

        except Exception as e:

            messagebox.showerror(
                "Error",
                f"Could not load permissions.\n\n{e}",
                parent=self
            )

    # ========================================================
    # CLEAR PERMISSIONS
    # ========================================================

    def clear_permissions(self):

        for key in self.permissions:

            self.permissions[key]["var"].set(
                0
            )

    # ========================================================
    # SAVE PERMISSIONS
    # ========================================================

    def save_permissions(self):

        if not self.current_user:

            messagebox.showerror(
                "Error",
                "Please select a cashier first!",
                parent=self
            )

            return

        full_name = self.current_user[2]

        if not messagebox.askyesno(
            "Confirm",
            f"Save permissions for {full_name}?",
            parent=self
        ):

            return

        # ----------------------------------------------------
        # Get checkbox values
        # ----------------------------------------------------

        values = []

        for key in PERMISSION_COLUMNS:

            values.append(
                self.permissions[key]["var"].get()
            )

        try:

            conn = connect_database()

            cursor = conn.cursor()

            cursor.execute("""
                UPDATE users
                SET
                    can_edit_price = ?,
                    can_edit_qty = ?,
                    can_delete_items = ?,
                    can_view_reports = ?,
                    can_access_stock = ?,
                    can_access_debtors = ?,
                    can_access_creditors = ?,
                    can_access_utility = ?
                WHERE id = ?
            """, (

                values[0],
                values[1],
                values[2],
                values[3],
                values[4],
                values[5],
                values[6],
                values[7],

                self.current_user[0]
            ))

            conn.commit()

            conn.close()

            messagebox.showinfo(
                "Success",
                f"✅ Permissions saved for {full_name}!",
                parent=self
            )

            self.status_label.config(
                text=(
                    f"✅ Permissions saved for "
                    f"{full_name}"
                ),
                fg=COLORS["accent_green"]
            )

        except Exception as e:

            messagebox.showerror(
                "Error",
                f"Could not save permissions.\n\n{e}",
                parent=self
            )


# ============================================================
# END OF permissions.py
# ============================================================
from store_settings import get_store_name
import sqlite3
import tkinter as tk
from security import hash_password, verify_password
from tkinter import ttk, messagebox
from core.audit_log import record_event


# ============================================================
# COLORS
# ============================================================

BG_COLOR = "#eef2f7"
HEADER_COLOR = "#2c5282"
WHITE = "#ffffff"


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


def setup_permission_columns():
    """
    Make sure the users table has all permission columns.
    This allows the permissions system to work with an
    existing/older database.
    """

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        # Make sure users table exists
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name='users'
        """)

        if not cursor.fetchone():
            raise Exception(
                "The 'users' table does not exist in pos_store.db."
            )

        # Get existing columns
        cursor.execute("PRAGMA table_info(users)")

        existing_columns = {
            row[1] for row in cursor.fetchall()
        }

        # Add missing permission columns
        for column in PERMISSION_COLUMNS:

            if column not in existing_columns:

                cursor.execute(
                    f"""
                    ALTER TABLE users
                    ADD COLUMN {column} INTEGER DEFAULT 0
                    """
                )

        if "must_change_password" not in existing_columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0"
            )

        # Complete the legacy migration before authentication. Plaintext
        # passwords are never accepted by the login path.
        cursor.execute("SELECT id, password, password_hash FROM users")
        for uid, legacy_password, password_hash_value in cursor.fetchall():
            if (not password_hash_value) and legacy_password:
                cursor.execute(
                    "UPDATE users SET password_hash=?, password='' WHERE id=?",
                    (hash_password(str(legacy_password)), uid),
                )

        conn.commit()

    finally:
        conn.close()


# ============================================================
# CHECK LOGIN
# ============================================================

def _check_credentials(username, password):
    """
    Check username/password.

    Returns a dictionary containing:
        username
        full_name
        role
        permissions

    Returns None if login fails.
    """

    # Make sure permission columns exist
    setup_permission_columns()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                username,
                full_name,
                role,
                password_hash,
                password,
                can_edit_price,
                can_edit_qty,
                can_delete_items,
                can_view_reports,
                can_access_stock,
                can_access_debtors,
                can_access_creditors,
                can_access_utility,
                can_void_sales, can_issue_credit_notes, can_manage_users, can_manage_branches,
                can_cashup, can_manage_expenses, branch_id, must_change_password
            FROM users
            WHERE username = ?
        """, (username,))

        row = cursor.fetchone()

    finally:
        conn.close()

    if not row:
        audit_conn = sqlite3.connect(DB_NAME)
        try:
            record_event(
                audit_conn,
                "LOGIN_FAILED",
                "Login attempted for unknown username",
                username=str(username),
                reference_type="user",
                details={"reason": "unknown_username"},
            )
        finally:
            audit_conn.close()
        return None

    password_hash_value = row[3] or ""
    # Plaintext password authentication is intentionally disabled. Legacy
    # plaintext values are migrated by database initialization, but they are
    # never accepted as credentials here.
    valid = verify_password(password, password_hash_value)
    if not valid:
        audit_conn = sqlite3.connect(DB_NAME)
        try:
            record_event(
                audit_conn,
                "LOGIN_FAILED",
                "Invalid password",
                username=str(username),
                reference_type="user",
                details={"reason": "invalid_password"},
            )
        finally:
            audit_conn.close()
        return None

    audit_conn = sqlite3.connect(DB_NAME)
    try:
        record_event(
            audit_conn,
            "LOGIN_SUCCESS",
            "User logged in successfully",
            username=str(row[0]),
            reference_type="user",
            details={"role": row[2]},
        )
    finally:
        audit_conn.close()

    return {
        "username": row[0],
        "full_name": row[1],
        "role": row[2],
        "can_edit_price": bool(row[5]),
        "can_edit_qty": bool(row[6]),
        "can_delete_items": bool(row[7]),
        "can_view_reports": bool(row[8]),
        "can_access_stock": bool(row[9]),
        "can_access_debtors": bool(row[10]),
        "can_access_creditors": bool(row[11]),
        "can_access_utility": bool(row[12]),
        "can_void_sales": bool(row[13]),
        "can_issue_credit_notes": bool(row[14]),
        "can_manage_users": bool(row[15]),
        "can_manage_branches": bool(row[16]),
        "can_cashup": bool(row[17]),
        "can_manage_expenses": bool(row[18]),
        "branch_id": row[19],
        "must_change_password": bool(row[20]),
    }


# ============================================================
# LOGIN WINDOW
# ============================================================

def _change_password_after_login(username, parent=None):
    """Force a first-run/admin password rotation without changing permissions."""
    popup = tk.Toplevel(parent) if parent else tk.Tk()
    popup.title("BKPOS - Change Password")
    popup.geometry("420x260")
    popup.resizable(False, False)
    popup.transient(parent) if parent else None
    popup.grab_set()

    tk.Label(popup, text="Password change required", font=("Arial", 15, "bold")).pack(pady=(20, 6))
    tk.Label(popup, text="Set a new password before continuing.", font=("Arial", 10)).pack(pady=(0, 15))

    frame = tk.Frame(popup)
    frame.pack(fill=tk.X, padx=30)
    tk.Label(frame, text="New password:").pack(anchor="w")
    new_entry = tk.Entry(frame, show="•", width=38)
    new_entry.pack(fill=tk.X, pady=(2, 10))
    tk.Label(frame, text="Confirm password:").pack(anchor="w")
    confirm_entry = tk.Entry(frame, show="•", width=38)
    confirm_entry.pack(fill=tk.X, pady=(2, 10))
    error = tk.Label(popup, text="", fg="#e53e3e")
    error.pack()

    result = {"ok": False}
    def save():
        new_password = new_entry.get()
        confirm = confirm_entry.get()
        if len(new_password) < 10:
            error.config(text="Password must be at least 10 characters.")
            return
        if new_password != confirm:
            error.config(text="Passwords do not match.")
            return
        conn = sqlite3.connect(DB_NAME)
        try:
            conn.execute("UPDATE users SET password='', password_hash=?, must_change_password=0 WHERE username=?",
                         (hash_password(new_password), username))
            conn.commit()
            result["ok"] = True
        finally:
            conn.close()
        popup.destroy()

    tk.Button(popup, text="Save new password", command=save).pack(pady=8)
    new_entry.focus_set()
    popup.wait_window()
    return result["ok"]


def show_login_window():
    """
    Shows the login screen.

    Returns:

        {
            "username": "...",
            "full_name": "...",
            "role": "...",
            "can_edit_price": True/False,
            ...
        }

    on successful login.

    Returns None if the window is closed.
    """

    # Prepare database before opening login
    try:
        setup_permission_columns()

    except Exception as e:

        messagebox.showerror(
            "Database Error",
            f"Could not prepare the database.\n\n{e}"
        )

        return None

    root = tk.Tk()

    root.title("BKPOS - Login")
    root.geometry("380x420")
    root.resizable(False, False)
    root.configure(bg=BG_COLOR)

    # --------------------------------------------------------
    # Center window
    # --------------------------------------------------------

    root.update_idletasks()

    x = (
        root.winfo_screenwidth() // 2
        - 190
    )

    y = (
        root.winfo_screenheight() // 2
        - 210
    )

    root.geometry(
        f"380x420+{x}+{y}"
    )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    result = {
        "value": None
    }

    # ========================================================
    # HEADER
    # ========================================================

    header = tk.Frame(
        root,
        bg=HEADER_COLOR,
        height=70
    )

    header.pack(
        fill=tk.X
    )

    header.pack_propagate(False)

    tk.Label(
        header,
        text=get_store_name(),
        font=("Arial", 15, "bold"),
        fg="white",
        bg=HEADER_COLOR
    ).pack(
        pady=(15, 0)
    )

    tk.Label(
        header,
        text="Cashier Login",
        font=("Arial", 10),
        fg="#cbd5e0",
        bg=HEADER_COLOR
    ).pack()

    # ========================================================
    # BODY
    # ========================================================

    body = tk.Frame(
        root,
        bg=BG_COLOR,
        padx=30,
        pady=25
    )

    body.pack(
        fill=tk.BOTH,
        expand=True
    )

    # --------------------------------------------------------
    # Username
    # --------------------------------------------------------

    tk.Label(
        body,
        text="Username",
        font=("Arial", 10, "bold"),
        bg=BG_COLOR
    ).pack(
        anchor="w"
    )

    entry_user = tk.Entry(
        body,
        font=("Arial", 12),
        width=25
    )

    entry_user.pack(
        pady=(2, 15),
        fill=tk.X
    )

    entry_user.focus_set()

    # --------------------------------------------------------
    # Password
    # --------------------------------------------------------

    tk.Label(
        body,
        text="Password",
        font=("Arial", 10, "bold"),
        bg=BG_COLOR
    ).pack(
        anchor="w"
    )

    entry_pass = tk.Entry(
        body,
        font=("Arial", 12),
        width=25,
        show="*"
    )

    entry_pass.pack(
        pady=(2, 5),
        fill=tk.X
    )

    # --------------------------------------------------------
    # Show password
    # --------------------------------------------------------

    show_pw_var = tk.BooleanVar(
        value=False
    )

    def toggle_show_password():

        entry_pass.config(
            show=""
            if show_pw_var.get()
            else "*"
        )

    tk.Checkbutton(
        body,
        text="Show password",
        variable=show_pw_var,
        bg=BG_COLOR,
        font=("Arial", 8),
        command=toggle_show_password
    ).pack(
        anchor="w",
        pady=(0, 15)
    )

    # --------------------------------------------------------
    # Error message
    # --------------------------------------------------------

    lbl_error = tk.Label(
        body,
        text="",
        font=("Arial", 9),
        fg="#e53e3e",
        bg=BG_COLOR
    )

    lbl_error.pack(
        pady=(0, 10)
    )

    # ========================================================
    # LOGIN
    # ========================================================

    def attempt_login(event=None):

        username = entry_user.get().strip()
        password = entry_pass.get().strip()

        if not username or not password:

            lbl_error.config(
                text="Please enter both username and password."
            )

            return

        try:

            match = _check_credentials(
                username,
                password
            )

        except Exception as e:

            messagebox.showerror(
                "Login Error",
                f"Could not check login.\n\n{e}",
                parent=root
            )

            return

        if match:

            if match.get("must_change_password"):
                if not _change_password_after_login(match["username"], root):
                    return
                match["must_change_password"] = False

            result["value"] = match

            root.destroy()

        else:

            lbl_error.config(
                text="Incorrect username or password."
            )

            entry_pass.delete(
                0,
                tk.END
            )

            entry_pass.focus_set()

    # --------------------------------------------------------
    # Login button
    # --------------------------------------------------------

    tk.Button(
        body,
        text="Log In",
        font=("Arial", 12, "bold"),
        bg="#3182ce",
        fg="white",
        pady=6,
        command=attempt_login
    ).pack(
        fill=tk.X
    )

    # --------------------------------------------------------
    # Default login information
    # --------------------------------------------------------

    tk.Label(
        body,
        text="First-run admin credentials are stored in the local setup credential file.",
        font=("Arial", 8),
        fg="#718096",
        bg=BG_COLOR,
        justify="center"
    ).pack(pady=(20, 0))

    # --------------------------------------------------------
    # Enter key
    # --------------------------------------------------------

    entry_user.bind(
        "<Return>",
        lambda e: entry_pass.focus_set()
    )

    entry_pass.bind(
        "<Return>",
        attempt_login
    )

    root.mainloop()

    return result["value"]


# ============================================================
# MANAGE USERS WINDOW
# ============================================================

class ManageUsersWindow(tk.Toplevel):
    """
    Admin-only screen for managing users.
    """

    def __init__(self, parent):

        super().__init__(parent)

        self.title(
            "Manage Users"
        )

        self.geometry(
            "560x480"
        )

        self.configure(
            bg=BG_COLOR
        )

        self.transient(
            parent
        )

        self.grab_set()

        # Make sure permission columns exist
        try:
            setup_permission_columns()

        except Exception as e:

            messagebox.showerror(
                "Database Error",
                f"Could not prepare database.\n\n{e}",
                parent=self
            )

            self.destroy()

            return

        # ====================================================
        # HEADER
        # ====================================================

        tk.Label(
            self,
            text="Manage Users",
            font=("Arial", 14, "bold"),
            bg=HEADER_COLOR,
            fg="white",
            pady=10
        ).pack(
            fill=tk.X
        )

        # ====================================================
        # BODY
        # ====================================================

        body = tk.Frame(
            self,
            bg=BG_COLOR,
            padx=15,
            pady=15
        )

        body.pack(
            fill=tk.BOTH,
            expand=True
        )

        # ====================================================
        # EXISTING USERS
        # ====================================================

        tk.Label(
            body,
            text="Existing Users",
            font=("Arial", 11, "bold"),
            bg=BG_COLOR
        ).pack(
            anchor="w"
        )

        table_frame = tk.Frame(
            body,
            bg=WHITE,
            bd=1,
            relief=tk.SOLID
        )

        table_frame.pack(
            fill=tk.BOTH,
            expand=True,
            pady=(5, 15)
        )

        columns = (
            "username",
            "full_name",
            "role"
        )

        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=8
        )

        self.tree.heading(
            "username",
            text="Username"
        )

        self.tree.heading(
            "full_name",
            text="Full Name"
        )

        self.tree.heading(
            "role",
            text="Role"
        )

        self.tree.column(
            "username",
            width=140
        )

        self.tree.column(
            "full_name",
            width=220
        )

        self.tree.column(
            "role",
            width=120,
            anchor="center"
        )

        self.tree.pack(
            fill=tk.BOTH,
            expand=True
        )

        # ====================================================
        # DELETE USER
        # ====================================================

        tk.Button(
            body,
            text="Delete Selected User",
            font=("Arial", 9, "bold"),
            bg="#e53e3e",
            fg="white",
            command=self.delete_selected_user
        ).pack(
            anchor="w",
            pady=(0, 15)
        )

        # ====================================================
        # ADD USER
        # ====================================================

        add_box = tk.LabelFrame(
            body,
            text="Add New User",
            bg=BG_COLOR,
            font=("Arial", 10, "bold")
        )

        add_box.pack(
            fill=tk.X
        )

        # Username

        tk.Label(
            add_box,
            text="Username:",
            bg=BG_COLOR
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=5,
            pady=5
        )

        self.entry_username = tk.Entry(
            add_box,
            width=20
        )

        self.entry_username.grid(
            row=0,
            column=1,
            padx=5,
            pady=5
        )

        # Password

        tk.Label(
            add_box,
            text="Password:",
            bg=BG_COLOR
        ).grid(
            row=0,
            column=2,
            sticky="w",
            padx=5,
            pady=5
        )

        self.entry_password = tk.Entry(
            add_box,
            width=20
        )

        self.entry_password.grid(
            row=0,
            column=3,
            padx=5,
            pady=5
        )

        # Full name

        tk.Label(
            add_box,
            text="Full Name:",
            bg=BG_COLOR
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=5,
            pady=5
        )

        self.entry_full_name = tk.Entry(
            add_box,
            width=20
        )

        self.entry_full_name.grid(
            row=1,
            column=1,
            padx=5,
            pady=5
        )

        # Role

        tk.Label(
            add_box,
            text="Role:",
            bg=BG_COLOR
        ).grid(
            row=1,
            column=2,
            sticky="w",
            padx=5,
            pady=5
        )

        self.cmb_role = ttk.Combobox(
            add_box,
            values=[
                "Cashier",
                "Admin"
            ],
            width=17,
            state="readonly"
        )

        self.cmb_role.set(
            "Cashier"
        )

        self.cmb_role.grid(
            row=1,
            column=3,
            padx=5,
            pady=5
        )

        # Add button

        tk.Button(
            add_box,
            text="Add User",
            font=("Arial", 10, "bold"),
            bg="#38a169",
            fg="white",
            command=self.add_user
        ).grid(
            row=2,
            column=0,
            columnspan=4,
            pady=10,
            sticky="ew",
            padx=5
        )

        # Load users

        self.load_users()

    # ========================================================
    # LOAD USERS
    # ========================================================

    def load_users(self):

        for row in self.tree.get_children():

            self.tree.delete(
                row
            )

        conn = sqlite3.connect(
            DB_NAME
        )

        cursor = conn.cursor()

        try:

            cursor.execute("""
                SELECT username, full_name, role
                FROM users
                ORDER BY username
            """)

            rows = cursor.fetchall()

        finally:

            conn.close()

        for row in rows:

            self.tree.insert(
                "",
                tk.END,
                values=row
            )

    # ========================================================
    # ADD USER
    # ========================================================

    def add_user(self):

        username = (
            self.entry_username
            .get()
            .strip()
        )

        password = (
            self.entry_password
            .get()
            .strip()
        )

        full_name = (
            self.entry_full_name
            .get()
            .strip()
        )

        role = self.cmb_role.get()

        if (
            not username
            or not password
            or not full_name
        ):

            messagebox.showerror(
                "Missing Info",
                "Please fill in username, password, and full name.",
                parent=self
            )

            return

        conn = sqlite3.connect(
            DB_NAME
        )

        cursor = conn.cursor()

        try:

            cursor.execute("""
                INSERT INTO users (
                    username,
                    password,
                    password_hash,
                    full_name,
                    role
                )
                VALUES (?, '', ?, ?, ?)
            """, (
                username,
                hash_password(password),
                full_name,
                role
            ))

            conn.commit()

            messagebox.showinfo(
                "Success",
                f"User '{username}' added.",
                parent=self
            )

            # Clear fields

            self.entry_username.delete(
                0,
                tk.END
            )

            self.entry_password.delete(
                0,
                tk.END
            )

            self.entry_full_name.delete(
                0,
                tk.END
            )

            self.cmb_role.set(
                "Cashier"
            )

            self.load_users()

        except sqlite3.IntegrityError:

            messagebox.showerror(
                "Username Taken",
                f"The username '{username}' already exists.",
                parent=self
            )

        except Exception as e:

            messagebox.showerror(
                "Database Error",
                f"Could not add user.\n\n{e}",
                parent=self
            )

        finally:

            conn.close()

    # ========================================================
    # DELETE USER
    # ========================================================

    def delete_selected_user(self):

        selected = self.tree.selection()

        if not selected:

            messagebox.showwarning(
                "No Selection",
                "Please select a user to delete.",
                parent=self
            )

            return

        username = self.tree.item(
            selected[0]
        )["values"][0]

        # Never allow default admin deletion

        if username == "admin":

            messagebox.showerror(
                "Not Allowed",
                "The default admin account can't be deleted.",
                parent=self
            )

            return

        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete user '{username}'?",
            parent=self
        ):

            return

        conn = sqlite3.connect(
            DB_NAME
        )

        cursor = conn.cursor()

        try:

            cursor.execute(
                "DELETE FROM users WHERE username = ?",
                (username,)
            )

            conn.commit()

        finally:

            conn.close()

        self.load_users()
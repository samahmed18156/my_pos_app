from core.logger import logger as _bkpos_logger
from core.config import DB_PATH
import sqlite3
import tkinter as tk
from security import hash_password
from tkinter import ttk, messagebox
from datetime import datetime
import time
import os
import csv
import shutil
from store_settings import set_store_name, get_store_name


# ============================================================
# COLORS - Modern Professional Theme
# ============================================================
COLORS = {
    "bg": "#f0f4f8",
    "sidebar": "#1a202c",
    "sidebar_hover": "#2d3748",
    "header": "#2b6cb0",
    "header_text": "#ffffff",
    "card_bg": "#ffffff",
    "card_shadow": "#e2e8f0",
    "text_primary": "#1a202c",
    "text_secondary": "#4a5568",
    "accent_blue": "#3182ce",
    "accent_green": "#38a169",
    "accent_orange": "#dd6b20",
    "accent_red": "#e53e3e",
    "accent_purple": "#805ad5",
    "border": "#e2e8f0",
    "hover_blue": "#2b6cb0",
}


FONTS = {
    "title": ("Segoe UI", 20, "bold"),
    "heading": ("Segoe UI", 14, "bold"),
    "subheading": ("Segoe UI", 12, "bold"),
    "normal": ("Segoe UI", 11),
    "small": ("Segoe UI", 9),
    "number": ("Segoe UI", 18, "bold"),
}


class AdminPortal(tk.Tk):

    def __init__(self, admin_user):
        super().__init__()

        self.parent = None
        self.admin_user = admin_user

        # Make sure branch support exists
        self.setup_branch_support()

        self.title(f"Admin Portal - {admin_user['full_name']}")
        self.geometry("1200x750")
        self.configure(bg=COLORS["bg"])
        self.minsize(1000, 600)

        self.create_title_bar()

        self.main_container = tk.Frame(
            self.main_container if hasattr(self, "main_container") else self,
            bg=COLORS["bg"]
        )

        # Recreate main container correctly
        self.main_container.destroy()
        self.main_container = tk.Frame(self, bg=COLORS["bg"])
        self.main_container.pack(fill=tk.BOTH, expand=True)

        self.create_sidebar()
        self.create_main_area()

        self.show_dashboard()

    # ============================================================
    # TITLE BAR
    # ============================================================

    def create_title_bar(self):

        title_bar = tk.Frame(
            self,
            bg=COLORS["header"],
            height=40
        )

        title_bar.pack(fill=tk.X, side=tk.TOP)
        title_bar.pack_propagate(False)

        tk.Label(
            title_bar,
            text="🔐 ADMIN PORTAL",
            font=("Segoe UI", 13, "bold"),
            fg="white",
            bg=COLORS["header"]
        ).pack(side=tk.LEFT, padx=15)

        tk.Label(
            title_bar,
            text=f"👤 {self.admin_user['full_name']} (Admin)",
            font=("Segoe UI", 10),
            fg="#bee3f8",
            bg=COLORS["header"]
        ).pack(side=tk.LEFT, padx=20)

        close_btn = tk.Button(
            title_bar,
            text="✕",
            font=("Segoe UI", 12, "bold"),
            bg=COLORS["header"],
            fg="white",
            bd=0,
            padx=10,
            command=self.close_app
        )

        close_btn.pack(side=tk.RIGHT, padx=5)

        close_btn.bind(
            "<Enter>",
            lambda e: close_btn.config(bg="#e53e3e")
        )

        close_btn.bind(
            "<Leave>",
            lambda e: close_btn.config(bg=COLORS["header"])
        )

    # ============================================================
    # SIDEBAR
    # ============================================================

    def create_sidebar(self):

        self.sidebar = tk.Frame(
            self.main_container,
            bg=COLORS["sidebar"],
            width=220
        )

        self.sidebar.pack(
            side=tk.LEFT,
            fill=tk.Y
        )

        self.sidebar.pack_propagate(False)

        sidebar_header = tk.Frame(
            self.sidebar,
            bg=COLORS["sidebar"],
            height=60
        )

        sidebar_header.pack(fill=tk.X)
        sidebar_header.pack_propagate(False)

        tk.Label(
            sidebar_header,
            text="🏪 POS",
            font=("Segoe UI", 16, "bold"),
            fg="white",
            bg=COLORS["sidebar"]
        ).pack(pady=10)

        menu_items = [
            ("📊", "Dashboard", self.show_dashboard, "#3182ce"),
            ("👥", "Users", self.show_users, "#805ad5"),
            ("💰", "Sales", self.show_sales, "#38a169"),
            ("📦", "Products", self.show_products, "#dd6b20"),
            ("📅", "Daily Report", self.show_daily_report, "#e53e3e"),
            ("⚙️", "Settings", self.show_settings, "#4a5568"),
            ("🚪", "Logout", self.logout, "#e53e3e"),
        ]

        self.sidebar_buttons = []

        for icon, text, command, color in menu_items:

            btn_frame = tk.Frame(
                self.sidebar,
                bg=COLORS["sidebar"]
            )

            btn_frame.pack(
                fill=tk.X,
                padx=8,
                pady=2
            )

            btn = tk.Button(
                btn_frame,
                text=f"{icon}  {text}",
                font=("Segoe UI", 11),
                bg=COLORS["sidebar"],
                fg="#a0aec0",
                bd=0,
                anchor="w",
                padx=15,
                pady=10,
                command=command
            )

            btn.pack(fill=tk.X)

            btn.bind(
                "<Enter>",
                lambda e, b=btn:
                b.config(
                    bg=COLORS["sidebar_hover"],
                    fg="white"
                )
            )

            btn.bind(
                "<Leave>",
                lambda e, b=btn:
                b.config(
                    bg=COLORS["sidebar"],
                    fg="#a0aec0"
                )
            )

            dot = tk.Label(
                btn_frame,
                text="●",
                font=("Segoe UI", 8),
                bg=COLORS["sidebar"],
                fg=COLORS["sidebar"],
                padx=0
            )

            dot.place(
                x=5,
                y=12
            )

            self.sidebar_buttons.append({
                "btn": btn,
                "dot": dot,
                "color": color
            })

        tk.Label(
            self.sidebar,
            text="v2.0.0",
            font=("Segoe UI", 8),
            fg="#4a5568",
            bg=COLORS["sidebar"]
        ).pack(
            side=tk.BOTTOM,
            pady=10
        )

    # ============================================================
    # MAIN AREA
    # ============================================================

    def create_main_area(self):

        self.main_frame = tk.Frame(
            self.main_container,
            bg=COLORS["bg"]
        )

        self.main_frame.pack(
            side=tk.RIGHT,
            fill=tk.BOTH,
            expand=True,
            padx=20,
            pady=20
        )

    def clear_main(self):

        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def set_active_button(self, index):

        for i, btn_data in enumerate(self.sidebar_buttons):

            btn = btn_data["btn"]
            dot = btn_data["dot"]

            if i == index:

                btn.config(
                    bg=COLORS["sidebar_hover"],
                    fg="white"
                )

                dot.config(
                    fg=btn_data["color"]
                )

            else:

                btn.config(
                    bg=COLORS["sidebar"],
                    fg="#a0aec0"
                )

                dot.config(
                    fg=COLORS["sidebar"]
                )

    def close_app(self):

        if messagebox.askyesno(
            "Close",
            "Are you sure you want to close the Admin Portal?"
        ):
            self.destroy()

    # ============================================================
    # BRANCH DATABASE SUPPORT
    # ============================================================

    def setup_branch_support(self):

        try:

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # ------------------------------------------------
            # Create branches table
            # ------------------------------------------------

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS branches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    branch_name TEXT NOT NULL,
                    branch_code TEXT UNIQUE NOT NULL,
                    address TEXT,
                    phone TEXT,
                    status TEXT DEFAULT 'Active'
                )
            """)

            # ------------------------------------------------
            # Check users table
            # ------------------------------------------------

            cursor.execute(
                "PRAGMA table_info(users)"
            )

            columns = [
                row[1]
                for row in cursor.fetchall()
            ]

            if "branch_id" not in columns:

                cursor.execute("""
                    ALTER TABLE users
                    ADD COLUMN branch_id INTEGER
                """)

            conn.commit()
            conn.close()

        except sqlite3.Error as e:

            messagebox.showerror(
                "Database Error",
                f"Could not initialize branch support.\n\n{e}"
            )

    # ============================================================
    # DASHBOARD
    # ============================================================

    def show_dashboard(self):

        self.clear_main()
        self.set_active_button(0)

        header_frame = tk.Frame(
            self.main_frame,
            bg=COLORS["bg"]
        )

        header_frame.pack(
            fill=tk.X,
            pady=(0, 20)
        )

        tk.Label(
            header_frame,
            text="📊 Dashboard",
            font=FONTS["title"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"]
        ).pack(side=tk.LEFT)

        tk.Label(
            header_frame,
            text=datetime.now().strftime(
                "%A, %B %d, %Y %I:%M %p"
            ),
            font=FONTS["normal"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"]
        ).pack(side=tk.RIGHT)

        self.create_summary_cards()
        self.create_recent_sales()

    def create_summary_cards(self):

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT SUM(total_amount) FROM sales_history"
        )

        total_sales = cursor.fetchone()[0] or 0.0

        cursor.execute(
            "SELECT COUNT(*) FROM sales_history"
        )

        total_trans = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT COUNT(*), SUM(total_amount)
            FROM sales_history
            WHERE DATE(timestamp) = DATE('now')
        """)

        today_count, today_total = cursor.fetchone()

        today_count = today_count or 0
        today_total = today_total or 0.0

        cursor.execute(
            "SELECT COUNT(*) FROM users"
        )

        total_users = cursor.fetchone()[0] or 0

        conn.close()

        cards = [
            (
                "💰 Total Sales",
                f"R {total_sales:,.2f}",
                COLORS["accent_blue"]
            ),
            (
                "🧾 Transactions",
                str(total_trans),
                COLORS["accent_green"]
            ),
            (
                "📆 Today's Sales",
                f"R {today_total:,.2f}",
                COLORS["accent_orange"]
            ),
            (
                "👥 Users",
                str(total_users),
                COLORS["accent_purple"]
            ),
        ]

        card_frame = tk.Frame(
            self.main_frame,
            bg=COLORS["bg"]
        )

        card_frame.pack(
            fill=tk.X,
            pady=(0, 20)
        )

        for title, value, color in cards:

            card = self.create_card(
                card_frame,
                title,
                value,
                color
            )

            card.pack(
                side=tk.LEFT,
                padx=10,
                expand=True,
                fill=tk.X
            )

    def create_card(
        self,
        parent,
        title,
        value,
        color
    ):

        card = tk.Frame(
            parent,
            bg=COLORS["card_bg"],
            height=100
        )

        card.pack_propagate(False)

        shadow = tk.Frame(
            card,
            bg=COLORS["card_shadow"],
            height=2
        )

        shadow.pack(
            fill=tk.X,
            side=tk.TOP
        )

        inner = tk.Frame(
            card,
            bg=COLORS["card_bg"],
            padx=15,
            pady=10
        )

        inner.pack(
            fill=tk.BOTH,
            expand=True
        )

        tk.Label(
            inner,
            text=title,
            font=FONTS["heading"],
            bg=COLORS["card_bg"],
            fg=COLORS["text_secondary"]
        ).pack(anchor="w")

        tk.Label(
            inner,
            text=value,
            font=FONTS["number"],
            bg=COLORS["card_bg"],
            fg=color
        ).pack(
            anchor="w",
            pady=(5, 0)
        )

        return card

    def create_recent_sales(self):

        tk.Label(
            self.main_frame,
            text="Recent Sales",
            font=FONTS["heading"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"]
        ).pack(
            anchor="w",
            pady=(10, 5)
        )

        table_frame = tk.Frame(
            self.main_frame,
            bg=COLORS["card_bg"],
            bd=1,
            relief=tk.SOLID
        )

        table_frame.pack(
            fill=tk.BOTH,
            expand=True
        )

        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Treeview",
            background=COLORS["card_bg"],
            foreground=COLORS["text_primary"],
            rowheight=30,
            font=("Segoe UI", 10)
        )

        style.configure(
            "Treeview.Heading",
            background=COLORS["bg"],
            foreground=COLORS["text_secondary"],
            font=("Segoe UI", 10, "bold"),
            borderwidth=0
        )

        style.map(
            "Treeview",
            background=[
                ("selected", COLORS["accent_blue"])
            ]
        )

        columns = (
            "id",
            "date",
            "total",
            "payment",
            "cashier"
        )

        tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=10
        )

        tree.heading("id", text="Receipt #")
        tree.heading("date", text="Date & Time")
        tree.heading("total", text="Total")
        tree.heading("payment", text="Payment")
        tree.heading("cashier", text="Cashier")

        tree.column(
            "id",
            width=80,
            anchor="center"
        )

        tree.column(
            "date",
            width=200,
            anchor="center"
        )

        tree.column(
            "total",
            width=130,
            anchor="e"
        )

        tree.column(
            "payment",
            width=130,
            anchor="center"
        )

        tree.column(
            "cashier",
            width=130,
            anchor="center"
        )

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient=tk.VERTICAL,
            command=tree.yview
        )

        tree.configure(
            yscroll=scrollbar.set
        )

        scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y
        )

        tree.pack(
            fill=tk.BOTH,
            expand=True,
            padx=2,
            pady=2
        )

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                timestamp,
                total_amount,
                payment_type,
                cashier
            FROM sales_history
            ORDER BY id DESC
            LIMIT 20
        """)

        rows = cursor.fetchall()
        conn.close()

        for row in rows:

            tree.insert(
                "",
                tk.END,
                values=(
                    f"#{row[0]}",
                    str(row[1])[:16]
                    if row[1]
                    else "N/A",
                    f"R {row[2]:,.2f}",
                    row[3] or "Unknown",
                    row[4] or "Unknown"
                )
            )

    # ============================================================
    # USERS MANAGEMENT
    # ============================================================

    def show_users(self):

        self.clear_main()
        self.set_active_button(1)

        tk.Label(
            self.main_frame,
            text="👥 User Management",
            font=FONTS["title"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"]
        ).pack(
            anchor="w",
            pady=(0, 10)
        )

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM users"
        )

        total = cursor.fetchone()[0] or 0

        conn.close()

        tk.Label(
            self.main_frame,
            text=f"Total Users: {total}",
            font=FONTS["subheading"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"]
        ).pack(
            anchor="w",
            pady=(0, 15)
        )

        # --------------------------------------------------------
        # TOOLBAR
        # --------------------------------------------------------

        toolbar = tk.Frame(
            self.main_frame,
            bg=COLORS["bg"]
        )

        toolbar.pack(
            fill=tk.X,
            pady=(0, 10)
        )

        tk.Button(
            toolbar,
            text="➕ Add User",
            font=FONTS["subheading"],
            bg=COLORS["accent_green"],
            fg="white",
            padx=15,
            pady=5,
            command=self.add_user,
            relief=tk.FLAT
        ).pack(side=tk.LEFT)

        tk.Button(
            toolbar,
            text="🔄 Refresh",
            font=FONTS["subheading"],
            bg=COLORS["accent_blue"],
            fg="white",
            padx=15,
            pady=5,
            command=self.show_users,
            relief=tk.FLAT
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Button(
            toolbar,
            text="🏪 Assign Branch",
            font=FONTS["subheading"],
            bg=COLORS["accent_orange"],
            fg="white",
            padx=15,
            pady=5,
            command=lambda: self.assign_user_branch(tree),
            relief=tk.FLAT
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Button(
            toolbar,
            text="🔑 Permissions",
            font=FONTS["subheading"],
            bg=COLORS["accent_purple"],
            fg="white",
            padx=15,
            pady=5,
            command=self.open_permissions,
            relief=tk.FLAT
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        # --------------------------------------------------------
        # USER TABLE
        # --------------------------------------------------------

        table_frame = tk.Frame(
            self.main_frame,
            bg=COLORS["card_bg"],
            bd=1,
            relief=tk.SOLID
        )

        table_frame.pack(
            fill=tk.BOTH,
            expand=True
        )

        columns = (
            "id",
            "username",
            "full_name",
            "role",
            "branch"
        )

        tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=12
        )

        tree.heading("id", text="ID")
        tree.heading("username", text="Username")
        tree.heading("full_name", text="Full Name")
        tree.heading("role", text="Role")
        tree.heading("branch", text="Branch")

        tree.column(
            "id",
            width=50,
            anchor="center"
        )

        tree.column(
            "username",
            width=150,
            anchor="center"
        )

        tree.column(
            "full_name",
            width=200,
            anchor="w"
        )

        tree.column(
            "role",
            width=100,
            anchor="center"
        )

        tree.column(
            "branch",
            width=180,
            anchor="center"
        )

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient=tk.VERTICAL,
            command=tree.yview
        )

        tree.configure(
            yscroll=scrollbar.set
        )

        scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y
        )

        tree.pack(
            fill=tk.BOTH,
            expand=True,
            padx=2,
            pady=2
        )

        # --------------------------------------------------------
        # RIGHT CLICK MENU
        # --------------------------------------------------------

        def on_right_click(event):

            item = tree.identify_row(event.y)

            if item:

                tree.selection_set(item)

                menu = tk.Menu(
                    self,
                    tearoff=0,
                    bg=COLORS["card_bg"]
                )

                menu.add_command(
                    label="🏪 Assign Branch",
                    command=lambda:
                    self.assign_user_branch(tree)
                )

                menu.add_command(
                    label="🗑️ Delete User",
                    command=lambda:
                    self.delete_user(tree)
                )

                menu.add_command(
                    label="🔑 Reset Password",
                    command=lambda:
                    self.reset_password(tree)
                )

                menu.post(
                    event.x_root,
                    event.y_root
                )

        tree.bind(
            "<Button-3>",
            on_right_click
        )

        # --------------------------------------------------------
        # LOAD USERS WITH BRANCH
        # --------------------------------------------------------

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                u.id,
                u.username,
                u.full_name,
                u.role,
                COALESCE(
                    b.branch_name,
                    'Not Assigned'
                )
            FROM users u
            LEFT JOIN branches b
                ON u.branch_id = b.id
            ORDER BY u.id
        """)

        rows = cursor.fetchall()

        conn.close()

        for row in rows:

            tree.insert(
                "",
                tk.END,
                values=row
            )

        self.user_tree = tree

    # ============================================================
    # ADD USER
    # ============================================================

    def add_user(self):

        popup = self.create_popup(
            "Add New User",
            420,
            430
        )

        body = tk.Frame(
            popup,
            bg=COLORS["bg"],
            padx=25,
            pady=20
        )

        body.pack(
            fill=tk.BOTH,
            expand=True
        )

        # --------------------------------------------------------
        # USER FIELDS
        # --------------------------------------------------------

        tk.Label(
            body,
            text="Username:",
            font=FONTS["subheading"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"]
        ).pack(
            anchor="w",
            pady=(0, 2)
        )

        username_entry = tk.Entry(
            body,
            font=FONTS["normal"],
            bd=1,
            relief=tk.SOLID
        )

        username_entry.pack(
            fill=tk.X,
            pady=(0, 10)
        )

        tk.Label(
            body,
            text="Full Name:",
            font=FONTS["subheading"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"]
        ).pack(
            anchor="w",
            pady=(0, 2)
        )

        fullname_entry = tk.Entry(
            body,
            font=FONTS["normal"],
            bd=1,
            relief=tk.SOLID
        )

        fullname_entry.pack(
            fill=tk.X,
            pady=(0, 10)
        )

        tk.Label(
            body,
            text="Password:",
            font=FONTS["subheading"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"]
        ).pack(
            anchor="w",
            pady=(0, 2)
        )

        password_entry = tk.Entry(
            body,
            font=FONTS["normal"],
            bd=1,
            relief=tk.SOLID,
            show="•"
        )

        password_entry.pack(
            fill=tk.X,
            pady=(0, 10)
        )

        tk.Label(
            body,
            text="Role:",
            font=FONTS["subheading"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"]
        ).pack(
            anchor="w",
            pady=(0, 2)
        )

        role_combo = ttk.Combobox(
            body,
            values=[
                "cashier",
                "admin"
            ],
            state="readonly",
            font=FONTS["normal"]
        )

        role_combo.set("cashier")

        role_combo.pack(
            fill=tk.X,
            pady=(0, 10)
        )

        # --------------------------------------------------------
        # BRANCH
        # --------------------------------------------------------

        tk.Label(
            body,
            text="Branch:",
            font=FONTS["subheading"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"]
        ).pack(
            anchor="w",
            pady=(0, 2)
        )

        branch_combo = ttk.Combobox(
            body,
            state="readonly",
            font=FONTS["normal"]
        )

        branch_combo.pack(
            fill=tk.X,
            pady=(0, 15)
        )

        branches = self.get_active_branches()

        branch_values = [
            f"{branch[0]} - {branch[1]}"
            for branch in branches
        ]

        branch_combo["values"] = [
            "Not Assigned"
        ] + branch_values

        branch_combo.set(
            "Not Assigned"
        )

        # --------------------------------------------------------
        # SAVE
        # --------------------------------------------------------

        def save():

            username = username_entry.get().strip()
            full_name = fullname_entry.get().strip()
            password = password_entry.get().strip()
            role = role_combo.get()
            branch_selection = branch_combo.get()

            if not username or not full_name or not password:

                messagebox.showerror(
                    "Error",
                    "Username, full name and password are required!",
                    parent=popup
                )

                return

            branch_id = None

            if (
                branch_selection
                and branch_selection != "Not Assigned"
            ):

                try:

                    branch_id = int(
                        branch_selection.split(
                            " - ",
                            1
                        )[0]
                    )

                except (ValueError, IndexError):

                    branch_id = None

            conn = sqlite3.connect(
                "pos_store.db"
            )

            cursor = conn.cursor()

            try:

                cursor.execute("""
                    INSERT INTO users
                    (
                        username,
                        password,
                        password_hash,
                        full_name,
                        role,
                        branch_id,
                        must_change_password
                    )
                    VALUES (?, '', ?, ?, ?, ?, ?)
                """, (
                    username,
                    hash_password(password),
                    full_name,
                    role,
                    branch_id,
                    1 if role.lower() == "admin" else 0
                ))

                conn.commit()

                messagebox.showinfo(
                    "Success",
                    f"User '{username}' added successfully!",
                    parent=popup
                )

                popup.destroy()
                self.show_users()

            except sqlite3.IntegrityError:

                messagebox.showerror(
                    "Error",
                    f"Username '{username}' already exists!",
                    parent=popup
                )

            except sqlite3.Error as e:

                messagebox.showerror(
                    "Database Error",
                    str(e),
                    parent=popup
                )

            finally:

                conn.close()

        btn_frame = tk.Frame(
            body,
            bg=COLORS["bg"]
        )

        btn_frame.pack(
            fill=tk.X
        )

        tk.Button(
            btn_frame,
            text="Save User",
            font=FONTS["subheading"],
            bg=COLORS["accent_green"],
            fg="white",
            padx=20,
            pady=5,
            command=save,
            relief=tk.FLAT
        ).pack(side=tk.LEFT)

        tk.Button(
            btn_frame,
            text="Cancel",
            font=FONTS["subheading"],
            bg=COLORS["accent_red"],
            fg="white",
            padx=20,
            pady=5,
            command=popup.destroy,
            relief=tk.FLAT
        ).pack(
            side=tk.LEFT,
            padx=5
        )

    # ============================================================
    # GET ACTIVE BRANCHES
    # ============================================================

    def get_active_branches(self):

        conn = sqlite3.connect(
            "pos_store.db"
        )

        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, branch_name
            FROM branches
            WHERE status = 'Active'
            ORDER BY branch_name
        """)

        branches = cursor.fetchall()

        conn.close()

        return branches

    # ============================================================
    # ASSIGN USER TO BRANCH
    # ============================================================

    def assign_user_branch(self, tree):

        selected = tree.selection()

        if not selected:

            messagebox.showwarning(
                "Select User",
                "Please select a user first."
            )

            return

        values = tree.item(
            selected[0]
        )["values"]

        user_id = values[0]
        username = values[1]
        full_name = values[2]

        popup = self.create_popup(
            f"Assign Branch - {username}",
            450,
            300
        )

        body = tk.Frame(
            popup,
            bg=COLORS["bg"],
            padx=25,
            pady=20
        )

        body.pack(
            fill=tk.BOTH,
            expand=True
        )

        tk.Label(
            body,
            text=f"User: {full_name}",
            font=FONTS["subheading"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"]
        ).pack(
            anchor="w",
            pady=(0, 15)
        )

        tk.Label(
            body,
            text="Select Branch:",
            font=FONTS["subheading"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"]
        ).pack(
            anchor="w",
            pady=(0, 5)
        )

        branch_combo = ttk.Combobox(
            body,
            state="readonly",
            font=FONTS["normal"]
        )

        branch_combo.pack(
            fill=tk.X,
            pady=(0, 15)
        )

        branches = self.get_active_branches()

        branch_values = [
            f"{branch[0]} - {branch[1]}"
            for branch in branches
        ]

        branch_combo["values"] = [
            "Not Assigned"
        ] + branch_values

        # --------------------------------------------------------
        # Get current branch
        # --------------------------------------------------------

        conn = sqlite3.connect(
            "pos_store.db"
        )

        cursor = conn.cursor()

        cursor.execute("""
            SELECT branch_id
            FROM users
            WHERE id = ?
        """, (user_id,))

        result = cursor.fetchone()

        conn.close()

        current_branch_id = (
            result[0]
            if result
            else None
        )

        current_selection = "Not Assigned"

        if current_branch_id:

            for branch_id, branch_name in branches:

                if branch_id == current_branch_id:

                    current_selection = (
                        f"{branch_id} - {branch_name}"
                    )

                    break

        branch_combo.set(
            current_selection
        )

        # --------------------------------------------------------
        # Save Assignment
        # --------------------------------------------------------

        def save_branch():

            selection = branch_combo.get()

            branch_id = None

            if (
                selection
                and selection != "Not Assigned"
            ):

                try:

                    branch_id = int(
                        selection.split(
                            " - ",
                            1
                        )[0]
                    )

                except (ValueError, IndexError):

                    messagebox.showerror(
                        "Error",
                        "Invalid branch selection.",
                        parent=popup
                    )

                    return

            try:

                conn = sqlite3.connect(
                    "pos_store.db"
                )

                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE users
                    SET branch_id = ?
                    WHERE id = ?
                """, (
                    branch_id,
                    user_id
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo(
                    "Success",
                    f"{username} has been assigned to "
                    f"{'the selected branch' if branch_id else 'no branch'}.",
                    parent=popup
                )

                popup.destroy()

                self.show_users()

            except sqlite3.Error as e:

                messagebox.showerror(
                    "Database Error",
                    f"Could not assign branch.\n\n{e}",
                    parent=popup
                )

        # --------------------------------------------------------
        # Buttons
        # --------------------------------------------------------

        btn_frame = tk.Frame(
            body,
            bg=COLORS["bg"]
        )

        btn_frame.pack(
            fill=tk.X,
            pady=(10, 0)
        )

        tk.Button(
            btn_frame,
            text="💾 Save Assignment",
            font=FONTS["subheading"],
            bg=COLORS["accent_green"],
            fg="white",
            padx=15,
            pady=6,
            command=save_branch,
            relief=tk.FLAT
        ).pack(
            side=tk.LEFT
        )

        tk.Button(
            btn_frame,
            text="Cancel",
            font=FONTS["subheading"],
            bg=COLORS["accent_red"],
            fg="white",
            padx=15,
            pady=6,
            command=popup.destroy,
            relief=tk.FLAT
        ).pack(
            side=tk.LEFT,
            padx=5
        )

    # ============================================================
    # DELETE USER
    # ============================================================

    def delete_user(self, tree):

        selected = tree.selection()

        if not selected:
            return

        values = tree.item(
            selected[0]
        )["values"]

        username = values[1]

        if username == self.admin_user["username"]:

            messagebox.showerror(
                "Error",
                "You cannot delete yourself!"
            )

            return

        if messagebox.askyesno(
            "Confirm",
            f"Delete user '{username}'?"
        ):

            conn = sqlite3.connect(
                "pos_store.db"
            )

            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM users WHERE username = ?",
                (username,)
            )

            conn.commit()
            conn.close()

            messagebox.showinfo(
                "Success",
                f"User '{username}' deleted!"
            )

            self.show_users()

    # ============================================================
    # RESET PASSWORD
    # ============================================================

    def reset_password(self, tree):

        selected = tree.selection()

        if not selected:
            return

        values = tree.item(
            selected[0]
        )["values"]

        username = values[1]

        popup = self.create_popup(
            f"Reset Password - {username}",
            350,
            180
        )

        body = tk.Frame(
            popup,
            bg=COLORS["bg"],
            padx=25,
            pady=20
        )

        body.pack(
            fill=tk.BOTH,
            expand=True
        )

        tk.Label(
            body,
            text="New Password:",
            font=FONTS["subheading"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"]
        ).pack(
            anchor="w",
            pady=(0, 2)
        )

        password_entry = tk.Entry(
            body,
            font=FONTS["normal"],
            width=30,
            bd=1,
            relief=tk.SOLID,
            show="•"
        )

        password_entry.pack(
            fill=tk.X,
            pady=(0, 15)
        )

        def save():

            new_pass = password_entry.get().strip()

            if not new_pass:

                messagebox.showerror(
                    "Error",
                    "Password cannot be empty!",
                    parent=popup
                )

                return

            conn = sqlite3.connect(
                "pos_store.db"
            )

            cursor = conn.cursor()

            cursor.execute("""
                UPDATE users
                SET password = '', password_hash = ?, must_change_password = 0
                WHERE username = ?
            """, (
                hash_password(new_pass),
                username
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo(
                "Success",
                f"Password for '{username}' updated!",
                parent=popup
            )

            popup.destroy()

        btn_frame = tk.Frame(
            body,
            bg=COLORS["bg"]
        )

        btn_frame.pack(
            fill=tk.X
        )

        tk.Button(
            btn_frame,
            text="Update",
            font=FONTS["subheading"],
            bg=COLORS["accent_green"],
            fg="white",
            padx=20,
            pady=5,
            command=save,
            relief=tk.FLAT
        ).pack(side=tk.LEFT)

        tk.Button(
            btn_frame,
            text="Cancel",
            font=FONTS["subheading"],
            bg=COLORS["accent_red"],
            fg="white",
            padx=20,
            pady=5,
            command=popup.destroy,
            relief=tk.FLAT
        ).pack(
            side=tk.LEFT,
            padx=5
        )

    # ============================================================
    # SALES REPORT
    # ============================================================

    def show_sales(self):

        self.clear_main()
        self.set_active_button(2)

        tk.Label(
            self.main_frame,
            text="💰 Sales Report",
            font=FONTS["title"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"]
        ).pack(
            anchor="w",
            pady=(0, 10)
        )

        conn = sqlite3.connect(
            "pos_store.db"
        )

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*),
                SUM(total_amount)
            FROM sales_history
        """)

        count, total = cursor.fetchone()

        count = count or 0
        total = total or 0.0

        cursor.execute("""
            SELECT
                payment_type,
                COUNT(*),
                SUM(total_amount)
            FROM sales_history
            GROUP BY payment_type
        """)

        by_payment = cursor.fetchall()

        conn.close()

        stats_frame = tk.Frame(
            self.main_frame,
            bg=COLORS["bg"]
        )

        stats_frame.pack(
            fill=tk.X,
            pady=(0, 15)
        )

        tk.Label(
            stats_frame,
            text=f"Total Transactions: {count}",
            font=FONTS["subheading"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"]
        ).pack(
            side=tk.LEFT,
            padx=(0, 30)
        )

        tk.Label(
            stats_frame,
            text=f"Total Sales: R {total:,.2f}",
            font=FONTS["subheading"],
            bg=COLORS["bg"],
            fg=COLORS["accent_blue"]
        ).pack(
            side=tk.LEFT
        )

        tk.Label(
            self.main_frame,
            text="💳 Payment Breakdown",
            font=FONTS["heading"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"]
        ).pack(
            anchor="w",
            pady=(10, 5)
        )

        for row in by_payment:

            tk.Label(
                self.main_frame,
                text=(
                    f"  {row[0]}: "
                    f"{row[1]} transactions - "
                    f"R {row[2]:,.2f}"
                ),
                font=FONTS["normal"],
                bg=COLORS["bg"],
                fg=COLORS["text_secondary"]
            ).pack(
                anchor="w"
            )

        tk.Label(
            self.main_frame,
            text="All Sales",
            font=FONTS["heading"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"]
        ).pack(
            anchor="w",
            pady=(15, 5)
        )

        table_frame = tk.Frame(
            self.main_frame,
            bg=COLORS["card_bg"],
            bd=1,
            relief=tk.SOLID
        )

        table_frame.pack(
            fill=tk.BOTH,
            expand=True
        )

        columns = (
            "id",
            "date",
            "total",
            "payment",
            "cashier"
        )

        tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=12
        )

        tree.heading(
            "id",
            text="Receipt #"
        )

        tree.heading(
            "date",
            text="Date & Time"
        )

        tree.heading(
            "total",
            text="Total"
        )

        tree.heading(
            "payment",
            text="Payment"
        )

        tree.heading(
            "cashier",
            text="Cashier"
        )

        tree.column(
            "id",
            width=80,
            anchor="center"
        )

        tree.column(
            "date",
            width=200,
            anchor="center"
        )

        tree.column(
            "total",
            width=130,
            anchor="e"
        )

        tree.column(
            "payment",
            width=130,
            anchor="center"
        )

        tree.column(
            "cashier",
            width=130,
            anchor="center"
        )

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient=tk.VERTICAL,
            command=tree.yview
        )

        tree.configure(
            yscroll=scrollbar.set
        )

        scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y
        )

        tree.pack(
            fill=tk.BOTH,
            expand=True,
            padx=2,
            pady=2
        )

        conn = sqlite3.connect(
            "pos_store.db"
        )

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                timestamp,
                total_amount,
                payment_type,
                cashier
            FROM sales_history
            ORDER BY id DESC
        """)

        rows = cursor.fetchall()

        conn.close()

        for row in rows:

            tree.insert(
                "",
                tk.END,
                values=(
                    f"#{row[0]}",
                    str(row[1])[:16]
                    if row[1]
                    else "N/A",
                    f"R {row[2]:,.2f}",
                    row[3] or "Unknown",
                    row[4] or "Unknown"
                )
            )

    # ============================================================
    # PRODUCTS
    # ============================================================

    def show_products(self):

        self.clear_main()
        self.set_active_button(3)

        tk.Label(
            self.main_frame,
            text="📦 Products",
            font=FONTS["title"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"]
        ).pack(
            anchor="w",
            pady=(0, 10)
        )

        table_frame = tk.Frame(
            self.main_frame,
            bg=COLORS["card_bg"],
            bd=1,
            relief=tk.SOLID
        )

        table_frame.pack(
            fill=tk.BOTH,
            expand=True
        )

        columns = (
            "barcode",
            "name",
            "price",
            "stock"
        )

        tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=15
        )

        tree.heading(
            "barcode",
            text="Barcode"
        )

        tree.heading(
            "name",
            text="Product Name"
        )

        tree.heading(
            "price",
            text="Price"
        )

        tree.heading(
            "stock",
            text="Stock"
        )

        tree.column(
            "barcode",
            width=130,
            anchor="center"
        )

        tree.column(
            "name",
            width=350,
            anchor="w"
        )

        tree.column(
            "price",
            width=120,
            anchor="e"
        )

        tree.column(
            "stock",
            width=100,
            anchor="center"
        )

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient=tk.VERTICAL,
            command=tree.yview
        )

        tree.configure(
            yscroll=scrollbar.set
        )

        scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y
        )

        tree.pack(
            fill=tk.BOTH,
            expand=True,
            padx=2,
            pady=2
        )

        conn = sqlite3.connect(
            "pos_store.db"
        )

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                barcode,
                description,
                selling_price,
                soh
            FROM products
            ORDER BY description
        """)

        rows = cursor.fetchall()

        conn.close()

        for row in rows:

            tree.insert(
                "",
                tk.END,
                values=(
                    row[0],
                    row[1],
                    f"R {row[2]:,.2f}",
                    f"{row[3]:.0f}"
                    if row[3]
                    else "0"
                )
            )

    # ============================================================
    # DAILY REPORT
    # ============================================================

    def show_daily_report(self):

        self.clear_main()
        self.set_active_button(4)

        tk.Label(
            self.main_frame,
            text="📅 Daily Report",
            font=FONTS["title"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"]
        ).pack(
            anchor="w",
            pady=(0, 10)
        )

        conn = sqlite3.connect(
            "pos_store.db"
        )

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*),
                SUM(total_amount)
            FROM sales_history
            WHERE DATE(timestamp) = DATE('now')
        """)

        count, total = cursor.fetchone()

        count = count or 0
        total = total or 0.0

        tk.Label(
            self.main_frame,
            text=(
                f"📆 "
                f"{datetime.now().strftime('%A, %B %d, %Y')}"
            ),
            font=FONTS["heading"],
            bg=COLORS["bg"],
            fg=COLORS["accent_blue"]
        ).pack(
            anchor="w"
        )

        stats_frame = tk.Frame(
            self.main_frame,
            bg=COLORS["bg"]
        )

        stats_frame.pack(
            fill=tk.X,
            pady=15
        )

        tk.Label(
            stats_frame,
            text=f"Transactions: {count}",
            font=FONTS["subheading"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"]
        ).pack(
            side=tk.LEFT,
            padx=(0, 30)
        )

        tk.Label(
            stats_frame,
            text=f"Total Sales: R {total:,.2f}",
            font=FONTS["subheading"],
            bg=COLORS["bg"],
            fg=COLORS["accent_green"]
        ).pack(
            side=tk.LEFT
        )

        cursor.execute("""
            SELECT
                cashier,
                COUNT(*),
                SUM(total_amount)
            FROM sales_history
            WHERE DATE(timestamp) = DATE('now')
            GROUP BY cashier
        """)

        by_cashier = cursor.fetchall()

        conn.close()

        if by_cashier:

            tk.Label(
                self.main_frame,
                text="👤 By Cashier:",
                font=FONTS["heading"],
                bg=COLORS["bg"],
                fg=COLORS["text_primary"]
            ).pack(
                anchor="w",
                pady=(10, 5)
            )

            for row in by_cashier:

                tk.Label(
                    self.main_frame,
                    text=(
                        f"  {row[0] or 'Unknown'}: "
                        f"{row[1]} transactions - "
                        f"R {row[2]:,.2f}"
                    ),
                    font=FONTS["normal"],
                    bg=COLORS["bg"],
                    fg=COLORS["text_secondary"]
                ).pack(
                    anchor="w"
                )

    # ============================================================
    # SETTINGS
    # ============================================================

    def show_settings(self):

        self.clear_main()
        self.set_active_button(5)

        tk.Label(
            self.main_frame,
            text="⚙️ Settings",
            font=FONTS["title"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"]
        ).pack(
            anchor="w",
            pady=(0, 20)
        )

        settings_frame = tk.Frame(
            self.main_frame,
            bg=COLORS["bg"]
        )

        settings_frame.pack(
            fill=tk.BOTH,
            expand=True
        )

        # ========================================================
        # GENERAL SETTINGS
        # ========================================================

        section1 = tk.LabelFrame(
            settings_frame,
            text="📋 General Settings",
            font=FONTS["heading"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"],
            padx=15,
            pady=10
        )

        section1.pack(
            fill=tk.X,
            pady=(0, 15)
        )

        row1 = tk.Frame(
            section1,
            bg=COLORS["bg"]
        )

        row1.pack(
            fill=tk.X,
            pady=5
        )

        tk.Label(
            row1,
            text="Store Name:",
            font=FONTS["normal"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"],
            width=15,
            anchor="w"
        ).pack(
            side=tk.LEFT
        )

        self.store_name_entry = tk.Entry(
            row1,
            font=FONTS["normal"],
            width=30,
            bd=1,
            relief=tk.SOLID
        )

        self.store_name_entry.insert(
            0,
            get_store_name()
        )

        self.store_name_entry.pack(
            side=tk.LEFT,
            padx=10
        )

        tk.Button(
            row1,
            text="Save",
            font=FONTS["small"],
            bg=COLORS["accent_green"],
            fg="white",
            padx=10,
            command=self.save_store_name
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        row2 = tk.Frame(
            section1,
            bg=COLORS["bg"]
        )

        row2.pack(
            fill=tk.X,
            pady=5
        )

        tk.Label(
            row2,
            text="Tax Rate (%):",
            font=FONTS["normal"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"],
            width=15,
            anchor="w"
        ).pack(
            side=tk.LEFT
        )

        self.tax_entry = tk.Entry(
            row2,
            font=FONTS["normal"],
            width=10,
            bd=1,
            relief=tk.SOLID
        )

        self.tax_entry.insert(
            0,
            "15"
        )

        self.tax_entry.pack(
            side=tk.LEFT,
            padx=10
        )

        tk.Button(
            row2,
            text="Save",
            font=FONTS["small"],
            bg=COLORS["accent_green"],
            fg="white",
            padx=10,
            command=self.save_tax_rate
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Label(
            row2,
            text="(Current: 15%)",
            font=FONTS["small"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"]
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        # ========================================================
        # BACKUP & EXPORT
        # ========================================================

        section2 = tk.LabelFrame(
            settings_frame,
            text="💾 Backup & Export",
            font=FONTS["heading"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"],
            padx=15,
            pady=10
        )

        section2.pack(
            fill=tk.X,
            pady=(0, 15)
        )

        row3 = tk.Frame(
            section2,
            bg=COLORS["bg"]
        )

        row3.pack(
            fill=tk.X,
            pady=5
        )

        tk.Button(
            row3,
            text="📥 Export Sales Data (CSV)",
            font=FONTS["normal"],
            bg=COLORS["accent_blue"],
            fg="white",
            padx=15,
            pady=5,
            command=self.export_sales_csv
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Button(
            row3,
            text="📤 Export Products (CSV)",
            font=FONTS["normal"],
            bg=COLORS["accent_blue"],
            fg="white",
            padx=15,
            pady=5,
            command=self.export_products_csv
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        row4 = tk.Frame(
            section2,
            bg=COLORS["bg"]
        )

        row4.pack(
            fill=tk.X,
            pady=5
        )

        tk.Button(
            row4,
            text="🗄️ Backup Database",
            font=FONTS["normal"],
            bg=COLORS["accent_orange"],
            fg="white",
            padx=15,
            pady=5,
            command=self.backup_database
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        # ========================================================
        # DATABASE
        # ========================================================

        section3 = tk.LabelFrame(
            settings_frame,
            text="🗄️ Database",
            font=FONTS["heading"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"],
            padx=15,
            pady=10
        )

        section3.pack(
            fill=tk.X,
            pady=(0, 15)
        )

        row5 = tk.Frame(
            section3,
            bg=COLORS["bg"]
        )

        row5.pack(
            fill=tk.X,
            pady=5
        )

        tk.Label(
            row5,
            text="Database Size:",
            font=FONTS["normal"],
            bg=COLORS["bg"],
            fg=COLORS["text_secondary"]
        ).pack(
            side=tk.LEFT
        )

        db_size = 0

        if os.path.exists(
            "pos_store.db"
        ):

            db_size = (
                os.path.getsize(
                    "pos_store.db"
                ) / 1024
            )

        tk.Label(
            row5,
            text=f"{db_size:.2f} KB",
            font=("Segoe UI", 11, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["accent_blue"]
        ).pack(
            side=tk.LEFT,
            padx=10
        )

        tk.Button(
            row5,
            text="🔄 Vacuum Database (Compact)",
            font=FONTS["small"],
            bg=COLORS["accent_purple"],
            fg="white",
            padx=10,
            pady=3,
            command=self.vacuum_database
        ).pack(
            side=tk.LEFT,
            padx=10
        )

        # ========================================================
        # SYSTEM
        # ========================================================

        section4 = tk.LabelFrame(
            settings_frame,
            text="🖥️ System",
            font=FONTS["heading"],
            bg=COLORS["bg"],
            fg=COLORS["text_primary"],
            padx=15,
            pady=10
        )

        section4.pack(
            fill=tk.X
        )

        row6 = tk.Frame(
            section4,
            bg=COLORS["bg"]
        )

        row6.pack(
            fill=tk.X,
            pady=5
        )

        tk.Button(
            row6,
            text="🔄 Reset All Data (Clear Sales)",
            font=FONTS["normal"],
            bg=COLORS["accent_red"],
            fg="white",
            padx=15,
            pady=5,
            command=self.clear_sales_data
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        tk.Button(
            row6,
            text="🏪 Manage Branches",
            font=FONTS["normal"],
            bg=COLORS["accent_purple"],
            fg="white",
            padx=15,
            pady=5,
            command=self.open_branches
        ).pack(
            side=tk.LEFT,
            padx=5
        )

        self.status_label = tk.Label(
            self.main_frame,
            text="✅ Ready",
            font=FONTS["small"],
            bg=COLORS["bg"],
            fg=COLORS["accent_green"]
        )

        self.status_label.pack(
            anchor="w",
            pady=(15, 0)
        )

    # ============================================================
    # SETTINGS FUNCTIONS
    # ============================================================

    def save_store_name(self):

        name = self.store_name_entry.get().strip()

        if name:
            try:
                set_store_name(name)
                messagebox.showinfo(
                    "Success",
                    f"Store name updated to: {name}"
                )
                self.status_label.config(
                    text="✅ Store name saved!",
                    fg=COLORS["accent_green"]
                )
            except Exception as e:
                messagebox.showerror("Error", f"Could not save store name:\n{e}")

        else:

            messagebox.showerror(
                "Error",
                "Store name cannot be empty!"
            )

    def save_tax_rate(self):

        try:

            tax = float(
                self.tax_entry.get().strip()
            )

            if tax < 0 or tax > 100:

                messagebox.showerror(
                    "Error",
                    "Tax rate must be between 0 and 100!"
                )

                return

            messagebox.showinfo(
                "Success",
                f"Tax rate updated to: {tax}%"
            )

            self.status_label.config(
                text=f"✅ Tax rate set to {tax}%",
                fg=COLORS["accent_green"]
            )

        except ValueError:

            messagebox.showerror(
                "Error",
                "Please enter a valid number!"
            )

    def export_sales_csv(self):

        try:

            with open(
                "sales_export.csv",
                "w",
                newline="",
                encoding="utf-8"
            ) as f:

                writer = csv.writer(f)

                writer.writerow([
                    "Receipt #",
                    "Date",
                    "Total",
                    "Payment",
                    "Cashier"
                ])

                conn = sqlite3.connect(
                    "pos_store.db"
                )

                cursor = conn.cursor()

                cursor.execute("""
                    SELECT
                        id,
                        timestamp,
                        total_amount,
                        payment_type,
                        cashier
                    FROM sales_history
                    ORDER BY id DESC
                """)

                rows = cursor.fetchall()

                conn.close()

                for row in rows:

                    writer.writerow([
                        row[0],
                        row[1],
                        row[2],
                        row[3],
                        row[4]
                    ])

            messagebox.showinfo(
                "Success",
                "Sales data exported to 'sales_export.csv'"
            )

            self.status_label.config(
                text="✅ Sales exported!",
                fg=COLORS["accent_green"]
            )

        except Exception as e:

            messagebox.showerror(
                "Error",
                f"Failed to export: {str(e)}"
            )

    def export_products_csv(self):

        try:

            with open(
                "products_export.csv",
                "w",
                newline="",
                encoding="utf-8"
            ) as f:

                writer = csv.writer(f)

                writer.writerow([
                    "Barcode",
                    "Description",
                    "Price",
                    "Stock"
                ])

                conn = sqlite3.connect(
                    "pos_store.db"
                )

                cursor = conn.cursor()

                cursor.execute("""
                    SELECT
                        barcode,
                        description,
                        selling_price,
                        soh
                    FROM products
                    ORDER BY description
                """)

                rows = cursor.fetchall()

                conn.close()

                for row in rows:

                    writer.writerow([
                        row[0],
                        row[1],
                        row[2],
                        row[3]
                    ])

            messagebox.showinfo(
                "Success",
                "Products exported to 'products_export.csv'"
            )

            self.status_label.config(
                text="✅ Products exported!",
                fg=COLORS["accent_green"]
            )

        except Exception as e:

            messagebox.showerror(
                "Error",
                f"Failed to export: {str(e)}"
            )

    def backup_database(self):

        try:

            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            backup_name = (
                f"pos_store_backup_{timestamp}.db"
            )

            if os.path.exists(
                "pos_store.db"
            ):

                shutil.copy2(
                    "pos_store.db",
                    backup_name
                )

                messagebox.showinfo(
                    "Success",
                    f"Database backed up to:\n{backup_name}"
                )

                self.status_label.config(
                    text=f"✅ Backup created: {backup_name}",
                    fg=COLORS["accent_green"]
                )

            else:

                messagebox.showerror(
                    "Error",
                    "Database file not found!"
                )

        except Exception as e:

            messagebox.showerror(
                "Error",
                f"Backup failed: {str(e)}"
            )

    def vacuum_database(self):

        try:

            conn = sqlite3.connect(
                "pos_store.db"
            )

            conn.execute(
                "VACUUM"
            )

            conn.close()

            db_size = 0

            if os.path.exists(
                "pos_store.db"
            ):

                db_size = (
                    os.path.getsize(
                        "pos_store.db"
                    ) / 1024
                )

            messagebox.showinfo(
                "Success",
                f"Database compacted!\n"
                f"New size: {db_size:.2f} KB"
            )

            self.status_label.config(
                text="✅ Database compacted!",
                fg=COLORS["accent_green"]
            )

        except Exception as e:

            messagebox.showerror(
                "Error",
                f"Failed to compact database: {str(e)}"
            )

    def clear_sales_data(self):

        if messagebox.askyesno(
            "⚠️ Warning",
            "This will DELETE ALL sales data!\n\n"
            "Are you absolutely sure you want to continue?"
        ):

            if messagebox.askyesno(
                "⚠️ Final Confirmation",
                "This action CANNOT be undone!\n\n"
                "Delete all sales data?"
            ):

                try:

                    conn = sqlite3.connect(
                        "pos_store.db"
                    )

                    conn.execute(
                        "DELETE FROM sales_history"
                    )

                    conn.execute(
                        "DELETE FROM sale_items"
                    )

                    conn.commit()
                    conn.close()

                    messagebox.showinfo(
                        "Success",
                        "All sales data has been cleared!"
                    )

                    self.status_label.config(
                        text="✅ Sales data cleared",
                        fg=COLORS["accent_green"]
                    )

                except Exception as e:

                    messagebox.showerror(
                        "Error",
                        f"Failed to clear data: {str(e)}"
                    )

    # ============================================================
    # BRANCH MANAGER
    # ============================================================

    def open_branches(self):

        try:

            from branches import BranchManager

            branch_window = BranchManager(
                self,
                self.admin_user
            )

            branch_window.transient(
                self
            )

            branch_window.focus_force()

            def on_close():

                try:
                    branch_window.grab_release()
                except tk.TclError:
                    _bkpos_logger.warning("Suppressed exception in ui/admin_portal.py", exc_info=exc)

                branch_window.destroy()

                self.deiconify()
                self.lift()
                self.focus_force()

            branch_window.protocol(
                "WM_DELETE_WINDOW",
                on_close
            )

        except ImportError as e:

            messagebox.showerror(
                "Branch Manager Error",
                "Could not load the Branch Manager.\n\n"
                "Make sure branches.py exists in the same "
                "folder as admin_portal.py.\n\n"
                f"Error: {e}",
                parent=self
            )

        except Exception as e:

            messagebox.showerror(
                "Branch Manager Error",
                f"Could not open Branch Manager.\n\n{e}",
                parent=self
            )

    # ============================================================
    # PERMISSIONS
    # ============================================================

    def open_permissions(self):

        try:

            from permissions import PermissionsWindow

            PermissionsWindow(
                self,
                self.admin_user
            )

        except ImportError as e:

            messagebox.showerror(
                "Permissions Error",
                "Could not load permissions.py.\n\n"
                f"Error: {e}",
                parent=self
            )

        except Exception as e:

            messagebox.showerror(
                "Permissions Error",
                f"Could not open Permissions window.\n\n{e}",
                parent=self
            )

    # ============================================================
    # LOGOUT
    # ============================================================

    def logout(self):

        if messagebox.askyesno(
            "Logout",
            "Are you sure you want to logout?"
        ):

            self.destroy()

    # ============================================================
    # HELPER - POPUP
    # ============================================================

    def create_popup(
        self,
        title,
        width,
        height
    ):

        popup = tk.Toplevel(
            self
        )

        popup.title(title)

        popup.geometry(
            f"{width}x{height}"
        )

        popup.configure(
            bg=COLORS["bg"]
        )

        popup.transient(
            self
        )

        popup.grab_set()

        popup.resizable(
            False,
            False
        )

        # --------------------------------------------------------
        # Center popup
        # --------------------------------------------------------

        self.update_idletasks()

        x = (
            self.winfo_x()
            + (self.winfo_width() // 2)
            - (width // 2)
        )

        y = (
            self.winfo_y()
            + (self.winfo_height() // 2)
            - (height // 2)
        )

        popup.geometry(
            f"{width}x{height}+{x}+{y}"
        )

        # --------------------------------------------------------
        # Header
        # --------------------------------------------------------

        header = tk.Frame(
            popup,
            bg=COLORS["header"],
            height=35
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
            text=title,
            font=("Segoe UI", 11, "bold"),
            fg="white",
            bg=COLORS["header"]
        ).pack(
            pady=5
        )

        return popup


# ============================================================
# END OF ADMIN PORTAL
# ============================================================
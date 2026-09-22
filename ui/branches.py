from core.logger import logger as _bkpos_logger
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox


# ============================================================
# DATABASE
# ============================================================

from core.config import DB_PATH
DB_NAME = DB_PATH


class BranchManager(tk.Toplevel):

    def __init__(self, parent, admin_user=None):
        super().__init__(parent)

        self.parent = parent
        self.admin_user = admin_user

        # ----------------------------------------------------
        # WINDOW
        # ----------------------------------------------------

        self.title("Manage Branches")
        self.geometry("1150x700")
        self.minsize(1000, 620)
        self.configure(bg="#f0f4f8")

        self.transient(parent)
        self.grab_set()

        self.protocol(
            "WM_DELETE_WINDOW",
            self.close_window
        )

        # ----------------------------------------------------
        # DATABASE
        # ----------------------------------------------------

        self.create_database()

        # ----------------------------------------------------
        # USER INTERFACE
        # ----------------------------------------------------

        self.create_widgets()

        # ----------------------------------------------------
        # LOAD DATA
        # ----------------------------------------------------

        self.load_branches()
        self.load_users()

    # ========================================================
    # DATABASE CONNECTION
    # ========================================================

    def get_connection(self):
        """
        Create a connection to the POS database.
        """

        conn = sqlite3.connect(DB_NAME)

        # Foreign keys must be enabled for every connection.
        conn.execute("PRAGMA foreign_keys = ON")

        return conn

    # ========================================================
    # CREATE / UPGRADE DATABASE
    # ========================================================

    def create_database(self):

        try:

            conn = self.get_connection()
            cursor = conn.cursor()

            # ------------------------------------------------
            # BRANCHES TABLE
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
            # CHECK WHETHER USERS TABLE EXISTS
            # ------------------------------------------------

            cursor.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                AND name = 'users'
            """)

            users_exists = cursor.fetchone() is not None

            if users_exists:

                # --------------------------------------------
                # CHECK USERS COLUMNS
                # --------------------------------------------

                cursor.execute("PRAGMA table_info(users)")

                columns = [
                    row[1]
                    for row in cursor.fetchall()
                ]

                # --------------------------------------------
                # ADD branch_id IF MISSING
                # --------------------------------------------

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
                f"Could not prepare the database.\n\n{e}",
                parent=self
            )

    # ========================================================
    # USER INTERFACE
    # ========================================================

    def create_widgets(self):

        # ====================================================
        # HEADER
        # ====================================================

        header = tk.Frame(
            self,
            bg="#805ad5",
            height=60
        )

        header.pack(
            fill=tk.X
        )

        header.pack_propagate(False)

        tk.Label(
            header,
            text="🏪 Manage Branches",
            font=("Segoe UI", 17, "bold"),
            bg="#805ad5",
            fg="white"
        ).pack(
            side=tk.LEFT,
            padx=20
        )

        tk.Button(
            header,
            text="✕",
            font=("Segoe UI", 12, "bold"),
            bg="#805ad5",
            fg="white",
            bd=0,
            activebackground="#e53e3e",
            activeforeground="white",
            command=self.close_window
        ).pack(
            side=tk.RIGHT,
            padx=15
        )

        # ====================================================
        # MAIN NOTEBOOK
        # ====================================================

        notebook_frame = tk.Frame(
            self,
            bg="#f0f4f8"
        )

        notebook_frame.pack(
            fill=tk.BOTH,
            expand=True,
            padx=15,
            pady=15
        )

        self.notebook = ttk.Notebook(
            notebook_frame
        )

        self.notebook.pack(
            fill=tk.BOTH,
            expand=True
        )

        # ----------------------------------------------------
        # BRANCH TAB
        # ----------------------------------------------------

        self.branch_tab = tk.Frame(
            self.notebook,
            bg="#f0f4f8"
        )

        self.notebook.add(
            self.branch_tab,
            text="  🏪 Branches  "
        )

        # ----------------------------------------------------
        # ASSIGN USERS TAB
        # ----------------------------------------------------

        self.user_tab = tk.Frame(
            self.notebook,
            bg="#f0f4f8"
        )

        self.notebook.add(
            self.user_tab,
            text="  👤 Assign Users  "
        )

        self.create_branch_tab()
        self.create_user_tab()

    # ========================================================
    # BRANCH TAB
    # ========================================================

    def create_branch_tab(self):

        # ====================================================
        # FORM
        # ====================================================

        form = tk.LabelFrame(
            self.branch_tab,
            text="Branch Information",
            font=("Segoe UI", 11, "bold"),
            bg="#f0f4f8",
            fg="#1a202c",
            padx=15,
            pady=15
        )

        form.pack(
            fill=tk.X,
            padx=10,
            pady=10
        )

        form.columnconfigure(
            1,
            weight=1
        )

        form.columnconfigure(
            3,
            weight=1
        )

        # ----------------------------------------------------
        # BRANCH NAME
        # ----------------------------------------------------

        tk.Label(
            form,
            text="Branch Name:",
            font=("Segoe UI", 10, "bold"),
            bg="#f0f4f8",
            fg="#1a202c"
        ).grid(
            row=0,
            column=0,
            padx=5,
            pady=7,
            sticky="w"
        )

        self.name_entry = tk.Entry(
            form,
            font=("Segoe UI", 10)
        )

        self.name_entry.grid(
            row=0,
            column=1,
            padx=5,
            pady=7,
            sticky="ew"
        )

        # ----------------------------------------------------
        # BRANCH CODE
        # ----------------------------------------------------

        tk.Label(
            form,
            text="Branch Code:",
            font=("Segoe UI", 10, "bold"),
            bg="#f0f4f8",
            fg="#1a202c"
        ).grid(
            row=0,
            column=2,
            padx=15,
            pady=7,
            sticky="w"
        )

        self.code_entry = tk.Entry(
            form,
            font=("Segoe UI", 10)
        )

        self.code_entry.grid(
            row=0,
            column=3,
            padx=5,
            pady=7,
            sticky="ew"
        )

        # ----------------------------------------------------
        # ADDRESS
        # ----------------------------------------------------

        tk.Label(
            form,
            text="Address:",
            font=("Segoe UI", 10, "bold"),
            bg="#f0f4f8",
            fg="#1a202c"
        ).grid(
            row=1,
            column=0,
            padx=5,
            pady=7,
            sticky="w"
        )

        self.address_entry = tk.Entry(
            form,
            font=("Segoe UI", 10)
        )

        self.address_entry.grid(
            row=1,
            column=1,
            padx=5,
            pady=7,
            sticky="ew"
        )

        # ----------------------------------------------------
        # PHONE
        # ----------------------------------------------------

        tk.Label(
            form,
            text="Phone:",
            font=("Segoe UI", 10, "bold"),
            bg="#f0f4f8",
            fg="#1a202c"
        ).grid(
            row=1,
            column=2,
            padx=15,
            pady=7,
            sticky="w"
        )

        self.phone_entry = tk.Entry(
            form,
            font=("Segoe UI", 10)
        )

        self.phone_entry.grid(
            row=1,
            column=3,
            padx=5,
            pady=7,
            sticky="ew"
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        tk.Label(
            form,
            text="Status:",
            font=("Segoe UI", 10, "bold"),
            bg="#f0f4f8",
            fg="#1a202c"
        ).grid(
            row=2,
            column=0,
            padx=5,
            pady=7,
            sticky="w"
        )

        self.status_combo = ttk.Combobox(
            form,
            values=[
                "Active",
                "Inactive"
            ],
            state="readonly",
            font=("Segoe UI", 10)
        )

        self.status_combo.set("Active")

        self.status_combo.grid(
            row=2,
            column=1,
            padx=5,
            pady=7,
            sticky="w"
        )

        # ====================================================
        # BUTTONS
        # ====================================================

        button_frame = tk.Frame(
            form,
            bg="#f0f4f8"
        )

        button_frame.grid(
            row=3,
            column=0,
            columnspan=4,
            pady=(15, 5)
        )

        self.make_button(
            button_frame,
            "➕ Add Branch",
            "#38a169",
            "#2f855a",
            self.add_branch
        )

        self.make_button(
            button_frame,
            "✏️ Update",
            "#3182ce",
            "#2c5282",
            self.update_branch
        )

        self.make_button(
            button_frame,
            "🗑️ Delete",
            "#e53e3e",
            "#c53030",
            self.delete_branch
        )

        self.make_button(
            button_frame,
            "🧹 Clear",
            "#718096",
            "#4a5568",
            self.clear_fields
        )

        self.make_button(
            button_frame,
            "🔄 Refresh",
            "#805ad5",
            "#6b46c1",
            self.load_branches
        )

        # ====================================================
        # TABLE LABEL
        # ====================================================

        tk.Label(
            self.branch_tab,
            text="Registered Branches",
            font=("Segoe UI", 12, "bold"),
            bg="#f0f4f8",
            fg="#1a202c"
        ).pack(
            anchor="w",
            padx=10,
            pady=(0, 5)
        )

        # ====================================================
        # TABLE FRAME
        # ====================================================

        table_frame = tk.Frame(
            self.branch_tab,
            bg="white",
            bd=1,
            relief=tk.SOLID
        )

        table_frame.pack(
            fill=tk.BOTH,
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        columns = (
            "id",
            "name",
            "code",
            "address",
            "phone",
            "status",
            "users"
        )

        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse"
        )

        # ----------------------------------------------------
        # HEADINGS
        # ----------------------------------------------------

        headings = {
            "id": "ID",
            "name": "Branch Name",
            "code": "Branch Code",
            "address": "Address",
            "phone": "Phone",
            "status": "Status",
            "users": "Users"
        }

        for column, heading in headings.items():

            self.tree.heading(
                column,
                text=heading
            )

        # ----------------------------------------------------
        # COLUMNS
        # ----------------------------------------------------

        self.tree.column(
            "id",
            width=55,
            minwidth=45,
            anchor="center"
        )

        self.tree.column(
            "name",
            width=180,
            minwidth=130
        )

        self.tree.column(
            "code",
            width=110,
            minwidth=90,
            anchor="center"
        )

        self.tree.column(
            "address",
            width=250,
            minwidth=150
        )

        self.tree.column(
            "phone",
            width=130,
            minwidth=100,
            anchor="center"
        )

        self.tree.column(
            "status",
            width=90,
            minwidth=70,
            anchor="center"
        )

        self.tree.column(
            "users",
            width=80,
            minwidth=60,
            anchor="center"
        )

        # ----------------------------------------------------
        # SCROLLBARS
        # ----------------------------------------------------

        vertical_scrollbar = ttk.Scrollbar(
            table_frame,
            orient=tk.VERTICAL,
            command=self.tree.yview
        )

        horizontal_scrollbar = ttk.Scrollbar(
            table_frame,
            orient=tk.HORIZONTAL,
            command=self.tree.xview
        )

        self.tree.configure(
            yscrollcommand=vertical_scrollbar.set,
            xscrollcommand=horizontal_scrollbar.set
        )

        vertical_scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y
        )

        horizontal_scrollbar.pack(
            side=tk.BOTTOM,
            fill=tk.X
        )

        self.tree.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True
        )

        self.tree.bind(
            "<<TreeviewSelect>>",
            self.select_branch
        )

        self.tree.bind(
            "<Double-1>",
            self.select_branch
        )

    # ========================================================
    # USER ASSIGNMENT TAB
    # ========================================================

    def create_user_tab(self):

        # ====================================================
        # TOP INFORMATION
        # ====================================================

        info = tk.LabelFrame(
            self.user_tab,
            text="Assign User to Branch",
            font=("Segoe UI", 11, "bold"),
            bg="#f0f4f8",
            fg="#1a202c",
            padx=15,
            pady=15
        )

        info.pack(
            fill=tk.X,
            padx=10,
            pady=10
        )

        info.columnconfigure(
            1,
            weight=1
        )

        # ----------------------------------------------------
        # USER
        # ----------------------------------------------------

        tk.Label(
            info,
            text="User:",
            font=("Segoe UI", 10, "bold"),
            bg="#f0f4f8",
            fg="#1a202c"
        ).grid(
            row=0,
            column=0,
            padx=5,
            pady=7,
            sticky="w"
        )

        self.user_combo = ttk.Combobox(
            info,
            state="readonly",
            font=("Segoe UI", 10),
            width=45
        )

        self.user_combo.grid(
            row=0,
            column=1,
            padx=5,
            pady=7,
            sticky="ew"
        )

        # ----------------------------------------------------
        # BRANCH
        # ----------------------------------------------------

        tk.Label(
            info,
            text="Branch:",
            font=("Segoe UI", 10, "bold"),
            bg="#f0f4f8",
            fg="#1a202c"
        ).grid(
            row=1,
            column=0,
            padx=5,
            pady=7,
            sticky="w"
        )

        self.user_branch_combo = ttk.Combobox(
            info,
            state="readonly",
            font=("Segoe UI", 10),
            width=45
        )

        self.user_branch_combo.grid(
            row=1,
            column=1,
            padx=5,
            pady=7,
            sticky="ew"
        )

        # ----------------------------------------------------
        # BUTTONS
        # ----------------------------------------------------

        button_frame = tk.Frame(
            info,
            bg="#f0f4f8"
        )

        button_frame.grid(
            row=2,
            column=0,
            columnspan=2,
            pady=(15, 5)
        )

        self.make_button(
            button_frame,
            "🔗 Assign Branch",
            "#3182ce",
            "#2c5282",
            self.assign_user_to_branch
        )

        self.make_button(
            button_frame,
            "🚫 Remove Assignment",
            "#e53e3e",
            "#c53030",
            self.remove_user_from_branch
        )

        self.make_button(
            button_frame,
            "🔄 Refresh Users",
            "#805ad5",
            "#6b46c1",
            self.load_users
        )

        # ====================================================
        # USER TABLE
        # ====================================================

        tk.Label(
            self.user_tab,
            text="Users and Branch Assignments",
            font=("Segoe UI", 12, "bold"),
            bg="#f0f4f8",
            fg="#1a202c"
        ).pack(
            anchor="w",
            padx=10,
            pady=(5, 5)
        )

        table_frame = tk.Frame(
            self.user_tab,
            bg="white",
            bd=1,
            relief=tk.SOLID
        )

        table_frame.pack(
            fill=tk.BOTH,
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        columns = (
            "id",
            "username",
            "name",
            "role",
            "branch"
        )

        self.user_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse"
        )

        headings = {
            "id": "ID",
            "username": "Username",
            "name": "Full Name",
            "role": "Role",
            "branch": "Branch"
        }

        for column, heading in headings.items():

            self.user_tree.heading(
                column,
                text=heading
            )

        self.user_tree.column(
            "id",
            width=60,
            anchor="center"
        )

        self.user_tree.column(
            "username",
            width=180
        )

        self.user_tree.column(
            "name",
            width=220
        )

        self.user_tree.column(
            "role",
            width=130,
            anchor="center"
        )

        self.user_tree.column(
            "branch",
            width=250
        )

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient=tk.VERTICAL,
            command=self.user_tree.yview
        )

        self.user_tree.configure(
            yscrollcommand=scrollbar.set
        )

        scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y
        )

        self.user_tree.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True
        )

        self.user_tree.bind(
            "<<TreeviewSelect>>",
            self.select_user
        )

    # ========================================================
    # BUTTON CREATOR
    # ========================================================

    def make_button(
        self,
        parent,
        text,
        bg,
        active_bg,
        command
    ):

        button = tk.Button(
            parent,
            text=text,
            font=("Segoe UI", 10, "bold"),
            bg=bg,
            fg="white",
            activebackground=active_bg,
            activeforeground="white",
            padx=16,
            pady=7,
            bd=0,
            cursor="hand2",
            command=command
        )

        button.pack(
            side=tk.LEFT,
            padx=5
        )

        return button

    # ========================================================
    # LOAD BRANCHES
    # ========================================================

    def load_branches(self):

        if not hasattr(self, "tree"):
            return

        for item in self.tree.get_children():
            self.tree.delete(item)

        try:

            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    b.id,
                    b.branch_name,
                    b.branch_code,
                    b.address,
                    b.phone,
                    b.status,
                    COUNT(u.id)
                FROM branches b
                LEFT JOIN users u
                    ON u.branch_id = b.id
                GROUP BY
                    b.id,
                    b.branch_name,
                    b.branch_code,
                    b.address,
                    b.phone,
                    b.status
                ORDER BY b.id ASC
            """)

            branches = cursor.fetchall()

            conn.close()

            for branch in branches:

                self.tree.insert(
                    "",
                    tk.END,
                    values=branch
                )

            # Update branch dropdown too.
            self.update_branch_combo()

        except sqlite3.OperationalError as e:

            # This happens if the existing users table does not
            # have branch_id for some unexpected reason.

            messagebox.showerror(
                "Database Error",
                f"Could not load branches.\n\n{e}",
                parent=self
            )

        except sqlite3.Error as e:

            messagebox.showerror(
                "Database Error",
                f"Could not load branches.\n\n{e}",
                parent=self
            )

    # ========================================================
    # UPDATE BRANCH COMBO
    # ========================================================

    def update_branch_combo(self):

        try:

            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, branch_name, branch_code
                FROM branches
                WHERE status = 'Active'
                ORDER BY branch_name
            """)

            branches = cursor.fetchall()

            conn.close()

            self.branch_map = {}

            values = []

            for branch_id, name, code in branches:

                display = f"{name} ({code})"

                values.append(display)

                self.branch_map[display] = branch_id

            self.user_branch_combo["values"] = values

        except sqlite3.Error as e:

            messagebox.showerror(
                "Database Error",
                f"Could not load branch list.\n\n{e}",
                parent=self
            )

    # ========================================================
    # LOAD USERS
    # ========================================================

    def load_users(self):

        if not hasattr(self, "user_tree"):
            return

        for item in self.user_tree.get_children():
            self.user_tree.delete(item)

        try:

            conn = self.get_connection()
            cursor = conn.cursor()

            # ------------------------------------------------
            # CHECK USERS TABLE
            # ------------------------------------------------

            cursor.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                AND name = 'users'
            """)

            if cursor.fetchone() is None:

                conn.close()

                self.user_combo["values"] = []

                messagebox.showwarning(
                    "Users Table Not Found",
                    "The users table does not exist yet.\n\n"
                    "Create your users/user-management system first, "
                    "then users can be assigned to branches.",
                    parent=self
                )

                return

            # ------------------------------------------------
            # GET USER COLUMNS
            # ------------------------------------------------

            cursor.execute(
                "PRAGMA table_info(users)"
            )

            columns = [
                row[1]
                for row in cursor.fetchall()
            ]

            # ------------------------------------------------
            # FIND USERNAME COLUMN
            # ------------------------------------------------

            if "username" not in columns:

                conn.close()

                messagebox.showerror(
                    "Database Error",
                    "The users table does not contain a 'username' column.",
                    parent=self
                )

                return

            # ------------------------------------------------
            # FIND FULL NAME COLUMN
            # ------------------------------------------------

            if "full_name" in columns:
                name_expression = "u.full_name"

            elif "name" in columns:
                name_expression = "u.name"

            else:
                name_expression = "''"

            # ------------------------------------------------
            # FIND ROLE COLUMN
            # ------------------------------------------------

            if "role" in columns:
                role_expression = "u.role"

            else:
                role_expression = "''"

            # ------------------------------------------------
            # USER TABLE
            # ------------------------------------------------

            if "branch_id" in columns:

                cursor.execute(f"""
                    SELECT
                        u.id,
                        u.username,
                        {name_expression},
                        {role_expression},
                        COALESCE(
                            b.branch_name || ' (' ||
                            b.branch_code || ')',
                            'Not Assigned'
                        )
                    FROM users u
                    LEFT JOIN branches b
                        ON b.id = u.branch_id
                    ORDER BY u.username
                """)

            else:

                # This should normally not happen because
                # create_database() adds branch_id.

                cursor.execute(f"""
                    SELECT
                        u.id,
                        u.username,
                        {name_expression},
                        {role_expression},
                        'Not Assigned'
                    FROM users u
                    ORDER BY u.username
                """)

            users = cursor.fetchall()

            conn.close()

            # ------------------------------------------------
            # POPULATE USER TABLE
            # ------------------------------------------------

            self.user_map = {}

            combo_values = []

            for user in users:

                user_id = user[0]
                username = user[1]
                full_name = user[2] or ""
                role = user[3] or ""

                display = username

                if full_name:
                    display += f" - {full_name}"

                if role:
                    display += f" [{role}]"

                self.user_map[display] = user_id

                combo_values.append(display)

                self.user_tree.insert(
                    "",
                    tk.END,
                    values=user
                )

            self.user_combo["values"] = combo_values

            if combo_values:

                self.user_combo.current(0)

            else:

                self.user_combo.set("")

        except sqlite3.Error as e:

            messagebox.showerror(
                "Database Error",
                f"Could not load users.\n\n{e}",
                parent=self
            )

    # ========================================================
    # SELECT USER
    # ========================================================

    def select_user(self, event=None):

        selected = self.user_tree.selection()

        if not selected:
            return

        item = selected[0]

        values = self.user_tree.item(
            item,
            "values"
        )

        if not values:
            return

        username = values[1]
        current_branch = values[4]

        # ----------------------------------------------------
        # Select matching user
        # ----------------------------------------------------

        for display, user_id in self.user_map.items():

            if display.startswith(
                str(username)
            ):

                self.user_combo.set(
                    display
                )

                break

        # ----------------------------------------------------
        # Select current branch
        # ----------------------------------------------------

        if current_branch != "Not Assigned":

            for display in self.branch_map:

                if display == current_branch:

                    self.user_branch_combo.set(
                        display
                    )

                    break

        else:

            self.user_branch_combo.set("")

    # ========================================================
    # ASSIGN USER TO BRANCH
    # ========================================================

    def assign_user_to_branch(self):

        user_display = self.user_combo.get().strip()
        branch_display = self.user_branch_combo.get().strip()

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if not user_display:

            messagebox.showerror(
                "Missing User",
                "Please select a user.",
                parent=self
            )

            return

        if not branch_display:

            messagebox.showerror(
                "Missing Branch",
                "Please select a branch.",
                parent=self
            )

            return

        if user_display not in self.user_map:

            messagebox.showerror(
                "Invalid User",
                "The selected user could not be found.",
                parent=self
            )

            return

        if branch_display not in self.branch_map:

            messagebox.showerror(
                "Invalid Branch",
                "The selected branch could not be found.",
                parent=self
            )

            return

        user_id = self.user_map[user_display]
        branch_id = self.branch_map[branch_display]

        # ----------------------------------------------------
        # UPDATE
        # ----------------------------------------------------

        try:

            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE users
                SET branch_id = ?
                WHERE id = ?
            """, (
                branch_id,
                user_id
            ))

            if cursor.rowcount == 0:

                conn.rollback()
                conn.close()

                messagebox.showerror(
                    "User Not Found",
                    "The selected user no longer exists.",
                    parent=self
                )

                self.load_users()

                return

            conn.commit()
            conn.close()

            messagebox.showinfo(
                "Assignment Successful",
                f"{user_display}\n\n"
                f"has been assigned to:\n"
                f"{branch_display}",
                parent=self
            )

            self.load_users()
            self.load_branches()

        except sqlite3.Error as e:

            messagebox.showerror(
                "Database Error",
                f"Could not assign the user to the branch.\n\n{e}",
                parent=self
            )

    # ========================================================
    # REMOVE USER FROM BRANCH
    # ========================================================

    def remove_user_from_branch(self):

        user_display = self.user_combo.get().strip()

        if not user_display:

            messagebox.showerror(
                "Missing User",
                "Please select a user first.",
                parent=self
            )

            return

        if user_display not in self.user_map:

            messagebox.showerror(
                "Invalid User",
                "The selected user could not be found.",
                parent=self
            )

            return

        user_id = self.user_map[user_display]

        answer = messagebox.askyesno(
            "Remove Branch Assignment",
            f"Remove the branch assignment from:\n\n"
            f"{user_display}?",
            parent=self
        )

        if not answer:
            return

        try:

            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE users
                SET branch_id = NULL
                WHERE id = ?
            """, (
                user_id,
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo(
                "Assignment Removed",
                f"{user_display} is no longer assigned to a branch.",
                parent=self
            )

            self.user_branch_combo.set("")

            self.load_users()
            self.load_branches()

        except sqlite3.Error as e:

            messagebox.showerror(
                "Database Error",
                f"Could not remove the branch assignment.\n\n{e}",
                parent=self
            )

    # ========================================================
    # ADD BRANCH
    # ========================================================

    def add_branch(self):

        name = self.name_entry.get().strip()
        code = self.code_entry.get().strip().upper()
        address = self.address_entry.get().strip()
        phone = self.phone_entry.get().strip()
        status = self.status_combo.get().strip()

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if not name:

            messagebox.showerror(
                "Missing Information",
                "Please enter the branch name.",
                parent=self
            )

            self.name_entry.focus_set()

            return

        if not code:

            messagebox.showerror(
                "Missing Information",
                "Please enter the branch code.",
                parent=self
            )

            self.code_entry.focus_set()

            return

        if not status:
            status = "Active"

        # ----------------------------------------------------
        # INSERT
        # ----------------------------------------------------

        try:

            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO branches
                (
                    branch_name,
                    branch_code,
                    address,
                    phone,
                    status
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                name,
                code,
                address,
                phone,
                status
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo(
                "Success",
                f"Branch '{name}' was added successfully!",
                parent=self
            )

            self.clear_fields()

            self.load_branches()
            self.load_users()

        except sqlite3.IntegrityError:

            messagebox.showerror(
                "Duplicate Branch Code",
                f"The branch code '{code}' already exists.\n\n"
                "Please use a different branch code.",
                parent=self
            )

        except sqlite3.Error as e:

            messagebox.showerror(
                "Database Error",
                f"Could not add the branch.\n\n{e}",
                parent=self
            )

    # ========================================================
    # SELECT BRANCH
    # ========================================================

    def select_branch(self, event=None):

        selected = self.tree.selection()

        if not selected:
            return

        item = selected[0]

        values = self.tree.item(
            item,
            "values"
        )

        if not values:
            return

        self.name_entry.delete(
            0,
            tk.END
        )

        self.name_entry.insert(
            0,
            values[1]
        )

        self.code_entry.delete(
            0,
            tk.END
        )

        self.code_entry.insert(
            0,
            values[2]
        )

        self.address_entry.delete(
            0,
            tk.END
        )

        self.address_entry.insert(
            0,
            values[3]
        )

        self.phone_entry.delete(
            0,
            tk.END
        )

        self.phone_entry.insert(
            0,
            values[4]
        )

        self.status_combo.set(
            values[5] if values[5] else "Active"
        )

    # ========================================================
    # UPDATE BRANCH
    # ========================================================

    def update_branch(self):

        selected = self.tree.selection()

        if not selected:

            messagebox.showerror(
                "No Branch Selected",
                "Please select a branch from the table first.",
                parent=self
            )

            return

        item = selected[0]

        values = self.tree.item(
            item,
            "values"
        )

        if not values:
            return

        branch_id = values[0]

        name = self.name_entry.get().strip()
        code = self.code_entry.get().strip().upper()
        address = self.address_entry.get().strip()
        phone = self.phone_entry.get().strip()
        status = self.status_combo.get().strip()

        if not name:

            messagebox.showerror(
                "Missing Information",
                "Branch name cannot be empty.",
                parent=self
            )

            self.name_entry.focus_set()

            return

        if not code:

            messagebox.showerror(
                "Missing Information",
                "Branch code cannot be empty.",
                parent=self
            )

            self.code_entry.focus_set()

            return

        if not status:
            status = "Active"

        try:

            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE branches
                SET
                    branch_name = ?,
                    branch_code = ?,
                    address = ?,
                    phone = ?,
                    status = ?
                WHERE id = ?
            """, (
                name,
                code,
                address,
                phone,
                status,
                branch_id
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo(
                "Success",
                f"Branch '{name}' was updated successfully!",
                parent=self
            )

            self.clear_fields()

            self.load_branches()
            self.load_users()

        except sqlite3.IntegrityError:

            messagebox.showerror(
                "Duplicate Branch Code",
                f"The branch code '{code}' is already being used.\n\n"
                "Please choose another code.",
                parent=self
            )

        except sqlite3.Error as e:

            messagebox.showerror(
                "Database Error",
                f"Could not update the branch.\n\n{e}",
                parent=self
            )

    # ========================================================
    # DELETE BRANCH
    # ========================================================

    def delete_branch(self):

        selected = self.tree.selection()

        if not selected:

            messagebox.showerror(
                "No Branch Selected",
                "Please select a branch from the table first.",
                parent=self
            )

            return

        item = selected[0]

        values = self.tree.item(
            item,
            "values"
        )

        if not values:
            return

        branch_id = values[0]
        branch_name = values[1]
        user_count = int(values[6])

        # ----------------------------------------------------
        # IMPORTANT:
        # Don't allow a branch with users to be deleted.
        # ----------------------------------------------------

        if user_count > 0:

            messagebox.showwarning(
                "Branch Has Users",
                f"'{branch_name}' currently has "
                f"{user_count} user(s) assigned to it.\n\n"
                "Remove those user assignments first "
                "before deleting the branch.",
                parent=self
            )

            return

        answer = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete this branch?\n\n"
            f"Branch: {branch_name}\n"
            f"ID: {branch_id}",
            parent=self
        )

        if not answer:
            return

        try:

            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM branches WHERE id = ?",
                (branch_id,)
            )

            conn.commit()
            conn.close()

            messagebox.showinfo(
                "Deleted",
                f"Branch '{branch_name}' was deleted successfully.",
                parent=self
            )

            self.clear_fields()

            self.load_branches()
            self.load_users()

        except sqlite3.Error as e:

            messagebox.showerror(
                "Database Error",
                f"Could not delete the branch.\n\n{e}",
                parent=self
            )

    # ========================================================
    # CLEAR BRANCH FIELDS
    # ========================================================

    def clear_fields(self):

        self.name_entry.delete(
            0,
            tk.END
        )

        self.code_entry.delete(
            0,
            tk.END
        )

        self.address_entry.delete(
            0,
            tk.END
        )

        self.phone_entry.delete(
            0,
            tk.END
        )

        self.status_combo.set(
            "Active"
        )

        if hasattr(self, "tree"):

            selected = self.tree.selection()

            if selected:

                self.tree.selection_remove(
                    selected
                )

        self.name_entry.focus_set()

    # ========================================================
    # CLOSE WINDOW
    # ========================================================

    def close_window(self):

        try:

            self.grab_release()

        except tk.TclError:
            _bkpos_logger.warning("Suppressed exception in ui/branches.py", exc_info=exc)

        self.destroy()


# ============================================================
# TEST MODE
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()

    root.title("Branch Manager Test")
    root.geometry("400x200")

    tk.Label(
        root,
        text="Branch Manager Test",
        font=("Segoe UI", 14, "bold")
    ).pack(
        pady=30
    )

    tk.Button(
        root,
        text="Open Branch Manager",
        font=("Segoe UI", 10),
        command=lambda: BranchManager(
            root,
            {
                "username": "admin",
                "full_name": "Administrator"
            }
        )
    ).pack()

    root.mainloop()
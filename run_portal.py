from core.config import DB_PATH
import sqlite3
from security import verify_password
import tkinter as tk
from tkinter import messagebox
from admin_portal import AdminPortal


def login_admin():
    root = tk.Tk()
    root.title("Admin Login")
    root.geometry("380x250")
    root.resizable(False, False)
    root.configure(bg="#f0f4f8")

    # Center the window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - 190
    y = (root.winfo_screenheight() // 2) - 125
    root.geometry(f"380x250+{x}+{y}")

    # Header
    header = tk.Frame(root, bg="#2b6cb0", height=50)
    header.pack(fill=tk.X, side=tk.TOP)
    header.pack_propagate(False)
    tk.Label(header, text="🔐 Admin Login", font=("Segoe UI", 16, "bold"),
             fg="white", bg="#2b6cb0").pack(pady=10)

    # Body
    body = tk.Frame(root, bg="#f0f4f8", padx=30, pady=20)
    body.pack(fill=tk.BOTH, expand=True)

    tk.Label(body, text="Username:", font=("Segoe UI", 11, "bold"),
             bg="#f0f4f8", fg="#4a5568").pack(anchor="w", pady=(0, 2))
    username_entry = tk.Entry(body, font=("Segoe UI", 11), width=30,
                              bd=1, relief=tk.SOLID)
    username_entry.pack(fill=tk.X, pady=(0, 10))
    username_entry.focus_set()

    tk.Label(body, text="Password:", font=("Segoe UI", 11, "bold"),
             bg="#f0f4f8", fg="#4a5568").pack(anchor="w", pady=(0, 2))
    password_entry = tk.Entry(body, font=("Segoe UI", 11), width=30,
                              bd=1, relief=tk.SOLID, show="•")
    password_entry.pack(fill=tk.X, pady=(0, 15))

    def do_login():
        username = username_entry.get().strip()
        password = password_entry.get().strip()

        if not username or not password:
            messagebox.showerror("Error", "Please enter username and password!")
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, full_name, role, password_hash
            FROM users
            WHERE username = ? AND LOWER(role) = 'admin'
        """, (username,))
        user = cursor.fetchone()
        conn.close()

        if user and verify_password(password, user[4]):
            admin_user = {
                "id": user[0],
                "username": user[1],
                "full_name": user[2],
                "role": user[3]
            }
            root.destroy()
            portal = AdminPortal(admin_user)
            portal.mainloop()
        else:
            messagebox.showerror("Error", "Invalid admin credentials!")
            password_entry.delete(0, tk.END)
            password_entry.focus_set()

    # Buttons
    btn_frame = tk.Frame(body, bg="#f0f4f8")
    btn_frame.pack(fill=tk.X, pady=(10, 0))

    tk.Button(btn_frame, text="🔓 Login", font=("Segoe UI", 11, "bold"),
              bg="#2b6cb0", fg="white", padx=20, pady=8,
              command=do_login, relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT)

    tk.Button(btn_frame, text="Cancel", font=("Segoe UI", 11, "bold"),
              bg="#e53e3e", fg="white", padx=20, pady=8,
              command=root.destroy, relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=10)

    # Help text
    tk.Label(body, text="First-run credentials are stored in the local setup credential file.", font=("Segoe UI", 9),
             bg="#f0f4f8", fg="#a0aec0", wraplength=320).pack(pady=(10, 0))

    # Bind Enter key
    username_entry.bind("<Return>", lambda e: password_entry.focus_set())
    password_entry.bind("<Return>", lambda e: do_login())

    root.mainloop()


if __name__ == "__main__":
    login_admin()
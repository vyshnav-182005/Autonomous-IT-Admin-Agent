"""
SQLite database operations for OpsPilot AI.
Handles user CRUD, password resets, and action logging.
"""

import aiosqlite
import os
from datetime import datetime
from typing import Optional
from database.models import User, UserRole, UserStatus, ActionLog

DB_PATH = os.getenv("DB_PATH", "database/opspilot.db")

# Seed data for initial users
SEED_USERS = [
    ("John Doe", "john@company.com", "Employee", "Active"),
    ("Jane Smith", "jane@company.com", "Admin", "Active"),
    ("Mark Wilson", "mark@company.com", "Employee", "Active"),
    ("Sarah Connor", "sarah@company.com", "Employee", "Active"),
    ("Admin User", "admin@company.com", "Admin", "Active"),
]


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    """Initialize database tables and seed data."""
    db = await get_db()
    try:
        # Create users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL DEFAULT 'Employee',
                status TEXT NOT NULL DEFAULT 'Active',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Create action log table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                target_email TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '',
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Seed users if table is empty
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        count = await cursor.fetchone()
        if count[0] == 0:
            await db.executemany(
                "INSERT INTO users (name, email, role, status) VALUES (?, ?, ?, ?)",
                SEED_USERS
            )

        await db.commit()
    finally:
        await db.close()


async def get_all_users(query: Optional[str] = None) -> list[dict]:
    """Get all users, optionally filtered by search query."""
    db = await get_db()
    try:
        if query:
            cursor = await db.execute(
                """SELECT * FROM users 
                   WHERE name LIKE ? OR email LIKE ? 
                   ORDER BY id""",
                (f"%{query}%", f"%{query}%")
            )
        else:
            cursor = await db.execute("SELECT * FROM users ORDER BY id")
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_user_by_email(email: str) -> Optional[dict]:
    """Find a user by email address."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_user_by_id(user_id: int) -> Optional[dict]:
    """Find a user by ID."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def create_user(name: str, email: str, role: str) -> dict:
    """
    Create a new user. Raises ValueError if email already exists.
    Returns the created user dict.
    """
    # Check for duplicate email
    existing = await get_user_by_email(email)
    if existing:
        raise ValueError(f"A user with email '{email}' already exists.")

    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO users (name, email, role) VALUES (?, ?, ?)",
            (name, email, role)
        )
        await db.commit()
        user_id = cursor.lastrowid

        # Log action
        await _log_action(db, "create_user", email, f"Created user '{name}' with role '{role}'")

        return {
            "id": user_id,
            "name": name,
            "email": email,
            "role": role,
            "status": "Active",
        }
    finally:
        await db.close()


async def reset_password(user_id: int) -> dict:
    """
    Simulate a password reset for a user.
    Returns the user dict with a success message.
    """
    user = await get_user_by_id(user_id)
    if not user:
        raise ValueError(f"User with ID {user_id} not found.")

    db = await get_db()
    try:
        # Log the action (no actual password change in mock)
        await _log_action(
            db, "reset_password", user["email"],
            f"Password reset for '{user['name']}'. Temporary password generated."
        )
        await db.commit()
        return user
    finally:
        await db.close()


async def disable_user(user_id: int) -> dict:
    """
    Disable a user account by setting status to 'Disabled'.
    Returns the updated user dict.
    """
    user = await get_user_by_id(user_id)
    if not user:
        raise ValueError(f"User with ID {user_id} not found.")

    if user["status"] == "Disabled":
        raise ValueError(f"User '{user['email']}' is already disabled.")

    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET status = 'Disabled' WHERE id = ?",
            (user_id,)
        )
        await _log_action(
            db, "disable_user", user["email"],
            f"Disabled user account for '{user['name']}'"
        )
        await db.commit()
        user["status"] = "Disabled"
        return user
    finally:
        await db.close()


async def delete_user(user_id: int) -> dict:
    """
    Permanently delete a user account from the database.
    Returns the deleted user dict.
    """
    user = await get_user_by_id(user_id)
    if not user:
        raise ValueError(f"User with ID {user_id} not found.")

    db = await get_db()
    try:
        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await _log_action(
            db, "delete_user", user["email"],
            f"Deleted user account for '{user['name']}'"
        )
        await db.commit()
        return user
    finally:
        await db.close()


async def get_action_log() -> list[dict]:
    """Get all action log entries, most recent first."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM action_log ORDER BY id DESC LIMIT 50"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def _log_action(db: aiosqlite.Connection, action: str, target_email: str, details: str):
    """Internal helper to log an action."""
    await db.execute(
        "INSERT INTO action_log (action, target_email, details) VALUES (?, ?, ?)",
        (action, target_email, details)
    )

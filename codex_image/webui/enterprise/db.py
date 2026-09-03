from __future__ import annotations

import hashlib
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DB_FILE_NAME = "app_enterprise.db"

def get_db(data_root: Path) -> sqlite3.Connection:
    data_root.mkdir(parents=True, exist_ok=True)
    db_path = data_root / DB_FILE_NAME
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    # 采用安全带盐哈希 (PBKDF2-HMAC-SHA256)
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${dk.hex()}"

def verify_password(stored_hash: str, password: str) -> bool:
    try:
        salt, expected_dk = stored_hash.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return dk.hex() == expected_dk
    except Exception:
        return False

def init_db_and_admin(data_root: Path) -> None:
    conn = get_db(data_root)
    cur = conn.cursor()

    # 1. 用户表
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        display_name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'employee', -- admin / employee
        created_at TEXT NOT NULL
    );
    """)

    # 2. 会话 Token 表
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)

    # 3. 统计报表表
    cur.execute("""
    CREATE TABLE IF NOT EXISTS generation_records (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        prompt TEXT,
        ratio TEXT,
        resolution TEXT,
        status TEXT, -- completed / failed
        duration_ms INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """)

    conn.commit()

    # 预置管理员：姓名 兰京，账户 HtaiAI，密码 Htai@123456
    cur.execute("SELECT id FROM users WHERE username = 'HtaiAI'")
    admin = cur.fetchone()
    if not admin:
        admin_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        pwd_hash = hash_password("Htai@123456")
        cur.execute(
            "INSERT INTO users (id, username, display_name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (admin_id, "HtaiAI", "兰京", pwd_hash, "admin", now)
        )
        conn.commit()
    conn.close()


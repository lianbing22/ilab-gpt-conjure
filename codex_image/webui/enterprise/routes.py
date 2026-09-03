from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Body, Cookie, FastAPI, Header, HTTPException, Request, Response
from codex_image.webui.context import WebUIContext

from .db import (
    get_db,
    hash_password,
    init_db_and_admin,
    verify_password,
)

AUTH_COOKIE_NAME = "ilab_auth_token"

def get_current_user(request: Request, ctx: WebUIContext) -> Optional[dict[str, Any]]:
    token = request.cookies.get(AUTH_COOKIE_NAME) or request.headers.get("x-auth-token")
    if not token:
        return None
    conn = get_db(ctx.source_data_root)
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.username, u.display_name, u.role, u.created_at
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)

def require_current_user(request: Request, ctx: WebUIContext) -> dict[str, Any]:
    user = get_current_user(request, ctx)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user

def register_enterprise_routes(app: FastAPI, ctx: WebUIContext) -> None:
    # 确保数据库与默认管理员已初始化
    init_db_and_admin(ctx.source_data_root)

    # 1. 认证接口：当前用户信息
    @app.get("/api/auth/me")
    def get_auth_me(request: Request) -> dict[str, Any]:
        user = get_current_user(request, ctx)
        return {"authenticated": bool(user), "user": user}

    # 2. 认证接口：登录
    @app.post("/api/auth/login")
    def login(response: Response, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", "")).strip()
        if not username or not password:
            raise HTTPException(status_code=400, detail="请输入账号和密码")

        conn = get_db(ctx.source_data_root)
        cur = conn.cursor()
        cur.execute("SELECT id, username, display_name, password_hash, role FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row or not verify_password(row["password_hash"], password):
            conn.close()
            raise HTTPException(status_code=401, detail="账号或密码错误")

        # 生成会话 Token
        token = uuid.uuid4().hex
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, row["id"], now))
        conn.commit()
        conn.close()

        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 30
        )
        return {
            "ok": True,
            "token": token,
            "user": {
                "id": row["id"],
                "username": row["username"],
                "display_name": row["display_name"],
                "role": row["role"],
            }
        }

    # 3. 认证接口：注册 (新员工)
    @app.post("/api/auth/register")
    def register(response: Response, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        username = str(payload.get("username", "")).strip()
        display_name = str(payload.get("display_name", "")).strip() or username
        password = str(payload.get("password", "")).strip()
        if not username or not password:
            raise HTTPException(status_code=400, detail="用户名和密码不能为空")
        if len(password) < 6:
            raise HTTPException(status_code=400, detail="密码长度不能少于 6 位")

        conn = get_db(ctx.source_data_root)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="该账号已被注册")

        user_id = uuid.uuid4().hex[:12]
        pwd_hash = hash_password(password)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            "INSERT INTO users (id, username, display_name, password_hash, role, created_at) VALUES (?, ?, ?, ?, 'employee', ?)",
            (user_id, username, display_name, pwd_hash, now)
        )

        token = uuid.uuid4().hex
        cur.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user_id, now))
        conn.commit()
        conn.close()

        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 30
        )
        return {
            "ok": True,
            "token": token,
            "user": {
                "id": user_id,
                "username": username,
                "display_name": display_name,
                "role": "employee",
            }
        }

    # 4. 认证接口：退出登录
    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response) -> dict[str, Any]:
        token = request.cookies.get(AUTH_COOKIE_NAME) or request.headers.get("x-auth-token")
        if token:
            conn = get_db(ctx.source_data_root)
            cur = conn.cursor()
            cur.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            conn.close()
        response.delete_cookie(AUTH_COOKIE_NAME)
        return {"ok": True}

    # 5. 统计报表：数据看板 (管理员全员大盘 vs 员工个人周报/月报)
    @app.get("/api/analytics/dashboard")
    def get_analytics_dashboard(request: Request) -> dict[str, Any]:
        user = require_current_user(request, ctx)
        is_admin = user.get("role") == "admin"

        conn = get_db(ctx.source_data_root)
        cur = conn.cursor()

        # 根据角色决定统计范围：员工仅统计本人，管理员统计全员
        user_filter = "" if is_admin else f"WHERE r.user_id = '{user['id']}'"

        # 总任务数、成功数
        cur.execute(f"SELECT count(*) as total, sum(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed FROM generation_records r {user_filter}")
        overview = dict(cur.fetchone())
        total_tasks = overview["total"] or 0
        completed_tasks = overview["completed"] or 0
        success_rate = round((completed_tasks / total_tasks * 100) if total_tasks else 100.0, 1)

        # 比例分布
        cur.execute(f"SELECT ratio, count(*) as count FROM generation_records r {user_filter} GROUP BY ratio ORDER BY count DESC LIMIT 6")
        ratio_distribution = [dict(r) for r in cur.fetchall()]

        # 用户排行（仅管理员可见）
        leaderboard = []
        if is_admin:
            cur.execute("""
                SELECT u.display_name, u.username, count(r.id) as task_count
                FROM users u
                LEFT JOIN generation_records r ON u.id = r.user_id
                GROUP BY u.id
                ORDER BY task_count DESC LIMIT 10
            """)
            leaderboard = [dict(r) for r in cur.fetchall()]

        # 员工列表统计（仅管理员可见）
        user_list = []
        if is_admin:
            cur.execute("SELECT id, username, display_name, role, created_at FROM users ORDER BY created_at DESC")
            user_list = [dict(r) for r in cur.fetchall()]

        conn.close()

        return {
            "scope": "enterprise_admin" if is_admin else "personal_employee",
            "current_user": user,
            "stats": {
                "total_generations": total_tasks,
                "completed_generations": completed_tasks,
                "success_rate": success_rate,
                "ratio_distribution": ratio_distribution,
                "leaderboard": leaderboard,
                "users": user_list,
            }
        }

    # 记录生图完成统计
    @app.post("/api/analytics/record")
    def record_generation(request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        user = get_current_user(request, ctx)
        user_id = user["id"] if user else "anonymous"

        conn = get_db(ctx.source_data_root)
        cur = conn.cursor()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        record_id = uuid.uuid4().hex[:12]
        cur.execute("""
            INSERT INTO generation_records (id, user_id, task_id, prompt, ratio, resolution, status, duration_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record_id,
            user_id,
            str(payload.get("task_id", "")),
            str(payload.get("prompt", ""))[:200],
            str(payload.get("ratio", "9:16")),
            str(payload.get("resolution", "1K")),
            str(payload.get("status", "completed")),
            int(payload.get("duration_ms", 0)),
            now
        ))
        conn.commit()
        conn.close()
        return {"ok": True}


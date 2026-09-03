from __future__ import annotations
import json

import shutil
import os

def _get_server_metrics(output_root: Path) -> dict[str, Any]:
    # 1. 磁盘使用情况
    total, used, free = shutil.disk_usage(output_root)
    disk_total_gb = round(total / (1024 ** 3), 1)
    disk_used_gb = round(used / (1024 ** 3), 1)
    disk_free_gb = round(free / (1024 ** 3), 1)
    disk_percent = round((used / total) * 100, 1)

    # 2. 内存使用情况 (Linux)
    mem_total_mb = 0
    mem_avail_mb = 0
    mem_percent = 0
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        meminfo = {}
        for line in lines:
            parts = line.split(":")
            if len(parts) == 2:
                meminfo[parts[0].strip()] = int(parts[1].split()[0])
        total_kb = meminfo.get("MemTotal", 0)
        avail_kb = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
        used_kb = total_kb - avail_kb
        mem_total_mb = round(total_kb / 1024, 1)
        mem_avail_mb = round(avail_kb / 1024, 1)
        mem_percent = round((used_kb / total_kb) * 100, 1) if total_kb else 0
    except Exception:
        pass

    # 3. CPU 核心数与负载
    cpu_count = os.cpu_count() or 1
    load_avg = [0.0, 0.0, 0.0]
    try:
        load_avg = [round(x, 2) for x in os.getloadavg()]
    except Exception:
        pass

    return {
        "disk": {
            "total_gb": disk_total_gb,
            "used_gb": disk_used_gb,
            "free_gb": disk_free_gb,
            "percent": disk_percent,
        },
        "memory": {
            "total_mb": mem_total_mb,
            "available_mb": mem_avail_mb,
            "percent": mem_percent,
        },
        "cpu": {
            "cores": cpu_count,
            "load_1m": load_avg[0],
            "load_5m": load_avg[1],
            "load_15m": load_avg[2],
        }
    }


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

    # 8. 基于 DeepSeek-v4-Flash 的提示词智能扩写与优化接口
    @app.post("/api/prompt/optimize")
    def optimize_prompt(request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        user = require_current_user(request, ctx)
        raw_prompt = str(payload.get("prompt", "")).strip()
        if not raw_prompt:
            raise HTTPException(status_code=400, detail="请输入需要优化的提示词")

        api_url = "https://ai-api.kkidc.com/v1/chat/completions"
        api_key = "sk-BVbEHeUeFmYIJHehTX81LBiDtzGXOBjUlaJsii6NBLN1BjLn"

        system_instruction = (
            "你是一个顶级AI绘画生图提示词专家。你的任务是将用户提供的简短或基础生图提示词进行扩写和优化。"
            "要求："
            "1. 丰富画面的构图、主体细节、光影氛围（如丁达尔光、轮廓光、柔光）、色彩质感（如胶片质感、金属反光、细腻皮肤）与环境景深。"
            "2. 保持用户原始意图不失真。"
            "3. 直接输出一段优化后的可直接用于生图的中文提示词段落，不要包含任何前缀闲聊、寒暄或分点解释，直接给出最终提示词纯文本。"
        )

        req_data = json.dumps({
            "model": "deepseek-v4-flash",
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"请优化这段生图提示词：{raw_prompt}"}
            ],
            "temperature": 0.7,
            "max_tokens": 800
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "codex-image/0.3.0"
        }

        import urllib.request
        import ssl
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(api_url, data=req_data, headers=headers)
        try:
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=30) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                optimized_text = res["choices"][0]["message"]["content"].strip()
                # 剔除可能带有的首尾引号
                if optimized_text.startswith(('"', '“')) and optimized_text.endswith(('"', '”')):
                    optimized_text = optimized_text[1:-1].strip()
                return {"ok": True, "optimized_prompt": optimized_text, "original_prompt": raw_prompt}
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"提示词优化调用失败: {str(exc)}") from exc


    # 6. 服务器性能与资源监控接口
    @app.get("/api/admin/system-metrics")
    def get_system_metrics(request: Request) -> dict[str, Any]:
        user = require_current_user(request, ctx)
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="仅管理员可查看服务器状态")
        return {"metrics": _get_server_metrics(ctx.output_root)}

    # 7. 历史图库与任务清理接口
    @app.post("/api/admin/cleanup-history")
    def cleanup_history_images(request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        user = require_current_user(request, ctx)
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="仅管理员有权清理历史图片")

        days = payload.get("days") # 1, 7, 30 或 None
        start_date = payload.get("start_date") # YYYY-MM-DD
        end_date = payload.get("end_date") # YYYY-MM-DD

        now_ts = datetime.now(timezone.utc).timestamp()
        deleted_count = 0
        freed_bytes = 0

        # 清理 output 目录下的任务输出文件
        tasks_dir = ctx.output_root / "tasks"
        if tasks_dir.exists():
            for task_path in list(tasks_dir.iterdir()):
                if not task_path.is_dir():
                    continue
                try:
                    mtime = task_path.stat().st_mtime
                    age_days = (now_ts - mtime) / 86400

                    should_delete = False
                    if days is not None:
                        if age_days >= float(days):
                            should_delete = True
                    elif start_date and end_date:
                        date_str = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
                        if start_date <= date_str <= end_date:
                            should_delete = True

                    if should_delete:
                        for f in task_path.rglob("*"):
                            if f.is_file():
                                freed_bytes += f.stat().st_size
                        shutil.rmtree(task_path, ignore_errors=True)
                        deleted_count += 1
                except Exception:
                    pass

        # 同时也清理数据库中的过期记录
        try:
            conn = get_db(ctx.source_data_root)
            cur = conn.cursor()
            if days is not None:
                cur.execute(f"DELETE FROM generation_records WHERE datetime(created_at) < datetime('now', '-{int(days)} days')")
            elif start_date and end_date:
                cur.execute("DELETE FROM generation_records WHERE date(created_at) >= ? AND date(created_at) <= ?", (start_date, end_date))
            conn.commit()
            conn.close()
        except Exception:
            pass

        return {
            "ok": True,
            "deleted_tasks": deleted_count,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        }

    # --- 用户管理增删改查 (仅管理员) ---
    @app.get("/api/admin/users")
    def list_admin_users(request: Request) -> dict[str, Any]:
        user = require_current_user(request, ctx)
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="无权访问用户管理")
        conn = get_db(ctx.source_data_root)
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.username, u.display_name, u.role, u.created_at,
                   count(r.id) as task_count
            FROM users u
            LEFT JOIN generation_records r ON u.id = r.user_id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """)
        users = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"users": users}

    @app.post("/api/admin/users/create")
    def create_admin_user(request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        cur_user = require_current_user(request, ctx)
        if cur_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="无权操作")
        u = str(payload.get("username", "")).strip()
        p = str(payload.get("password", "")).strip()
        d = str(payload.get("display_name", "")).strip() or u
        role = str(payload.get("role", "employee")).strip()
        if not u or not p:
            raise HTTPException(status_code=400, detail="账号和密码不能为空")

        conn = get_db(ctx.source_data_root)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (u,))
        if cur.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="该账号已存在")

        user_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        pwd_hash = hash_password(p)
        cur.execute(
            "INSERT INTO users (id, username, display_name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, u, d, pwd_hash, role, now)
        )
        conn.commit()
        conn.close()
        return {"ok": True}

    @app.post("/api/admin/users/{user_id}/delete")
    def delete_admin_user(user_id: str, request: Request) -> dict[str, Any]:
        cur_user = require_current_user(request, ctx)
        if cur_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="无权操作")
        if user_id == cur_user.get("id"):
            raise HTTPException(status_code=400, detail="不能删除当前登录的管理员自己")

        conn = get_db(ctx.source_data_root)
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM generation_records WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return {"ok": True}

    @app.post("/api/admin/users/{user_id}/reset-password")
    def reset_user_password(user_id: str, request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        cur_user = require_current_user(request, ctx)
        if cur_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="无权操作")
        new_pwd = str(payload.get("password", "")).strip()
        if not new_pwd or len(new_pwd) < 6:
            raise HTTPException(status_code=400, detail="新密码长度不能少于 6 位")

        conn = get_db(ctx.source_data_root)
        cur = conn.cursor()
        pwd_hash = hash_password(new_pwd)
        cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pwd_hash, user_id))
        cur.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return {"ok": True}

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


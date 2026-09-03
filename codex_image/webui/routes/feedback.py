from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from codex_image.webui.context import WebUIContext

def _feedback_file(source_data_root: Path) -> Path:
    target_dir = source_data_root / "feedback"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "feedback_messages.json"

def _load_feedback(source_data_root: Path) -> list[dict[str, Any]]:
    path = _feedback_file(source_data_root)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

def _save_feedback(source_data_root: Path, items: list[dict[str, Any]]) -> None:
    path = _feedback_file(source_data_root)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

def register_feedback_routes(app: FastAPI, ctx: WebUIContext) -> None:
    @app.get("/api/feedback")
    def list_feedback() -> dict[str, Any]:
        items = _load_feedback(ctx.source_data_root)
        # 按时间倒序
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {"messages": items}

    @app.post("/api/feedback")
    def create_feedback(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        content = str(payload.get("content", "")).strip()
        nickname = str(payload.get("nickname", "")).strip() or "热心创作者"
        contact = str(payload.get("contact", "")).strip()
        if not content:
            raise HTTPException(status_code=400, detail="留言内容不能为空")

        msg = {
            "id": uuid.uuid4().hex[:12],
            "nickname": nickname,
            "contact": contact,
            "content": content,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "replies": []
        }
        items = _load_feedback(ctx.source_data_root)
        items.append(msg)
        _save_feedback(ctx.source_data_root, items)
        return {"ok": True, "message": msg}

    @app.post("/api/feedback/{msg_id}/reply")
    def reply_feedback(msg_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        content = str(payload.get("content", "")).strip()
        author = str(payload.get("author", "")).strip() or "管理员"
        if not content:
            raise HTTPException(status_code=400, detail="回复内容不能为空")

        items = _load_feedback(ctx.source_data_root)
        found = False
        for msg in items:
            if msg.get("id") == msg_id:
                msg.setdefault("replies", []).append({
                    "id": uuid.uuid4().hex[:8],
                    "author": author,
                    "content": content,
                    "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                })
                found = True
                break
        if not found:
            raise HTTPException(status_code=404, detail="留言未找到")
        _save_feedback(ctx.source_data_root, items)
        return {"ok": True}

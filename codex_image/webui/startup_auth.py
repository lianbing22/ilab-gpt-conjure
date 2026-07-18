from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

AUTH_SOURCES = {"codex", "api"}
LEGACY_AUTH_SOURCES = {"auto", "cock" + "pit"}


def detect_startup_auth_source() -> str:
    # 默认强制走 API 直连，避免同事各自配置 Codex 登录态。
    return "api"


def _read_existing_source(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("source") or "").strip().lower()


def initialize_auth_settings(path: str | Path, *, force: bool = False) -> str:
    settings_path = Path(path)
    existing = _read_existing_source(settings_path)
    if not force and existing in AUTH_SOURCES:
        return existing
    source = detect_startup_auth_source()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps({"source": source}, indent=2), encoding="utf-8")
    return source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize WebUI auth source settings.")
    parser.add_argument("--settings-path", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    source = initialize_auth_settings(args.settings_path, force=bool(args.force))
    print(source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

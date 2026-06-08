from __future__ import annotations

import unittest
from pathlib import Path


class LegacyAccountPoolRemovalTests(unittest.TestCase):
    def test_removed_account_pool_name_does_not_appear_in_tracked_sources(self) -> None:
        forbidden = ("Cock" + "pit", "cock" + "pit")
        ignored_dirs = {
            ".git",
            ".mypy_cache",
            ".playwright-cli",
            ".pytest_cache",
            ".venv",
            ".worktrees",
            ".dist",
            "dist",
            "node_modules",
            "output",
            "outputs",
            "public-repos",
        }
        ignored_suffixes = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".db", ".sqlite", ".zip"}
        allowed_paths = {Path("tests/test_legacy_account_pool_removed.py")}
        hits: list[str] = []

        for path in Path(".").rglob("*"):
            if path.is_dir():
                continue
            if not path.is_file():
                continue
            if allowed_paths.intersection(path.parents) or path in allowed_paths:
                continue
            if any(part in ignored_dirs for part in path.parts):
                continue
            if path.suffix.lower() in ignored_suffixes:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for term in forbidden:
                if term in text:
                    hits.append(str(path))
                    break

        self.assertEqual([], sorted(hits))


if __name__ == "__main__":
    unittest.main()

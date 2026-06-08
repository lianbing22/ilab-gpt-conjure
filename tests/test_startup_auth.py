from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_image.auth import AuthState


class StartupAuthTests(unittest.TestCase):
    def _auth_state(self, root: Path, token: str | None) -> AuthState:
        return AuthState(
            path=root / "auth.json",
            access_token=token,
            refresh_token=None,
            id_token=None,
            account_id="acct-local" if token else None,
            last_refresh=None,
            raw={},
        )

    def test_detect_startup_auth_source_uses_codex_when_oauth_token_exists(self) -> None:
        from codex_image.webui.startup_auth import detect_startup_auth_source

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("codex_image.webui.startup_auth.load_auth_state", return_value=self._auth_state(root, "token")):
                self.assertEqual(detect_startup_auth_source(), "codex")

    def test_detect_startup_auth_source_uses_api_without_codex_oauth_token(self) -> None:
        from codex_image.webui.startup_auth import detect_startup_auth_source

        with patch("codex_image.webui.startup_auth.load_auth_state", side_effect=FileNotFoundError("missing")):
            self.assertEqual(detect_startup_auth_source(), "api")

    def test_initialize_auth_settings_preserves_user_selected_sources(self) -> None:
        from codex_image.webui.startup_auth import initialize_auth_settings

        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "webui-auth-settings.json"
            settings_path.write_text(json.dumps({"source": "api"}), encoding="utf-8")
            with patch("codex_image.webui.startup_auth.detect_startup_auth_source", return_value="codex"):
                selected = initialize_auth_settings(settings_path)

            self.assertEqual(selected, "api")
            self.assertEqual(json.loads(settings_path.read_text(encoding="utf-8"))["source"], "api")

    def test_initialize_auth_settings_migrates_missing_or_legacy_sources(self) -> None:
        from codex_image.webui.startup_auth import initialize_auth_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_path = root / "missing.json"
            legacy_path = root / "legacy.json"
            legacy_path.write_text(json.dumps({"source": "cock" + "pit"}), encoding="utf-8")

            with patch("codex_image.webui.startup_auth.detect_startup_auth_source", return_value="codex"):
                self.assertEqual(initialize_auth_settings(missing_path), "codex")
                self.assertEqual(initialize_auth_settings(legacy_path), "codex")

            self.assertEqual(json.loads(missing_path.read_text(encoding="utf-8"))["source"], "codex")
            self.assertEqual(json.loads(legacy_path.read_text(encoding="utf-8"))["source"], "codex")


if __name__ == "__main__":
    unittest.main()

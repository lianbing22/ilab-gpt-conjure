from pathlib import Path


def test_mobile_workspace_has_compact_summary_and_progressive_settings() -> None:
    html = Path("codex_image/webui/static/index.html").read_text(encoding="utf-8")
    source = Path("codex_image/webui/frontend/src/mobile-workspace.ts").read_text(encoding="utf-8")
    styles = Path("codex_image/webui/static/styles/80-utilities-responsive.css").read_text(encoding="utf-8")

    assert 'id="mobileOutputSettingsToggle"' in html
    assert 'id="mobileOutputSummary"' in html
    assert 'id="mobileAdvancedSettingsToggle"' in html
    assert 'classList.toggle("mobile-settings-expanded"' in source
    assert 'classList.toggle("mobile-advanced-expanded"' in source
    assert '.output-panel.mobile-settings-expanded' in styles
    assert '.output-panel.mobile-settings-expanded:not(.mobile-advanced-expanded)' in styles


def test_mobile_workspace_prioritizes_prompt_preview_and_sticky_action() -> None:
    source = Path("codex_image/webui/frontend/src/mobile-workspace.ts").read_text(encoding="utf-8")
    styles = Path("codex_image/webui/static/styles/80-utilities-responsive.css").read_text(encoding="utf-8")

    assert '.dashboard.mobile-has-preview .preview-col' in styles
    assert 'position: fixed' in styles[styles.index(".prompt-run-wrap"):]
    assert 'height: 52px' in styles[styles.index(".prompt-compose .run-button"):]
    assert 'new MutationObserver(syncPreviewState)' in source
    assert 'window.matchMedia("(max-width: 520px)")' in source

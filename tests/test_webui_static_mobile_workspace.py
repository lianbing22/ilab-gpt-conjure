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


def test_mobile_workspace_keeps_materials_before_output_and_preview() -> None:
    redesign = Path("codex_image/webui/static/styles/85-ui-redesign.css").read_text(encoding="utf-8")

    assert ".prompt-panel { order: 1; }" in redesign
    assert ".image-panel { order: 2; }" in redesign
    assert ".output-panel { order: 3; }" in redesign
    assert ".dashboard.mobile-has-preview .preview-col { order: 4; }" in redesign


def test_mobile_task_drawer_restores_task_content_and_locks_background() -> None:
    source = Path("codex_image/webui/frontend/src/sidebar-drawer.ts").read_text(encoding="utf-8")
    redesign = Path("codex_image/webui/static/styles/85-ui-redesign.css").read_text(encoding="utf-8")

    assert 'document.body.classList.add("mobile-task-drawer-open")' in source
    assert 'toggle.setAttribute("aria-label", translate("sidebar.closeTaskCenter"))' in source
    assert 'sidebar.setAttribute("aria-label", translate("sidebar.taskCenter"))' in source
    assert ".sidebar.sidebar-drawer-open .task-history-shell" in redesign
    drawer_styles = redesign[redesign.index(".sidebar.sidebar-drawer-open .task-history-shell"):]
    assert "display: flex" in drawer_styles
    assert "body.mobile-task-drawer-open" in redesign


def test_mobile_workspace_uses_native_page_scrolling() -> None:
    redesign = Path("codex_image/webui/static/styles/85-ui-redesign.css").read_text(encoding="utf-8")
    mobile = redesign[redesign.index("@media (max-width: 520px)"):]

    assert "overflow-y: auto" in mobile
    assert "touch-action: pan-y" in mobile
    assert ".layout-container" in mobile
    assert "min-height: 100dvh" in mobile
    assert ".sidebar:not(.sidebar-drawer-open)" in mobile
    assert "position: fixed" in mobile
    assert "padding-top: 68px" in mobile
    assert ".dashboard" in mobile
    assert "overflow: visible" in mobile

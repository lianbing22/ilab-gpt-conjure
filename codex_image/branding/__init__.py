"""Offline brand-overlay module for batch Logo + Slogan composition.

This package is intentionally dependency-light (Pillow + stdlib only) and
side-effect-free: the :func:`compose` family never touches the filesystem, and
the CLI owns all disk I/O. See ``codex_image/branding/compositor.py`` for the
core pure function and ``codex_image/branding/cli.py`` for the batch runner.
"""

from __future__ import annotations

from codex_image.branding.compositor import (
    COMPOSITOR_VERSION,
    compose,
    compose_with_report,
    compute_request_hash,
)
from codex_image.branding.contrast import (
    CONTRAST_AMBIGUOUS_BAND,
    choose_asset_tone,
    mean_luminance,
    tone_is_ambiguous,
)
from codex_image.branding.models import (
    Anchor,
    BrandTemplate,
    LayoutKind,
    OverlayKey,
    PlacementConfig,
    ToneKey,
    content_hash,
)
from codex_image.branding.placement import classify_layout, compute_placement

__all__ = [
    "COMPOSITOR_VERSION",
    "CONTRAST_AMBIGUOUS_BAND",
    "Anchor",
    "BrandTemplate",
    "LayoutKind",
    "OverlayKey",
    "PlacementConfig",
    "ToneKey",
    "choose_asset_tone",
    "classify_layout",
    "compose",
    "compose_with_report",
    "compute_placement",
    "compute_request_hash",
    "content_hash",
    "mean_luminance",
    "tone_is_ambiguous",
]

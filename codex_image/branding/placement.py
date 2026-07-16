from __future__ import annotations

from typing import Literal

from codex_image.branding.models import Anchor, LayoutKind, PlacementConfig


def _clamp_unit(value: float) -> float:
    """Clamp a ratio into the legal [0, 1] range."""
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def classify_layout(width: int, height: int) -> LayoutKind:
    """Bucket an image into square / portrait / landscape from real pixels.

    A tolerance band of 0.9 <= w/h <= 1.1 is treated as square so that
    near-1:1 generated images (common with diffusion models) don't flip
    buckets on a few pixels of difference. ``w > h`` is landscape, anything
    else (taller than wide, outside the band) is portrait.
    """
    if width <= 0 or height <= 0:
        # Degenerate inputs default to square so callers still get a valid key.
        return "square"
    ratio = width / height
    if 0.9 <= ratio <= 1.1:
        return "square"
    if width > height:
        return "landscape"
    return "portrait"


def compute_placement(
    canvas_w: int,
    canvas_h: int,
    placement: PlacementConfig,
    element_w: int,
    element_h: int,
) -> tuple[int, int, int, int]:
    """Compute the (x, y, target_w, target_h) box for one overlay element.

    Pure function, no image I/O. Steps:

    1. ``target_w = canvas_w * width_ratio`` (ratio clamped to [0,1]).
    2. ``target_h`` scales the element height by the same factor as the width
       so the aspect ratio is preserved. We never read the element's native
       width when deriving height; we use the ratio element_h/element_w so a
       tall slogan stays tall.
    3. The element is never allowed to exceed the canvas: if ``target_w``
       overshoots it is clamped to ``canvas_w`` and ``target_h`` recomputed.
    4. ``x``/``y`` follow the anchor plus the margin offset
       (``margin_x = canvas_w * margin_x_ratio``, ``margin_y = canvas_h *
       margin_y_ratio``), both ratios clamped to [0,1].

    Margins are measured *inward from the chosen edge*: top-left places the
    box at (margin_x, margin_y); bottom-right places it so its right/bottom
    edge sits at canvas - margin.
    """
    if canvas_w <= 0 or canvas_h <= 0:
        return (0, 0, 0, 0)
    if element_w <= 0 or element_h <= 0:
        return (0, 0, 0, 0)

    width_ratio = _clamp_unit(placement.width_ratio)
    margin_x_ratio = _clamp_unit(placement.margin_x_ratio)
    margin_y_ratio = _clamp_unit(placement.margin_y_ratio)

    target_w = max(1, round(canvas_w * width_ratio))
    # Cap so the element never exceeds the canvas width.
    if target_w > canvas_w:
        target_w = canvas_w
    # Preserve aspect ratio using the element's native h/w.
    scale = target_w / element_w
    target_h = max(1, round(element_h * scale))
    if target_h > canvas_h:
        # If height blew past the canvas, re-derive width from height to fit.
        target_h = canvas_h
        scale = target_h / element_h
        target_w = max(1, round(element_w * scale))
        if target_w > canvas_w:
            target_w = canvas_w

    margin_x = canvas_w * margin_x_ratio
    margin_y = canvas_h * margin_y_ratio

    x, y = _anchor_origin(placement.anchor, canvas_w, canvas_h, target_w, target_h, margin_x, margin_y)
    # Floor to ints so downstream alpha_composite gets pixel-aligned boxes.
    return (int(round(x)), int(round(y)), int(target_w), int(target_h))


def _anchor_origin(
    anchor: Anchor,
    canvas_w: int,
    canvas_h: int,
    target_w: int,
    target_h: int,
    margin_x: float,
    margin_y: float,
) -> tuple[float, float]:
    """Resolve top-left corner (x, y) for the box given the anchor and margins."""
    if anchor == "top-left":
        return (margin_x, margin_y)
    if anchor == "top-right":
        return (canvas_w - target_w - margin_x, margin_y)
    if anchor == "bottom-left":
        return (margin_x, canvas_h - target_h - margin_y)
    # bottom-right
    return (canvas_w - target_w - margin_x, canvas_h - target_h - margin_y)

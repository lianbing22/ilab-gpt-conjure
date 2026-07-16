from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Literal


# Corner anchors for placing an overlay element on the canvas.
Anchor = Literal["top-left", "top-right", "bottom-left", "bottom-right"]

# Image aspect-ratio buckets. Driven by real pixel dimensions, not metadata.
LayoutKind = Literal["square", "portrait", "landscape"]

# Which overlay asset sits on the canvas.
OverlayKey = Literal["logo", "slogan"]

# A named set of tone-specific assets (dark ink for bright backgrounds, etc.).
# NOTE: hyphenated to match BrandTemplate.theme_mode and the CLI --theme-mode flag.
ToneKey = Literal["light-assets", "dark-assets"]


@dataclass(frozen=True)
class PlacementConfig:
    """Where and how large a single overlay element should be rendered.

    All ratios are clamped to [0, 1] by the compositor before use, so callers
    may pass loose values without corrupting the canvas.
    """

    anchor: Anchor
    # Element width as a fraction of canvas width (0-1).
    width_ratio: float
    # Horizontal margin as a fraction of canvas width (0-1).
    margin_x_ratio: float
    # Vertical margin as a fraction of canvas height (0-1).
    margin_y_ratio: float


@dataclass(frozen=True)
class BrandTemplate:
    """A fully-described brand overlay recipe.

    `placements` selects per-layout, per-element geometry. `asset_variants`
    maps a tone key to a dict of asset ids / paths; the compositor picks the
    tone by sampling the canvas and then resolves the matching assets.
    """

    id: str
    version: int
    name: str
    theme_mode: Literal["auto", "light-assets", "dark-assets"]
    variant_policy: Literal["per-element", "unified"]
    placements: dict[LayoutKind, dict[OverlayKey, PlacementConfig]] = field(default_factory=dict)
    asset_variants: dict[ToneKey, dict[OverlayKey, str]] = field(default_factory=dict)


# Fields that are pure runtime / cache metadata and must NOT contribute to the
# stable content hash (changing them must not bust idempotency keys).
_RUNTIME_FIELDS: frozenset[str] = frozenset()


def _normalize_template_for_hash(template: BrandTemplate) -> dict[str, object]:
    """Produce a JSON-serializable, order-independent view of the template.

    PlacementConfig dataclasses are inlined so that two structurally identical
    templates hash identically regardless of dataclass identity.
    """
    raw = asdict(template)
    cleaned: dict[str, object] = {}
    for key, value in raw.items():
        if key in _RUNTIME_FIELDS:
            continue
        cleaned[key] = value
    return cleaned


def content_hash(template: BrandTemplate) -> str:
    """Stable sha256 hex of the template's semantic content.

    Used as an idempotency key component: two templates with the same content
    produce the same hash, and any field change changes it. Serialization is
    sorted (order-independent) so dict insertion order does not matter.
    """
    payload = json.dumps(_normalize_template_for_hash(template), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

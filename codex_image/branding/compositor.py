from __future__ import annotations

import hashlib

from PIL import Image, ImageOps

from codex_image.branding.contrast import (
    CONTRAST_AMBIGUOUS_BAND,
    choose_asset_tone,
    mean_luminance,
    tone_is_ambiguous,
)
from codex_image.branding.models import BrandTemplate, OverlayKey, ToneKey
from codex_image.branding.placement import classify_layout, compute_placement


# Bumped whenever the compositing algorithm changes so request hashes can
# invalidate cached outputs across releases.
COMPOSITOR_VERSION = "pillow-compositor-v1"

# Default luminance midpoint used to decide tone / scrim necessity.
_DEFAULT_THRESHOLD = 128.0

# Opacity of the scrim dropped behind an element when contrast is ambiguous.
_SCRIM_ALPHA = 140


def compose(
    raw_image: Image.Image,
    logo: Image.Image,
    slogan: Image.Image,
    template: BrandTemplate,
    *,
    theme_mode_override: str | None = None,
) -> Image.Image:
    """Composite a logo and a slogan onto ``raw_image`` per ``template``.

    Pure function: takes PIL images, returns a new RGBA PIL image, and never
    touches the filesystem. The caller (CLI / tests) owns disk I/O.

    The ``logo`` / ``slogan`` arguments are the assets to burn in for *this*
    call. Tone selection logic still runs so that:

    * ``theme_mode == "auto"`` samples the canvas and reports which tone it
      would use (the caller is expected to pass the matching asset already;
      this function does not swap assets at runtime — it just decides the
      box origin and whether a scrim is needed).
    * A ``theme_mode_override`` (or a non-auto template ``theme_mode``) skips
      sampling and forces a tone, which is useful for batch runs where you
      already know which asset set you loaded.

    Returns a 4-tuple second element carrying diagnostic info via a side
    channel: see :func:`compose_with_report` for the version that also returns
    layout / tone / scrim decisions. ``compose`` itself returns just the image
    to keep the common path simple.
    """
    image, _report = compose_with_report(
        raw_image,
        logo=logo,
        slogan=slogan,
        template=template,
        theme_mode_override=theme_mode_override,
    )
    return image


def compose_with_report(
    raw_image: Image.Image,
    *,
    logo: Image.Image,
    slogan: Image.Image,
    template: BrandTemplate,
    theme_mode_override: str | None = None,
) -> tuple[Image.Image, dict[str, object]]:
    """Like :func:`compose` but also returns a diagnostics dict.

    The report contains, per element: ``layout``, the resolved ``tone``,
    the placement ``box`` (x, y, w, h), and ``scrim`` (bool). Useful for the
    CLI to print and for tests to assert on without re-sampling pixels.
    """
    # (1) Normalize EXIF orientation up-front so all geometry is in display space.
    canvas = ImageOps.exif_transpose(raw_image)
    canvas = canvas.convert("RGBA")
    canvas_w, canvas_h = canvas.size

    # (2) Pick the layout bucket and its placement table.
    layout = classify_layout(canvas_w, canvas_h)
    placements = template.placements.get(layout)
    if placements is None:
        # No recipe for this layout: return the canvas untouched with an empty
        # report so callers can still write the image out.
        report: dict[str, object] = {"layout": layout, "elements": {}}
        return canvas, report

    # (3) Resolve tone. Forced overrides win, otherwise sample the canvas.
    forced_tone = _resolve_forced_tone(template, theme_mode_override)

    logo_box = _box_for(canvas, canvas_w, canvas_h, placements["logo"], logo)
    slogan_box = _box_for(canvas, canvas_w, canvas_h, placements["slogan"], slogan)

    if forced_tone is not None:
        tone: ToneKey = forced_tone
        logo_lum = mean_luminance(_crop_region(canvas, logo_box))
        slogan_lum = mean_luminance(_crop_region(canvas, slogan_box))
    elif template.variant_policy == "unified":
        # Sample only the logo region and use the same tone for both elements.
        logo_lum = mean_luminance(_crop_region(canvas, logo_box))
        tone = choose_asset_tone(logo_lum, _DEFAULT_THRESHOLD)
        slogan_lum = mean_luminance(_crop_region(canvas, slogan_box))
    else:
        # per-element: each element samples its own region.
        logo_lum = mean_luminance(_crop_region(canvas, logo_box))
        slogan_lum = mean_luminance(_crop_region(canvas, slogan_box))
        tone = choose_asset_tone(logo_lum, _DEFAULT_THRESHOLD)

    # (4) Composite each element, with an optional scrim when contrast is iffy.
    # PIL images are immutable in the sense that alpha_composite returns a new
    # image, so each helper returns the (possibly new) canvas + a scrim flag.
    canvas, logo_used_scrim = _paste_element(canvas, logo, logo_box, logo_lum, forced_tone is not None)
    canvas, slogan_used_scrim = _paste_element(canvas, slogan, slogan_box, slogan_lum, forced_tone is not None)

    report = {
        "layout": layout,
        "tone": tone,
        "elements": {
            "logo": {"box": logo_box, "luminance": logo_lum, "scrim": logo_used_scrim},
            "slogan": {"box": slogan_box, "luminance": slogan_lum, "scrim": slogan_used_scrim},
        },
    }
    return canvas, report


def _resolve_forced_tone(
    template: BrandTemplate,
    theme_mode_override: str | None,
) -> ToneKey | None:
    """Return a forced tone if the template or override disables auto-sampling."""
    source = theme_mode_override if theme_mode_override is not None else template.theme_mode
    if source == "light-assets":
        return "light-assets"
    if source == "dark-assets":
        return "dark-assets"
    return None


def _box_for(
    canvas: Image.Image,
    canvas_w: int,
    canvas_h: int,
    placement,
    element: Image.Image,
) -> tuple[int, int, int, int]:
    """Compute the placement box for an element, guarding zero-size assets."""
    element = ImageOps.exif_transpose(element)
    ew, eh = element.size
    if ew <= 0 or eh <= 0:
        return (0, 0, 0, 0)
    return compute_placement(canvas_w, canvas_h, placement, ew, eh)


def _crop_region(canvas: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    """Crop the canvas region an element will occupy, clipped to canvas bounds."""
    x, y, w, h = box
    if w <= 0 or h <= 0:
        return Image.new("RGBA", (1, 1))
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(canvas.width, x + w)
    y1 = min(canvas.height, y + h)
    if x1 <= x0 or y1 <= y0:
        return Image.new("RGBA", (1, 1))
    return canvas.crop((x0, y0, x1, y1))


def _paste_element(
    canvas: Image.Image,
    element: Image.Image,
    box: tuple[int, int, int, int],
    region_luminance: float,
    tone_forced: bool,
) -> tuple[Image.Image, bool]:
    """Resize, optionally scrim, and alpha-composite one element onto canvas.

    Returns the (possibly new) canvas and whether a scrim was inserted. The
    element is scaled to ``box`` and composited via ``Image.alpha_composite``
    so transparency is preserved.

    A scrim (semi-opaque rectangle) is dropped behind the element when the
    sampled region is ambiguous AND tone is not forced — i.e. we're trusting
    the sampler but it's too close to the threshold to be safe. The scrim
    color is chosen *opposite* to the chosen tone: a dark-ink asset gets a
    light scrim, a light-ink asset gets a dark scrim.
    """
    x, y, w, h = box
    if w <= 0 or h <= 0:
        return canvas, False

    element = ImageOps.exif_transpose(element).convert("RGBA")
    if element.size != (w, h):
        element = element.resize((w, h), Image.Resampling.LANCZOS)

    used_scrim = False
    if not tone_forced and tone_is_ambiguous(region_luminance, _DEFAULT_THRESHOLD):
        used_scrim = True
        tone = choose_asset_tone(region_luminance, _DEFAULT_THRESHOLD)
        # Dark ink (dark-assets on bright bg) reads better on a light scrim;
        # light ink (light-assets on dark bg) reads better on a dark scrim.
        scrim_rgb = (255, 255, 255) if tone == "dark-assets" else (0, 0, 0)
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        scrim = Image.new("RGBA", (w, h), (*scrim_rgb, _SCRIM_ALPHA))
        layer.paste(scrim, (x, y))
        canvas = Image.alpha_composite(canvas, layer)

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(element, (x, y), element)
    canvas = Image.alpha_composite(canvas, layer)
    return canvas, used_scrim


def compute_request_hash(
    raw_bytes: bytes,
    template: BrandTemplate,
    logo_bytes: bytes,
    slogan_bytes: bytes,
) -> str:
    """Stable sha256 over (raw image, template, logo, slogan, compositor version).

    The template contributes via :func:`content_hash` so a metadata-only
    change (e.g. bumping a runtime field) does not bust the key, but any
    meaningful recipe change does. The compositor version is mixed in so that
    an algorithmic change invalidates all previously cached branded outputs.
    """
    # Imported lazily here to keep the module's top-level import graph minimal
    # and to avoid a circular reference (models imports nothing from here).
    from codex_image.branding.models import content_hash

    raw_sha = hashlib.sha256(raw_bytes).hexdigest()
    template_hash = content_hash(template)
    logo_sha = hashlib.sha256(logo_bytes).hexdigest()
    slogan_sha = hashlib.sha256(slogan_bytes).hexdigest()
    payload = "|".join([raw_sha, template_hash, logo_sha, slogan_sha, COMPOSITOR_VERSION])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

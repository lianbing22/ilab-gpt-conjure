from __future__ import annotations

from typing import Literal

from PIL import Image, ImageStat


# Below this distance from the threshold we consider contrast unreliable and
# let the compositor decide to drop a scrim behind the element. Kept here so
# tests and the compositor share one definition.
CONTRAST_AMBIGUOUS_BAND = 20.0


def mean_luminance(image_box: Image.Image) -> float:
    """Average luminance (0-255) of a PIL image region.

    The input is expected to be the already-cropped region of the canvas the
    element will cover. We convert to the ``L`` channel (perceptual
    ITU-R 601-2 luma) and take the mean of all pixels, ignoring alpha so that
    a mostly-transparent region still reports the visible ink's brightness.
    """
    if image_box.width <= 0 or image_box.height <= 0:
        return 0.0
    luma = image_box.convert("L")
    # ImageStat(luma).mean returns a list with one entry per band; the single L
    # band gives us the average luminance in [0, 255]. This avoids the
    # deprecated Image.getdata() call.
    means = ImageStat.Stat(luma).mean
    if not means:
        return 0.0
    return float(means[0])


def choose_asset_tone(
    box_luminance: float,
    threshold: float = 128.0,
) -> Literal["light-assets", "dark-assets"]:
    """Pick which tone of brand asset to use for a given background region.

    **This mapping is intentionally counter-intuitive** and the return value
    describes *which asset set to use*, not *what the background looks like*:

    * A **bright** background (luminance above ``threshold``) needs **dark**
      ink to be legible, so we return ``"dark-assets"`` (i.e. the dark-toned
      logo / slogan).
    * A **dark** background (luminance at or below ``threshold``) needs
      **light** ink, so we return ``"light-assets"``.

    The returned string is one of the keys of
    :class:`~codex_image.branding.models.BrandTemplate.asset_variants`, so it
    can index directly into the template. Values exactly on the threshold are
    treated as dark (light-assets), which matches the "needs light ink" rule.
    """
    if box_luminance > threshold:
        return "dark-assets"
    return "light-assets"


def tone_is_ambiguous(box_luminance: float, threshold: float = 128.0) -> bool:
    """True when the sampled luminance is too close to the threshold to trust.

    The compositor uses this to decide whether to drop a semi-opaque scrim
    behind the element so it reads on either tone.
    """
    return abs(box_luminance - threshold) < CONTRAST_AMBIGUOUS_BAND

from __future__ import annotations

from io import BytesIO
import tempfile
from pathlib import Path
import unittest

from PIL import Image

from codex_image.branding.compositor import (
    COMPOSITOR_VERSION,
    compose,
    compose_with_assets,
    compose_with_report,
    compute_request_hash,
)
from codex_image.branding.contrast import (
    CONTRAST_AMBIGUOUS_BAND,
    choose_asset_tone,
    mean_luminance,
    tone_is_ambiguous,
)
from codex_image.branding.models import BrandTemplate, PlacementConfig, content_hash
from codex_image.branding.placement import classify_layout, compute_placement


def _png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _solid(size: tuple[int, int], color, mode: str = "RGB") -> Image.Image:
    return Image.new(mode, size, color)


def _default_template(
    *,
    theme_mode: str = "auto",
    variant_policy: str = "per-element",
    anchor_logo: str = "top-left",
    anchor_slogan: str = "bottom-right",
    width_ratio_logo: float = 0.16,
    width_ratio_slogan: float = 0.30,
    margin: float = 0.035,
) -> BrandTemplate:
    placements = {
        layout: {
            "logo": PlacementConfig(anchor_logo, width_ratio_logo, margin, margin),
            "slogan": PlacementConfig(anchor_slogan, width_ratio_slogan, margin, margin),
        }
        for layout in ("square", "portrait", "landscape")
    }
    return BrandTemplate(
        id="test-template",
        version=1,
        name="Test",
        theme_mode=theme_mode,
        variant_policy=variant_policy,
        placements=placements,
        asset_variants={
            "light-assets": {"logo": "logo-light", "slogan": "slogan-light"},
            "dark-assets": {"logo": "logo-dark", "slogan": "slogan-dark"},
        },
    )


class ClassifyLayoutTests(unittest.TestCase):
    def test_square_at_one_to_one(self) -> None:
        self.assertEqual(classify_layout(1024, 1024), "square")

    def test_square_band_includes_0_95(self) -> None:
        # 0.95 ratio sits inside the [0.9, 1.1] band.
        self.assertEqual(classify_layout(950, 1000), "square")

    def test_square_band_includes_1_05(self) -> None:
        self.assertEqual(classify_layout(1050, 1000), "square")

    def test_landscape_16_to_9(self) -> None:
        self.assertEqual(classify_layout(1920, 1080), "landscape")

    def test_portrait_9_to_16(self) -> None:
        self.assertEqual(classify_layout(1080, 1920), "portrait")

    def test_degenerate_dimensions_default_to_square(self) -> None:
        self.assertEqual(classify_layout(0, 0), "square")


class ComputePlacementTests(unittest.TestCase):
    def _config(self, anchor: str, width_ratio: float = 0.2, margin: float = 0.05) -> PlacementConfig:
        return PlacementConfig(anchor, width_ratio, margin, margin)

    def test_top_left_anchor(self) -> None:
        # canvas 1000x1000, element 200x100, ratio 0.2, margin 0.05
        placement = self._config("top-left")
        x, y, w, h = compute_placement(1000, 1000, placement, 200, 100)
        self.assertEqual((x, y, w, h), (50, 50, 200, 100))

    def test_top_right_anchor(self) -> None:
        placement = self._config("top-right")
        x, y, w, h = compute_placement(1000, 1000, placement, 200, 100)
        # x = canvas_w - target_w - margin = 1000 - 200 - 50 = 750
        self.assertEqual((x, y, w, h), (750, 50, 200, 100))

    def test_top_center_anchor(self) -> None:
        placement = self._config("top-center")
        x, y, w, h = compute_placement(1000, 1000, placement, 200, 100)
        self.assertEqual((x, y, w, h), (400, 50, 200, 100))

    def test_bottom_left_anchor(self) -> None:
        placement = self._config("bottom-left")
        x, y, w, h = compute_placement(1000, 1000, placement, 200, 100)
        # y = canvas_h - target_h - margin = 1000 - 100 - 50 = 850
        self.assertEqual((x, y, w, h), (50, 850, 200, 100))

    def test_bottom_right_anchor(self) -> None:
        placement = self._config("bottom-right")
        x, y, w, h = compute_placement(1000, 1000, placement, 200, 100)
        self.assertEqual((x, y, w, h), (750, 850, 200, 100))

    def test_bottom_center_anchor(self) -> None:
        placement = self._config("bottom-center")
        x, y, w, h = compute_placement(1000, 1000, placement, 200, 100)
        self.assertEqual((x, y, w, h), (400, 850, 200, 100))

    def test_aspect_ratio_preserved_for_tall_element(self) -> None:
        # element 100x400 (tall) at width ratio 0.5 on a 1000 wide canvas.
        placement = self._config("top-left", width_ratio=0.5, margin=0.0)
        x, y, w, h = compute_placement(1000, 1000, placement, 100, 400)
        # target_w = 500; scale = 5; target_h = 400*5 = 2000 -> clamped to
        # canvas_h 1000, then width re-derived: 1000/400*100 = 250.
        self.assertEqual(w, 250)
        self.assertEqual(h, 1000)
        self.assertEqual((x, y), (0, 0))

    def test_width_ratio_clamped_to_unit(self) -> None:
        # ratio > 1 must clamp so the element never exceeds the canvas.
        placement = PlacementConfig("top-left", width_ratio=2.0, margin_x_ratio=0.0, margin_y_ratio=0.0)
        x, y, w, h = compute_placement(500, 500, placement, 100, 100)
        self.assertEqual(w, 500)
        self.assertEqual(h, 500)
        self.assertEqual((x, y), (0, 0))

    def test_margin_clamped_to_unit(self) -> None:
        placement = PlacementConfig("bottom-right", width_ratio=0.2, margin_x_ratio=5.0, margin_y_ratio=5.0)
        x, y, w, h = compute_placement(1000, 1000, placement, 200, 100)
        # margin clamped to 1.0 -> margin 1000; box pushed fully off-canvas.
        self.assertEqual(w, 200)
        self.assertEqual(h, 100)
        self.assertEqual(x, 1000 - 200 - 1000)
        self.assertEqual(y, 1000 - 100 - 1000)


class MeanLuminanceTests(unittest.TestCase):
    def test_white_is_255(self) -> None:
        image = _solid((64, 64), (255, 255, 255))
        self.assertAlmostEqual(mean_luminance(image), 255.0, places=1)

    def test_black_is_0(self) -> None:
        image = _solid((64, 64), (0, 0, 0))
        self.assertAlmostEqual(mean_luminance(image), 0.0, places=1)

    def test_mid_gray(self) -> None:
        image = _solid((64, 64), (128, 128, 128))
        self.assertAlmostEqual(mean_luminance(image), 128.0, places=1)


class ChooseAssetToneTests(unittest.TestCase):
    def test_bright_background_picks_dark_assets(self) -> None:
        # White canvas needs dark ink to be legible.
        self.assertEqual(choose_asset_tone(255.0), "dark-assets")

    def test_dark_background_picks_light_assets(self) -> None:
        self.assertEqual(choose_asset_tone(0.0), "light-assets")

    def test_threshold_boundary_is_light(self) -> None:
        # Values at the threshold are treated as dark background -> light ink.
        self.assertEqual(choose_asset_tone(128.0), "light-assets")

    def test_just_above_threshold_is_dark(self) -> None:
        self.assertEqual(choose_asset_tone(128.0 + 0.1), "dark-assets")

    def test_return_value_is_a_valid_asset_variant_key(self) -> None:
        template = _default_template()
        valid_keys = set(template.asset_variants.keys())
        self.assertIn(choose_asset_tone(255.0), valid_keys)
        self.assertIn(choose_asset_tone(0.0), valid_keys)


class ToneIsAmbiguousTests(unittest.TestCase):
    def test_extremes_are_not_ambiguous(self) -> None:
        self.assertFalse(tone_is_ambiguous(255.0))
        self.assertFalse(tone_is_ambiguous(0.0))

    def test_near_threshold_is_ambiguous(self) -> None:
        self.assertTrue(tone_is_ambiguous(128.0))
        self.assertTrue(tone_is_ambiguous(128.0 + CONTRAST_AMBIGUOUS_BAND - 1))
        self.assertTrue(tone_is_ambiguous(128.0 - CONTRAST_AMBIGUOUS_BAND + 1))


class ContentHashTests(unittest.TestCase):
    def test_identical_templates_hash_equal(self) -> None:
        self.assertEqual(content_hash(_default_template()), content_hash(_default_template()))

    def test_different_field_changes_hash(self) -> None:
        a = _default_template()
        b = _default_template()
        object.__setattr__(b, "name", "Other")
        self.assertNotEqual(content_hash(a), content_hash(b))

    def test_placement_change_changes_hash(self) -> None:
        a = _default_template()
        b = _default_template(anchor_logo="bottom-right")
        self.assertNotEqual(content_hash(a), content_hash(b))

    def test_hash_is_hex_sha256_length(self) -> None:
        self.assertEqual(len(content_hash(_default_template())), 64)


class ComposeTests(unittest.TestCase):
    def test_white_canvas_with_red_logo_and_blue_slogan_preserves_size(self) -> None:
        canvas = _solid((512, 512), (255, 255, 255))
        # Solid red/blue overlays with full opacity.
        logo = _solid((100, 60), (220, 30, 30), mode="RGBA")
        slogan = _solid((300, 60), (30, 30, 220), mode="RGBA")
        template = _default_template()

        composed = compose(canvas, logo, slogan, template)

        self.assertEqual(composed.size, (512, 512))
        self.assertEqual(composed.mode, "RGBA")

    def test_logo_pixels_actually_composited(self) -> None:
        canvas = _solid((512, 512), (255, 255, 255))
        logo = _solid((100, 60), (220, 30, 30), mode="RGBA")
        slogan = _solid((300, 60), (30, 30, 220), mode="RGBA")
        template = _default_template()
        composed = compose(canvas, logo, slogan, template)

        # With auto theme on a white canvas, no scrim is dropped (luminance is
        # 255, far from the threshold). So the top-left region (where the logo
        # sits) should be dominated by the logo's red ink, not the white base.
        pixel = composed.getpixel((60, 30))
        self.assertGreater(pixel[0], 150)  # red channel high
        self.assertLess(pixel[1], 100)     # green low
        self.assertLess(pixel[2], 100)     # blue low

    def test_report_layout_and_tone_on_white_square(self) -> None:
        canvas = _solid((512, 512), (255, 255, 255))
        logo = _solid((100, 60), (220, 30, 30), mode="RGBA")
        slogan = _solid((300, 60), (30, 30, 220), mode="RGBA")
        template = _default_template()
        _, report = compose_with_report(canvas, logo=logo, slogan=slogan, template=template)

        self.assertEqual(report["layout"], "square")
        self.assertEqual(report["tone"], "dark-assets")  # white -> dark ink
        elements = report["elements"]
        # No scrim needed on a clearly bright background.
        self.assertFalse(elements["logo"]["scrim"])
        self.assertFalse(elements["slogan"]["scrim"])

    def test_dark_canvas_does_not_trigger_scrim_and_picks_light_tone(self) -> None:
        canvas = _solid((512, 512), (0, 0, 0))
        logo = _solid((100, 60), (235, 235, 235), mode="RGBA")
        slogan = _solid((300, 60), (235, 235, 235), mode="RGBA")
        template = _default_template()
        _, report = compose_with_report(canvas, logo=logo, slogan=slogan, template=template)

        self.assertEqual(report["tone"], "light-assets")
        elements = report["elements"]
        self.assertFalse(elements["logo"]["scrim"])
        self.assertFalse(elements["slogan"]["scrim"])

    def test_mid_gray_canvas_triggers_scrim(self) -> None:
        # A mid-gray canvas (luminance ~128) is ambiguous, so the compositor
        # drops a scrim behind each element.
        canvas = _solid((512, 512), (128, 128, 128))
        logo = _solid((100, 60), (220, 30, 30), mode="RGBA")
        slogan = _solid((300, 60), (30, 30, 220), mode="RGBA")
        template = _default_template()
        _, report = compose_with_report(canvas, logo=logo, slogan=slogan, template=template)

        elements = report["elements"]
        self.assertTrue(elements["logo"]["scrim"])
        self.assertTrue(elements["slogan"]["scrim"])

    def test_forced_theme_mode_skips_scrim_and_samples(self) -> None:
        # A mid-gray canvas would normally trigger a scrim, but forcing a tone
        # disables the scrim path entirely.
        canvas = _solid((512, 512), (128, 128, 128))
        logo = _solid((100, 60), (220, 30, 30), mode="RGBA")
        slogan = _solid((300, 60), (30, 30, 220), mode="RGBA")
        template = _default_template()
        _, report = compose_with_report(
            canvas, logo=logo, slogan=slogan, template=template, theme_mode_override="dark-assets"
        )
        elements = report["elements"]
        self.assertFalse(elements["logo"]["scrim"])
        self.assertFalse(elements["slogan"]["scrim"])
        self.assertEqual(report["tone"], "dark-assets")

    def test_layout_without_placement_returns_canvas_untouched(self) -> None:
        # A template with no placement for the detected layout composes nothing.
        template = BrandTemplate(
            id="empty",
            version=1,
            name="Empty",
            theme_mode="auto",
            variant_policy="per-element",
            placements={},  # nothing for square
            asset_variants={"light-assets": {"logo": "l", "slogan": "l"}, "dark-assets": {"logo": "d", "slogan": "d"}},
        )
        canvas = _solid((256, 256), (10, 20, 30))
        logo = _solid((40, 40), (255, 0, 0), mode="RGBA")
        slogan = _solid((40, 40), (0, 255, 0), mode="RGBA")
        composed, report = compose_with_report(canvas, logo=logo, slogan=slogan, template=template)

        self.assertEqual(report["elements"], {})
        self.assertEqual(composed.getpixel((0, 0)), (10, 20, 30, 255))


class ComputeRequestHashTests(unittest.TestCase):
    def test_stable_for_identical_inputs(self) -> None:
        template = _default_template()
        a = compute_request_hash(b"raw", template, b"logo", b"slogan")
        b = compute_request_hash(b"raw", template, b"logo", b"slogan")
        self.assertEqual(a, b)

    def test_changes_when_raw_changes(self) -> None:
        template = _default_template()
        a = compute_request_hash(b"raw-a", template, b"logo", b"slogan")
        b = compute_request_hash(b"raw-b", template, b"logo", b"slogan")
        self.assertNotEqual(a, b)

    def test_changes_when_logo_changes(self) -> None:
        template = _default_template()
        a = compute_request_hash(b"raw", template, b"logo-a", b"slogan")
        b = compute_request_hash(b"raw", template, b"logo-b", b"slogan")
        self.assertNotEqual(a, b)

    def test_changes_when_slogan_changes(self) -> None:
        template = _default_template()
        a = compute_request_hash(b"raw", template, b"logo", b"slogan-a")
        b = compute_request_hash(b"raw", template, b"logo", b"slogan-b")
        self.assertNotEqual(a, b)

    def test_changes_when_template_changes(self) -> None:
        a = compute_request_hash(b"raw", _default_template(anchor_logo="top-left"), b"logo", b"slogan")
        b = compute_request_hash(b"raw", _default_template(anchor_logo="bottom-right"), b"logo", b"slogan")
        self.assertNotEqual(a, b)

    def test_version_is_part_of_the_hash_contract(self) -> None:
        # Sanity: the constant is defined and non-empty so future bumps work.
        self.assertIsInstance(COMPOSITOR_VERSION, str)
        self.assertTrue(COMPOSITOR_VERSION)


class ComposeWithAssetsTests(unittest.TestCase):
    """Auto-selecting variant: both tone variants supplied, sampler picks."""

    def _dual_assets(self) -> dict[str, dict[str, Image.Image]]:
        # Distinct colors per tone so we can detect which asset was burned in.
        # light-assets = near-white ink (for dark backgrounds)
        # dark-assets = near-black ink (for bright backgrounds)
        return {
            "light-assets": {
                "logo": _solid((100, 60), (245, 245, 245), mode="RGBA"),
                "slogan": _solid((300, 60), (245, 245, 245), mode="RGBA"),
            },
            "dark-assets": {
                "logo": _solid((100, 60), (20, 20, 20), mode="RGBA"),
                "slogan": _solid((300, 60), (20, 20, 20), mode="RGBA"),
            },
        }

    def test_bright_canvas_uses_dark_assets(self) -> None:
        canvas = _solid((512, 512), (255, 255, 255))
        _, report = compose_with_assets(canvas, assets=self._dual_assets(), template=_default_template())

        self.assertEqual(report["tone"], "dark-assets")
        self.assertEqual(report["elements"]["logo"]["chosen_tone"], "dark-assets")
        self.assertEqual(report["elements"]["slogan"]["chosen_tone"], "dark-assets")

    def test_dark_canvas_uses_light_assets(self) -> None:
        canvas = _solid((512, 512), (10, 10, 10))
        _, report = compose_with_assets(canvas, assets=self._dual_assets(), template=_default_template())

        self.assertEqual(report["tone"], "light-assets")
        self.assertEqual(report["elements"]["logo"]["chosen_tone"], "light-assets")
        self.assertEqual(report["elements"]["slogan"]["chosen_tone"], "light-assets")

    def test_dark_canvas_burns_in_light_ink_pixels(self) -> None:
        # Regression for the value-validation finding: a dark canvas must end up
        # with light ink (high luminance) in the logo region, not dark ink.
        canvas = _solid((512, 512), (10, 10, 10))
        composed, _ = compose_with_assets(canvas, assets=self._dual_assets(), template=_default_template())

        # Logo sits top-left; sample a pixel well inside it.
        pixel = composed.getpixel((40, 25))
        self.assertGreater(sum(pixel[:3]), 500)  # bright ink on dark bg

    def test_forced_tone_pins_both_elements(self) -> None:
        canvas = _solid((512, 512), (10, 10, 10))  # would pick light-assets
        _, report = compose_with_assets(
            canvas,
            assets=self._dual_assets(),
            template=_default_template(),
            theme_mode_override="dark-assets",
        )

        self.assertEqual(report["tone"], "dark-assets")
        self.assertEqual(report["elements"]["logo"]["chosen_tone"], "dark-assets")

    def test_report_includes_chosen_tone_key(self) -> None:
        canvas = _solid((512, 512), (255, 255, 255))
        _, report = compose_with_assets(canvas, assets=self._dual_assets(), template=_default_template())

        for element in report["elements"].values():
            self.assertIn("chosen_tone", element)


class CLIBatchTests(unittest.TestCase):
    def test_cli_brands_all_inputs_with_suffix(self) -> None:
        from codex_image.branding.cli import main as cli_main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = root / "in"
            output = root / "out"
            inputs.mkdir()
            (inputs / "a.png").write_bytes(_png(_solid((512, 512), (255, 255, 255))))
            (inputs / "b.png").write_bytes(_png(_solid((768, 432), (255, 255, 255))))
            logo_path = root / "logo.png"
            slogan_path = root / "slogan.png"
            logo_path.write_bytes(_png(_solid((100, 60), (220, 30, 30), mode="RGBA")))
            slogan_path.write_bytes(_png(_solid((300, 60), (30, 30, 220), mode="RGBA")))

            code = cli_main([
                "--inputs", str(inputs),
                "--logo", str(logo_path),
                "--slogan", str(slogan_path),
                "--output", str(output),
            ])

            self.assertEqual(code, 0)
            self.assertTrue((output / "a-branded.png").exists())
            self.assertTrue((output / "b-branded.png").exists())
            with Image.open(output / "a-branded.png") as branded:
                self.assertEqual(branded.size, (512, 512))
                self.assertEqual(branded.mode, "RGB")

    def test_cli_auto_select_mode_uses_matching_tone_per_image(self) -> None:
        from codex_image.branding.cli import main as cli_main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = root / "in"
            output = root / "out"
            inputs.mkdir()
            # A bright canvas and a dark canvas in the same batch.
            (inputs / "bright.png").write_bytes(_png(_solid((512, 512), (255, 255, 255))))
            (inputs / "dark.png").write_bytes(_png(_solid((512, 512), (10, 10, 10))))
            asset = lambda color: _png(_solid((100, 60), color, mode="RGBA"))
            (root / "logo-light.png").write_bytes(asset((245, 245, 245)))
            (root / "logo-dark.png").write_bytes(asset((20, 20, 20)))
            (root / "slogan-light.png").write_bytes(asset((245, 245, 245)))
            (root / "slogan-dark.png").write_bytes(asset((20, 20, 20)))

            code = cli_main([
                "--inputs", str(inputs),
                "--logo-light", str(root / "logo-light.png"),
                "--logo-dark", str(root / "logo-dark.png"),
                "--slogan-light", str(root / "slogan-light.png"),
                "--slogan-dark", str(root / "slogan-dark.png"),
                "--output", str(output),
            ])

            self.assertEqual(code, 0)
            self.assertTrue((output / "bright-branded.png").exists())
            self.assertTrue((output / "dark-branded.png").exists())
            # Both processed despite the brightness mismatch — auto-select
            # resolved the right asset for each.

    def test_cli_rejects_missing_assets(self) -> None:
        from codex_image.branding.cli import main as cli_main

        with tempfile.TemporaryDirectory() as tmp:
            inputs = Path(tmp) / "in"
            inputs.mkdir()
            (inputs / "a.png").write_bytes(_png(_solid((64, 64), (0, 0, 0))))

            # Neither single nor all-four provided -> error.
            code = cli_main(["--inputs", str(inputs), "--output", str(Path(tmp) / "out")])

            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()

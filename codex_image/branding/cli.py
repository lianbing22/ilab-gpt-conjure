from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from PIL import Image, UnidentifiedImageError

from codex_image.branding.compositor import compose_with_report
from codex_image.branding.models import BrandTemplate, PlacementConfig


def _build_default_template(args: argparse.Namespace) -> BrandTemplate:
    """Construct a BrandTemplate purely from CLI flags (no external JSON)."""
    placements = {
        layout: {
            "logo": PlacementConfig(
                anchor=args.anchor_logo,
                width_ratio=args.width_ratio_logo,
                margin_x_ratio=args.margin,
                margin_y_ratio=args.margin,
            ),
            "slogan": PlacementConfig(
                anchor=args.anchor_slogan,
                width_ratio=args.width_ratio_slogan,
                margin_x_ratio=args.margin,
                margin_y_ratio=args.margin,
            ),
        }
        for layout in ("square", "portrait", "landscape")
    }
    return BrandTemplate(
        id="cli-default-template",
        version=1,
        name="CLI default",
        theme_mode=args.theme_mode,
        variant_policy="per-element",
        placements=placements,
        # Asset ids only — the CLI loads the actual asset files itself.
        asset_variants={
            "light-assets": {"logo": "logo-light", "slogan": "slogan-light"},
            "dark-assets": {"logo": "logo-dark", "slogan": "slogan-dark"},
        },
    )


def _iter_inputs(inputs_dir: Path) -> list[Path]:
    """List candidate input PNGs in deterministic name order."""
    suffixes = {".png"}
    return sorted(p for p in inputs_dir.iterdir() if p.is_file() and p.suffix.lower() in suffixes)


def _branded_output_path(output_dir: Path, source: Path) -> Path:
    """Map an input filename to <stem>-branded.png in the output dir."""
    return output_dir / f"{source.stem}-branded.png"


def _process_one(
    source: Path,
    output: Path,
    logo: Image.Image,
    slogan: Image.Image,
    template: BrandTemplate,
) -> dict[str, object]:
    """Compose one image and write it out. Returns the diagnostic report."""
    with Image.open(source) as raw:
        # Detach from the file-backed image so the result outlives the `with`.
        raw.load()
        composed, report = compose_with_report(
            raw,
            logo=logo,
            slogan=slogan,
            template=template,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    # Flatten to RGB and save as PNG so branded outputs are portable and
    # preview-friendly (no alpha surprises in viewers).
    composed.convert("RGB").save(output, format="PNG")
    report["output"] = str(output)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m codex_image.branding.cli",
        description="Offline batch brand overlay (Logo + Slogan PNGs) for generated images.",
    )
    parser.add_argument("--inputs", required=True, type=Path, help="Directory of base PNG images to brand.")
    parser.add_argument("--logo", required=True, type=Path, help="Transparent PNG logo to overlay.")
    parser.add_argument("--slogan", required=True, type=Path, help="Transparent PNG slogan to overlay.")
    parser.add_argument("--output", required=True, type=Path, help="Output directory for branded PNGs.")
    parser.add_argument("--anchor-logo", default="top-left", help="Corner for the logo.")
    parser.add_argument("--anchor-slogan", default="bottom-right", help="Corner for the slogan.")
    parser.add_argument("--width-ratio-logo", type=float, default=0.16, help="Logo width as a fraction of canvas width.")
    parser.add_argument("--width-ratio-slogan", type=float, default=0.30, help="Slogan width as a fraction of canvas width.")
    parser.add_argument("--margin", type=float, default=0.035, help="x and y margin as a fraction of canvas width / height.")
    parser.add_argument(
        "--theme-mode",
        default="auto",
        choices=["auto", "light-assets", "dark-assets"],
        help="Tone selection: auto samples the canvas, the others force a tone.",
    )
    args = parser.parse_args(argv)

    inputs_dir: Path = args.inputs
    output_dir: Path = args.output
    if not inputs_dir.is_dir():
        print(f"error: --inputs {inputs_dir} is not a directory", file=sys.stderr)
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        logo = Image.open(args.logo).convert("RGBA")
        slogan = Image.open(args.slogan).convert("RGBA")
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        print(f"error: could not load logo/slogan assets: {exc}", file=sys.stderr)
        return 2

    template = _build_default_template(args)

    sources = _iter_inputs(inputs_dir)
    if not sources:
        print(f"no input PNGs found in {inputs_dir}", file=sys.stderr)
        return 1

    processed = 0
    for source in sources:
        output = _branded_output_path(output_dir, source)
        try:
            report = _process_one(source, output, logo, slogan, template)
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            print(f"skip {source.name}: {exc}", file=sys.stderr)
            continue

        elements = report["elements"]
        assert isinstance(elements, dict)
        logo_el = elements["logo"]
        slogan_el = elements["slogan"]
        print(
            f"{source.name} -> {Path(str(report['output'])).name} | "
            f"layout={report['layout']} tone={report['tone']} | "
            f"logo box={logo_el['box']} scrim={logo_el['scrim']} | "
            f"slogan box={slogan_el['box']} scrim={slogan_el['scrim']}"
        )
        processed += 1

    print(f"done: branded {processed}/{len(sources)} image(s) into {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

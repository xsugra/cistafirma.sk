#!/usr/bin/env python3
"""Generate the favicon set in `frontend/public/` from the brand logo.

Why this file exists at all: a favicon is a handful of small binaries that git
stores and nobody can regenerate. Twelve months from now the logo is replaced,
the .ico still shows the old mark, and there is no way back except guessing which
sizes and which crop were used. So the crop is written down as code, and the
binaries are an output rather than a source.

Run it after replacing `frontend/logo/cistafirma-logo.png`:

    python3 scripts/generate-favicons.py

It needs Pillow (`pip install pillow`); it is a development-time tool and is not
part of any build. `frontend/Dockerfile.prod` never runs it -- the generated
files are committed, and `vite build` copies `frontend/public/` verbatim into
`dist/`, so production needs neither Python nor Pillow.

Three decisions in here are deliberate and are worth keeping if you edit it:

* The logo is a blue mark on a **transparent** field, so nothing is squared off by
  trimming the image: the mark is measured from the alpha channel and centred on
  a square canvas with an even margin. Hard-coding a crop box would silently
  mis-frame the next logo.

* The sizes at or below 48px get `ALPHA_GAMMA` applied to the alpha channel
  *after* resampling, and the larger ones do not. The mark is fine line art --
  1329px of drawing squeezed into 16 gives each output pixel ~83 source pixels to
  average, so every thin stroke lands as a pale wash and the tab icon reads as a
  smudge rather than as the logo. Weighting the averaged alpha back up is what
  "make it hold up at small sizes" means in practice. At 180px the same curve
  would do nothing useful (those pixels are already opaque) and would only harden
  the mark's soft edges, so it is scoped by size rather than applied throughout.

* `apple-touch-icon.png` is composited on **black**, and only that one is. iOS
  does not keep transparency in a home-screen icon, so what it composites onto is
  left to the platform; the mark carries a glow, and a glow on an unknown colour
  is a gamble. Black is the logo's own ground -- the mark as the file shows it --
  so the icon is the same image everywhere instead of a different one per device.
"""

from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "frontend" / "logo" / "cistafirma-logo.png"
OUT_DIR = REPO / "frontend" / "public"

# Alpha above which a pixel counts as the mark. The glow fades to nothing over a
# wide radius, so a threshold of 1 would grow the box to whatever faint haze the
# encoder left behind; 8 is above that noise floor and below the visible edge.
ALPHA_FLOOR = 8

# Empty space kept around the mark, as a fraction of the square, per side. A
# favicon is drawn in a 16px box with the tab bar's own padding around it, and a
# mark touching the edges reads as clipped rather than as large.
MARGIN = 0.08

# See the module docstring. 1.0 would mean "no adjustment".
ALPHA_GAMMA = 0.65
GAMMA_MAX_SIZE = 48

# Emitted sizes. 16 and 32 are the two a desktop browser actually asks for; 48 is
# what Windows uses for a desktop shortcut; 180 is iOS's home-screen icon.
ICO_SIZES = (16, 32, 48)
STANDALONE_PNGS = {"favicon-16x16.png": 16, "favicon-32x32.png": 32}
APPLE_TOUCH_SIZE = 180


def square_master(image: Image.Image) -> Image.Image:
    """The mark, centred on a transparent square canvas."""
    box = image.getchannel("A").point(lambda v: 255 if v > ALPHA_FLOOR else 0).getbbox()
    if box is None:
        raise SystemExit(f"{SOURCE} is fully transparent -- nothing to crop.")
    mark = image.crop(box)

    side = round(max(mark.size) / (1 - 2 * MARGIN))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(mark, ((side - mark.width) // 2, (side - mark.height) // 2))
    return canvas


def render(master: Image.Image, size: int) -> Image.Image:
    """One square icon at `size`, with the small-size alpha adjustment applied."""
    icon = master.resize((size, size), Image.LANCZOS)
    if size <= GAMMA_MAX_SIZE:
        alpha = icon.getchannel("A").point(lambda v: round(255 * (v / 255) ** ALPHA_GAMMA))
        icon.putalpha(alpha)
    return icon


def main() -> None:
    master = square_master(Image.open(SOURCE).convert("RGBA"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"source {SOURCE.name} -> square {master.size[0]}px")

    for name, size in STANDALONE_PNGS.items():
        render(master, size).save(OUT_DIR / name, optimize=True)

    # Opaque, on the logo's own black ground -- see the module docstring.
    apple = Image.new("RGBA", master.size, (0, 0, 0, 255))
    apple.alpha_composite(master)
    apple.convert("RGB").resize((APPLE_TOUCH_SIZE,) * 2, Image.LANCZOS).save(
        OUT_DIR / "apple-touch-icon.png", optimize=True
    )

    # One .ico holding every size, so a client that asks for the file at the site
    # root gets the size it wants rather than a downscaled 32. Each entry is the
    # same image as its standalone PNG (`append_images` is matched by exact size
    # and used as-is); letting Pillow derive them instead would give the .ico's
    # 16px a different, un-gamma'd image than `favicon-16x16.png`.
    frames = {size: render(master, size) for size in ICO_SIZES}
    largest = max(ICO_SIZES)
    frames[largest].save(
        OUT_DIR / "favicon.ico",
        format="ICO",
        # BMP rather than the PNG entries Pillow defaults to: it is what every
        # version of every client has read since Windows 95, at a cost of a
        # couple of KB on a file nobody downloads twice.
        bitmap_format="bmp",
        sizes=[(size, size) for size in ICO_SIZES],
        append_images=[frames[size] for size in ICO_SIZES if size != largest],
    )

    for path in sorted(OUT_DIR.iterdir()):
        print(f"  {path.name:24s} {path.stat().st_size:>7,d} B")


if __name__ == "__main__":
    main()

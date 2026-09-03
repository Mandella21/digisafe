"""Generate the raster favicons from the DigiSafe shield mark.

    python tools/build_favicons.py

Writes static/img/favicon.ico and the PNG sizes referenced by base.html and
account_base.html.

Why raster at all, when static/img/favicon.svg exists and every current browser
supports SVG favicons: browsers request /favicon.ico from the site root on
their own, before parsing any HTML, and several contexts that show a site icon
never read the <link> tags at all - bookmark bars restored from an old profile,
some in-app browsers, Windows pinned sites. Shipping both means the mark
appears everywhere rather than almost everywhere.

Drawn here rather than rasterised from the SVG because rendering SVG needs
libcairo, which is not present on a plain Windows install - so a tool that
converted the file would be a tool nobody could run. The geometry below mirrors
static/img/favicon.svg: a shield with two concentric ridges, deliberately
simplified, because detail that reads at 32px turns to mud at 16.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).resolve().parent.parent
IMG_DIR = BASE_DIR / "static" / "img"

# Drawn at this size and downsampled, which is what gives smooth edges without
# any explicit anti-aliasing: Pillow's LANCZOS filter does it on the way down.
SUPERSAMPLE = 1024

# The brand gradient, top-left to bottom-right, matching favicon.svg.
GRADIENT = [
    (0.00, (0x06, 0xB6, 0xD4)),
    (0.55, (0x25, 0x63, 0xEB)),
    (1.00, (0x1D, 0x4E, 0xD8)),
]


def _lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _gradient_image(size):
    """A diagonal gradient, evaluated per pixel along the top-left/bottom-right axis."""
    image = Image.new("RGB", (size, size))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            # Position along the diagonal, normalised to 0..1.
            t = (x + y) / (2 * (size - 1))
            for i in range(len(GRADIENT) - 1):
                t0, c0 = GRADIENT[i]
                t1, c1 = GRADIENT[i + 1]
                if t0 <= t <= t1:
                    pixels[x, y] = _lerp(c0, c1, (t - t0) / (t1 - t0))
                    break
            else:
                pixels[x, y] = GRADIENT[-1][1]
    return image


def _shield_mask(size):
    """The shield silhouette, as an alpha mask.

    Built from the same proportions as the SVG: a flat top, straight shoulders,
    and sides that draw in to a rounded point at the bottom.
    """
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    s = size / 32.0  # the SVG is authored on a 32-unit grid

    def p(x, y):
        return (x * s, y * s)

    # Upper body: flat top edge, straight sides down to where the taper starts.
    draw.polygon([p(16, 0.6), p(30.8, 6.1), p(30.8, 17.5), p(1.2, 17.5), p(1.2, 6.1)], fill=255)
    # Rounded top corners, so the shoulders are not knife-edged at small sizes.
    draw.rounded_rectangle([p(1.2, 5.4), p(30.8, 17.5)], radius=1.6 * s, fill=255)

    # Lower taper: sampled as a polygon rather than a true bezier - at 16px the
    # difference is invisible, and this keeps the shape exact and predictable.
    steps = 160
    left, right = [], []
    for i in range(steps + 1):
        t = i / steps
        # Half-width shrinks from full at the shoulder to nothing at the tip,
        # easing off gently so the sides bow outward like the SVG's curve.
        half = 14.8 * (1 - t ** 2.05)
        y = 17.5 + t * (31.5 - 17.5)
        left.append(p(16 - half, y))
        right.append(p(16 + half, y))
    draw.polygon(left + list(reversed(right)), fill=255)

    return mask


def _draw_ridges(image, size):
    """Two white concentric arcs, the 'signal' motif from the full logo."""
    draw = ImageDraw.Draw(image)
    s = size / 32.0

    def box(cx, cy, r):
        return [(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s]

    # Outer ridge, then inner - both centred where the SVG places them.
    # The inner radius is larger than the SVG's because a 2.6-wide stroke on a
    # 2.8 radius closes into a solid blob at 512px; opened out, it still reads
    # as an arc at every size.
    draw.arc(box(16, 19.6, 8.0), start=200, end=340, fill=(255, 255, 255, 255), width=int(2.6 * s))
    draw.arc(box(16, 19.6, 4.0), start=200, end=340, fill=(255, 255, 255, 255), width=int(2.4 * s))
    # The vertical tail below the ridges, closing the motif.
    draw.line([16 * s, 20.4 * s, 16 * s, 25.8 * s], fill=(255, 255, 255, 255), width=int(2.4 * s))


def build_master(size=SUPERSAMPLE):
    gradient = _gradient_image(size).convert("RGBA")
    gradient.putalpha(_shield_mask(size))
    _draw_ridges(gradient, size)
    return gradient


def main() -> int:
    if not IMG_DIR.is_dir():
        print(f"Cannot find {IMG_DIR}", file=sys.stderr)
        return 1

    print(f"  Drawing master at {SUPERSAMPLE}x{SUPERSAMPLE}...")
    master = build_master()

    outputs = {
        "favicon-16.png": 16,
        "favicon-32.png": 32,
        "favicon-48.png": 48,
        "apple-touch-icon.png": 180,
        "icon-192.png": 192,
        "icon-512.png": 512,
    }
    for name, size in outputs.items():
        master.resize((size, size), Image.LANCZOS).save(IMG_DIR / name, "PNG", optimize=True)
        print(f"  wrote {name:24} {size}x{size}")

    # A multi-resolution .ico, so the browser picks the size it needs rather
    # than scaling one badly.
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
    master.resize((64, 64), Image.LANCZOS).save(
        IMG_DIR / "favicon.ico", format="ICO", sizes=ico_sizes
    )
    print(f"  wrote {'favicon.ico':24} {', '.join(f'{w}x{h}' for w, h in ico_sizes)}")

    print("\n  Done. These are committed, so no build step is needed to deploy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

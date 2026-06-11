"""One-off generator for PWA icons.

Produces PNGs in static/icons/ matching the sidebar logo style:
indigo rounded square with a white "A" wordmark centered. Run via:

    uv run python scripts/generate_pwa_icons.py

Run again whenever you swap the brand color or wordmark. The output
PNGs are committed (they're gitignored if you'd rather regenerate
in CI — see static/icons/.gitignore).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent.parent / "static" / "icons"

# Match `--primary` from static_src/css/input.css (oklch(0.55 0.25 264) = indigo).
PRIMARY = (88, 92, 222, 255)
FOREGROUND = (255, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)

# (filename, size_px, corner_radius_pct, padding_pct)
#   padding_pct > 0 = "maskable" — leaves safe-zone for OS-level cropping.
ICONS = [
    ("favicon.png",            32,  20, 0),
    ("apple-touch-icon.png",   180, 20, 0),
    ("icon-192.png",           192, 20, 0),
    ("icon-512.png",           512, 20, 0),
    ("icon-maskable-512.png",  512, 50, 12),  # round + safe-zone padding
]


def _font_for_size(size_px: int) -> ImageFont.FreeTypeFont:
    """Pick a system-bundled bold font sized to fit nicely."""
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",        # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",     # Linux
        "/Library/Fonts/Arial Bold.ttf",                            # macOS old
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, int(size_px * 0.55))
    return ImageFont.load_default()


def render_one(filename: str, size: int, corner_pct: int, padding_pct: int) -> None:
    img = Image.new("RGBA", (size, size), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    pad = int(size * padding_pct / 100)
    radius = int((size - 2 * pad) * corner_pct / 100)
    draw.rounded_rectangle(
        (pad, pad, size - pad, size - pad),
        radius=radius,
        fill=PRIMARY,
    )

    font = _font_for_size(size - 2 * pad)
    text = "A"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # Center optically — `bbox` includes a tiny vertical bias for descenders.
    tx = (size - tw) / 2 - bbox[0]
    ty = (size - th) / 2 - bbox[1]
    draw.text((tx, ty), text, font=font, fill=FOREGROUND)

    out = OUT_DIR / filename
    img.save(out, format="PNG", optimize=True)
    print(f"  ✓ {filename} ({size}x{size})")


def render_svg() -> None:
    """Single scalable SVG for `<link rel="icon" type="image/svg+xml">`.

    Modern browsers prefer this over PNG when available — it's tiny,
    crisp at any size, and theme-aware via currentColor if we wanted.
    """
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
        '<rect width="512" height="512" rx="100" fill="#585cde"/>'
        '<text x="256" y="365" text-anchor="middle" '
        'font-family="-apple-system,Segoe UI,sans-serif" '
        'font-weight="800" font-size="320" fill="#fff">A</text>'
        '</svg>\n'
    )
    out = OUT_DIR / "icon.svg"
    out.write_text(svg)
    print(f"  ✓ icon.svg")


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"→ Writing PWA icons to {OUT_DIR}")
    for filename, size, corner_pct, padding_pct in ICONS:
        render_one(filename, size, corner_pct, padding_pct)
    render_svg()
    print("✓ done")

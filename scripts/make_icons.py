"""Generate the Resident app's PWA icons (apps/resident/public/icon-192.png, icon-512.png).

A water drop over waves on the brand blue. Usage: python scripts/make_icons.py (needs Pillow).
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "apps" / "resident" / "public"
BRAND, WHITE, WAVE = (11, 61, 145), (255, 255, 255), (66, 165, 245)


def icon(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), BRAND)
    d = ImageDraw.Draw(img)
    s = size / 512
    # water drop
    d.ellipse([176 * s, 150 * s, 336 * s, 310 * s], fill=WHITE)
    d.polygon([(256 * s, 60 * s), (185 * s, 200 * s), (327 * s, 200 * s)], fill=WHITE)
    # waves
    for i, y in enumerate((360, 410)):
        for x in range(40, 480, 80):
            d.arc([(x) * s, (y - 25) * s, (x + 80) * s, (y + 25) * s], start=0 if i else 180, end=180 if i else 360,
                  fill=WAVE, width=max(int(14 * s), 2))
    return img


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        icon(size).save(OUT / f"icon-{size}.png")
        print("wrote", OUT / f"icon-{size}.png")

"""Build the site's screen images from the raw iPhone screenshots.

- Dims unrelated parts of settings screens.
- Removes the real status bar glyphs (inpainting) and draws a clean 9:41 bar.
- Resizes to 720px wide WebP.
- Builds icon PNGs from the app icon.
Usage: python -I process.py <src_dir> <repo_assets_dir>
"""
import sys
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SRC, DST = sys.argv[1], sys.argv[2]
FONT = ImageFont.truetype("C:/Windows/Fonts/seguisb.ttf", 54 * 4)

SCREENS = {
    1: "hero", 23: "colour", 4: "photo-access", 6: "find-trips", 7: "scanning",
    8: "trips-found", 10: "globe", 11: "japan", 12: "japan-route", 13: "stop",
    14: "countries", 17: "trip-settings", 18: "privacy-settings",
    19: "style-outdoors", 20: "style-dark", 21: "style-satellite", 22: "style-light",
}
LIGHT = {22}
# Rows (original px) to keep bright; everything else below the status bar is dimmed.
KEEP = {
    17: (478, 1100),   # Merge photos within + New trip after a gap of
    18: (528, 1712),   # Privacy & Data section
}


def dim_except(im, keep):
    w, h = im.size
    mask = Image.new("L", (w, h), 255)
    ImageDraw.Draw(mask).rectangle((0, keep[0], w, keep[1]), fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(10))
    mask.paste(0, (0, 0, w, 150))   # leave the status bar area as is
    bg = Image.new("RGB", (w, h), (21, 22, 26))
    dimmed = Image.blend(im, bg, 0.72)
    return Image.composite(dimmed, im, mask)


def erase_status(im):
    a = np.array(im)
    region = np.zeros(a.shape[:2], np.uint8)
    region[55:140, 110:330] = 1     # time + flame/arrow icon
    region[55:140, 845:1120] = 1    # signal, wifi, battery
    white = (a.min(axis=2) > 140).astype(np.uint8)
    mask = region * white
    mask[70:128, 1010:1112] = 1     # battery: whole body incl. digits/grey tail
    mask = cv2.dilate(mask * 255, np.ones((7, 7), np.uint8))
    out = cv2.inpaint(cv2.cvtColor(a, cv2.COLOR_RGB2BGR), mask, 6, cv2.INPAINT_TELEA)
    return Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))


def draw_status(im, fg):
    """Draw a clean iOS status bar at 4x then downsample for anti-aliasing."""
    S = 4
    x0, y0, x1, y1 = 100, 50, 1130, 140
    m = Image.new("L", ((x1 - x0) * S, (y1 - y0) * S), 0)
    d = ImageDraw.Draw(m)
    P = lambda x, y: ((x - x0) * S, (y - y0) * S)

    # Time
    d.text(P(224, 98), "9:41", font=FONT, fill=255, anchor="mm")

    # Signal bars
    bottom, bw, gap = 115, 11, 4.6
    for i, hgt in enumerate((14, 21, 28, 36)):
        bx = 865 + i * (bw + gap)
        d.rounded_rectangle((*P(bx, bottom - hgt), *P(bx + bw, bottom)), radius=3 * S, fill=255)

    # Wi-Fi: three annular sectors around a centre below the glyph
    cx, cy = 971.5, 116
    rings = [(40, 32), (27, 19), (14, 0)]
    for ro, ri in rings:
        d.pieslice((*P(cx - ro, cy - ro), *P(cx + ro, cy + ro)), 225, 315, fill=255)
        if ri:
            d.pieslice((*P(cx - ri, cy - ri), *P(cx + ri, cy + ri)), 225, 315, fill=0)

    # Battery: translucent outline, solid full charge, nub
    d.rounded_rectangle((*P(1018, 79), *P(1092, 117)), radius=12 * S, fill=110)
    d.rounded_rectangle((*P(1021.5, 82.5), *P(1088.5, 113.5)), radius=9 * S, fill=0)
    d.rounded_rectangle((*P(1024, 85), *P(1086, 111)), radius=7 * S, fill=255)
    d.rounded_rectangle((*P(1095, 91), *P(1100, 105)), radius=2 * S, fill=110)

    m = m.resize((x1 - x0, y1 - y0), Image.LANCZOS)
    layer = Image.new("RGB", m.size, fg)
    im.paste(layer, (x0, y0), m)
    return im


for i, name in SCREENS.items():
    im = Image.open(f"{SRC}/{i}.png").convert("RGB")
    if i not in LIGHT:
        im = erase_status(im)
    if i in KEEP:
        im = dim_except(im, KEEP[i])
    im = draw_status(im, (0, 0, 0) if i in LIGHT else (255, 255, 255))
    im = im.resize((720, round(720 * im.height / im.width)), Image.LANCZOS)
    im.save(f"{DST}/screens/{name}.webp", "WEBP", quality=82, method=6)

# App icon
icon = Image.open(f"{SRC}/24.png").convert("RGB")
icon.resize((180, 180), Image.LANCZOS).save(f"{DST}/apple-touch-icon.png")
big = icon.resize((768, 768), Image.LANCZOS)
mask = Image.new("L", big.size, 0)
ImageDraw.Draw(mask).rounded_rectangle((0, 0, 767, 767), radius=int(768 * 0.225), fill=255)
big.putalpha(mask)
big.resize((192, 192), Image.LANCZOS).save(f"{DST}/icon-192.png")
big.resize((64, 64), Image.LANCZOS).save(f"{DST}/favicon.png")
print("done")

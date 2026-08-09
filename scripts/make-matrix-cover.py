#!/usr/bin/env python3
"""Generate a RAINBOW MATRIX cover image for a post that has no cover.

The look is the dashboard theme, not an approximation of it: the palette, the glyph
set, the per-column hue spread and the scanline+vignette veil are all taken from
~/homepage/config/custom.css and custom.js. This renders one still frame of that
animation rather than simulating it.

Deterministic: the rain is seeded from the slug, so regenerating a cover produces the
same image and a rebuild does not churn the repo.

    python3 scripts/make-matrix-cover.py <slug> "<title>" [--out static/images/posts/<slug>-cover.png]

Lives in the repo (not ~/Desktop/my_scripts) because it is a blog tool and has to
survive a VM rebuild — CLAUDE.md's rule for anything that must persist.
"""

import argparse
import colorsys
import hashlib
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

WIDTH, HEIGHT = 1200, 500

# --- custom.css:15-38 -------------------------------------------------------
RAINBOW = ["#ff2e63", "#ff8a00", "#ffe600", "#25ff6a", "#00e5ff", "#7b5bff", "#ff2ec4"]
TEXT = "#e9fff3"

# custom.js GLYPHS, verbatim.
GLYPHS = (
    "アイウエオカキクケコサシス"
    "セソタチツテトナニヌネノハ"
    "ヒフヘホマミムメモヤユヨラ"
    "リルレロワヲン"
    "0123456789<>[]{}/\\=+*#$%&@"
)

FONT_SIZE = 18          # custom.js FONT_SIZE
GLYPH_FONT = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
TITLE_FONT = (
    "/home/student/labdeck/app/node_modules/@expo-google-fonts/"
    "jetbrains-mono/700Bold/JetBrainsMono_700Bold.ttf"
)


def glyph_table(kana_font, ascii_font):
    """Pair each glyph with a font that can actually draw it.

    This mirrors the dashboard rather than working around it: custom.css asks for
    JetBrainsMono Nerd Font and the RED MATRIX theme installs a katakana fallback
    underneath. Here JetBrains Mono covers the digits and symbols, and
    DroidSansFallbackFull — the only font on this host with real katakana — covers the
    kana. PIL does no font fallback of its own, so anything unmatched renders as a tofu
    box; render a private-use codepoint to learn that box's signature, then filter.
    """
    import hashlib as _h

    def sig(font, ch):
        m = font.getmask(ch)
        return _h.md5(bytes(m)).hexdigest() if m.getbbox() else None

    tofu = {id(f): sig(f, "\ue000") for f in (kana_font, ascii_font)}
    table = []
    for ch in GLYPHS:
        for font in (ascii_font, kana_font):
            s = sig(font, ch)
            if s is not None and s != tofu[id(font)]:
                table.append((ch, font))
                break
    if not table:
        raise SystemExit("no usable glyphs in either font")
    return table


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def sample_rainbow(t):
    """Sample the seven stops at t in [0,1], evenly spaced."""
    t = max(0.0, min(1.0, t))
    scaled = t * (len(RAINBOW) - 1)
    i = min(len(RAINBOW) - 2, int(scaled))
    f = scaled - i
    a, b = hex_rgb(RAINBOW[i]), hex_rgb(RAINBOW[i + 1])
    return tuple(round(a[j] + (b[j] - a[j]) * f) for j in range(3))


def hsl(h_deg, s, light):
    r, g, b = colorsys.hls_to_rgb((h_deg % 360) / 360.0, light, s)
    return (round(r * 255), round(g * 255), round(b * 255))


def draw_rain(img, rng):
    """One still frame of custom.js: per-column hue across the spectrum, a bright head
    and a trail that fades — the trail is what the translucent-black overdraw produces
    in the animated original."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    kana = ImageFont.truetype(GLYPH_FONT, FONT_SIZE)
    ascii_f = ImageFont.truetype(TITLE_FONT, FONT_SIZE)
    glyphs = glyph_table(kana, ascii_f)

    columns = img.width // FONT_SIZE + 1
    for i in range(columns):
        x = i * FONT_SIZE
        # custom.js: hues[i] = ((i / columns) * 360 + random * 24) % 360
        hue = ((i / columns) * 360 + rng.random() * 24) % 360
        head = rng.randint(-12, img.height // FONT_SIZE + 4)
        trail = rng.randint(6, 26)

        for n in range(trail):
            y = (head - n) * FONT_SIZE
            if y < -FONT_SIZE or y > img.height:
                continue
            ch, font = glyphs[rng.randrange(len(glyphs))]
            if n == 0:
                col = hsl(hue, 1.0, 0.88) + (217,)     # bright head, alpha .85
            else:
                fade = max(0.0, 1.0 - n / trail)
                col = hsl(hue, 1.0, 0.55) + (int(140 * fade),)
            d.text((x, y), ch, font=font, fill=col)

    return Image.alpha_composite(img, layer)


def draw_veil(img):
    """custom.css:66-86 — scanlines and a vignette in one layer."""
    veil = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(veil)

    for y in range(0, img.height, 3):
        d.line([(0, y), (img.width, y)], fill=(255, 255, 255, 14))

    # Radial darkening, strongest at the edges: 0.46 centre -> 0.74 outer in the CSS.
    vign = Image.new("L", img.size, 0)
    vd = ImageDraw.Draw(vign)
    cx, cy = img.width / 2, img.height * 0.32
    steps = 60
    maxr = max(img.width, img.height)
    for s in range(steps, 0, -1):
        r = maxr * s / steps
        # Inverted: darkest at the edges, lightest at the focal point, matching the CSS
        # radial-gradient which goes 0.74 black at centre out to 0.46 at the rim only
        # because it sits over a *brighter* page. Here the rain is the bright thing, so
        # the edges are what need holding back.
        alpha = int(215 * (1 - (s / steps)) ** 1.6)
        vd.ellipse([cx - r * 1.15, cy - r, cx + r * 1.15, cy + r], fill=alpha)
    vign = vign.filter(ImageFilter.GaussianBlur(40))
    veil = Image.alpha_composite(veil, Image.merge("RGBA", (
        Image.new("L", img.size, 0), Image.new("L", img.size, 0),
        Image.new("L", img.size, 0), vign)))

    return Image.alpha_composite(img, veil)


def fit_lines(title, font_path, max_width, start_size):
    """Shrink and wrap until the title fits in at most three lines."""
    for size in range(start_size, 22, -2):
        font = ImageFont.truetype(font_path, size)
        words, lines, cur = title.split(), [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if font.getbbox(trial)[2] <= max_width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if len(lines) <= 3 and all(font.getbbox(l)[2] <= max_width for l in lines):
            return font, lines
    return ImageFont.truetype(font_path, 24), [title]


def draw_title(img, title):
    """Rainbow text with a dark halo — custom.css:90-107 uses background-clip:text plus
    stacked drop-shadows because the rain runs straight through the letterforms."""
    pad = 64
    max_w = img.width - pad * 2
    font, lines = fit_lines(title.upper(), TITLE_FONT, max_w, 62)

    line_h = font.getbbox("Ag")[3] + 18
    total_h = line_h * len(lines) + 26
    top = (img.height - total_h) // 2

    # Halo first, on its own blurred layer.
    halo = Image.new("RGBA", img.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    for li, line in enumerate(lines):
        hd.text((pad, top + li * line_h), line, font=font, fill=(0, 0, 0, 255))
    halo = halo.filter(ImageFilter.GaussianBlur(9))
    img = Image.alpha_composite(img, halo)
    img = Image.alpha_composite(img, halo)   # twice: the CSS stacks two drop-shadows

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # Spread the spectrum over the characters, not over the image width. Sampling by x
    # position meant a short title like "USES" only ever reached the red end of the
    # gradient. This is what the app's RainbowHeading does — every heading gets the
    # whole spectrum regardless of length — and it reads across wrapped lines as one run.
    total = sum(len(l) for l in lines)
    idx = 0
    for li, line in enumerate(lines):
        x = pad
        y = top + li * line_h
        for ch in line:
            w = d.textlength(ch, font=font)
            t = 0.0 if total <= 1 else idx / (total - 1)
            d.text((x, y), ch, font=font, fill=sample_rainbow(t) + (255,))
            x += w
            idx += 1

    # The 1px rainbow rule under a heading — custom.css:109-118, at 45% opacity.
    rule_y = top + line_h * len(lines) + 6
    for px in range(pad, img.width - pad):
        d.line([(px, rule_y), (px, rule_y + 2)],
               fill=sample_rainbow((px - pad) / max_w) + (115,))

    return Image.alpha_composite(img, layer)


def build(slug, title, out):
    # Seeded from the slug: same input, same image, no repo churn on regeneration.
    rng = random.Random(int(hashlib.sha256(slug.encode()).hexdigest()[:12], 16))

    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    img = draw_rain(img, rng)
    img = draw_veil(img)
    img = draw_title(img, title)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("title")
    ap.add_argument("--out")
    args = ap.parse_args()

    for path in (GLYPH_FONT, TITLE_FONT):
        if not os.path.isfile(path):
            sys.exit(f"missing font: {path}")

    out = args.out or f"static/images/posts/{args.slug}/cover.png"
    print(build(args.slug, args.title, out))


if __name__ == "__main__":
    main()

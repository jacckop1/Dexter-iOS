from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import json

ROOT = Path("Generated/Assets.xcassets")
APPICON = ROOT / "AppIcon.appiconset"
ACCENT = ROOT / "AccentColor.colorset"
LAUNCH = ROOT / "LaunchBackground.colorset"

for path in (APPICON, ACCENT, LAUNCH):
    path.mkdir(parents=True, exist_ok=True)

SIZE = 1024
image = Image.new("RGB", (SIZE, SIZE), (6, 6, 10))
pixels = image.load()

# Deep cinematic blue-black gradient with a subtle vignette.
for y in range(SIZE):
    for x in range(SIZE):
        t = (x + y) / (2 * (SIZE - 1))
        distance = ((x - SIZE / 2) ** 2 + (y - SIZE / 2) ** 2) ** 0.5 / 724
        red = int(max(3, 9 + 24 * t - 14 * distance))
        green = int(max(3, 7 + 14 * t - 10 * distance))
        blue = int(max(8, 18 + 48 * t - 8 * distance))
        pixels[x, y] = (red, green, blue)

# Atmospheric glow fields.
glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
glow_draw = ImageDraw.Draw(glow, "RGBA")
glow_draw.ellipse((520, -80, 1120, 520), fill=(80, 70, 255, 95))
glow_draw.ellipse((-180, 520, 520, 1220), fill=(0, 180, 255, 58))
glow = glow.filter(ImageFilter.GaussianBlur(120))
image = Image.alpha_composite(image.convert("RGBA"), glow)

# Geometric D mark and neon bloom.
mark = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
halo = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
halo_draw = ImageDraw.Draw(halo, "RGBA")
halo_draw.arc((245, 205, 810, 820), start=-90, end=90, fill=(120, 70, 255, 230), width=118)
halo_draw.rounded_rectangle((265, 238, 380, 785), radius=56, fill=(70, 130, 255, 210))
halo = halo.filter(ImageFilter.GaussianBlur(48))
mark = Image.alpha_composite(mark, halo)

mark_draw = ImageDraw.Draw(mark, "RGBA")
white = (245, 247, 255, 255)
cyan = (40, 194, 255, 255)
mark_draw.rounded_rectangle((286, 236, 390, 788), radius=50, fill=white)
mark_draw.rounded_rectangle((334, 236, 526, 334), radius=46, fill=white)
mark_draw.rounded_rectangle((334, 690, 526, 788), radius=46, fill=white)
mark_draw.arc((250, 205, 810, 820), start=-90, end=90, fill=white, width=96)
mark_draw.rounded_rectangle((362, 253, 380, 770), radius=9, fill=(150, 110, 255, 180))
mark_draw.arc((266, 223, 792, 800), start=-82, end=28, fill=cyan, width=14)
mark_draw.ellipse((196, 196, 828, 828), outline=(255, 255, 255, 28), width=2)

image = Image.alpha_composite(image, mark).convert("RGB")

# Final edge vignette to keep the icon calm at small sizes.
vignette = Image.new("L", (SIZE, SIZE), 0)
vignette_pixels = vignette.load()
for y in range(SIZE):
    for x in range(SIZE):
        dx = (x - SIZE / 2) / (SIZE / 2)
        dy = (y - SIZE / 2) / (SIZE / 2)
        distance = min(1.0, (dx * dx + dy * dy) ** 0.5)
        vignette_pixels[x, y] = int(105 * distance * distance)
image = Image.composite(Image.new("RGB", (SIZE, SIZE), (0, 0, 0)), image, vignette)

specs = [
    ("iphone", "20x20", "2x", 40),
    ("iphone", "20x20", "3x", 60),
    ("iphone", "29x29", "2x", 58),
    ("iphone", "29x29", "3x", 87),
    ("iphone", "40x40", "2x", 80),
    ("iphone", "40x40", "3x", 120),
    ("iphone", "60x60", "2x", 120),
    ("iphone", "60x60", "3x", 180),
    ("ipad", "20x20", "1x", 20),
    ("ipad", "20x20", "2x", 40),
    ("ipad", "29x29", "1x", 29),
    ("ipad", "29x29", "2x", 58),
    ("ipad", "40x40", "1x", 40),
    ("ipad", "40x40", "2x", 80),
    ("ipad", "76x76", "1x", 76),
    ("ipad", "76x76", "2x", 152),
    ("ipad", "83.5x83.5", "2x", 167),
    ("ios-marketing", "1024x1024", "1x", 1024),
]

images = []
for idiom, logical_size, scale, pixel_size in specs:
    filename = f"icon-{idiom}-{logical_size.replace('.', '_')}@{scale}.png"
    image.resize((pixel_size, pixel_size), Image.Resampling.LANCZOS).save(
        APPICON / filename,
        optimize=True,
    )
    images.append(
        {
            "idiom": idiom,
            "size": logical_size,
            "scale": scale,
            "filename": filename,
        }
    )

with open(APPICON / "Contents.json", "w", encoding="utf-8") as handle:
    json.dump({"images": images, "info": {"author": "xcode", "version": 1}}, handle, indent=2)

with open(ACCENT / "Contents.json", "w", encoding="utf-8") as handle:
    json.dump(
        {
            "colors": [
                {
                    "idiom": "universal",
                    "color": {
                        "color-space": "srgb",
                        "components": {
                            "red": "0.420",
                            "green": "0.200",
                            "blue": "0.920",
                            "alpha": "1.000",
                        },
                    },
                }
            ],
            "info": {"author": "xcode", "version": 1},
        },
        handle,
        indent=2,
    )

with open(LAUNCH / "Contents.json", "w", encoding="utf-8") as handle:
    json.dump(
        {
            "colors": [
                {
                    "idiom": "universal",
                    "color": {
                        "color-space": "srgb",
                        "components": {
                            "red": "0.018",
                            "green": "0.018",
                            "blue": "0.025",
                            "alpha": "1.000",
                        },
                    },
                }
            ],
            "info": {"author": "xcode", "version": 1},
        },
        handle,
        indent=2,
    )

with open(ROOT / "Contents.json", "w", encoding="utf-8") as handle:
    json.dump({"info": {"author": "xcode", "version": 1}}, handle, indent=2)

print("Generated Dexter app icon, accent color, and launch color.")

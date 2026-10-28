"""generate_icons.py — توليد أيقونات PWA برمجياً."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT = Path(__file__).parent / "static"
OUT.mkdir(exist_ok=True)


def make_icon(size: int, output: Path) -> None:
    img = Image.new("RGB", (size, size), "#667eea")
    draw = ImageDraw.Draw(img)

    for y in range(size):
        ratio = y / size
        r = int(0x66 + (0x76 - 0x66) * ratio)
        g = int(0x7e + (0x4b - 0x7e) * ratio)
        b = int(0xea + (0xa2 - 0xea) * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b))

    margin = size // 6
    draw.ellipse([margin, margin, size - margin, size - margin], fill="white")

    # Try emoji font first, fallback to "P"
    emoji_paths = [
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
        "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf",
    ]
    emoji_drawn = False
    for ep in emoji_paths:
        try:
            emoji_font = ImageFont.truetype(ep, size // 2)
            draw.text(
                (size // 2, size // 2),
                "🧬",
                font=emoji_font,
                anchor="mm",
                embedded_color=True,
            )
            emoji_drawn = True
            break
        except Exception:
            continue
    if not emoji_drawn:
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size // 2
            )
            draw.text(
                (size // 2, size // 2),
                "P",
                fill="#667eea",
                font=font,
                anchor="mm",
            )
        except Exception:
            pass

    img.save(output, "PNG", optimize=True)
    print(f"✅ {output}")


if __name__ == "__main__":
    make_icon(192, OUT / "icon-192.png")
    make_icon(512, OUT / "icon-512.png")

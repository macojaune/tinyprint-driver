"""Generate two 400-row paper-advance rulers. Does not connect or print."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def ruler(dense):
    image = Image.new("1", (384, 400), 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=16)
    draw.text((6, 4), "B DENSE" if dense else "A CLAIR", font=font, fill=0)
    for y in range(32, 392):
        if dense:
            # Dense panels; thin white boundaries make compression obvious.
            if y % 40 >= 3:
                draw.line((112, y, 375, y), fill=0)
        elif (y // 8) % 2 == 0:
            draw.line((224, y, 239, y), fill=0)
    for mm in range(41):
        y = 40 + mm * 8
        draw.line((55 if mm % 10 else 40, y, 103, y), fill=0)
        if mm % 10 == 0:
            draw.text((4, y-8), str(mm), font=font, fill=0)
            draw.line((106, y, 378, y), fill=0)
    return image


if __name__ == "__main__":
    out = Path("private/calibration")
    out.mkdir(parents=True, exist_ok=True)
    ruler(False).save(out / "01-sparse.png")
    ruler(True).save(out / "02-dense.png")
    print("Generated two 400-row rulers; 0–40 labels must span 40 mm. No printing.")

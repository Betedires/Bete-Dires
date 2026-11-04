import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

def get_font(size: int):
    """Attempts to load a clean TTF font; falls back to default if unavailable."""
    font_candidates = [
        "arial.ttf",
        "DejaVuSans-Bold.ttf",
        "tahoma.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:\\Windows\\Fonts\\arial.ttf"
    ]
    for font_name in font_candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue
    return ImageFont.load_default()

def add_watermark(
    image_path: str,
    watermark_path: str | None = None,
    watermark_text: str | None = None,
    output_path: str | None = None
) -> str:
    """
    Applies a watermark to the image at image_path.
    If watermark_path PNG exists, pastes it scaled at bottom right.
    Otherwise, renders watermark_text with a high-contrast outline.
    Saves to output_path (or overwrites image_path if output_path is None).
    """
    save_dest = output_path or image_path

    # Check for image watermark
    wm_png = watermark_path or os.getenv("WATERMARK_PATH", "watermark.png")
    if not os.path.isabs(wm_png) and not os.path.exists(wm_png):
        # Check inside telegram_forwarder dir
        script_dir = os.path.dirname(os.path.abspath(__file__))
        alt = os.path.join(script_dir, wm_png)
        if os.path.exists(alt):
            wm_png = alt

    text = watermark_text or os.getenv("WATERMARK_TEXT", "Bete Dires")

    try:
        base_image = Image.open(image_path).convert("RGBA")
        width, height = base_image.size

        if os.path.exists(wm_png) and wm_png.lower().endswith(".png"):
            # Image-based watermark overlay
            watermark = Image.open(wm_png).convert("RGBA")
            wm_width = int(width * 0.22)
            if wm_width < 80:
                wm_width = 80
            wm_height = int((wm_width / float(watermark.width)) * watermark.height)
            watermark = watermark.resize((wm_width, wm_height), Image.Resampling.LANCZOS)

            padding = 20
            position = (width - wm_width - padding, height - wm_height - padding)

            transparent = Image.new('RGBA', base_image.size, (0, 0, 0, 0))
            transparent.paste(base_image, (0, 0))
            transparent.paste(watermark, position, mask=watermark)
            final_image = transparent.convert("RGB")
        else:
            # Text-based watermark overlay with black outline for visibility
            final_image = base_image.convert("RGB")
            draw = ImageDraw.Draw(final_image)

            font_size = max(22, int(width * 0.045))
            font = get_font(font_size)

            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            margin = int(width * 0.03)
            x = width - text_w - margin
            y = height - text_h - margin

            # Draw 2px dark outline
            outline_color = (0, 0, 0)
            for dx in (-2, 0, 2):
                for dy in (-2, 0, 2):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), text, font=font, fill=outline_color)

            # Draw white fill
            draw.text((x, y), text, font=font, fill=(255, 255, 255))

        os.makedirs(os.path.dirname(os.path.abspath(save_dest)), exist_ok=True)
        final_image.save(save_dest, format="JPEG", quality=88)
        return save_dest

    except Exception as e:
        print(f"Error applying watermark: {e}")
        return image_path

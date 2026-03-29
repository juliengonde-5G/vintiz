import io

from PIL import Image, ImageDraw, ImageFont


def generate_label(
    product_name: str,
    category: str,
    barcode_data: str,
    price: str,
    week: int,
) -> bytes:
    """Generate a Vintiz-branded product label image as PNG bytes.

    Creates a white label with a black border containing:
    - Logo area / brand name at top
    - SEM (week) number
    - Category
    - Barcode data string
    - Price
    """
    width, height = 400, 250
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # Black border
    draw.rectangle([0, 0, width - 1, height - 1], outline="black", width=2)

    # Use default font (Pillow built-in)
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        font_price = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except (IOError, OSError):
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_price = ImageFont.load_default()

    # Header: brand name
    draw.text((width // 2, 20), "VINTIZ", fill="black", font=font_large, anchor="mt")

    # Divider line
    draw.line([(10, 45), (width - 10, 45)], fill="black", width=1)

    # SEM number
    draw.text((15, 55), f"SEM {week:02d}", fill="black", font=font_medium)

    # Category
    draw.text((15, 80), category, fill="black", font=font_medium)

    # Product name (truncate if too long)
    display_name = product_name[:35] + "..." if len(product_name) > 35 else product_name
    draw.text((15, 105), display_name, fill="black", font=font_small)

    # Barcode data string
    draw.text((15, 130), barcode_data, fill="black", font=font_small)

    # Divider line
    draw.line([(10, 160), (width - 10, 160)], fill="black", width=1)

    # Price
    draw.text((width // 2, 195), price, fill="black", font=font_price, anchor="mm")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()

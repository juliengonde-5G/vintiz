import io

from PIL import Image, ImageDraw, ImageFont


def generate_label(
    product_name: str,
    category: str,
    barcode_data: str,
    price: str,
    week: int,
    barcode_image: bytes | None = None,
) -> bytes:
    """Generate a Vintiz-branded product label image as PNG bytes.

    Creates a white label with a black border containing:
    - Logo VINTIZ in large text at top
    - SEM (week) number
    - Category in large text
    - Barcode image (if provided) or barcode data string
    - Price in bold
    Dimensions: 400x250
    """
    width, height = 400, 250
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # Black border
    draw.rectangle([0, 0, width - 1, height - 1], outline="black", width=2)

    # Load fonts
    try:
        font_logo = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        font_price = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    except (IOError, OSError):
        font_logo = ImageFont.load_default()
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_price = ImageFont.load_default()

    # Header background strip
    draw.rectangle([0, 0, width, 50], fill="#1A7A6A")

    # Logo VINTIZ centered in header
    draw.text((width // 2, 25), "VINTIZ", fill="white", font=font_logo, anchor="mm")

    # SEM number (top-right inside header)
    draw.text((width - 10, 10), f"SEM {week:02d}", fill="white", font=font_small, anchor="rt")

    # Category in large below header
    draw.text((15, 62), category.upper(), fill="#1A7A6A", font=font_large)

    # Product name (truncate if too long)
    display_name = product_name[:40] + "..." if len(product_name) > 40 else product_name
    draw.text((15, 90), display_name, fill="#333333", font=font_medium)

    # Divider line
    draw.line([(10, 115), (width - 10, 115)], fill="#CCCCCC", width=1)

    if barcode_image is not None:
        # Paste barcode image into label
        try:
            bc_img = Image.open(io.BytesIO(barcode_image)).convert("RGB")
            # Resize barcode to fit: max 230x60
            bc_img.thumbnail((230, 60), Image.LANCZOS)
            bc_x = 15
            bc_y = 120
            img.paste(bc_img, (bc_x, bc_y))
            # Barcode text below image
            draw.text((15, bc_y + bc_img.height + 4), barcode_data, fill="#666666", font=font_small)
        except Exception:
            # Fallback to text if image paste fails
            draw.text((15, 125), barcode_data, fill="#666666", font=font_small)
    else:
        # Display barcode as text
        draw.text((15, 125), barcode_data, fill="#666666", font=font_small)

    # Divider above price
    draw.line([(10, 200), (width - 10, 200)], fill="#CCCCCC", width=1)

    # Price — right-aligned, large and bold
    draw.text((width - 15, 225), price, fill="#1A7A6A", font=font_price, anchor="rm")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()

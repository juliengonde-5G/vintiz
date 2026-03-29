import io

import barcode
from barcode.writer import ImageWriter


def generate_barcode(
    week: int, category_code: str, sequence: int, price_cents: int
) -> bytes:
    """Generate a Code 128 barcode image as PNG bytes.

    The barcode data encodes: SEM{week}-{category_code}-{sequence:04d}-{price_cents}
    """
    data = f"SEM{week:02d}-{category_code}-{sequence:04d}-{price_cents}"
    code128 = barcode.get("code128", data, writer=ImageWriter())

    buffer = io.BytesIO()
    code128.write(buffer, options={"write_text": True, "module_height": 10.0})
    buffer.seek(0)
    return buffer.getvalue()

"""Generate Open Graph images for social sharing (1200x630)."""
import io
from decimal import Decimal

from PIL import Image, ImageDraw, ImageFont

# OG image dimensions (standard)
WIDTH = 1200
HEIGHT = 630

# Colors matching the midnight-blue theme
BG_COLOR = (245, 247, 251)       # #f5f7fb
CARD_BG = (255, 255, 255)        # #ffffff
INK = (12, 24, 41)               # #0c1829
ACCENT = (30, 64, 175)           # #1e40af
MUTED = (85, 112, 160)           # #5570a0
BORDER = (208, 218, 234)         # #d0daea


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load Inter from system or fall back to default."""
    weight = "Bold" if bold else "Regular"
    candidates = [
        f"/usr/share/fonts/truetype/inter/Inter-{weight}.ttf",
        f"/usr/share/fonts/Inter-{weight}.ttf",
        f"/System/Library/Fonts/Supplemental/Arial {weight}.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default(size)


def _mono_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a monospace font or fall back."""
    candidates = [
        "/usr/share/fonts/truetype/source-code-pro/SourceCodePro-Regular.ttf",
        "/usr/share/fonts/SourceCodePro-Regular.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default(size)


def _format_large(value: float) -> str:
    abs_val = abs(value)
    if abs_val >= 1e9:
        return f"R$ {value / 1e9:,.2f}B".replace(",", ".")
    if abs_val >= 1e6:
        return f"R$ {value / 1e6:,.2f}M".replace(",", ".")
    return f"R$ {value:,.0f}".replace(",", ".")


def _fmt(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def generate_og_image(
    ticker: str,
    name: str,
    pe10: float | None = None,
    pe10_label: str = "P/L10",
    pfcf10: float | None = None,
    pfcf10_label: str = "P/FCL10",
    peg: float | None = None,
    market_cap: float | None = None,
) -> bytes:
    """Generate a 1200x630 OG image as PNG bytes."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Card background (centered, with margin)
    card_margin = 40
    card_rect = [card_margin, card_margin, WIDTH - card_margin, HEIGHT - card_margin]
    draw.rounded_rectangle(card_rect, radius=16, fill=CARD_BG, outline=BORDER, width=1)

    # Fonts
    font_title = _font(42, bold=True)
    font_ticker = _mono_font(24)
    font_label = _mono_font(18)
    font_value = _font(64)
    font_small = _font(20)
    font_branding = _font(22)

    # Header: Company name + ticker
    x_pad = card_margin + 50
    y = card_margin + 45

    draw.text((x_pad, y), name, fill=INK, font=font_title)
    ticker_bbox = draw.textbbox((0, 0), ticker, font=font_ticker)
    draw.text((WIDTH - card_margin - 50 - (ticker_bbox[2] - ticker_bbox[0]), y + 10), ticker, fill=MUTED, font=font_ticker)

    # Divider
    y += 70
    draw.line([(x_pad, y), (WIDTH - card_margin - 50, y)], fill=BORDER, width=1)

    # Metrics row
    y += 30
    metrics = []

    pe10_display = pe10_label.replace("PE", "P/L").replace("PFCF", "P/FCL")
    if pe10 is not None:
        metrics.append((pe10_display, _fmt(pe10)))

    pfcf10_display = pfcf10_label.replace("PE", "P/L").replace("PFCF", "P/FCL") if pfcf10_label else "P/FCL10"
    if pfcf10 is not None:
        metrics.append((pfcf10_display, _fmt(pfcf10)))

    if peg is not None:
        metrics.append(("PEG", _fmt(peg, 2)))

    if not metrics:
        metrics.append(("Dados", "—"))

    col_width = (WIDTH - 2 * card_margin - 100) // max(len(metrics), 1)

    for i, (label, value) in enumerate(metrics):
        cx = x_pad + i * col_width + col_width // 2

        # Label
        label_bbox = draw.textbbox((0, 0), label, font=font_label)
        label_w = label_bbox[2] - label_bbox[0]
        draw.text((cx - label_w // 2, y), label, fill=MUTED, font=font_label)

        # Value
        value_bbox = draw.textbbox((0, 0), value, font=font_value)
        value_w = value_bbox[2] - value_bbox[0]
        draw.text((cx - value_w // 2, y + 35), value, fill=INK, font=font_value)

    # Market cap at bottom
    y_bottom = HEIGHT - card_margin - 70
    if market_cap is not None:
        mc_text = f"Market Cap: {_format_large(market_cap)}"
        draw.text((x_pad, y_bottom), mc_text, fill=MUTED, font=font_small)

    # Branding
    brand = "sponda.capital"
    brand_bbox = draw.textbbox((0, 0), brand, font=font_branding)
    brand_w = brand_bbox[2] - brand_bbox[0]
    draw.text((WIDTH - card_margin - 50 - brand_w, y_bottom + 2), brand, fill=ACCENT, font=font_branding)

    # Export
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def generate_homepage_og_image() -> bytes:
    """Generate a branded OG image for the homepage."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_title = _font(72, bold=True)
    font_sub = _font(24)

    # Title centered
    title = "Sponda"
    title_bbox = draw.textbbox((0, 0), title, font=font_title)
    title_w = title_bbox[2] - title_bbox[0]
    title_h = title_bbox[3] - title_bbox[1]
    draw.text(((WIDTH - title_w) // 2, (HEIGHT - title_h) // 2 - 40), title, fill=INK, font=font_title)

    # Subtitle
    sub = "Indicadores de empresas brasileiras para investidores em valor"
    sub_bbox = draw.textbbox((0, 0), sub, font=font_sub)
    sub_w = sub_bbox[2] - sub_bbox[0]
    draw.text(((WIDTH - sub_w) // 2, (HEIGHT + title_h) // 2), sub, fill=MUTED, font=font_sub)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

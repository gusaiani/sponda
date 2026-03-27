"""Generate Open Graph images for social sharing (1200x630)."""
import io
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont

# OG image dimensions (standard)
WIDTH = 1200
HEIGHT = 630

# Colors matching the midnight-blue theme
BG_COLOR = (245, 247, 251)       # #f5f7fb
CARD_BG = (255, 255, 255)        # #ffffff
INK = (12, 24, 41)               # #0c1829
BRAND_NAVY = (27, 52, 126)      # #1b347e — logo color on the website
MUTED = (85, 112, 160)           # #5570a0
BORDER = (208, 218, 234)         # #d0daea

# Bundled fonts directory (shipped with the repo)
_FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"


def _load_font(filename: str, size: int, fallbacks: list[str] | None = None) -> ImageFont.FreeTypeFont:
    """Load a bundled font, falling back to system paths then default."""
    bundled = _FONTS_DIR / filename
    if bundled.is_file():
        return ImageFont.truetype(str(bundled), size)
    for path in (fallbacks or []):
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default(size)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load Inter (regular or bold)."""
    filename = "Inter-Bold.ttf" if bold else "Inter-Regular.ttf"
    weight = "Bold" if bold else "Regular"
    return _load_font(filename, size, [
        f"/usr/share/fonts/truetype/inter/Inter-{weight}.ttf",
        f"/System/Library/Fonts/Supplemental/Arial {weight}.ttf",
    ])


def _mono_font(size: int) -> ImageFont.FreeTypeFont:
    """Load Source Code Pro monospace font."""
    return _load_font("SourceCodePro-Regular.ttf", size, [
        "/usr/share/fonts/truetype/source-code-pro/SourceCodePro-Regular.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
    ])


def _brand_font(size: int) -> ImageFont.FreeTypeFont:
    """Load Satoshi Medium — the brand typeface used for 'SPONDA' on the website."""
    return _load_font("Satoshi-Medium.ttf", size, [
        "/usr/share/fonts/truetype/satoshi/Satoshi-Medium.ttf",
    ])



def _fetch_logo(url: str) -> Image.Image | None:
    """Download a logo image from a URL, returning a PIL Image or None.

    Handles SVG by converting to PNG via CairoSVG.
    """
    try:
        request = Request(url, headers={"User-Agent": "Sponda-OG/1.0"})
        with urlopen(request, timeout=5) as response:
            data = response.read()

        if url.endswith(".svg") or b"<svg" in data[:500]:
            import cairosvg
            png_data = cairosvg.svg2png(bytestring=data, output_width=512)
            return Image.open(io.BytesIO(png_data)).convert("RGBA")

        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def generate_og_image(
    ticker: str,
    name: str,
    logo_url: str | None = None,
) -> bytes:
    """Generate a 1200x630 OG image as PNG bytes.

    Renders at 2x (2400x1260) for crisp text, then downscales to 1200x630.
    """
    scale = 2
    canvas_w = WIDTH * scale
    canvas_h = HEIGHT * scale
    img = Image.new("RGB", (canvas_w, canvas_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Card background (centered, with margin)
    margin = 80
    card_rect = [margin, margin, canvas_w - margin, canvas_h - margin]
    draw.rounded_rectangle(card_rect, radius=32, fill=CARD_BG, outline=BORDER, width=2)

    # Fonts (all at 2x)
    font_brand = _brand_font(144)
    font_title = _font(176, bold=True)
    font_ticker = _mono_font(104)
    font_tagline = _font(60)

    x_pad = margin + 80
    x_right = canvas_w - margin - 80

    # Top: SPONDA brand (left) + tagline (right)
    y = margin + 60
    draw.text((x_pad, y), "SPONDA", fill=BRAND_NAVY, font=font_brand)

    tagline = "Para investidores em valor"
    tagline_bbox = draw.textbbox((0, 0), tagline, font=font_tagline)
    tagline_w = tagline_bbox[2] - tagline_bbox[0]
    tagline_h = tagline_bbox[3] - tagline_bbox[1]
    brand_rendered_bbox = draw.textbbox((0, 0), "SPONDA", font=font_brand)
    brand_rendered_h = brand_rendered_bbox[3] - brand_rendered_bbox[1]
    tagline_y = y + brand_rendered_h - tagline_h
    draw.text((x_right - tagline_w, tagline_y), tagline, fill=MUTED, font=font_tagline)

    # Company name + ticker
    brand_bbox = draw.textbbox((0, 0), "SPONDA", font=font_brand)
    brand_h = brand_bbox[3] - brand_bbox[1]
    y += int(brand_h * 1.6)
    title_bbox = draw.textbbox((0, 0), name, font=font_title)
    title_h = title_bbox[3] - title_bbox[1]
    ticker_bbox = draw.textbbox((0, 0), ticker, font=font_ticker)
    ticker_w = ticker_bbox[2] - ticker_bbox[0]
    ticker_h = ticker_bbox[3] - ticker_bbox[1]
    gap = 40
    max_name_w = x_right - x_pad - ticker_w - gap

    # Truncate name with ellipsis if it doesn't fit
    display_name = name
    name_w = draw.textbbox((0, 0), display_name, font=font_title)[2] - draw.textbbox((0, 0), display_name, font=font_title)[0]
    if name_w > max_name_w:
        while len(display_name) > 1:
            display_name = display_name[:-1]
            truncated = display_name.rstrip() + "…"
            name_w = draw.textbbox((0, 0), truncated, font=font_title)[2] - draw.textbbox((0, 0), truncated, font=font_title)[0]
            if name_w <= max_name_w:
                display_name = truncated
                break

    draw.text((x_pad, y), display_name, fill=INK, font=font_title)
    ticker_y = y + (title_h - ticker_h) // 2 + ticker_h // 4
    draw.text((x_right - ticker_w, ticker_y), ticker, fill=MUTED, font=font_ticker)

    # Company logo centered in remaining space below company name
    y_after_title = y + title_h
    y_card_bottom = canvas_h - margin
    logo = _fetch_logo(logo_url) if logo_url else None
    if logo is not None:
        available_h = y_card_bottom - y_after_title
        logo_max_h = int(available_h * 0.7)
        logo_ratio = logo.width / logo.height
        logo_h = min(logo_max_h, logo.height)
        logo_w = int(logo_h * logo_ratio)
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
        logo_x = (canvas_w - logo_w) // 2
        logo_y = y_after_title + (available_h - logo_h) // 2
        img.paste(logo, (logo_x, logo_y), logo)

    # Downscale to final 1200x630
    img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)

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

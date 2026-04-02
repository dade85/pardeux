from __future__ import annotations

import base64
import io
import json
import math
import os
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

APP_DIR = Path(__file__).resolve().parent
ASSETS_DIR = APP_DIR / "assets"
DATA_DIR = APP_DIR / "data"
LOGO_PATH = ASSETS_DIR / "pardeux_wordmark.png"
DEMO_CATALOG_PATH = DATA_DIR / "demo_catalog.csv"

if LOGO_PATH.exists():
    logo = Image.open(LOGO_PATH)
    st.image(logo, width=420)
else:
    st.error(f"Logo not found: {LOGO_PATH}")



BORDEAUX = "#6E1F34"
BORDEAUX_DARK = "#41111F"
BORDEAUX_SOFT = "#8D2B45"
CREME = "#F3E7D7"
CREME_SOFT = "#FBF6EF"
GOLD = "#CDAA7D"
CHARCOAL = "#241A1A"
MUTED = "#7A6761"
SUCCESS = "#55725C"
WARN = "#A86B34"


# ---------- Helpers ----------
def ensure_dirs() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def create_wordmark_logo(path: Path) -> None:
    if path.exists():
        return
    w, h = 1700, 520
    img = Image.new("RGBA", (w, h), CREME)
    draw = ImageDraw.Draw(img)

    try:
        font_main = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 128)
        font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
        font_dot = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 154)
    except Exception:
        font_main = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_dot = ImageFont.load_default()

    # background frame
    draw.rounded_rectangle((18, 18, w - 18, h - 18), radius=28, outline=GOLD, width=4)
    draw.rounded_rectangle((36, 36, w - 36, h - 36), radius=22, outline=BORDEAUX, width=2)

    # title
    title = "PAR DEUX"
    tw = draw.textlength(title, font=font_main)
    draw.text(((w - tw) / 2, 145), title, fill=BORDEAUX, font=font_main)
    draw.text((w / 2 + tw / 2 + 14, 122), ".", fill=GOLD, font=font_dot)

    subtitle = "DESIGNER VINTAGE"
    sw = draw.textlength(subtitle, font=font_sub)
    draw.text(((w - sw) / 2, 314), subtitle, fill=CHARCOAL, font=font_sub)

    # thin luxury lines
    y = 392
    draw.line((255, y, 635, y), fill=GOLD, width=3)
    draw.line((1065, y, 1445, y), fill=GOLD, width=3)

    img = img.filter(ImageFilter.SMOOTH_MORE)
    img.save(path)


def create_bag_card_image(title: str, brand: str, color_hex: str = BORDEAUX_SOFT) -> Image.Image:
    w, h = 900, 1100
    img = Image.new("RGBA", (w, h), CREME_SOFT)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((18, 18, w - 18, h - 18), radius=42, fill=CREME_SOFT, outline=GOLD, width=3)
    draw.rounded_rectangle((46, 80, w - 46, h - 112), radius=34, fill="#EFE0CF", outline="#E4D0B8", width=2)

    cx = w // 2
    # handle
    draw.arc((250, 160, 650, 500), start=195, end=345, fill=color_hex, width=20)
    # body
    draw.rounded_rectangle((190, 310, 710, 720), radius=60, fill=color_hex, outline=BORDEAUX_DARK, width=5)
    # flap
    draw.polygon([(180, 320), (720, 320), (652, 515), (248, 515)], fill="#7C3048", outline=BORDEAUX_DARK)
    # clasp
    draw.rounded_rectangle((408, 492, 492, 572), radius=10, fill=GOLD, outline=BORDEAUX_DARK, width=3)
    draw.rectangle((432, 500, 468, 560), fill="#EAD9C2", outline=BORDEAUX_DARK, width=2)

    try:
        ft_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        ft_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 44)
    except Exception:
        ft_brand = ImageFont.load_default()
        ft_title = ImageFont.load_default()

    bw = draw.textlength(brand.upper(), font=ft_brand)
    draw.text(((w - bw) / 2, 805), brand.upper(), fill=MUTED, font=ft_brand)

    title_lines = wrap_text(draw, title, ft_title, max_width=w - 180)
    y = 850
    for line in title_lines:
        lw = draw.textlength(line, font=ft_title)
        draw.text(((w - lw) / 2, y), line, fill=CHARCOAL, font=ft_title)
        y += 54
    return img


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def create_demo_catalog(path: Path) -> None:
    if path.exists():
        return
    records = [
        {
            "product_id": 1,
            "brand": "Celine",
            "model": "Macadam Canvas Shoulder Bag",
            "display_name": "Celine Macadam Canvas Shoulder Bag",
            "price_eur": 595,
            "condition": "Very Good",
            "style_tags": "classic,casual,logo-canvas,everyday,heritage",
            "category": "Shoulder Bag",
            "material": "Canvas & leather trim",
            "color_family": "Brown",
            "rarity_score": 70,
            "timelessness_score": 81,
            "investment_score": 74,
            "lifestyle_fit": "Daily wear, casual city use, understated vintage collector",
            "description": "A heritage Celine shoulder silhouette with iconic Macadam canvas that suits understated, relaxed luxury wardrobes.",
            "image_path": "",
            "image_url": "",
            "product_url": "https://pardeuxdesignervintage.com/en/products/chanel-gst-shoulder-bag",
            "product_url": "https://pardeuxdesignervintage.com/en/products/chanel-flap-bag",
            "product_url": "https://pardeuxdesignervintage.com/en/products/chanel-classic-flap-tweed",
            "product_url": "https://pardeuxdesignervintage.com/en/products/celine-macadam-canvas-shoulder-bag",
        },
        {
            "product_id": 2,
            "brand": "Chanel",
            "model": "Classic Flap Tweed",
            "display_name": "Chanel Classic Flap Tweed",
            "price_eur": 6449,
            "condition": "Excellent",
            "style_tags": "timeless,iconic,evening,collector,investment,statement",
            "category": "Flap Bag",
            "material": "Tweed & leather",
            "color_family": "Pink / Multitone",
            "rarity_score": 91,
            "timelessness_score": 94,
            "investment_score": 93,
            "lifestyle_fit": "Collector, special occasions, prestige wardrobe",
            "description": "A high desirability Chanel classic with collector appeal, ideal for clients who value scarcity and brand heritage.",
            "image_path": "",
            "image_url": "",
        },
        {
            "product_id": 3,
            "brand": "Chanel",
            "model": "Flap Bag",
            "display_name": "Chanel Flap Bag",
            "price_eur": 3999,
            "condition": "Very Good",
            "style_tags": "timeless,classic,day-to-evening,investment,elegant",
            "category": "Flap Bag",
            "material": "Leather",
            "color_family": "Black",
            "rarity_score": 84,
            "timelessness_score": 96,
            "investment_score": 89,
            "lifestyle_fit": "Elevated daily wear, dinners, travel, classic capsule wardrobe",
            "description": "A versatile Chanel flap that bridges everyday elegance and occasion styling with enduring resale strength.",
            "image_path": "",
            "image_url": "",
        },
        {
            "product_id": 4,
            "brand": "Chanel",
            "model": "GST Shoulder Bag",
            "display_name": "Chanel GST Shoulder Bag",
            "price_eur": 3450,
            "condition": "Good",
            "style_tags": "structured,workwear,carryall,quiet-luxury,investment",
            "category": "Tote / Shoulder",
            "material": "Caviar leather",
            "color_family": "Black",
            "rarity_score": 79,
            "timelessness_score": 88,
            "investment_score": 84,
            "lifestyle_fit": "Business, travel, premium work wardrobe, practical luxury",
            "description": "A spacious Chanel shoulder bag for clients wanting practicality, polish, and strong logo-recognition without sacrificing utility.",
            "image_path": "",
            "image_url": "",
        },
    ]
    pd.DataFrame(records).to_csv(path, index=False)


def load_demo_catalog() -> pd.DataFrame:
    return pd.read_csv(DEMO_CATALOG_PATH)


def parse_tags(tag_string: str) -> List[str]:
    return [t.strip() for t in str(tag_string).split(",") if t.strip()]


def euro(n: float) -> str:
    return f"€{n:,.0f}".replace(",", ".")


def pick_bag_color(name: str) -> str:
    name = name.lower()
    if "celine" in name or "macadam" in name:
        return "#8B5E3C"
    if "tweed" in name:
        return "#A05771"
    if "gst" in name:
        return "#3B2228"
    return BORDEAUX_SOFT


def image_to_base64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def file_to_base64(upload) -> str:
    return base64.b64encode(upload.read()).decode("utf-8")


def get_image_mime(upload) -> str:
    mime = getattr(upload, "type", None) or "image/png"
    return mime


@st.cache_data(show_spinner=False)
def _extract_image_url_from_html(page_url: str, html: str) -> Optional[str]:
    try:
        soup = BeautifulSoup(html, "html.parser")

        meta_candidates = []
        for attr, value in [("property", "og:image"), ("name", "og:image"), ("name", "twitter:image"), ("property", "twitter:image")]:
            tag = soup.find("meta", attrs={attr: value})
            if tag and tag.get("content"):
                meta_candidates.append(tag.get("content"))

        for candidate in meta_candidates:
            if candidate:
                return urljoin(page_url, candidate)

        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = (script.string or script.get_text() or "").strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            blocks = data if isinstance(data, list) else [data]
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                image = block.get("image")
                if isinstance(image, str) and image:
                    return urljoin(page_url, image)
                if isinstance(image, list) and image:
                    first = image[0]
                    if isinstance(first, str) and first:
                        return urljoin(page_url, first)

        for img in soup.find_all("img"):
            for key in ["src", "data-src", "data-original", "data-image"]:
                candidate = img.get(key)
                if candidate and not candidate.startswith("data:"):
                    return urljoin(page_url, candidate)
    except Exception:
        return None
    return None


@st.cache_data(show_spinner=False)
def resolve_bag_image_from_url(url: str) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, timeout=18, headers=headers)
        resp.raise_for_status()
        content_type = (resp.headers.get("Content-Type") or "").lower()

        if "image/" in content_type:
            return resp.content, content_type, url

        html = resp.text
        image_url = _extract_image_url_from_html(url, html)
        if image_url:
            img_resp = requests.get(image_url, timeout=18, headers=headers)
            img_resp.raise_for_status()
            img_type = (img_resp.headers.get("Content-Type") or "image/png").lower()
            return img_resp.content, img_type, image_url
    except Exception:
        return None, None, None
    return None, None, None


@st.cache_data(show_spinner=False)
def load_image_from_url(url: str) -> Optional[Image.Image]:
    try:
        img_bytes, _, _ = resolve_bag_image_from_url(url)
        if img_bytes is None:
            return None
        return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    except Exception:
        return None


def compute_match_score(product: pd.Series, style_prompt: str, budget: float, lifestyle: str) -> int:
    score = 50
    tags = " ".join(parse_tags(product.get("style_tags", ""))).lower()
    style_prompt = style_prompt.lower()
    lifestyle = lifestyle.lower()

    for token in ["timeless", "classic", "quiet luxury", "work", "collector", "evening", "daily", "casual", "black", "structured"]:
        if token in style_prompt and token in tags:
            score += 8
        if token in lifestyle and token in tags:
            score += 5

    price = float(product["price_eur"])
    if budget > 0:
        ratio = price / budget
        if ratio <= 1:
            score += 12
        elif ratio <= 1.15:
            score += 4
        elif ratio > 1.4:
            score -= 12

    score += int(product.get("timelessness_score", 0) / 12)
    score += int(product.get("investment_score", 0) / 15)
    return max(1, min(score, 99))


def build_bag_insight(product: pd.Series, style_prompt: str, budget: float, lifestyle: str) -> Dict[str, str]:
    price = float(product["price_eur"])
    match_score = compute_match_score(product, style_prompt, budget, lifestyle)
    rarity = int(product.get("rarity_score", 75))
    timeless = int(product.get("timelessness_score", 80))
    invest = int(product.get("investment_score", 80))

    value_note = (
        "Strong value-retention candidate within vintage luxury due to iconography, stable brand desirability, and resale recognisability."
        if invest >= 88
        else "Solid value-preservation potential, especially when well maintained and paired with enduring wardrobe relevance."
        if invest >= 80
        else "More style-led than purely investment-led; best positioned as a smart personal luxury purchase."
    )

    if price <= budget:
        budget_note = "Comfortably inside the selected budget, which improves conversion confidence."
    elif price <= budget * 1.15:
        budget_note = "Slightly above budget, but defensible if the client prioritises longevity and resale strength."
    else:
        budget_note = "Premium stretch purchase; should be positioned on desirability, scarcity, and long-term wardrobe utility."

    why = (
        f"{product['display_name']} fits a {lifestyle.lower() or 'luxury lifestyle'} profile with a {product['category'].lower()} silhouette, "
        f"{product['material']}, and a style signature oriented around {', '.join(parse_tags(product['style_tags'])[:3])}."
    )

    outfit_anchor = (
        f"Best paired with outfits described as '{style_prompt}' where the bag acts as the anchor luxury object, not a secondary accessory."
        if style_prompt.strip()
        else "Works best when the outfit remains clean and deliberate so the bag remains the focal luxury object."
    )

    return {
        "match_score": str(match_score),
        "why_it_works": why,
        "timelessness": f"{timeless}/100 — enduring silhouette and brand-coded recognisability.",
        "rarity": f"{rarity}/100 — scarcity and desirability signal for sourcing or purchase urgency.",
        "investment": f"{invest}/100 — {value_note}",
        "budget_fit": budget_note,
        "outfit_anchor": outfit_anchor,
        "lifestyle_fit": str(product.get("lifestyle_fit", "")),
    }


def render_star_meter(score: int) -> str:
    filled = round(score / 20)
    return "★" * filled + "☆" * (5 - filled)


def apply_theme() -> None:
    st.set_page_config(page_title="PAR DEUX AI Luxury Advisor", page_icon="👜", layout="wide", initial_sidebar_state="expanded")
    st.markdown(
        f"""
        <style>
        :root {{
            --bordeaux: {BORDEAUX};
            --bordeaux-dark: {BORDEAUX_DARK};
            --bordeaux-soft: {BORDEAUX_SOFT};
            --creme: {CREME};
            --creme-soft: {CREME_SOFT};
            --gold: {GOLD};
            --charcoal: {CHARCOAL};
            --muted: {MUTED};
        }}
        .stApp {{
            background:
                radial-gradient(circle at top right, rgba(205,170,125,0.18), transparent 28%),
                linear-gradient(180deg, #fcf7f1 0%, #f7efe4 100%);
            color: var(--charcoal);
        }}
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #2a0f18 0%, #4b1726 100%);
            border-right: 1px solid rgba(205,170,125,0.30);
        }}
        [data-testid="stSidebar"] * {{ color: #fbf3ea !important; }}
        .brand-shell {{
            background: linear-gradient(135deg, rgba(110,31,52,0.98) 0%, rgba(61,18,31,0.98) 100%);
            border: 1px solid rgba(205,170,125,0.45);
            padding: 1.2rem 1.2rem 1rem 1.2rem;
            border-radius: 22px;
            box-shadow: 0 20px 60px rgba(43, 12, 21, 0.22);
            margin-bottom: 1rem;
        }}
        .hero-card {{
            background: linear-gradient(135deg, rgba(110,31,52,0.97) 0%, rgba(69,19,33,0.97) 48%, rgba(36,13,18,0.99) 100%);
            border: 1px solid rgba(205,170,125,0.46);
            padding: 1.65rem 1.8rem;
            border-radius: 26px;
            color: #fff6ed;
            box-shadow: 0 28px 70px rgba(43, 12, 21, 0.26);
        }}
        .hero-title {{ font-size: 2.2rem; font-weight: 700; letter-spacing: 0.02em; margin-bottom: 0.2rem; }}
        .hero-sub {{ color: #eedfd0; font-size: 1rem; line-height: 1.6; }}
        .lux-card {{
            background: rgba(255,251,245,0.92);
            border: 1px solid rgba(110,31,52,0.15);
            border-radius: 22px;
            padding: 1rem 1rem 0.9rem 1rem;
            box-shadow: 0 18px 40px rgba(93, 53, 41, 0.08);
        }}
        .metric-card {{
            background: linear-gradient(180deg, rgba(255,251,247,0.97), rgba(247,238,228,0.95));
            border: 1px solid rgba(110,31,52,0.10);
            border-radius: 20px;
            padding: 1rem 1rem;
            min-height: 118px;
        }}
        .metric-label {{ color: var(--muted); font-size: 0.86rem; text-transform: uppercase; letter-spacing: .09em; }}
        .metric-value {{ color: var(--bordeaux); font-size: 1.55rem; font-weight: 700; margin-top: .25rem; }}
        .metric-foot {{ color: var(--charcoal); font-size: 0.93rem; margin-top: .35rem; }}
        .section-kicker {{ color: var(--bordeaux-soft); letter-spacing: .16em; text-transform: uppercase; font-size: .8rem; font-weight: 700; }}
        .section-title {{ color: var(--charcoal); font-size: 1.55rem; font-weight: 700; margin-bottom: .5rem; }}
        .subtle {{ color: var(--muted); }}
        .bag-pill {{
            display:inline-block; padding: .32rem .62rem; margin:.15rem .18rem .15rem 0;
            border-radius:999px; background: rgba(110,31,52,.08); color: var(--bordeaux);
            border: 1px solid rgba(110,31,52,.10); font-size: .83rem;
        }}
        .recommendation-box {{
            background: linear-gradient(180deg, #fffdf8, #f8efe4);
            border-left: 5px solid var(--gold);
            border-radius: 18px;
            padding: 1rem 1rem;
            box-shadow: 0 12px 28px rgba(80, 44, 35, 0.07);
        }}
        .render-note {{
            background: rgba(110,31,52,.07);
            border: 1px dashed rgba(110,31,52,.30);
            color: var(--charcoal);
            padding: .9rem 1rem;
            border-radius: 16px;
        }}
        .stButton > button, .stDownloadButton > button {{
            background: linear-gradient(135deg, var(--bordeaux) 0%, var(--bordeaux-dark) 100%);
            color: #fff4ea;
            border: 1px solid rgba(205,170,125,0.45);
            border-radius: 999px;
            padding: .65rem 1.15rem;
            font-weight: 600;
        }}
        .stMultiSelect [data-baseweb="tag"] {{ background: rgba(110,31,52,.12); color: var(--bordeaux) !important; }}
        .stMultiSelect [data-baseweb="tag"] * {{ color: var(--bordeaux) !important; fill: var(--bordeaux) !important; }}
        input, textarea {{ color: var(--charcoal) !important; -webkit-text-fill-color: var(--charcoal) !important; }}
        input::placeholder, textarea::placeholder {{ color: #9a857c !important; -webkit-text-fill-color: #9a857c !important; opacity: 1 !important; }}
        [data-baseweb="input"] > div, [data-baseweb="base-input"] > div, [data-baseweb="select"] > div, .stTextInput div[data-baseweb="base-input"] > div, .stTextArea textarea, .stNumberInput div[data-baseweb="base-input"] > div, .stMultiSelect div[data-baseweb="select"] > div {{
            background: #fffaf4 !important;
            color: var(--charcoal) !important;
            border-color: rgba(205,170,125,0.45) !important;
        }}
        [data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea {{
            color: #2d1d1d !important;
            -webkit-text-fill-color: #2d1d1d !important;
            background: #fffaf4 !important;
        }}
        [data-testid="stSidebar"] [data-baseweb="input"] > div,
        [data-testid="stSidebar"] [data-baseweb="base-input"] > div,
        [data-testid="stSidebar"] [data-baseweb="select"] > div,
        [data-testid="stSidebar"] .stMultiSelect div[data-baseweb="select"] > div,
        [data-testid="stSidebar"] .stTextArea textarea {{
            background: #fffaf4 !important;
            color: #2d1d1d !important;
            border: 1px solid rgba(205,170,125,0.55) !important;
        }}
        [data-testid="stSidebar"] [data-baseweb="select"] span,
        [data-testid="stSidebar"] [data-baseweb="select"] div,
        [data-testid="stSidebar"] [data-baseweb="tag"] span,
        [data-testid="stSidebar"] [data-baseweb="tag"] div,
        [data-testid="stSidebar"] [data-baseweb="popover"] *,
        [data-testid="stSidebar"] [data-baseweb="select"] [role="combobox"],
        [data-testid="stSidebar"] [data-baseweb="select"] [data-testid="stMarkdownContainer"],
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] .stMarkdown,
        [data-testid="stSidebar"] .stCaptionContainer {{ color: #fbf3ea !important; }}
        [data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"],
        [data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"] *,
        [data-testid="stSidebar"] [data-baseweb="select"] [aria-selected="true"],
        [data-testid="stSidebar"] [data-baseweb="select"] [role="option"] {{ color: #2d1d1d !important; }}
        [data-testid="stSidebar"] [data-baseweb="select"] input,
        [data-testid="stSidebar"] [data-baseweb="select"] input::placeholder,
        [data-testid="stSidebar"] [data-baseweb="select"] svg,
        [data-testid="stSidebar"] [data-baseweb="select"] svg path {{ color: #2d1d1d !important; fill: #2d1d1d !important; stroke: #2d1d1d !important; }}
        .stTabs [data-baseweb="tab"] {{ font-weight: 700; }}
        .stTabs [aria-selected="true"] {{ color: var(--bordeaux); }}
        .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1350px; }}
        hr {{ border-color: rgba(110,31,52,0.12); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def product_image(product: pd.Series, override: Optional[Dict[str, Any]] = None) -> Image.Image:
    override = override or {}

    upload = override.get("upload")
    if upload is not None:
        try:
            return Image.open(io.BytesIO(upload.getvalue())).convert("RGBA")
        except Exception:
            pass

    override_url = str(override.get("url", "") or "").strip()
    if override_url:
        img = load_image_from_url(override_url)
        if img is not None:
            return img

    img_path = str(product.get("image_path", "") or "").strip()
    if img_path and Path(img_path).exists():
        return Image.open(img_path).convert("RGBA")

    product_page_url = str(product.get("product_url", "") or "").strip()
    if product_page_url:
        img = load_image_from_url(product_page_url)
        if img is not None:
            return img

    img_url = str(product.get("image_url", "") or "").strip()
    if img_url:
        img = load_image_from_url(img_url)
        if img is not None:
            return img

    return create_bag_card_image(str(product["display_name"]), str(product["brand"]), pick_bag_color(str(product["display_name"])))


def product_to_prompt_block(product: pd.Series) -> str:
    return (
        f"Bag: {product['display_name']} | Brand: {product['brand']} | Category: {product['category']} | "
        f"Material: {product['material']} | Color Family: {product['color_family']} | "
        f"Condition: {product['condition']} | Description: {product['description']}"
    )


def build_render_prompt(
    user_prompt: str,
    selected_products: List[pd.Series],
    lifestyle: str,
    styling_goal: str,
    body_notes: str,
) -> str:
    product_blocks = "\n".join(product_to_prompt_block(p) for p in selected_products)
    bag_count = "one bag" if len(selected_products) == 1 else f"{len(selected_products)} bags in separate luxury shopping look variations"
    return f"""
Create a photorealistic luxury ecommerce fashion rendering of the same person from the uploaded image.
Preserve the person's facial identity, skin tone, approximate body proportions, and overall likeness.
Style the person according to this wardrobe request: {user_prompt.strip() or styling_goal.strip() or 'quiet luxury editorial styling'}.
Lifestyle context: {lifestyle or 'premium city lifestyle'}.
Body and fit notes: {body_notes or 'keep the proportions realistic and flattering'}.
Use {bag_count}. Each selected bag must visually match the real product reference and remain the focal luxury accessory.
Do not alter the face into another person. Keep the output elegant, believable, chic, high-fashion, and premium boutique quality.
The bag reference details are:
{product_blocks}
Background should feel refined, minimal, and premium. The result should look like a polished editorial still for a luxury vintage boutique.
""".strip()


def get_openai_client(api_key: Optional[str]) -> Optional[Any]:
    if not api_key or OpenAI is None:
        return None
    try:
        return OpenAI(api_key=api_key)
    except Exception:
        return None


def generate_ai_advisory(
    client: Optional[Any],
    selected_df: pd.DataFrame,
    style_prompt: str,
    lifestyle: str,
    budget: float,
    sourcing_needed: bool,
) -> str:
    if selected_df.empty:
        return "Select at least one bag to generate advisory insights."

    if client is None:
        bullets = []
        top = selected_df.sort_values(["investment_score", "timelessness_score"], ascending=False).iloc[0]
        for _, row in selected_df.iterrows():
            insight = build_bag_insight(row, style_prompt, budget, lifestyle)
            bullets.append(
                f"• {row['display_name']}: {insight['why_it_works']} Investment view: {insight['investment']} Budget fit: {insight['budget_fit']}"
            )
        sourcing_line = (
            "Because sourcing mode is on, the advisor should also offer to find adjacent rare pieces when the chosen option is unavailable or if the client wants a stronger collector play."
            if sourcing_needed
            else "Because sourcing mode is off, the advisor should keep the recommendation tight and conversion-oriented around the current stock."
        )
        return (
            f"Leading recommendation: {top['display_name']} appears strongest when balancing style alignment, brand desirability, and value retention.\n\n"
            + "\n".join(bullets)
            + f"\n\n{sourcing_line}"
        )

    try:
        catalog_json = selected_df[
            [
                "display_name",
                "brand",
                "price_eur",
                "condition",
                "style_tags",
                "material",
                "category",
                "description",
                "timelessness_score",
                "rarity_score",
                "investment_score",
                "lifestyle_fit",
            ]
        ].to_dict(orient="records")

        prompt = f"""
You are an elite luxury vintage advisor working for PAR DEUX.
Give a concise but premium commercial recommendation for the selected bags.
Client styling prompt: {style_prompt or 'not specified'}
Client lifestyle: {lifestyle or 'not specified'}
Budget in EUR: {budget}
Sourcing required: {sourcing_needed}
Selected bags JSON:
{json.dumps(catalog_json, ensure_ascii=False)}

Provide:
1. a lead recommendation
2. why each selected bag is or is not the best fit
3. a short investment / value-retention perspective
4. a styling note linked to the requested outfit
5. a final next-best action for conversion
Keep it polished and commercially persuasive, but grounded.
""".strip()
        rsp = client.responses.create(model="gpt-5.4", input=prompt)
        text = getattr(rsp, "output_text", "") or ""
        return text.strip() or "AI advisory returned no text."
    except Exception as exc:
        return f"AI advisory fallback activated due to API issue: {exc}"


def generate_render_image(
    client: Optional[Any],
    user_photo,
    selected_products: List[pd.Series],
    bag_reference_overrides: Dict[int, Dict[str, Any]],
    outfit_prompt: str,
    lifestyle: str,
    styling_goal: str,
    body_notes: str,
) -> Tuple[Optional[Image.Image], str]:
    prompt = build_render_prompt(outfit_prompt, selected_products, lifestyle, styling_goal, body_notes)
    if client is None or user_photo is None:
        return None, prompt

    try:
        images_payload = []
        # primary user image
        user_bytes = user_photo.getvalue()
        images_payload.append((f"user.{(user_photo.name or 'png').split('.')[-1]}", user_bytes, get_image_mime(user_photo)))

        # bag refs use uploaded or URL-based real product images when available
        for idx, product in enumerate(selected_products[:3], start=1):
            override = bag_reference_overrides.get(int(product["product_id"]), {})
            bag_img = product_image(product, override=override)
            b = io.BytesIO()
            bag_img.save(b, format="PNG")
            images_payload.append((f"bag_{idx}.png", b.getvalue(), "image/png"))

        result = client.images.edit(
            model="gpt-image-1.5",
            image=images_payload,
            prompt=prompt,
            size="1024x1536",
            quality="high",
            output_format="png",
        )
        data = result.data[0].b64_json
        img = Image.open(io.BytesIO(base64.b64decode(data)))
        return img, prompt
    except Exception as exc:
        return None, f"{prompt}\n\n[Render generation could not complete: {exc}]"


def simulate_sourcing(selected_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in selected_df.iterrows():
        price = float(row["price_eur"])
        rows.extend(
            [
                {
                    "Requested bag": row["display_name"],
                    "Marketplace": "Trusted European reseller",
                    "Status": "Possible match",
                    "Indicative price": euro(price * 0.96),
                    "Rationale": "Comparable condition and likely faster fulfilment.",
                },
                {
                    "Requested bag": row["display_name"],
                    "Marketplace": "Collector network lead",
                    "Status": "Rare lead",
                    "Indicative price": euro(price * 1.08),
                    "Rationale": "Potentially stronger rarity profile; suited for collector-minded buyers.",
                },
            ]
        )
    return pd.DataFrame(rows)


def show_metric(label: str, value: str, foot: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-foot">{foot}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def selected_products_df(catalog: pd.DataFrame, selected_ids: List[int]) -> pd.DataFrame:
    if not selected_ids:
        return catalog.iloc[0:0].copy()
    return catalog[catalog["product_id"].isin(selected_ids)].copy()


def sidebar(catalog: pd.DataFrame) -> Dict[str, Any]:
    with st.sidebar:
        st.markdown('<div class="brand-shell">', unsafe_allow_html=True)
        st.image(str(LOGO_PATH), use_container_width=True)
        st.caption("AI Luxury Stylist · Shopper Agent · Photorealistic Try-On Studio")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("### Boutique Configuration")
        catalog_options = {f"{r.display_name} · {euro(float(r.price_eur))}": int(r.product_id) for r in catalog.itertuples()}
        selected_labels = st.multiselect(
            "Select one or multiple bags from stock",
            options=list(catalog_options.keys()),
            default=list(catalog_options.keys())[:1],
        )
        selected_ids = [catalog_options[x] for x in selected_labels]

        budget = st.slider("Customer budget (€)", min_value=500, max_value=10000, value=3500, step=250)
        lifestyle = st.selectbox(
            "Lifestyle",
            ["Daily elegance", "Quiet luxury", "Work & travel", "Collector / prestige", "Evening / occasion"],
            index=1,
        )
        style_prompt = st.text_area(
            "Desired outfit / styling prompt",
            value="Chic bordeaux-toned quiet luxury outfit with refined tailoring and understated jewelry",
            height=110,
        )
        body_notes = st.text_input("Shape / size notes", value="Keep the wearer realistic, elegant, and proportionate")
        sourcing_toggle = st.toggle("Enable sourcing expansion", value=True)

        bag_reference_overrides: Dict[int, Dict[str, Any]] = {}
        if selected_ids:
            st.markdown("### Bag Reference Images")
            st.caption("Use the real PAR DEUX bag photo for each selected item. You can paste an image URL or upload the product image directly.")
            selected_catalog = catalog[catalog["product_id"].isin(selected_ids)]
            for row in selected_catalog.itertuples():
                with st.expander(f"{row.display_name}", expanded=len(selected_ids) == 1):
                    url_key = f"bag_url_{row.product_id}"
                    upload_key = f"bag_upload_{row.product_id}"
                    default_url = getattr(row, "product_url", "") or getattr(row, "image_url", "") or ""
                    bag_url = st.text_input("Bag product page or image URL", value=default_url, key=url_key, placeholder="Paste the PAR DEUX product page URL or a direct image URL")
                    resolved_bytes, resolved_type, resolved_source = (None, None, None)
                    if bag_url.strip():
                        resolved_bytes, resolved_type, resolved_source = resolve_bag_image_from_url(bag_url.strip())
                        if resolved_bytes is not None:
                            try:
                                st.image(Image.open(io.BytesIO(resolved_bytes)).convert("RGBA"), caption="Resolved directly from website", use_container_width=True)
                                if resolved_source and resolved_source != bag_url.strip():
                                    st.caption(f"Resolved image source: {resolved_source}")
                            except Exception:
                                pass
                        else:
                            st.warning("Could not resolve an image from this URL. Paste the product page URL or upload the bag photo directly.")
                    bag_upload = st.file_uploader("Or upload the actual bag photo", type=["png", "jpg", "jpeg", "webp"], key=upload_key)
                    bag_reference_overrides[int(row.product_id)] = {"url": bag_url, "upload": bag_upload}

        st.markdown("### API / Generation")
        api_key = st.text_input("OpenAI API key", type="password", help="Required for live AI advisory and image rendering.")
        st.caption("Without a key, the app still runs with deterministic demo logic and prompt generation.")

    return {
        "selected_ids": selected_ids,
        "budget": float(budget),
        "lifestyle": lifestyle,
        "style_prompt": style_prompt,
        "body_notes": body_notes,
        "sourcing_toggle": sourcing_toggle,
        "api_key": api_key,
        "bag_reference_overrides": bag_reference_overrides,
    }

def boutique_grid(selected_df: pd.DataFrame, style_prompt: str, budget: float, lifestyle: str, bag_reference_overrides: Dict[int, Dict[str, Any]]) -> None:
    if selected_df.empty:
        st.warning("Select at least one bag from the sidebar to activate the advisor.")
        return

    st.markdown('<div class="section-kicker">Current PAR DEUX Selection</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Curated luxury stock, elevated with intelligence</div>', unsafe_allow_html=True)
    st.markdown('<p class="subtle">Choose a single hero bag for a direct conversion journey or compare several luxury options side by side.</p>', unsafe_allow_html=True)

    cols = st.columns(min(3, max(1, len(selected_df))))
    for col, (_, row) in zip(cols, selected_df.iterrows()):
        with col:
            img = product_image(row, override=bag_reference_overrides.get(int(row["product_id"]), {}))
            st.image(img, use_container_width=True)
            st.markdown(f"### {row['display_name']}")
            st.markdown(f"**{euro(float(row['price_eur']))}** · {row['condition']}")
            st.caption(row["description"])
            for tag in parse_tags(row["style_tags"]):
                st.markdown(f'<span class="bag-pill">{tag}</span>', unsafe_allow_html=True)
            insight = build_bag_insight(row, style_prompt, budget, lifestyle)
            st.markdown("<div class='recommendation-box'>", unsafe_allow_html=True)
            st.markdown(f"**Fit score:** {insight['match_score']}/99")
            st.markdown(f"**Timelessness:** {insight['timelessness']}")
            st.markdown(f"**Investment:** {insight['investment']}")
            st.markdown("</div>", unsafe_allow_html=True)


def compare_panel(selected_df: pd.DataFrame, style_prompt: str, budget: float, lifestyle: str) -> None:
    st.markdown('<div class="section-kicker">Decision Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Why this bag is commercially and stylistically compelling</div>', unsafe_allow_html=True)
    if selected_df.empty:
        return

    compare_rows = []
    for _, row in selected_df.iterrows():
        insight = build_bag_insight(row, style_prompt, budget, lifestyle)
        compare_rows.append(
            {
                "Bag": row["display_name"],
                "Price": euro(float(row["price_eur"])),
                "Fit score": insight["match_score"],
                "Timelessness": row["timelessness_score"],
                "Rarity": row["rarity_score"],
                "Investment": row["investment_score"],
                "Best for": row["lifestyle_fit"],
            }
        )
    compare_df = pd.DataFrame(compare_rows).sort_values("Fit score", ascending=False)
    st.dataframe(compare_df, use_container_width=True, hide_index=True)


def hero(selected_df: pd.DataFrame, lifestyle: str) -> None:
    count = len(selected_df)
    brands = ", ".join(sorted(selected_df["brand"].unique())) if count else "PAR DEUX stock"
    title = "PAR DEUX AI Luxury Advisor & Try-On Studio"
    body = (
        f"A highly chic Streamlit experience that lets a client select {count or 'their'} bag(s) from live luxury stock, receive commercial and investment-grade advisory, and request a photorealistic rendering of themselves with the chosen bag and outfit concept."
        f" The current selection spans {brands} and is configured for a {lifestyle.lower()} journey."
    )
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-title">{title}</div>
            <div class="hero-sub">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    ensure_dirs()
    create_wordmark_logo(LOGO_PATH)
    create_demo_catalog(DEMO_CATALOG_PATH)
    apply_theme()

    catalog = load_demo_catalog()
    cfg = sidebar(catalog)
    selected_df = selected_products_df(catalog, cfg["selected_ids"])
    client = get_openai_client(cfg["api_key"])

    hero(selected_df, cfg["lifestyle"])
    st.write("")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        show_metric("Selected bags", str(len(selected_df)), "Supports single-bag conversion or multi-bag comparison journeys.")
    with c2:
        avg_price = euro(float(selected_df["price_eur"].mean())) if not selected_df.empty else "€0"
        show_metric("Average ticket", avg_price, "Useful for AOV and luxury positioning scenarios.")
    with c3:
        lead_score = "0"
        if not selected_df.empty:
            lead_score = str(max(compute_match_score(r, cfg["style_prompt"], cfg["budget"], cfg["lifestyle"]) for _, r in selected_df.iterrows()))
        show_metric("Top fit score", lead_score, "Blend of style match, timelessness, and budget alignment.")
    with c4:
        sourcing = "On" if cfg["sourcing_toggle"] else "Off"
        show_metric("Sourcing mode", sourcing, "When enabled, the app simulates on-demand rare bag sourcing.")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Boutique",
        "AI Advisor",
        "Try-On Studio",
        "Sourcing Concierge",
        "Setup & Notes",
    ])

    with tab1:
        boutique_grid(selected_df, cfg["style_prompt"], cfg["budget"], cfg["lifestyle"], cfg["bag_reference_overrides"])
        st.write("")
        compare_panel(selected_df, cfg["style_prompt"], cfg["budget"], cfg["lifestyle"])

    with tab2:
        st.markdown('<div class="section-kicker">Luxury Advisory Layer</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Guides the client to the right bag based on style, budget, and lifestyle</div>', unsafe_allow_html=True)

        if selected_df.empty:
            st.info("Select at least one bag first.")
        else:
            narrative = generate_ai_advisory(
                client=client,
                selected_df=selected_df,
                style_prompt=cfg["style_prompt"],
                lifestyle=cfg["lifestyle"],
                budget=cfg["budget"],
                sourcing_needed=cfg["sourcing_toggle"],
            )
            st.markdown("<div class='lux-card'>", unsafe_allow_html=True)
            st.write(narrative)
            st.markdown("</div>", unsafe_allow_html=True)

            st.write("")
            for _, row in selected_df.iterrows():
                insight = build_bag_insight(row, cfg["style_prompt"], cfg["budget"], cfg["lifestyle"])
                with st.expander(f"Insight breakdown · {row['display_name']}", expanded=len(selected_df) == 1):
                    a, b = st.columns(2)
                    with a:
                        st.markdown(f"**Why it works**  \n{insight['why_it_works']}")
                        st.markdown(f"**Timelessness**  \n{insight['timelessness']}")
                        st.markdown(f"**Rarity**  \n{insight['rarity']}")
                        st.markdown(f"**Lifestyle fit**  \n{insight['lifestyle_fit']}")
                    with b:
                        st.markdown(f"**Investment view**  \n{insight['investment']}")
                        st.markdown(f"**Budget fit**  \n{insight['budget_fit']}")
                        st.markdown(f"**Outfit anchor**  \n{insight['outfit_anchor']}")
                        st.markdown(f"**Luxury confidence meter**  \n{render_star_meter(int(insight['match_score']))}")

    with tab3:
        st.markdown('<div class="section-kicker">Photorealistic Rendering Layer</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Exact-user luxury styling render with selected PAR DEUX bag(s)</div>', unsafe_allow_html=True)
        st.markdown('<p class="subtle">Upload the client photo, keep the selected bag(s), and describe the desired outfit. The app builds the full generation prompt and can call OpenAI image editing when an API key is supplied.</p>', unsafe_allow_html=True)

        left, right = st.columns([1.05, 1.25])
        with left:
            user_photo = st.file_uploader("Upload customer photo", type=["png", "jpg", "jpeg"], key="customer_photo")
            styling_goal = st.text_area(
                "Rendering direction",
                value="Photorealistic luxury editorial look, elegant posture, refined boutique setting, premium natural light",
                height=120,
            )
            generate_btn = st.button("Generate luxury render", use_container_width=True)
            st.markdown(
                "<div class='render-note'>The render pipeline now prioritises the real bag image you provide for each selected item through the sidebar. If no real image is provided, the app still falls back to an elegant reference card.</div>",
                unsafe_allow_html=True,
            )

        with right:
            if user_photo is not None:
                st.image(user_photo, caption="Uploaded customer reference", use_container_width=True)
            else:
                st.info("Upload a customer photo to enable the rendering workflow.")

            if not selected_df.empty:
                st.markdown("#### Selected bag reference images")
                preview_cols = st.columns(min(3, len(selected_df)))
                for col, (_, row) in zip(preview_cols, selected_df.iterrows()):
                    with col:
                        override = cfg["bag_reference_overrides"].get(int(row["product_id"]), {})
                        st.image(product_image(row, override=override), caption=row["display_name"], use_container_width=True)

        if generate_btn:
            if selected_df.empty:
                st.warning("Select at least one bag before rendering.")
            else:
                with st.spinner("Composing the luxury render workflow..."):
                    img, prompt = generate_render_image(
                        client=client,
                        user_photo=user_photo,
                        selected_products=[row for _, row in selected_df.iterrows()],
                        bag_reference_overrides=cfg["bag_reference_overrides"],
                        outfit_prompt=cfg["style_prompt"],
                        lifestyle=cfg["lifestyle"],
                        styling_goal=styling_goal,
                        body_notes=cfg["body_notes"],
                    )
                st.markdown("#### Generation prompt used")
                st.code(prompt, language="markdown")
                if img is not None:
                    st.image(img, caption="AI luxury try-on render", use_container_width=True)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    st.download_button("Download render", data=buf.getvalue(), file_name="pardeux_render.png", mime="image/png")
                else:
                    st.warning("Live rendering was not executed. The prompt above is ready for generation once a valid API key and customer photo are provided.")

    with tab4:
        st.markdown('<div class="section-kicker">Rare Bag Expansion</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Extends beyond current inventory by sourcing rare bags globally on demand</div>', unsafe_allow_html=True)
        if selected_df.empty:
            st.info("Select one or multiple bags to activate sourcing comparisons.")
        else:
            sourcing_df = simulate_sourcing(selected_df)
            st.dataframe(sourcing_df, use_container_width=True, hide_index=True)
            st.markdown(
                "<div class='lux-card'><strong>Commercial note.</strong> This layer converts the advisor from a stock-bound webshop assistant into a revenue generator that can also monetize sourcing fees and collector-style requests.</div>",
                unsafe_allow_html=True,
            )

    with tab5:
        st.markdown('<div class="section-kicker">Deployment Notes</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">What is production-ready versus what must be wired to live PAR DEUX systems</div>', unsafe_allow_html=True)
        st.markdown(
            """
- The app ships with a **demo catalog** and an elegant PAR DEUX-inspired wordmark generated locally.
- For production, replace the generated wordmark with the official PAR DEUX logo file and point each stock item to its real product image path or image URL. You can also upload real bag photos directly in the sidebar for immediate try-on use.
- The **AI Advisor** works without an API key using deterministic scoring, but becomes richer with live OpenAI text generation.
- The **Try-On Studio** is designed to call OpenAI image editing with the customer photo plus bag references; it requires a valid API key to render live output.
- You can connect this app to Shopify, WooCommerce, or a CMS export by replacing `data/demo_catalog.csv` with your live stock feed.
- Strongly recommended for production: explicit consent checkbox, data retention policy, and image deletion workflow.
            """
        )
        st.code(
            "streamlit run app.py",
            language="bash",
        )
        st.download_button(
            "Download demo catalog CSV",
            data=DEMO_CATALOG_PATH.read_bytes(),
            file_name="demo_catalog.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()

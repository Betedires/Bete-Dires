import os
import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import urllib.request
from aiogram import Bot
from aiogram.types import BufferedInputFile
import httpx
from bs4 import BeautifulSoup
import re
import uuid
from config import WATERMARK_TEXT

FONT_URL = "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf"
FONT_PATH = "Roboto-Bold.ttf"

def is_valid_image(data: bytes) -> bool:
    """Validates image data by magic bytes header and PIL verification."""
    if not data or len(data) < 12:
        return False
    # Check common magic headers
    is_jpeg = data.startswith(b'\xff\xd8\xff')
    is_png = data.startswith(b'\x89PNG\r\n\x1a\n')
    is_gif = data.startswith(b'GIF87a') or data.startswith(b'GIF89a')
    is_webp = data[:4] == b'RIFF' and data[8:12] == b'WEBP'
    if not (is_jpeg or is_png or is_gif or is_webp):
        return False
    try:
        img = Image.open(BytesIO(data))
        img.verify()
        return True
    except Exception:
        return False

def get_font(size=40):
    if not os.path.exists(FONT_PATH):
        urllib.request.urlretrieve(FONT_URL, FONT_PATH)
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except IOError:
        return ImageFont.load_default()

def apply_watermark(image_bytes: bytes, text: str = WATERMARK_TEXT) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)
    
    width, height = image.size
    font_size = int(width * 0.05)
    if font_size < 20: font_size = 20
    
    font = get_font(font_size)
    bbox = draw.textbbox((0,0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    margin = int(width * 0.03)
    x = width - text_w - margin
    y = height - text_h - margin
    
    outline_color = "black"
    draw.text((x-2, y-2), text, font=font, fill=outline_color)
    draw.text((x+2, y-2), text, font=font, fill=outline_color)
    draw.text((x-2, y+2), text, font=font, fill=outline_color)
    draw.text((x+2, y+2), text, font=font, fill=outline_color)
    
    draw.text((x, y), text, font=font, fill="white")
    
    out_io = BytesIO()
    image.save(out_io, format="JPEG", quality=85)
    return out_io.getvalue()

def build_caption(item, bot_username: str) -> str:
    # Assuming bot_username or user's username is passed. 
    # Wait, the username is the submitter's username! We didn't save it in Item. We should add it.
    pass

async def scrape_telegram_photos(url: str) -> list[str]:
    # Convert t.me/channel/123 to t.me/s/channel/123 (Server-side view)
    if "t.me/s/" not in url:
        if "t.me/" in url:
            url = url.replace("t.me/", "t.me/s/")
    
    async with httpx.AsyncClient() as client:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = await client.get(url, headers=headers, follow_redirects=True, timeout=12.0)
            if response.status_code != 200:
                print(f"Scraper: HTTP {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. Main Media Group Wrapper
            # In t.me/s/ view, media group photos often appear in these wraps
            photo_wraps = soup.find_all("a", class_="tgme_widget_message_photo_wrap")
            
            image_urls = []
            for el in photo_wraps:
                style = el.get("style", "")
                # Find the background-image URL
                match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style)
                if match:
                    image_urls.append(match.group(1))
            
            # 2. Grid items (another common format for albums)
            grid_items = soup.find_all("div", class_="tgme_widget_message_inline_image")
            for el in grid_items:
                style = el.get("style", "")
                match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style)
                if match:
                    image_urls.append(match.group(1))

            # 3. Fallback to OpenGraph image if nothing found
            if not image_urls:
                og_image = soup.find("meta", property="og:image")
                if og_image:
                    image_urls.append(og_image["content"])
            
            # Dedup URLs
            image_urls = list(dict.fromkeys(image_urls))
            
            downloaded_files = []
            for img_url in image_urls[:10]:
                try:
                    img_res = await client.get(img_url, timeout=10.0)
                    if img_res.status_code == 200:
                        filename = f"tg_import_{uuid.uuid4().hex[:8]}.jpg"
                        filepath = os.path.join("uploads", filename)
                        os.makedirs("uploads", exist_ok=True)
                        with open(filepath, "wb") as f:
                            f.write(img_res.content)
                        downloaded_files.append(filename)
                except Exception as ex:
                    print(f"Failed to download {img_url}: {ex}")
            
            return downloaded_files
        except Exception as e:
            print(f"Scraper error: {e}")
            return []

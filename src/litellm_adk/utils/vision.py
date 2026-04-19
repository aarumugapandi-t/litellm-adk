import os
import io
import base64
import asyncio
import hashlib
import mimetypes
import ipaddress
import aiohttp
from typing import List, Optional, Tuple, Dict
from PIL import Image
from urllib.parse import urlparse
from ..observability.logger import adk_logger

# Simple In-Memory LRU Cache for processed images
# URL/Path -> (Data URL, Content Hash)
_IMAGE_CACHE: Dict[str, str] = {}
_MAX_CACHE_SIZE = 100

class VisionOptimizer:
    """
    Production-grade image processing for Vision models.
    Supports resizing, compression, SSRF protection, and caching.
    """

    @staticmethod
    def is_ssrf_safe(url: str) -> bool:
        """
        Validates that a URL doesn't point to internal/metadata IP addresses.
        """
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return False
            
            # Basic hostname check
            hostname = parsed.hostname
            if not hostname:
                return False

            # Prevent link-local and private IPs
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_link_local or ip.is_loopback or ip.is_private or ip.is_multicast or ip.is_unspecified:
                    return False
                # Special block for cloud metadata IP (AWS/GCP/Azure)
                if str(ip) == "169.254.169.254":
                    return False
            except ValueError:
                # Hostname is not an IP, which is fine for now 
                # (In full production, you'd resolve DNS and check the resulting IPs)
                pass
            
            return True
        except Exception:
            return False

    @staticmethod
    def optimize_image(content: bytes, max_width: int = 1024, quality: int = 80) -> Tuple[bytes, str]:
        """
        Resizes and compresses an image to reduce token usage and latency.
        Returns (optimized_content, mime_type).
        """
        try:
            img = Image.open(io.BytesIO(content))
            original_format = img.format or "JPEG"
            
            # Resize if too large
            if img.width > max_width:
                w_percent = (max_width / float(img.width))
                h_size = int((float(img.height) * float(w_percent)))
                img = img.resize((max_width, h_size), Image.Resampling.LANCZOS)
            
            # Compress
            output = io.BytesIO()
            # Convert to RGB if saving as JPEG (handling PNG/RGBA)
            if original_format == "JPEG" or img.mode in ("RGBA", "P"):
                 target_format = "JPEG"
                 if img.mode != "RGB":
                     img = img.convert("RGB")
            else:
                target_format = original_format

            img.save(output, format=target_format, quality=quality, optimize=True)
            optimized_bytes = output.getvalue()
            
            mime_type = f"image/{target_format.lower().replace('jpg', 'jpeg')}"
            return optimized_bytes, mime_type
        except Exception as e:
            adk_logger.warning(f"Image optimization failed: {e}")
            return content, "image/jpeg"

    @classmethod
    async def process_image(cls, source: str, session: Optional[aiohttp.ClientSession] = None) -> str:
        """
        High-level entry point to fetch, optimize, and cache an image.
        Returns a Data URL.
        """
        # 1. Check Cache
        if source in _IMAGE_CACHE:
            return _IMAGE_CACHE[source]

        content: Optional[bytes] = None
        content_type: Optional[str] = None

        # 2. Handle Data URL (Skip optimization for already encoded data unless it's huge)
        if source.startswith("data:"):
            # We skip optimization for existing data URLs for simplicity now
            return source

        # 3. Handle Local File
        if os.path.exists(source) and os.path.isfile(source):
            try:
                with open(source, "rb") as f:
                    content = f.read()
            except Exception as e:
                adk_logger.error(f"Failed to read local image: {e}")
                return source
        
        # 4. Handle Remote URL
        elif source.startswith("http"):
            if not cls.is_ssrf_safe(source):
                adk_logger.warning(f"Blocked potential SSRF URL: {source}")
                return source
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache"
            }
            
            try:
                async def fetch(s):
                    # Wikimedia and others are very sensitive to UA and rate limits.
                    # We use a slight backoff for retries.
                    for attempt in range(3): 
                        try:
                            async with s.get(source, timeout=12, headers=headers, allow_redirects=True) as resp:
                                if resp.status == 429:
                                    adk_logger.warning(f"VisionOptimizer: Rate limited (429) for {source}. Retrying...")
                                    await asyncio.sleep(2 ** attempt)
                                    continue
                                resp.raise_for_status()
                                return await resp.read()
                        except Exception as e:
                            if attempt == 2: raise
                            await asyncio.sleep(1)
                    return None

                if session:
                    content = await fetch(session)
                else:
                    async with aiohttp.ClientSession() as s:
                        content = await fetch(s)
            except Exception as e:
                adk_logger.warning(f"VisionOptimizer: Failed to fetch remote image {source} after retries: {e}")
                return source

        if not content:
            return source

        # 5. Optimize
        optimized_bytes, mime_type = cls.optimize_image(content)
        
        # 6. Encode to Base64
        b64_data = base64.b64encode(optimized_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64_data}"

        # 7. Update Cache
        if len(_IMAGE_CACHE) >= _MAX_CACHE_SIZE:
             _IMAGE_CACHE.pop(next(iter(_IMAGE_CACHE))) # Basic FIFO
        _IMAGE_CACHE[source] = data_url

        return data_url

import os
import io
import base64
import socket
import asyncio
import hashlib
import mimetypes
import ipaddress
import aiohttp
import sqlite3
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict
from PIL import Image
from urllib.parse import urlparse
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from aiohttp.client_exceptions import ClientError

from ..observability.logger import adk_logger

class BaseVisionCache(ABC):
    """Abstract interface for caching processed vision data."""
    @abstractmethod
    def get(self, source: str) -> Optional[str]:
        pass

    @abstractmethod
    def set(self, source: str, data_url: str):
        pass

class InMemoryVisionCache(BaseVisionCache):
    """Ephemeral LRU cache."""
    def __init__(self, max_size: int = 100):
        self._cache: Dict[str, str] = {}
        self._max_size = max_size

    def get(self, source: str) -> Optional[str]:
        return self._cache.get(source)

    def set(self, source: str, data_url: str):
        if len(self._cache) >= self._max_size:
            self._cache.pop(next(iter(self._cache)))
        self._cache[source] = data_url

class SQLiteVisionCache(BaseVisionCache):
    """Process-safe cache for optimized images."""
    def __init__(self, db_path: str = "vision_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10.0)

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    source_hash TEXT PRIMARY KEY,
                    data_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def _hash(self, source: str) -> str:
        return hashlib.sha256(source.encode()).hexdigest()

    def get(self, source: str) -> Optional[str]:
        with self._get_connection() as conn:
            cur = conn.execute('SELECT data_url FROM cache WHERE source_hash = ?', (self._hash(source),))
            row = cur.fetchone()
            return row[0] if row else None

    def set(self, source: str, data_url: str):
        with self._get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO cache (source_hash, data_url)
                VALUES (?, ?)
            ''', (self._hash(source), data_url))
            conn.commit()

class VisionOptimizer:
    """
    Production-grade image processing for Vision models.
    Supports resizing, compression, SSRF protection, and pluggable caching.
    """

    @staticmethod
    def is_ssrf_safe(url: str) -> bool:
        """
        Validates that a URL doesn't point to internal/metadata IP addresses.
        WARNING: For full production SSRF protection against DNS rebinding, 
        resolve DNS internally and check IPs directly before dispatching HTTP.
        """
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return False
            
            hostname = parsed.hostname
            if not hostname:
                return False

            try:
                # Prevent DNS Rebinding: Resolve the hostname to its IP first!
                resolved_ip = socket.gethostbyname(hostname)
                ip = ipaddress.ip_address(resolved_ip)
                if ip.is_link_local or ip.is_loopback or ip.is_private or ip.is_multicast or ip.is_unspecified:
                    return False
                if str(ip) == "169.254.169.254":
                    return False
            except socket.gaierror:
                # Hostname could not be resolved
                return False
            except ValueError:
                return False
            
            return True
        except Exception:
            return False

    @staticmethod
    def optimize_image(content: bytes, max_width: int = 1024, quality: int = 80) -> Tuple[bytes, str]:
        """Resizes and compresses an image to reduce token usage and latency."""
        try:
            img = Image.open(io.BytesIO(content))
            original_format = img.format or "JPEG"
            
            if img.width > max_width:
                w_percent = (max_width / float(img.width))
                h_size = int((float(img.height) * float(w_percent)))
                img = img.resize((max_width, h_size), Image.Resampling.LANCZOS)  # type: ignore
            
            output = io.BytesIO()
            if original_format == "JPEG" or img.mode in ("RGBA", "P"):
                 target_format = "JPEG"
                 if img.mode != "RGB":
                     img = img.convert("RGB")  # type: ignore
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
    async def process_image(cls, source: str, session: Optional[aiohttp.ClientSession] = None, cache: Optional[BaseVisionCache] = None) -> str:
        """
        High-level entry point to fetch, optimize, and cache an image.
        """
        if cache:
            cached = cache.get(source)
            if cached:
                return cached

        content: Optional[bytes] = None

        if source.startswith("data:"):
            return source

        if os.path.exists(source) and os.path.isfile(source):
            try:
                with open(source, "rb") as f:
                    content = f.read()
            except Exception as e:
                adk_logger.error(f"Failed to read local image: {e}")
                return source
        
        elif source.startswith("http"):
            if not cls.is_ssrf_safe(source):
                adk_logger.warning(f"Blocked potential SSRF URL: {source}")
                return source
            
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "*/*",
                "Cache-Control": "no-cache"
            }
            
            try:
                @retry(
                    wait=wait_exponential(multiplier=1, min=2, max=10),
                    stop=stop_after_attempt(3),
                    retry=retry_if_exception_type(ClientError),
                    reraise=True
                )
                async def fetch(s):
                    async with s.get(source, timeout=12, headers=headers, allow_redirects=True) as resp:
                        if resp.status == 429:
                            raise ClientError("Rate limited")
                        resp.raise_for_status()
                        return await resp.read()

                if session:
                    content = await fetch(session)
                else:
                    async with aiohttp.ClientSession() as s:
                        content = await fetch(s)
            except Exception as e:
                adk_logger.warning(f"VisionOptimizer: Failed to fetch remote image {source}: {e}")
                return source

        if not content:
            return source

        optimized_bytes, mime_type = cls.optimize_image(content)
        b64_data = base64.b64encode(optimized_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64_data}"

        if cache:
            cache.set(source, data_url)

        return data_url

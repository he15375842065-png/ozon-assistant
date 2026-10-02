"""Image download / process / cache pipeline for product images.

1688 image URLs are downloaded once, normalized (RGB JPEG, max dimension,
EXIF stripped) and cached locally under a URL-hash filename so repeated
drafts never re-download the same file.

Ozon only accepts *public* image URLs, so ``public_url()`` maps a cached file
to a public URL only when ``media_public_base_url`` is configured; otherwise
it returns ``None`` and the caller must warn the user (see
``RealOzonConnector``).
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageOps

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024
MAX_DIMENSION_PX = 2000
JPEG_QUALITY = 88


class MediaError(RuntimeError):
    """Image pipeline failure."""


class MediaPipeline:
    def __init__(
        self,
        cache_dir: str | Path = "./data/media",
        public_base_url: str | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.public_base_url = (public_base_url or "").rstrip("/") or None
        self._client = client

    # -- public API -------------------------------------------------------

    def fetch(self, url: str) -> Path:
        """Download ``url`` (if not cached) and return the processed file path."""
        cleaned = url.strip()
        if not cleaned.lower().startswith(("http://", "https://")):
            raise MediaError(f"不支持的图片 URL：{cleaned[:80]}")
        digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:32]
        target = self.cache_dir / f"{digest}.jpg"
        if target.exists():
            return target
        data = self._download(cleaned)
        self._process_bytes(data, target)
        return target

    def public_url(self, local_path: str | Path) -> str | None:
        """Map a cached file to its public URL, or ``None`` when unconfigured."""
        if not self.public_base_url:
            return None
        name = Path(local_path).name
        return f"{self.public_base_url}/{name}"

    def stats(self) -> dict[str, Any]:
        files = list(self.cache_dir.glob("*.jpg"))
        total_bytes = sum(f.stat().st_size for f in files)
        return {"files": len(files), "bytes": total_bytes}

    # -- internals --------------------------------------------------------

    def _download(self, url: str) -> bytes:
        client = self._client or httpx.Client(timeout=30.0, follow_redirects=True)
        try:
            with client.stream("GET", url) as response:
                if response.status_code != 200:
                    raise MediaError(
                        f"图片下载失败：HTTP {response.status_code}（{url[:80]}）"
                    )
                content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
                if content_type and content_type not in ALLOWED_CONTENT_TYPES:
                    raise MediaError(f"不支持的图片类型：{content_type}")
                chunks: list[bytes] = []
                received = 0
                for chunk in response.iter_bytes(65536):
                    received += len(chunk)
                    if received > MAX_DOWNLOAD_BYTES:
                        raise MediaError("图片超过 15MB 上限，已放弃下载。")
                    chunks.append(chunk)
                return b"".join(chunks)
        except httpx.TimeoutException as exc:
            raise MediaError(f"图片下载超时：{url[:80]}") from exc
        except httpx.HTTPError as exc:
            raise MediaError(f"图片下载网络失败：{exc}") from exc

    @staticmethod
    def _process_bytes(data: bytes, target: Path) -> None:
        try:
            with Image.open(io.BytesIO(data)) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                if max(image.size) > MAX_DIMENSION_PX:
                    image.thumbnail((MAX_DIMENSION_PX, MAX_DIMENSION_PX))
                tmp = target.with_suffix(".tmp")
                image.save(tmp, format="JPEG", quality=JPEG_QUALITY, optimize=True)
                tmp.replace(target)
        except Exception as exc:
            raise MediaError(f"图片处理失败：{exc}") from exc

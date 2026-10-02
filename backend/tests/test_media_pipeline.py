import io

import httpx
import pytest
from PIL import Image

from app.integrations.media.pipeline import MediaError, MediaPipeline


def _png_bytes(size: tuple[int, int] = (64, 64)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(200, 30, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def _pipeline(tmp_path, payload: bytes, **kwargs) -> MediaPipeline:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=payload, headers={"content-type": "image/png"}
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return MediaPipeline(cache_dir=tmp_path / "media", client=client, **kwargs)


def test_fetch_downloads_and_caches(tmp_path):
    pipeline = _pipeline(tmp_path, _png_bytes())
    first = pipeline.fetch("https://example.com/a.png")
    assert first.exists()
    assert first.suffix == ".jpg"
    # Second fetch hits the cache; transport raising proves no re-download.
    def _boom(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not re-download")

    pipeline._client = httpx.Client(transport=httpx.MockTransport(_boom))
    second = pipeline.fetch("https://example.com/a.png")
    assert second == first


def test_fetch_normalizes_to_jpeg(tmp_path):
    pipeline = _pipeline(tmp_path, _png_bytes((3000, 100)))
    path = pipeline.fetch("https://example.com/big.png")
    with Image.open(path) as image:
        assert image.format == "JPEG"
        assert max(image.size) <= 2000


def test_fetch_rejects_non_image_content_type(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"<html></html>", headers={"content-type": "text/html"}
        )

    pipeline = MediaPipeline(
        cache_dir=tmp_path / "media",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(MediaError, match="不支持的图片类型"):
        pipeline.fetch("https://example.com/page")


def test_fetch_rejects_bad_url(tmp_path):
    pipeline = MediaPipeline(cache_dir=tmp_path / "media")
    with pytest.raises(MediaError, match="不支持的图片 URL"):
        pipeline.fetch("ftp://example.com/a.png")


def test_public_url_none_when_unconfigured(tmp_path):
    pipeline = _pipeline(tmp_path, _png_bytes())
    path = pipeline.fetch("https://example.com/a.png")
    assert pipeline.public_url(path) is None


def test_public_url_when_configured(tmp_path):
    pipeline = _pipeline(
        tmp_path, _png_bytes(), public_base_url="https://cdn.example.com/media/"
    )
    path = pipeline.fetch("https://example.com/a.png")
    assert pipeline.public_url(path) == f"https://cdn.example.com/media/{path.name}"


def test_stats(tmp_path):
    pipeline = _pipeline(tmp_path, _png_bytes())
    pipeline.fetch("https://example.com/a.png")
    pipeline.fetch("https://example.com/b.png")
    stats = pipeline.stats()
    assert stats["files"] == 2
    assert stats["bytes"] > 0

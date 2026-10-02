"""Read-only 1688 collection in a dedicated, user-visible browser session.

No credentials are read from the user's everyday browser. Login and site
verification are completed manually. Failed collection never uses mock data.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any
from urllib.parse import urlparse
import re

from app.core.errors import IntegrationError, ValidationError
from app.integrations.sources.mock_1688 import Alibaba1688DataProvider


def validate_offer_url(url: str) -> str:
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValidationError("1688 商品链接端口无效") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname != "detail.1688.com"
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 80, 443}
        or re.fullmatch(r"/offer/\d+\.html", parsed.path) is None
    ):
        raise ValidationError("请输入完整的 1688 商品链接：https://detail.1688.com/offer/数字.html")
    # Tracking parameters are not required to identify the offer.
    return f"https://detail.1688.com{parsed.path}"


_SNAPSHOT_SCRIPT = """() => {
  const globals = {};
  for (const key of ['__INIT_DATA', '__INIT_DATA__', '__INITIAL_STATE__',
      '__NEXT_DATA__', '__GLOBAL_DATA', '__GLOBAL_DATA__', 'offerData',
      'iDetailData', 'wingxViewData', '__OD_CONFIG__']) {
    try {
      if (window[key] && typeof window[key] === 'object') {
        const serialized = JSON.stringify(window[key]);
        if (serialized.length < 2000000) globals[key] = JSON.parse(serialized);
      }
    } catch (_) {}
  }
  return {url: location.href, title: document.title,
    text: (document.body?.innerText || '').slice(0, 150000),
    html: document.documentElement.outerHTML.slice(0, 4000000),
    scripts: Array.from(document.scripts).map(s => s.textContent || '')
      .filter(s => s.length > 0 && s.length < 2000000).slice(0, 100), globals};
}"""


class Alibaba1688BrowserManager:
    """All Playwright objects remain on one dedicated worker thread."""

    def __init__(
        self,
        profile_dir: str,
        timeout_ms: int = 30000,
        channel: str = "chrome",
    ) -> None:
        self.profile_dir = str(Path(profile_dir).resolve())
        self.timeout_ms = timeout_ms
        self.channel = (channel or "chrome").strip().lower()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="1688-browser")
        self._playwright: Any = None
        self._context: Any = None
        self._page: Any = None
        self._opened = False

    def status(self) -> dict[str, str]:
        return self._executor.submit(self._status).result()

    def _status(self) -> dict[str, str]:
        if self._opened and self._page is not None:
            try:
                # Pump close events after the user manually closes the window.
                self._page.wait_for_timeout(0)
                self._opened = not self._page.is_closed()
            except Exception:
                self._close_context()
        return {
            "status": "opened" if self._opened else "closed",
            "message": "专用采集浏览器已打开，请手动完成登录或验证" if self._opened else "采集浏览器尚未打开",
        }

    def open_browser(self, url: str | None = None) -> dict[str, str]:
        target = validate_offer_url(url) if url else "https://www.1688.com/"
        return self._executor.submit(self._open_browser, target).result()

    def fetch(self, url: str) -> dict[str, Any]:
        target = validate_offer_url(url)
        return self._executor.submit(self._fetch, target).result()

    def _ensure_page(self) -> Any:
        from playwright.sync_api import Error, sync_playwright

        if self._page is not None:
            try:
                self._page.wait_for_timeout(0)
                if not self._page.is_closed():
                    return self._page
            except Error:
                pass
        self._close_context()
        Path(self.profile_dir).mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        options = dict(
            user_data_dir=self.profile_dir,
            headless=False,
            locale="zh-CN",
            viewport={"width": 1280, "height": 900},
            accept_downloads=False,
            chromium_sandbox=True,
            timeout=self.timeout_ms,
            # 1688 风控会识别 Playwright 的自动化标记并拦截登录弹窗：
            # 去掉 --enable-automation，关闭 AutomationControlled blink 特性，
            # 再把 navigator.webdriver 抹掉，让页面看起来像手动打开的浏览器。
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        try:
            # Prefer the configured browser channel (default: Google Chrome),
            # then fall back to Edge, then to Playwright's bundled Chromium.
            channels: list[str | None] = [self.channel]
            for fallback in ("msedge", None):
                if fallback not in channels:
                    channels.append(fallback)
            last_error: Error | None = None
            for candidate in channels:
                try:
                    if candidate:
                        self._context = self._playwright.chromium.launch_persistent_context(
                            channel=candidate, **options
                        )
                    else:
                        self._context = self._playwright.chromium.launch_persistent_context(
                            **options
                        )
                    last_error = None
                    break
                except Error as exc:
                    message = str(exc).lower()
                    if "not found" in message or "doesn't exist" in message:
                        last_error = exc
                        continue
                    raise
            if last_error is not None and self._context is None:
                raise last_error
            self._context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            self._page.set_default_timeout(self.timeout_ms)
            self._context.on("close", lambda _: setattr(self, "_opened", False))
            self._page.on("close", lambda _: setattr(self, "_opened", False))
            self._opened = True
            return self._page
        except Error as exc:
            self._close_context()
            raise IntegrationError(
                "无法打开采集浏览器。请安装 Google Chrome（设置页可切换为 Microsoft Edge），或运行 backend\\.venv\\Scripts\\python.exe -m playwright install chromium；若浏览器已开，请关闭占用同一采集会话的窗口后重试。"
            ) from exc

    def _open_browser(self, target: str) -> dict[str, str]:
        from playwright.sync_api import Error

        page = self._ensure_page()
        try:
            if page.url != target:
                page.goto(target, wait_until="domcontentloaded", timeout=self.timeout_ms)
            page.bring_to_front()
        except Error as exc:
            raise IntegrationError("1688 页面未能打开，请检查网络；采集浏览器会保留，方便手动检查。") from exc
        return {"status": "opened", "message": "已打开专用1688采集浏览器，请手动登录或完成验证后返回采集。登录会话仅保存在本机采集配置目录。"}

    def _fetch(self, target: str) -> dict[str, Any]:
        from playwright.sync_api import Error
        from app.integrations.sources.alibaba1688_parser import parse_1688_snapshot

        page = self._ensure_page()
        responses: list[Any] = []

        def receive(response: Any) -> None:
            try:
                parsed = urlparse(response.url)
                if not parsed.hostname or not parsed.hostname.endswith(".1688.com"):
                    return
                if response.request.resource_type not in {"xhr", "fetch"}:
                    return
                if "json" not in response.headers.get("content-type", "") or len(responses) >= 40:
                    return
                if int(response.headers.get("content-length", "0")) > 2000000:
                    return
                # Only observed responses are read; no private API is called.
                body = response.body()
                if len(body) <= 2000000:
                    responses.append(response.json())
            except (Error, ValueError, TypeError):
                pass

        page.on("response", receive)
        try:
            page.goto(target, wait_until="domcontentloaded", timeout=self.timeout_ms)
            deadline = monotonic() + min(15, self.timeout_ms / 1000)
            last_error: IntegrationError | None = None
            while True:
                snapshot = page.evaluate(_SNAPSHOT_SCRIPT)
                snapshot["responses"] = responses
                try:
                    raw = parse_1688_snapshot(snapshot, target)
                    raw.update(provider="browser_1688", source="1688", mock=False,
                               collected_at=datetime.now(timezone.utc).isoformat())
                    return raw
                except IntegrationError as exc:
                    last_error = exc
                    # Leave login/verification to the user; never automate it.
                    if any(word in str(exc) for word in ("要求登录", "要求完成访问验证", "下架", "不存在")):
                        raise
                    if monotonic() >= deadline:
                        raise last_error
                    page.wait_for_timeout(500)
        except IntegrationError:
            raise
        except Error as exc:
            raise IntegrationError("1688 页面读取失败或超时，请在采集浏览器确认商品页面可正常打开，再重试。没有保存任何模拟商品。") from exc
        finally:
            if not page.is_closed():
                page.remove_listener("response", receive)

    def _close_context(self) -> None:
        try:
            if self._context is not None:
                self._context.close()
        except Exception:
            # A user may already have closed the dedicated window.
            pass
        finally:
            if self._playwright is not None:
                self._playwright.stop()
            self._context = self._page = self._playwright = None
            self._opened = False

    def close(self) -> None:
        try:
            self._executor.submit(self._close_context).result()
        finally:
            self._executor.shutdown(wait=True)


_MANAGERS: dict[tuple[str, str], Alibaba1688BrowserManager] = {}
_MANAGER_LOCK = Lock()


def _manager_key(profile_dir: str, channel: str) -> tuple[str, str]:
    return (str(Path(profile_dir).resolve()), (channel or "chrome").strip().lower())


def get_browser_manager(settings: Any) -> Alibaba1688BrowserManager:
    key = _manager_key(
        settings.source_browser_profile,
        getattr(settings, "source_browser_channel", "chrome"),
    )
    with _MANAGER_LOCK:
        if key not in _MANAGERS:
            _MANAGERS[key] = Alibaba1688BrowserManager(
                key[0],
                settings.source_browser_timeout_ms,
                key[1],
            )
        return _MANAGERS[key]


def close_browser_managers() -> None:
    with _MANAGER_LOCK:
        managers = list(_MANAGERS.values())
        _MANAGERS.clear()
    for manager in managers:
        try:
            manager.close()
        except Exception:
            # One already-closed browser must not leave other sessions running.
            pass


class Browser1688Provider(Alibaba1688DataProvider):
    def __init__(
        self, profile_dir: str, timeout_ms: int = 30000, channel: str = "chrome"
    ) -> None:
        self.profile_dir = profile_dir
        self.timeout_ms = timeout_ms
        self.channel = (channel or "chrome").strip().lower()

    def fetch(self, url: str) -> dict[str, Any]:
        key = _manager_key(self.profile_dir, self.channel)
        with _MANAGER_LOCK:
            if key not in _MANAGERS:
                _MANAGERS[key] = Alibaba1688BrowserManager(
                    key[0], self.timeout_ms, key[1]
                )
            manager = _MANAGERS[key]
        return manager.fetch(url)

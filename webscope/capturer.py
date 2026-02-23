"""Screenshot, DOM snapshot, and style extraction for each page."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from playwright.async_api import Page

from .models import CaptureData, ElementInfo
from .utils import sanitize_filename, ensure_dir

logger = logging.getLogger(__name__)


class Capturer:
    """Captures page state: screenshots, DOM, styles, and network requests."""

    def __init__(self, output_dir: Path):
        self.screenshots_dir = output_dir / "screenshots"
        ensure_dir(self.screenshots_dir)
        self._network_log: List[Dict[str, str]] = []

    def attach_network_logging(self, page: Page) -> None:
        """Attach request/response listeners to capture network activity."""
        self._network_log = []

        def on_response(response):
            try:
                self._network_log.append({
                    "url": response.url,
                    "method": response.request.method,
                    "status": str(response.status),
                    "type": response.request.resource_type,
                })
            except Exception:
                pass

        page.on("response", on_response)

    async def capture_page(self, page: Page, url: str, suffix: str = "") -> CaptureData:
        """
        Capture full page state.

        Args:
            page: Playwright page object
            url: Current page URL
            suffix: Optional suffix for screenshot filename (e.g., '_modal')

        Returns:
            CaptureData with screenshot, DOM, styles, network log
        """
        timestamp = datetime.now()
        filename = sanitize_filename(url) + suffix + ".png"
        screenshot_path = self.screenshots_dir / filename

        # Take screenshot with timeout
        try:
            await page.screenshot(path=str(screenshot_path), full_page=True, timeout=15000)
            logger.debug(f"Screenshot saved: {screenshot_path}")
        except Exception as e:
            logger.warning(f"Screenshot failed for {url}: {e}")

        # Get DOM snapshot (simplified) with timeout
        try:
            dom_snapshot = await asyncio.wait_for(
                self._get_dom_snapshot(page),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"DOM snapshot timed out for {url}")
            dom_snapshot = ""
        except Exception as e:
            logger.warning(f"DOM snapshot failed for {url}: {e}")
            dom_snapshot = ""

        # Get page title and meta
        try:
            title = await page.title() or ""
        except Exception as e:
            logger.warning(f"Failed to get page title: {e}")
            title = ""

        meta_description = ""
        try:
            meta_description = await page.eval_on_selector(
                'meta[name="description"]',
                "el => el.content"
            ) or ""
        except Exception:
            pass

        # Extract computed styles with timeout
        try:
            computed_styles = await asyncio.wait_for(
                self._extract_styles(page),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"Style extraction timed out for {url}")
            computed_styles = {}
        except Exception as e:
            logger.warning(f"Style extraction failed for {url}: {e}")
            computed_styles = {}

        # Collect network log and reset
        network_requests = list(self._network_log)
        self._network_log = []

        return CaptureData(
            url=url,
            timestamp=timestamp,
            screenshot_path=screenshot_path,
            dom_snapshot=dom_snapshot,
            title=title,
            meta_description=meta_description,
            computed_styles=computed_styles,
            network_requests=network_requests,
        )

    async def _get_dom_snapshot(self, page: Page) -> str:
        """Get simplified DOM structure."""
        try:
            return await page.evaluate("""() => {
                function simplify(el, depth) {
                    if (depth > 6) return '';
                    const tag = el.tagName?.toLowerCase();
                    if (!tag) return '';
                    const skip = ['script', 'style', 'noscript', 'svg', 'path'];
                    if (skip.includes(tag)) return '';

                    const attrs = [];
                    if (el.id) attrs.push(`id="${el.id}"`);
                    if (el.className && typeof el.className === 'string')
                        attrs.push(`class="${el.className.trim().substring(0, 60)}"`);
                    if (el.getAttribute('role'))
                        attrs.push(`role="${el.getAttribute('role')}"`);

                    const indent = '  '.repeat(depth);
                    const attrStr = attrs.length ? ' ' + attrs.join(' ') : '';
                    let result = `${indent}<${tag}${attrStr}>\\n`;

                    for (const child of el.children) {
                        result += simplify(child, depth + 1);
                    }
                    return result;
                }
                return simplify(document.body, 0).substring(0, 15000);
            }""")
        except Exception as e:
            logger.warning(f"DOM snapshot failed: {e}")
            return ""

    async def _extract_styles(self, page: Page) -> Dict[str, Any]:
        """Extract key visual styles from the page."""
        try:
            return await page.evaluate("""() => {
                const styles = { colors: [], fonts: [], background_color: '', primary_color: '' };

                // Get background color from body
                const bodyStyle = getComputedStyle(document.body);
                styles.background_color = bodyStyle.backgroundColor;

                // Collect colors and fonts from visible elements
                const colorSet = new Set();
                const fontSet = new Set();
                const elements = document.querySelectorAll('h1,h2,h3,p,a,button,nav,header,footer,main');

                elements.forEach(el => {
                    const s = getComputedStyle(el);
                    if (s.color) colorSet.add(s.color);
                    if (s.backgroundColor && s.backgroundColor !== 'rgba(0, 0, 0, 0)')
                        colorSet.add(s.backgroundColor);
                    if (s.fontFamily) fontSet.add(s.fontFamily.split(',')[0].trim().replace(/['"]/g, ''));
                });

                styles.colors = [...colorSet].slice(0, 20);
                styles.fonts = [...fontSet].slice(0, 10);

                // Try to identify primary color (most common non-black/white/gray link/button color)
                const links = document.querySelectorAll('a, button');
                links.forEach(el => {
                    const s = getComputedStyle(el);
                    if (s.color && !['rgb(0, 0, 0)', 'rgb(255, 255, 255)'].includes(s.color)) {
                        styles.primary_color = s.color;
                    }
                });

                return styles;
            }""")
        except Exception as e:
            logger.warning(f"Style extraction failed: {e}")
            return {}

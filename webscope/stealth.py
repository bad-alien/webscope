"""Human-like browser behavior and anti-detection for Playwright."""

import logging
import random
from typing import Optional, Tuple, List

import numpy as np
from playwright.async_api import Page, ElementHandle, Browser, BrowserContext

logger = logging.getLogger(__name__)


class StealthConfig:
    """Configuration for stealth behavior patterns."""

    def __init__(
        self,
        delay_min: float = 0.5,
        delay_max: float = 2.0,
        mouse_speed: float = 1.0,
        scroll_pause_min: float = 0.3,
        scroll_pause_max: float = 1.2,
    ):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.mouse_speed = mouse_speed
        self.scroll_pause_min = scroll_pause_min
        self.scroll_pause_max = scroll_pause_max


class HumanBehavior:
    """
    Wraps Playwright Page to add human-like behavior to all interactions.

    Key principles:
    - All mouse movements use Bézier curves with realistic timing
    - Random delays sampled from Gaussian distribution (not uniform)
    - Scroll with acceleration, deceleration, and reading pauses
    - Clicks slightly offset from element center
    - Hover before click for realistic behavior
    """

    def __init__(self, page: Page, config: StealthConfig):
        self.page = page
        self.config = config
        self._current_mouse_pos: Tuple[float, float] = (0, 0)

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """
        Navigate to URL with human-like delay variation.

        Args:
            url: Target URL
            wait_until: Playwright wait condition (default 'domcontentloaded' to avoid networkidle hangs)
        """
        await self.gaussian_delay(mean=1.5, std=0.5)
        try:
            await self.page.goto(url, wait_until=wait_until, timeout=30000)
        except Exception as e:
            # Try again with just 'load' if first attempt fails
            logger.warning(f"goto failed with {wait_until}, retrying with 'load': {e}")
            await self.page.goto(url, wait_until="load", timeout=30000)
        await self.gaussian_delay(mean=0.8, std=0.3)

    async def click(self, selector: str, timeout: float = 5000) -> None:
        """
        Click element with human-like mouse movement and timing.

        Steps:
        1. Locate element and get bounding box
        2. Move mouse to element using Bézier curve
        3. Add small random offset from center (±5-15px)
        4. Hover for random duration (100-400ms)
        5. Click with random delay before mousedown (20-80ms)
        6. Random delay after click (gaussian)

        Args:
            selector: CSS selector
            timeout: Max wait time for element (ms)
        """
        element = await self.page.wait_for_selector(selector, timeout=timeout)
        if element:
            await self._human_click_element(element)

    async def _human_click_element(self, element: ElementHandle) -> None:
        """Internal method for human-like element clicking."""
        box = await element.bounding_box()
        if not box:
            raise ValueError("Element has no bounding box (not visible?)")

        # Calculate target with offset
        center_x = box["x"] + box["width"] / 2
        center_y = box["y"] + box["height"] / 2
        offset_x = random.uniform(
            -min(box["width"] * 0.3, 15), min(box["width"] * 0.3, 15)
        )
        offset_y = random.uniform(
            -min(box["height"] * 0.3, 15), min(box["height"] * 0.3, 15)
        )
        target_x = center_x + offset_x
        target_y = center_y + offset_y

        # Move mouse with Bézier curve
        await self._bezier_mouse_move(target_x, target_y)

        # Hover pause
        await self.random_delay(0.1, 0.4)

        # Click
        await self.page.mouse.click(target_x, target_y)

        # Post-click delay
        await self.gaussian_delay(mean=0.5, std=0.2)

    async def _bezier_mouse_move(self, target_x: float, target_y: float) -> None:
        """
        Move mouse from current position to target using cubic Bézier curve.

        Algorithm:
        1. Generate 2 random control points between start and end
        2. Use cubic Bézier formula: B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃
        3. Sample curve at 20-40 steps (randomized)
        4. Add small jitter to each point (±2px) for imperfection
        5. Timing: slower at start/end (ease-in-out), faster in middle
        """
        start_x, start_y = self._current_mouse_pos

        # Generate control points
        dx = target_x - start_x
        dy = target_y - start_y
        distance = (dx**2 + dy**2) ** 0.5

        # Skip Bézier for very short distances
        if distance < 10:
            await self.page.mouse.move(target_x, target_y)
            self._current_mouse_pos = (target_x, target_y)
            return

        # Perpendicular vector
        perp_x = -dy
        perp_y = dx
        perp_len = (perp_x**2 + perp_y**2) ** 0.5
        if perp_len > 0:
            perp_x /= perp_len
            perp_y /= perp_len

        offset1 = random.uniform(10, 50) * random.choice([-1, 1])
        offset2 = random.uniform(10, 50) * -np.sign(offset1)  # Opposite direction

        p0 = np.array([start_x, start_y])
        p1 = np.array(
            [start_x + dx / 3 + perp_x * offset1, start_y + dy / 3 + perp_y * offset1]
        )
        p2 = np.array(
            [
                start_x + 2 * dx / 3 + perp_x * offset2,
                start_y + 2 * dy / 3 + perp_y * offset2,
            ]
        )
        p3 = np.array([target_x, target_y])

        # Sample curve
        steps = random.randint(20, 40)
        duration = distance * 0.002 * self.config.mouse_speed

        for i in range(steps + 1):
            # Ease-in-out cubic
            t_linear = i / steps
            t = self._ease_in_out_cubic(t_linear)

            # Cubic Bézier
            point = (
                (1 - t) ** 3 * p0
                + 3 * (1 - t) ** 2 * t * p1
                + 3 * (1 - t) * t**2 * p2
                + t**3 * p3
            )

            # Add jitter
            jitter_x = random.uniform(-2, 2)
            jitter_y = random.uniform(-2, 2)

            x = point[0] + jitter_x
            y = point[1] + jitter_y

            await self.page.mouse.move(x, y)
            self._current_mouse_pos = (x, y)

            # Small random delay
            if i < steps:
                await self.random_delay(0, 0.01)

    @staticmethod
    def _ease_in_out_cubic(t: float) -> float:
        """Ease-in-out cubic interpolation."""
        if t < 0.5:
            return 4 * t**3
        else:
            return 1 - (-2 * t + 2) ** 3 / 2

    async def scroll_page(self, target_y: Optional[float] = None, max_iterations: int = 20) -> None:
        """
        Scroll page with human-like behavior.

        Algorithm:
        1. If no target, scroll to bottom in chunks
        2. Each scroll chunk:
           - Distance: random 300-600px
           - Overshoot by 20-50px, then correct back
           - Reading pause (gaussian) after each chunk
        3. Speed variation: faster in middle, slower at start/end
        4. Random micro-pauses (50-150ms) during scroll
        5. Limit iterations to prevent infinite loops

        Args:
            target_y: Target scroll position (None = scroll to bottom)
            max_iterations: Maximum scroll iterations to prevent infinite loops
        """
        try:
            if target_y is None:
                target_y = await self.page.evaluate("document.body.scrollHeight")

            current_y = await self.page.evaluate("window.pageYOffset")
            iterations = 0
            last_y = -1

            while current_y < target_y - 100 and iterations < max_iterations:  # Stop near bottom, not exact
                # Break if we're not making progress (stuck)
                if current_y == last_y:
                    break
                last_y = current_y

                # Random chunk size
                chunk = random.uniform(300, 600)
                overshoot = random.uniform(20, 50)

                # Scroll with overshoot
                await self.page.mouse.wheel(0, chunk + overshoot)
                await self.random_delay(0.05, 0.15)

                # Correct back
                await self.page.mouse.wheel(0, -overshoot)

                # Reading pause
                await self.gaussian_delay(
                    mean=(self.config.scroll_pause_min + self.config.scroll_pause_max) / 2,
                    std=(self.config.scroll_pause_max - self.config.scroll_pause_min) / 4,
                )

                current_y = await self.page.evaluate("window.pageYOffset")
                iterations += 1

        except Exception as e:
            # Don't let scroll failures break the entire crawl
            logger.warning(f"Scroll page failed: {e}")

    async def type_text(self, selector: str, text: str) -> None:
        """
        Type text with human-like delays between keystrokes.

        Delay between keys: Gaussian(mean=0.08s, std=0.03s)

        Args:
            selector: Input element selector
            text: Text to type
        """
        await self.click(selector)

        for char in text:
            await self.page.keyboard.type(char)
            await self.gaussian_delay(mean=0.08, std=0.03)

    async def gaussian_delay(self, mean: float, std: float) -> None:
        """
        Delay sampled from Gaussian distribution (more realistic than uniform).

        Args:
            mean: Mean delay in seconds
            std: Standard deviation in seconds
        """
        delay = max(0, random.gauss(mean, std))
        delay = min(delay, mean + 3 * std)
        await self.page.wait_for_timeout(int(delay * 1000))

    async def random_delay(self, min_sec: float, max_sec: float) -> None:
        """Uniform random delay (use sparingly, prefer gaussian_delay)."""
        delay = random.uniform(min_sec, max_sec)
        await self.page.wait_for_timeout(int(delay * 1000))


async def create_stealth_browser(
    playwright, config: StealthConfig, headless: bool = True
) -> Tuple[Browser, BrowserContext]:
    """
    Create browser with anti-detection measures.

    Steps:
    1. Randomize viewport from realistic sizes
    2. Rotate User-Agent from pool of real Chrome UAs
    3. Set realistic headers
    4. Disable automation flags

    Returns:
        Tuple of (browser, context)
    """
    # Launch with anti-automation args
    browser = await playwright.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    )

    # Randomized viewport
    viewports = [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1536, "height": 864},
        {"width": 1440, "height": 900},
    ]
    viewport = random.choice(viewports)

    # Select User-Agent
    user_agent = random.choice(get_user_agent_pool())

    context = await browser.new_context(
        viewport=viewport,
        user_agent=user_agent,
        locale="en-US",
        timezone_id="America/New_York",
    )

    # Set extra headers
    await context.set_extra_http_headers(
        {
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }
    )

    # Apply playwright-stealth if available
    try:
        from playwright_stealth import stealth_async

        page = await context.new_page()
        await stealth_async(page)
        await page.close()
    except ImportError:
        pass  # Optional enhancement

    return browser, context


def get_user_agent_pool() -> List[str]:
    """
    Return pool of realistic Chrome User-Agent strings.

    Pool includes:
    - Windows 10/11 (60%)
    - macOS (30%)
    - Linux (10%)
    - Chrome versions 120-125
    - Mix of Intel and ARM architectures
    """
    return [
        # Windows (15 variants - 60%)
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.86 Safari/537.36",
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.60 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.112 Safari/537.36",
        # macOS (8 variants - 30%)
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; ARM Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; ARM Mac OS X 13_3_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        # Linux (2 variants - 10%)
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ]

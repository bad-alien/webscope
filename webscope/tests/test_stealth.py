"""Unit tests for webscope/stealth.py"""

import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from webscope.stealth import (
    StealthConfig,
    HumanBehavior,
    create_stealth_browser,
    get_user_agent_pool
)


class TestStealthConfig:
    """Test StealthConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = StealthConfig()

        assert config.delay_min == 0.5
        assert config.delay_max == 2.0
        assert config.mouse_speed == 1.0
        assert config.scroll_pause_min == 0.3
        assert config.scroll_pause_max == 1.2

    def test_custom_values(self):
        """Test custom configuration values."""
        config = StealthConfig(
            delay_min=1.0,
            delay_max=3.0,
            mouse_speed=0.5,
            scroll_pause_min=0.5,
            scroll_pause_max=1.5
        )

        assert config.delay_min == 1.0
        assert config.delay_max == 3.0
        assert config.mouse_speed == 0.5
        assert config.scroll_pause_min == 0.5
        assert config.scroll_pause_max == 1.5


class TestGetUserAgentPool:
    """Test user agent pool function."""

    def test_returns_list(self):
        """Test that function returns a list."""
        pool = get_user_agent_pool()
        assert isinstance(pool, list)

    def test_pool_not_empty(self):
        """Test that pool contains user agents."""
        pool = get_user_agent_pool()
        assert len(pool) > 0

    def test_all_valid_user_agents(self):
        """Test that all user agents are valid strings."""
        pool = get_user_agent_pool()
        for ua in pool:
            assert isinstance(ua, str)
            assert len(ua) > 0
            assert "Mozilla" in ua
            assert "Chrome" in ua

    def test_contains_different_platforms(self):
        """Test that pool contains different platforms."""
        pool = get_user_agent_pool()

        has_windows = any("Windows" in ua for ua in pool)
        has_mac = any("Macintosh" in ua for ua in pool)
        has_linux = any("Linux" in ua or "Ubuntu" in ua for ua in pool)

        assert has_windows
        assert has_mac
        assert has_linux

    def test_user_agents_have_version(self):
        """Test that user agents contain version numbers."""
        pool = get_user_agent_pool()
        for ua in pool:
            # Should contain Chrome version like Chrome/123.0.0.0
            assert "Chrome/" in ua


class TestHumanBehaviorEaseFunction:
    """Test the easing function used for mouse movement."""

    def test_ease_in_out_cubic_at_zero(self):
        """Test ease function at t=0."""
        result = HumanBehavior._ease_in_out_cubic(0)
        assert result == 0

    def test_ease_in_out_cubic_at_one(self):
        """Test ease function at t=1."""
        result = HumanBehavior._ease_in_out_cubic(1)
        assert result == 1

    def test_ease_in_out_cubic_at_half(self):
        """Test ease function at t=0.5."""
        result = HumanBehavior._ease_in_out_cubic(0.5)
        assert 0.4 < result < 0.6  # Should be around 0.5

    def test_ease_in_out_cubic_monotonic(self):
        """Test that ease function is monotonically increasing."""
        values = [HumanBehavior._ease_in_out_cubic(t / 10) for t in range(11)]
        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1]

    def test_ease_in_out_cubic_range(self):
        """Test that ease function stays in [0, 1] range."""
        for t in [0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]:
            result = HumanBehavior._ease_in_out_cubic(t)
            assert 0 <= result <= 1


class TestHumanBehavior:
    """Test HumanBehavior class."""

    @pytest.fixture
    def human_behavior(self, mock_playwright_page):
        """Create HumanBehavior instance."""
        config = StealthConfig(delay_min=0.1, delay_max=0.2)
        return HumanBehavior(mock_playwright_page, config)

    def test_initialization(self, human_behavior, mock_playwright_page):
        """Test HumanBehavior initialization."""
        assert human_behavior.page == mock_playwright_page
        assert human_behavior.config is not None
        assert human_behavior._current_mouse_pos == (0, 0)

    @pytest.mark.asyncio
    async def test_goto(self, human_behavior, mock_playwright_page):
        """Test goto method."""
        await human_behavior.goto("https://example.com")

        # Verify page.goto was called
        mock_playwright_page.goto.assert_called_once()
        args = mock_playwright_page.goto.call_args
        assert args[0][0] == "https://example.com"
        assert args[1]["wait_until"] == "domcontentloaded"

    @pytest.mark.asyncio
    async def test_goto_custom_wait(self, human_behavior, mock_playwright_page):
        """Test goto with custom wait condition."""
        await human_behavior.goto("https://example.com", wait_until="load")

        args = mock_playwright_page.goto.call_args
        assert args[1]["wait_until"] == "load"

    @pytest.mark.asyncio
    async def test_click(self, human_behavior, mock_playwright_page):
        """Test click method."""
        # Mock element with bounding box
        element = AsyncMock()
        element.bounding_box.return_value = {
            "x": 100,
            "y": 200,
            "width": 80,
            "height": 40
        }
        mock_playwright_page.wait_for_selector.return_value = element

        await human_behavior.click("#test-button")

        # Verify selector was waited for
        mock_playwright_page.wait_for_selector.assert_called_once_with(
            "#test-button",
            timeout=5000
        )

        # Verify mouse click was called
        mock_playwright_page.mouse.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_click_with_timeout(self, human_behavior, mock_playwright_page):
        """Test click with custom timeout."""
        element = AsyncMock()
        element.bounding_box.return_value = {
            "x": 100,
            "y": 200,
            "width": 80,
            "height": 40
        }
        mock_playwright_page.wait_for_selector.return_value = element

        await human_behavior.click("#test-button", timeout=10000)

        args = mock_playwright_page.wait_for_selector.call_args
        assert args[1]["timeout"] == 10000

    @pytest.mark.asyncio
    async def test_click_with_offset(self, human_behavior, mock_playwright_page):
        """Test that click adds random offset from center."""
        element = AsyncMock()
        element.bounding_box.return_value = {
            "x": 100,
            "y": 200,
            "width": 80,
            "height": 40
        }
        mock_playwright_page.wait_for_selector.return_value = element

        await human_behavior.click("#test-button")

        # Get the click coordinates
        click_args = mock_playwright_page.mouse.click.call_args[0]
        click_x, click_y = click_args

        # Center would be (140, 220), but we add offset
        center_x, center_y = 140, 220

        # Click should be near center but not exactly at center
        assert abs(click_x - center_x) <= 24  # Max offset is min(80*0.3, 15) = 15
        assert abs(click_y - center_y) <= 12  # Max offset is min(40*0.3, 15) = 12

    @pytest.mark.asyncio
    async def test_bezier_mouse_move_short_distance(self, human_behavior, mock_playwright_page):
        """Test mouse movement for short distances skips Bezier curve."""
        await human_behavior._bezier_mouse_move(5, 5)

        # For short distances (< 10px), should just do direct move
        mock_playwright_page.mouse.move.assert_called()

    @pytest.mark.asyncio
    async def test_bezier_mouse_move_long_distance(self, human_behavior, mock_playwright_page):
        """Test mouse movement for long distances uses Bezier curve."""
        await human_behavior._bezier_mouse_move(500, 500)

        # Should make multiple move calls for Bezier curve
        assert mock_playwright_page.mouse.move.call_count > 10

    @pytest.mark.asyncio
    async def test_scroll_page_default(self, human_behavior, mock_playwright_page):
        """Test page scrolling to bottom."""
        # Mock scroll height and current position
        mock_playwright_page.evaluate.side_effect = [
            1000,  # scrollHeight
            0,     # first pageYOffset
            350,   # second pageYOffset
            700,   # third pageYOffset
            1000,  # fourth pageYOffset (at bottom)
        ]

        await human_behavior.scroll_page()

        # Should have called mouse.wheel multiple times
        assert mock_playwright_page.mouse.wheel.call_count > 0

    @pytest.mark.asyncio
    async def test_scroll_page_custom_target(self, human_behavior, mock_playwright_page):
        """Test scrolling to specific position."""
        mock_playwright_page.evaluate.side_effect = [
            0,    # initial position
            500,  # after scroll
        ]

        await human_behavior.scroll_page(target_y=500)

        # Should scroll
        assert mock_playwright_page.mouse.wheel.call_count > 0

    @pytest.mark.asyncio
    async def test_type_text(self, human_behavior, mock_playwright_page):
        """Test text typing."""
        element = AsyncMock()
        element.bounding_box.return_value = {
            "x": 100,
            "y": 200,
            "width": 200,
            "height": 30
        }
        mock_playwright_page.wait_for_selector.return_value = element

        await human_behavior.type_text("#input", "Hello")

        # Should have typed each character
        assert mock_playwright_page.keyboard.type.call_count == 5

    @pytest.mark.asyncio
    async def test_gaussian_delay(self, human_behavior, mock_playwright_page):
        """Test Gaussian delay."""
        await human_behavior.gaussian_delay(mean=0.1, std=0.01)

        # Should have called wait_for_timeout
        mock_playwright_page.wait_for_timeout.assert_called()

        # Get the delay value
        delay_ms = mock_playwright_page.wait_for_timeout.call_args[0][0]

        # Should be positive and reasonable (within 3 std devs)
        assert 0 < delay_ms < 200  # Max would be ~130ms (0.1 + 3*0.01 = 0.13s)

    @pytest.mark.asyncio
    async def test_random_delay(self, human_behavior, mock_playwright_page):
        """Test uniform random delay."""
        await human_behavior.random_delay(0.1, 0.2)

        # Should have called wait_for_timeout
        mock_playwright_page.wait_for_timeout.assert_called()

        # Get the delay value
        delay_ms = mock_playwright_page.wait_for_timeout.call_args[0][0]

        # Should be between min and max (in ms)
        assert 100 <= delay_ms <= 200


class TestCreateStealthBrowser:
    """Test browser creation with stealth features."""

    @pytest.mark.asyncio
    async def test_create_stealth_browser(self):
        """Test stealth browser creation."""
        config = StealthConfig()

        # Mock playwright
        mock_playwright = MagicMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.set_extra_http_headers = AsyncMock()
        mock_page.close = AsyncMock()

        browser, context = await create_stealth_browser(
            mock_playwright,
            config,
            headless=True
        )

        # Verify browser was launched with anti-automation args
        launch_args = mock_playwright.chromium.launch.call_args[1]
        assert launch_args["headless"] is True
        assert "--disable-blink-features=AutomationControlled" in launch_args["args"]

        # Verify context was created
        mock_browser.new_context.assert_called_once()
        context_args = mock_browser.new_context.call_args[1]
        assert "viewport" in context_args
        assert "user_agent" in context_args
        assert context_args["locale"] == "en-US"

        # Verify headers were set
        mock_context.set_extra_http_headers.assert_called_once()

        assert browser == mock_browser
        assert context == mock_context

    @pytest.mark.asyncio
    async def test_create_stealth_browser_headless(self):
        """Test browser creation in headless mode."""
        config = StealthConfig()

        mock_playwright = MagicMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()

        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.set_extra_http_headers = AsyncMock()

        await create_stealth_browser(mock_playwright, config, headless=True)

        launch_args = mock_playwright.chromium.launch.call_args[1]
        assert launch_args["headless"] is True

    @pytest.mark.asyncio
    async def test_create_stealth_browser_headed(self):
        """Test browser creation in headed mode."""
        config = StealthConfig()

        mock_playwright = MagicMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()

        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.set_extra_http_headers = AsyncMock()

        await create_stealth_browser(mock_playwright, config, headless=False)

        launch_args = mock_playwright.chromium.launch.call_args[1]
        assert launch_args["headless"] is False

    @pytest.mark.asyncio
    async def test_randomized_viewport(self):
        """Test that viewport is randomized from pool."""
        config = StealthConfig()

        mock_playwright = MagicMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()

        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.set_extra_http_headers = AsyncMock()

        await create_stealth_browser(mock_playwright, config)

        context_args = mock_browser.new_context.call_args[1]
        viewport = context_args["viewport"]

        # Should be one of the predefined viewports
        valid_viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1536, "height": 864},
            {"width": 1440, "height": 900},
        ]
        assert viewport in valid_viewports

    @pytest.mark.asyncio
    async def test_randomized_user_agent(self):
        """Test that user agent is randomized from pool."""
        config = StealthConfig()

        mock_playwright = MagicMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()

        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.set_extra_http_headers = AsyncMock()

        await create_stealth_browser(mock_playwright, config)

        context_args = mock_browser.new_context.call_args[1]
        user_agent = context_args["user_agent"]

        # Should be from the pool
        pool = get_user_agent_pool()
        assert user_agent in pool

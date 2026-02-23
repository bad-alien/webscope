"""Pytest configuration and shared fixtures for WebScope tests."""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import pytest

from webscope.models import CrawlConfig, CaptureData, PageResult, ElementInfo, AnalysisResult


@pytest.fixture
def tmp_dir(tmp_path):
    """Create a temporary directory for test outputs."""
    return tmp_path


@pytest.fixture
def sample_config(tmp_path):
    """Create a sample CrawlConfig for testing."""
    return CrawlConfig(
        start_url="https://example.com",
        output_dir=tmp_path,
        max_depth=3,
        max_pages=20,
        headless=True,
        delay_min=0.5,
        delay_max=2.0,
        anthropic_api_key="test-api-key"
    )


@pytest.fixture
def sample_html():
    """Sample HTML content for testing."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="description" content="Test page description">
    <title>Test Page</title>
</head>
<body>
    <header>
        <nav>
            <a href="/">Home</a>
            <a href="/about">About</a>
            <a href="/contact">Contact</a>
        </nav>
    </header>
    <main>
        <h1>Welcome to Test Site</h1>
        <p>This is a test page.</p>
        <button id="test-button">Click Me</button>
        <a href="/products">Products</a>
        <a href="https://external.com">External Link</a>
    </main>
    <footer>
        <p>Copyright 2026</p>
    </footer>
</body>
</html>"""


@pytest.fixture
def sample_capture_data(tmp_path):
    """Create sample CaptureData for testing."""
    screenshot_path = tmp_path / "test_screenshot.png"
    screenshot_path.write_text("fake screenshot")

    return CaptureData(
        url="https://example.com",
        timestamp=datetime.now(),
        screenshot_path=screenshot_path,
        dom_snapshot="<html><body><h1>Test</h1></body></html>",
        title="Test Page",
        meta_description="A test page",
        computed_styles={
            "colors": ["#FFFFFF", "#000000", "#0066CC"],
            "fonts": ["Arial", "Helvetica"],
            "background_color": "#FFFFFF"
        },
        network_requests=[
            {"url": "https://example.com/api/data", "method": "GET", "status": "200", "type": "xhr"}
        ]
    )


@pytest.fixture
def sample_element_info():
    """Create sample ElementInfo for testing."""
    return ElementInfo(
        selector="#test-button",
        tag="button",
        text_content="Click Me",
        aria_label="Test button",
        role="button",
        bounding_box={"x": 100.0, "y": 200.0, "width": 80.0, "height": 40.0}
    )


@pytest.fixture
def sample_analysis_result():
    """Create sample AnalysisResult for testing."""
    return AnalysisResult(
        url="https://example.com",
        page_purpose="This is a landing page for a test website",
        page_type="landing",
        components_identified=[
            {"name": "Header", "description": "Navigation bar", "location": "top"},
            {"name": "Hero", "description": "Main banner", "location": "main"}
        ],
        layout_pattern="Single column layout",
        ui_patterns=["Card grid", "Sticky header"],
        framework_hints=["React", "Tailwind CSS"],
        design_description="Modern minimal design",
        color_palette_description="Blue and white palette"
    )


@pytest.fixture
def sample_page_result(sample_capture_data, sample_analysis_result):
    """Create sample PageResult for testing."""
    return PageResult(
        url="https://example.com",
        depth=0,
        discovered_from=None,
        initial_capture=sample_capture_data,
        outgoing_links=["https://example.com/about", "https://example.com/contact"],
        analysis=sample_analysis_result,
        processing_time_seconds=1.5
    )


@pytest.fixture
def mock_playwright_page():
    """Create a mock Playwright page object."""
    from unittest.mock import AsyncMock, MagicMock

    page = AsyncMock()
    page.url = "https://example.com"
    page.goto = AsyncMock()
    page.title = AsyncMock(return_value="Test Page")
    page.screenshot = AsyncMock()
    page.content = AsyncMock(return_value="<html><body>Test</body></html>")
    page.evaluate = AsyncMock(return_value={})
    page.eval_on_selector = AsyncMock(return_value="Test description")
    page.eval_on_selector_all = AsyncMock(return_value=[
        "https://example.com/page1",
        "https://example.com/page2"
    ])
    page.query_selector_all = AsyncMock(return_value=[])
    page.wait_for_selector = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.mouse = MagicMock()
    page.mouse.move = AsyncMock()
    page.mouse.click = AsyncMock()
    page.mouse.wheel = AsyncMock()
    page.keyboard = MagicMock()
    page.keyboard.type = AsyncMock()
    page.keyboard.press = AsyncMock()

    return page

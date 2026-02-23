"""Integration tests for WebScope.

These tests spin up a simple HTTP server and run the full crawler pipeline.
"""

import asyncio
import http.server
import socketserver
import threading
import time
from pathlib import Path

import pytest

from webscope.models import CrawlConfig
from webscope.cli import run_crawl


# Sample HTML pages for testing
INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="description" content="Test home page">
    <title>Test Site - Home</title>
    <style>
        body { font-family: Arial; background-color: #f0f0f0; }
        .header { background-color: #333; color: white; padding: 20px; }
        .button { background-color: #0066cc; color: white; padding: 10px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Welcome to Test Site</h1>
        <nav>
            <a href="/">Home</a>
            <a href="/about.html">About</a>
        </nav>
    </div>
    <main>
        <p>This is a test page for WebScope integration testing.</p>
        <button id="test-btn" class="button">Click Me</button>
    </main>
    <footer>
        <p>Copyright 2026</p>
    </footer>
</body>
</html>"""

ABOUT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="description" content="About us">
    <title>Test Site - About</title>
</head>
<body>
    <h1>About Us</h1>
    <p>This is the about page.</p>
    <a href="/">Back to Home</a>
</body>
</html>"""


class TestHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler that serves our test HTML."""

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(INDEX_HTML.encode())
        elif self.path == "/about.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(ABOUT_HTML.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress log messages."""
        pass


@pytest.fixture(scope="module")
def http_server():
    """Start a test HTTP server."""
    # Find an available port
    port = 8765

    server = socketserver.TCPServer(("127.0.0.1", port), TestHTTPHandler)

    # Start server in background thread
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Wait for server to be ready
    time.sleep(0.5)

    yield f"http://127.0.0.1:{port}"

    # Cleanup
    server.shutdown()


@pytest.mark.asyncio
@pytest.mark.timeout(60)  # Prevent hanging
async def test_full_pipeline(http_server, tmp_path):
    """Test the complete crawling pipeline."""
    config = CrawlConfig(
        start_url=http_server,
        output_dir=tmp_path,
        max_depth=1,
        max_pages=2,
        headless=True,
        delay_min=0.1,
        delay_max=0.2,
        enable_ai=False,  # Skip AI for integration test
        verbose=False
    )

    # Run the full pipeline with timeout
    try:
        report = await asyncio.wait_for(run_crawl(config), timeout=30)

        # Verify crawl completed
        assert report is not None
        assert report.total_pages_crawled > 0

        # Verify pages were discovered
        assert len(report.pages) > 0

        # Verify screenshots exist
        screenshots_dir = tmp_path / "screenshots"
        assert screenshots_dir.exists()

        screenshot_files = list(screenshots_dir.glob("*.png"))
        assert len(screenshot_files) > 0

        # Verify report was generated
        report_path = tmp_path / "report.md"
        assert report_path.exists()

        # Verify report content
        content = report_path.read_text()
        assert "Web App Analysis" in content
        assert "127.0.0.1" in content or "Localhost" in content
        assert "## Overview" in content
        assert "## Pages" in content

        # Verify sitemap was built
        assert len(report.sitemap) > 0

    except asyncio.TimeoutError:
        pytest.fail("Crawl timed out after 30 seconds")


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_single_page_capture(http_server, tmp_path):
    """Test capturing a single page without following links."""
    config = CrawlConfig(
        start_url=http_server,
        output_dir=tmp_path,
        max_depth=0,  # Don't follow links
        max_pages=1,
        headless=True,
        delay_min=0.1,
        delay_max=0.2,
        enable_ai=False,
        verbose=False
    )

    try:
        report = await asyncio.wait_for(run_crawl(config), timeout=20)

        # Should have exactly 1 page
        assert report.total_pages_crawled == 1
        assert len(report.pages) == 1

        page = report.pages[0]
        assert page.url == http_server or page.url == f"{http_server}/"
        assert page.depth == 0
        assert page.initial_capture is not None

        # Verify capture data
        capture = page.initial_capture
        assert capture.title == "Test Site - Home"
        assert "Test home page" in capture.meta_description
        assert capture.screenshot_path.exists()

        # Verify DOM snapshot was captured
        assert len(capture.dom_snapshot) > 0
        assert "<body" in capture.dom_snapshot or "<h1" in capture.dom_snapshot

    except asyncio.TimeoutError:
        pytest.fail("Single page capture timed out")


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_link_discovery(http_server, tmp_path):
    """Test that links are discovered and followed."""
    config = CrawlConfig(
        start_url=http_server,
        output_dir=tmp_path,
        max_depth=1,
        max_pages=5,
        headless=True,
        delay_min=0.1,
        delay_max=0.2,
        enable_ai=False,
        same_domain_only=True,
        verbose=False
    )

    try:
        report = await asyncio.wait_for(run_crawl(config), timeout=30)

        # Should discover and crawl the about page
        assert report.total_pages_crawled >= 2

        # Check that about page was found
        urls = [page.url for page in report.pages]
        about_url = f"{http_server}/about.html"

        # Either the exact URL or a normalized version
        assert any(about_url in url or "about" in url for url in urls)

    except asyncio.TimeoutError:
        pytest.fail("Link discovery test timed out")


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_screenshot_capture(http_server, tmp_path):
    """Test that screenshots are properly captured."""
    config = CrawlConfig(
        start_url=http_server,
        output_dir=tmp_path,
        max_depth=0,
        max_pages=1,
        headless=True,
        delay_min=0.1,
        delay_max=0.2,
        enable_ai=False,
        verbose=False
    )

    try:
        report = await asyncio.wait_for(run_crawl(config), timeout=20)

        page = report.pages[0]
        screenshot_path = page.initial_capture.screenshot_path

        # Verify screenshot exists and has content
        assert screenshot_path.exists()
        assert screenshot_path.stat().st_size > 0

        # Verify it's a PNG file
        with open(screenshot_path, 'rb') as f:
            header = f.read(8)
            # PNG magic number
            assert header[:4] == b'\x89PNG'

    except asyncio.TimeoutError:
        pytest.fail("Screenshot capture test timed out")


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_style_extraction(http_server, tmp_path):
    """Test that styles are extracted from pages."""
    config = CrawlConfig(
        start_url=http_server,
        output_dir=tmp_path,
        max_depth=0,
        max_pages=1,
        headless=True,
        delay_min=0.1,
        delay_max=0.2,
        enable_ai=False,
        verbose=False
    )

    try:
        report = await asyncio.wait_for(run_crawl(config), timeout=20)

        page = report.pages[0]
        styles = page.initial_capture.computed_styles

        # Should have extracted some styles
        assert "colors" in styles or "fonts" in styles or "background_color" in styles

        # If colors were extracted, should include some from our test page
        if "colors" in styles and styles["colors"]:
            # Our test page has #333, #0066cc, white, etc.
            colors = styles["colors"]
            assert len(colors) > 0

    except asyncio.TimeoutError:
        pytest.fail("Style extraction test timed out")


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_depth_limiting(http_server, tmp_path):
    """Test that depth limiting works correctly."""
    config = CrawlConfig(
        start_url=http_server,
        output_dir=tmp_path,
        max_depth=0,  # Only crawl start page
        max_pages=10,
        headless=True,
        delay_min=0.1,
        delay_max=0.2,
        enable_ai=False,
        verbose=False
    )

    try:
        report = await asyncio.wait_for(run_crawl(config), timeout=20)

        # Should only have 1 page (the start page)
        assert report.total_pages_crawled == 1

        # All pages should be at depth 0
        for page in report.pages:
            assert page.depth == 0

    except asyncio.TimeoutError:
        pytest.fail("Depth limiting test timed out")


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_report_generation(http_server, tmp_path):
    """Test that Markdown report is properly generated."""
    config = CrawlConfig(
        start_url=http_server,
        output_dir=tmp_path,
        max_depth=1,
        max_pages=2,
        headless=True,
        delay_min=0.1,
        delay_max=0.2,
        enable_ai=False,
        verbose=False
    )

    try:
        report = await asyncio.wait_for(run_crawl(config), timeout=30)

        report_path = tmp_path / "report.md"
        assert report_path.exists()

        content = report_path.read_text()

        # Verify report structure
        assert "# " in content  # Has title
        assert "## Overview" in content
        assert "## Sitemap" in content
        assert "## Pages" in content

        # Verify page content
        assert "Test Site - Home" in content

        # Verify metadata
        assert "Pages analyzed:" in content
        assert "Duration:" in content

    except asyncio.TimeoutError:
        pytest.fail("Report generation test timed out")

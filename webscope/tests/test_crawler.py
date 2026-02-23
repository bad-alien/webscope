"""Unit tests for webscope/crawler.py"""

from unittest.mock import AsyncMock, MagicMock
from collections import deque

import pytest

from webscope.crawler import Crawler, normalize_url
from webscope.models import CrawlConfig
from webscope.stealth import HumanBehavior, StealthConfig


class TestNormalizeUrl:
    """Test the normalize_url function in crawler.py."""

    def test_removes_fragment(self):
        """Test fragment removal."""
        url = "https://example.com/page#section"
        result = normalize_url(url)
        assert "#" not in result
        assert result == "https://example.com/page"

    def test_lowercase_domain(self):
        """Test domain lowercasing."""
        url = "https://EXAMPLE.COM/page"
        result = normalize_url(url)
        assert result == "https://example.com/page"

    def test_sorts_query_params(self):
        """Test query parameter sorting."""
        url = "https://example.com?z=3&a=1"
        result = normalize_url(url)
        assert result == "https://example.com?a=1&z=3"

    def test_removes_trailing_slash(self):
        """Test trailing slash removal."""
        url = "https://example.com/page/"
        result = normalize_url(url)
        assert result == "https://example.com/page"

    def test_removes_default_ports(self):
        """Test default port removal."""
        url1 = "http://example.com:80/page"
        url2 = "https://example.com:443/page"
        assert ":80" not in normalize_url(url1)
        assert ":443" not in normalize_url(url2)


class TestCrawler:
    """Test Crawler class."""

    @pytest.fixture
    def mock_human(self, mock_playwright_page):
        """Create mock HumanBehavior."""
        stealth_config = StealthConfig()
        return HumanBehavior(mock_playwright_page, stealth_config)

    @pytest.fixture
    def crawler(self, sample_config, mock_human):
        """Create a Crawler instance."""
        return Crawler("https://example.com", sample_config, mock_human)

    def test_initialization(self, crawler):
        """Test crawler initialization."""
        assert crawler.start_url == "https://example.com"
        assert crawler.domain == "example.com"
        assert len(crawler.visited) == 0
        assert len(crawler.queue) == 0

    def test_domain_extraction(self, sample_config, mock_human):
        """Test domain extraction from start URL."""
        crawler = Crawler("https://sub.example.com:8080/path", sample_config, mock_human)
        assert crawler.domain == "sub.example.com:8080"

    @pytest.mark.asyncio
    async def test_crawl_single_page(self, crawler):
        """Test crawling a single page."""
        pages = []
        async for url, depth, parent in crawler.crawl():
            pages.append((url, depth, parent))

        assert len(pages) == 1
        assert pages[0] == ("https://example.com", 0, None)
        assert "https://example.com" in crawler.visited

    @pytest.mark.asyncio
    async def test_crawl_respects_max_pages(self, sample_config, mock_human):
        """Test max_pages limit."""
        sample_config.max_pages = 3
        crawler = Crawler("https://example.com", sample_config, mock_human)

        # Manually add URLs to queue
        for i in range(10):
            crawler.queue.append((f"https://example.com/page{i}", 0, None))

        pages = []
        async for url, depth, parent in crawler.crawl():
            pages.append(url)

        assert len(pages) == 3  # Should stop at max_pages

    @pytest.mark.asyncio
    async def test_crawl_respects_max_depth(self, sample_config, mock_human):
        """Test max_depth limit."""
        sample_config.max_depth = 2
        crawler = Crawler("https://example.com", sample_config, mock_human)

        # Add URLs at different depths (start_url is already queued by crawl())
        crawler.queue.append(("https://example.com/page1", 1, "https://example.com"))
        crawler.queue.append(("https://example.com/page2", 2, "https://example.com/page1"))
        crawler.queue.append(("https://example.com/page3", 3, "https://example.com/page2"))  # Too deep

        pages = []
        async for url, depth, parent in crawler.crawl():
            pages.append((url, depth))

        # start_url (depth 0) + page1 (depth 1) + page2 (depth 2) = 3, page3 filtered
        assert len(pages) == 3
        assert all(depth <= 2 for url, depth in pages)

    @pytest.mark.asyncio
    async def test_url_deduplication(self, crawler):
        """Test that URLs are only visited once."""
        # Add same URL multiple times
        crawler.queue.append(("https://example.com", 0, None))
        crawler.queue.append(("https://example.com", 1, None))
        crawler.queue.append(("https://example.com", 2, None))

        pages = []
        async for url, depth, parent in crawler.crawl():
            pages.append(url)

        assert len(pages) == 1  # Should only visit once

    @pytest.mark.asyncio
    async def test_discover_links_on_page(self, crawler, mock_playwright_page):
        """Test link discovery on a page."""
        # Mock the eval_on_selector_all to return links
        mock_playwright_page.eval_on_selector_all.return_value = [
            "https://example.com/about",
            "https://example.com/contact",
            "https://other.com/external",  # Different domain
        ]

        links = await crawler.discover_links_on_page(
            mock_playwright_page,
            "https://example.com",
            0
        )

        # Should find same-domain links
        assert len(links) == 2
        assert "https://example.com/about" in links
        assert "https://example.com/contact" in links

        # Should have added to queue
        assert len(crawler.queue) == 2

    @pytest.mark.asyncio
    async def test_discover_links_same_domain_only(self, crawler, mock_playwright_page):
        """Test same_domain_only filtering."""
        mock_playwright_page.eval_on_selector_all.return_value = [
            "https://example.com/page1",
            "https://sub.example.com/page2",  # Different subdomain
            "https://other.com/page3",  # Different domain
        ]

        links = await crawler.discover_links_on_page(
            mock_playwright_page,
            "https://example.com",
            0
        )

        # Should only include exact domain match
        assert len(links) == 1
        assert links[0] == "https://example.com/page1"

    @pytest.mark.asyncio
    async def test_discover_links_allows_cross_domain_when_disabled(
        self, sample_config, mock_human, mock_playwright_page
    ):
        """Test cross-domain crawling when same_domain_only is False."""
        sample_config.same_domain_only = False
        crawler = Crawler("https://example.com", sample_config, mock_human)

        mock_playwright_page.eval_on_selector_all.return_value = [
            "https://example.com/page1",
            "https://other.com/page2",
        ]

        links = await crawler.discover_links_on_page(
            mock_playwright_page,
            "https://example.com",
            0
        )

        # Should include both links
        assert len(links) == 2

    @pytest.mark.asyncio
    async def test_discover_links_skips_visited(self, crawler, mock_playwright_page):
        """Test that visited URLs are not re-queued."""
        # Mark a URL as visited
        crawler.visited.add("https://example.com/about")

        mock_playwright_page.eval_on_selector_all.return_value = [
            "https://example.com/about",  # Already visited
            "https://example.com/contact",
        ]

        links = await crawler.discover_links_on_page(
            mock_playwright_page,
            "https://example.com",
            0
        )

        # Should discover both but only queue the unvisited one
        assert len(links) == 1
        assert links[0] == "https://example.com/contact"

    @pytest.mark.asyncio
    async def test_discover_links_increments_depth(self, crawler, mock_playwright_page):
        """Test that discovered links have incremented depth."""
        mock_playwright_page.eval_on_selector_all.return_value = [
            "https://example.com/page1"
        ]

        await crawler.discover_links_on_page(
            mock_playwright_page,
            "https://example.com",
            1  # Current depth
        )

        # Check queued URL has depth 2
        assert len(crawler.queue) == 1
        url, depth, parent = crawler.queue[0]
        assert depth == 2

    @pytest.mark.asyncio
    async def test_discover_links_handles_exceptions(self, crawler, mock_playwright_page):
        """Test graceful handling of eval exceptions."""
        # Make eval_on_selector_all raise an exception
        mock_playwright_page.eval_on_selector_all.side_effect = Exception("Eval failed")

        links = await crawler.discover_links_on_page(
            mock_playwright_page,
            "https://example.com",
            0
        )

        # Should return empty list on error
        assert links == []

    def test_should_respect_robots_default(self, crawler):
        """Test robots.txt check (not implemented, always returns True)."""
        result = crawler.should_respect_robots("https://example.com/page")
        assert result is True

    def test_should_respect_robots_when_disabled(self, sample_config, mock_human):
        """Test robots.txt check when respect_robots is False."""
        sample_config.respect_robots = False
        crawler = Crawler("https://example.com", sample_config, mock_human)

        result = crawler.should_respect_robots("https://example.com/page")
        assert result is True  # Always True when disabled

    @pytest.mark.asyncio
    async def test_crawl_tracks_parent_urls(self, crawler, mock_playwright_page):
        """Test that parent URLs are tracked correctly."""
        mock_playwright_page.eval_on_selector_all.return_value = [
            "https://example.com/child"
        ]

        # Start crawl
        async for url, depth, parent in crawler.crawl():
            if url == "https://example.com":
                # Discover links after first page
                await crawler.discover_links_on_page(mock_playwright_page, url, depth)
                break

        # Check that child has correct parent
        assert len(crawler.queue) == 1
        child_url, child_depth, child_parent = crawler.queue[0]
        assert child_url == "https://example.com/child"
        assert child_parent == "https://example.com"

    @pytest.mark.asyncio
    async def test_crawl_breadth_first_order(self, sample_config, mock_human):
        """Test that crawling follows breadth-first order."""
        crawler = Crawler("https://example.com", sample_config, mock_human)

        # Manually set up BFS test structure
        crawler.queue.append(("https://example.com", 0, None))
        crawler.queue.append(("https://example.com/a", 1, "https://example.com"))
        crawler.queue.append(("https://example.com/b", 1, "https://example.com"))
        crawler.queue.append(("https://example.com/c", 2, "https://example.com/a"))

        depths = []
        async for url, depth, parent in crawler.crawl():
            depths.append(depth)

        # Should visit depth 0, then all depth 1, then depth 2
        assert depths == [0, 1, 1, 2]

"""Link discovery and page queue management for breadth-first crawling."""

from collections import deque
from typing import AsyncIterator, List, Optional, Set, Tuple
from urllib.parse import urlparse

from playwright.async_api import Page

from .models import CrawlConfig
from .stealth import HumanBehavior
from .utils import get_root_domain, normalize_url as utils_normalize_url


class Crawler:
    """
    BFS crawler with depth tracking and URL deduplication.
    """

    def __init__(
        self, start_url: str, config: CrawlConfig, human: HumanBehavior
    ):
        self.start_url = utils_normalize_url(start_url)
        self.config = config
        self.human = human

        self.visited: Set[str] = set()
        self.queue: deque = deque()  # (url, depth, parent_url)
        self.domain = urlparse(start_url).netloc
        self.root_domain = get_root_domain(self.domain)

    async def crawl(self) -> AsyncIterator[Tuple[str, int, Optional[str]]]:
        """
        Crawl pages breadth-first.

        Yields:
            Tuple of (url, depth, parent_url) for each page to process

        Algorithm:
        1. Add start_url to queue at depth 0
        2. While queue not empty and pages < max_pages:
           a. Pop url from queue
           b. If already visited or depth > max_depth, skip
           c. Yield url for processing
           d. Mark as visited
           e. After processing (caller handles), discover links and enqueue
        """
        self.queue.append((self.start_url, 0, None))
        pages_crawled = 0

        while self.queue and pages_crawled < self.config.max_pages:
            url, depth, parent = self.queue.popleft()

            if url in self.visited or depth > self.config.max_depth:
                continue

            self.visited.add(url)
            pages_crawled += 1

            yield url, depth, parent

    async def discover_links_on_page(
        self, page: Page, current_url: str, current_depth: int
    ) -> List[str]:
        """
        Find all same-domain links on current page and enqueue them.

        Args:
            page: Playwright page object
            current_url: URL of current page
            current_depth: Depth of current page

        Returns:
            List of discovered URLs (for PageResult)
        """
        import logging
        logger = logging.getLogger(__name__)

        # Extract all <a href> elements with timeout
        try:
            logger.debug("Discovering links on page")
            links = await page.eval_on_selector_all(
                "a[href]", "elements => elements.map(el => el.href)"
            )
            logger.debug(f"Found {len(links)} links")
        except Exception as e:
            logger.warning(f"Failed to discover links: {e}")
            links = []

        discovered = []
        for link in links:
            try:
                normalized = normalize_url(link)

                # Filter to same domain if configured
                if self.config.same_domain_only:
                    link_netloc = urlparse(normalized).netloc
                    if self.config.include_subdomains:
                        if get_root_domain(link_netloc) != self.root_domain:
                            continue
                    else:
                        if link_netloc != self.domain:
                            continue

                # Skip if already visited
                if normalized not in self.visited:
                    self.queue.append((normalized, current_depth + 1, current_url))
                    discovered.append(normalized)
            except Exception as e:
                # Skip malformed URLs
                logger.debug(f"Error normalizing URL {link}: {e}")
                continue

        logger.debug(f"Discovered {len(discovered)} new links")
        return discovered

    def should_respect_robots(self, url: str) -> bool:
        """
        Check if URL is allowed by robots.txt.

        Implementation:
        - Use urllib.robotparser.RobotFileParser
        - Cache robots.txt per domain
        - If config.respect_robots is False, always return True
        """
        if not self.config.respect_robots:
            return True

        # TODO: Implement robots.txt parsing
        # For now, always allow
        return True


def normalize_url(url: str) -> str:
    """
    Normalize URL for deduplication.

    Steps:
    1. Remove fragment (#section)
    2. Remove trailing slash (unless it's just the domain)
    3. Lowercase scheme and domain
    4. Sort query parameters alphabetically
    5. Remove default ports (:80, :443)

    Examples:
    - https://Example.com/Page/ → https://example.com/page
    - https://site.com/page?b=2&a=1 → https://site.com/page?a=1&b=2
    """
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(url)

    # Remove fragment
    parsed = parsed._replace(fragment="")

    # Lowercase scheme and netloc
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove default ports (exact match only)
    if netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif netloc.endswith(":443"):
        netloc = netloc[:-4]

    # Sort query params
    query_dict = parse_qs(parsed.query, keep_blank_values=True)
    sorted_query = urlencode(sorted(query_dict.items()), doseq=True)

    # Normalize path: strip trailing slash, treat empty as /
    path = parsed.path.rstrip("/") or "/"

    return urlunparse((scheme, netloc, path, parsed.params, sorted_query, ""))

"""
WebScope CLI entry point.

Main command-line interface for the web crawler.
Usage: python -m webscope <url> [options]
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from webscope.models import CrawlConfig, Report, PageResult
from webscope.utils import setup_logging, ensure_dir, normalize_url

# Load .env from the webscope package directory and project root
load_dotenv(Path(__file__).parent / ".env")
load_dotenv(Path(__file__).parent.parent / ".env")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog='webscope',
        description='Crawl web apps and generate detailed analysis reports',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m webscope https://example.com
  python -m webscope https://example.com --depth 5 --max-pages 50
  python -m webscope https://example.com --output ./reports --no-ai
  python -m webscope https://example.com --headed --delay 2.0 5.0
        """
    )

    parser.add_argument('url', help='Target URL to crawl')
    parser.add_argument('--depth', type=int, default=3, metavar='N',
                        help='Maximum crawl depth (default: 3)')
    parser.add_argument('--max-pages', type=int, default=20, metavar='N',
                        help='Maximum number of pages to crawl (default: 20)')
    parser.add_argument('--output', type=Path, default=None,
                        metavar='DIR', help='Output directory for report (default: webscope/reports/<domain>)')
    parser.add_argument('--no-ai', action='store_true',
                        help='Skip LLM analysis')

    headless_group = parser.add_mutually_exclusive_group()
    headless_group.add_argument('--headless', action='store_true', default=True,
                                help='Run browser in headless mode (default)')
    headless_group.add_argument('--headed', dest='headless', action='store_false',
                                help='Run browser in headed mode (show window)')

    parser.add_argument('--include-subdomains', action='store_true',
                        help='Crawl subdomains of the target domain (e.g. blog.example.com)')
    parser.add_argument('--delay', type=float, nargs=2, default=[1.0, 3.0],
                        metavar=('MIN', 'MAX'),
                        help='Delay range in seconds between actions (default: 1.0 3.0)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')

    return parser.parse_args()


def validate_url(url: str) -> str:
    """Validate and normalize the input URL."""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    if not url.strip():
        raise ValueError("URL cannot be empty")
    normalize_url(url)
    return url


async def run_crawl(config: CrawlConfig) -> Report:
    """
    Execute the full crawl pipeline.

    Flow: launch browser -> crawl pages -> interact -> capture -> analyze -> report
    """
    from playwright.async_api import async_playwright
    from webscope.stealth import HumanBehavior, StealthConfig, create_stealth_browser
    from webscope.crawler import Crawler
    from webscope.interactor import Interactor
    from webscope.capturer import Capturer
    from webscope.analyzer import Analyzer
    from webscope.reporter import Reporter

    logger = logging.getLogger(__name__)
    crawl_started = datetime.now()
    pages: list[PageResult] = []
    sitemap: dict[str, list[str]] = {}

    print(f"\n  WebScope - Crawling {config.start_url}\n")

    async with async_playwright() as pw:
        # Create stealth browser
        stealth_config = StealthConfig(
            delay_min=config.delay_min,
            delay_max=config.delay_max,
            mouse_speed=config.mouse_speed,
            scroll_pause_min=config.scroll_pause_min,
            scroll_pause_max=config.scroll_pause_max,
        )
        browser, context = await create_stealth_browser(
            pw, stealth_config, headless=config.headless
        )

        page = await context.new_page()
        human = HumanBehavior(page, stealth_config)
        crawler = Crawler(config.start_url, config, human)
        interactor = Interactor(human, config)
        capturer = Capturer(config.output_dir)

        # Attach network logging
        capturer.attach_network_logging(page)

        # Crawl pages
        page_count = 0
        async for url, depth, parent_url in crawler.crawl():
            page_count += 1
            page_start = time.time()
            print(f"  [{page_count}/{config.max_pages}] depth={depth}  {url}")

            try:
                # Navigate
                logger.debug(f"Navigating to {url}")
                await human.goto(url)
                logger.debug("Navigation complete")

                # Capture initial state
                logger.debug("Capturing initial page state")
                initial_capture = await capturer.capture_page(page, url)
                logger.debug("Initial capture complete")

                # Scroll the page to load lazy content
                logger.debug("Scrolling page")
                await human.scroll_page()
                logger.debug("Scrolling complete")

                # Discover links BEFORE interactions
                logger.debug("Discovering outgoing links (pre-interaction)")
                outgoing_links = await crawler.discover_links_on_page(
                    page, url, depth
                )

                # Discover and explore interactive elements
                logger.debug("Discovering interactive elements")
                elements = await interactor.discover_interactive_elements(page)
                logger.debug(f"Discovered {len(elements)} elements")

                logger.debug("Exploring interactions")
                interactions = await interactor.explore_interactions(page, elements)
                logger.debug(f"Completed {len(interactions)} interactions")

                # Take post-interaction captures for significant changes
                interaction_captures = []
                has_dom_changes = False
                for interaction in interactions:
                    if interaction.modal_opened or interaction.dom_changed:
                        has_dom_changes = True
                        cap = await capturer.capture_page(
                            page, url, suffix=f"_interaction_{len(interaction_captures)}"
                        )
                        interaction_captures.append(cap)

                # Re-discover links AFTER interactions revealed new content
                # (e.g., clicking splash reveals nav menu with links)
                if has_dom_changes:
                    logger.debug("DOM changed during interactions — checking for revealed links")
                    from webscope.crawler import normalize_url as crawler_normalize
                    from urllib.parse import urlparse

                    # First check current state (interactions may have left content revealed)
                    post_links = await interactor.discover_new_links(page)
                    logger.debug(f"Found {len(post_links)} links in current state")

                    # If no links found, try re-clicking elements that caused changes
                    if not post_links:
                        for interaction in interactions:
                            if not (interaction.dom_changed and interaction.success and not interaction.url_changed):
                                continue
                            try:
                                logger.debug(f"Re-clicking {interaction.element.selector} to toggle content")
                                await human.click(interaction.element.selector, timeout=5000)
                                await page.wait_for_timeout(1200)
                                post_links = await interactor.discover_new_links(page)
                                logger.debug(f"Found {len(post_links)} links after re-clicking")
                                if post_links:
                                    break  # Found links, stop trying
                            except Exception as e:
                                logger.debug(f"Re-click failed: {e}")

                    for link in post_links:
                        try:
                            normalized = crawler_normalize(link)
                        except Exception:
                            continue
                        link_domain = urlparse(normalized).netloc
                        logger.debug(f"  Link: {normalized} | domain: '{link_domain}' vs crawler: '{crawler.domain}'")
                        from webscope.utils import get_root_domain
                        if config.include_subdomains:
                            domain_match = get_root_domain(link_domain) == crawler.root_domain
                        else:
                            crawl_domain = crawler.domain.removeprefix("www.")
                            link_base = link_domain.removeprefix("www.")
                            domain_match = link_base == crawl_domain
                        if domain_match:
                            if normalized not in crawler.visited:
                                crawler.queue.append((normalized, depth + 1, url))
                                if normalized not in outgoing_links:
                                    outgoing_links.append(normalized)
                                logger.debug(f"  Queued: {normalized}")

                    # Take a screenshot of revealed state if we found new links
                    if post_links:
                        cap = await capturer.capture_page(page, url, suffix="_revealed")
                        interaction_captures.append(cap)

                    logger.debug(f"Total outgoing links after interactions: {len(outgoing_links)}")

                sitemap[url] = outgoing_links
                logger.debug(f"Discovered {len(outgoing_links)} outgoing links")

                page_result = PageResult(
                    url=url,
                    depth=depth,
                    discovered_from=parent_url,
                    initial_capture=initial_capture,
                    interactions=interactions,
                    interaction_captures=interaction_captures,
                    outgoing_links=outgoing_links,
                    processing_time_seconds=time.time() - page_start,
                )
                pages.append(page_result)

            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                pages.append(PageResult(
                    url=url,
                    depth=depth,
                    discovered_from=parent_url,
                    processing_time_seconds=time.time() - page_start,
                ))

        await browser.close()

    crawl_finished = datetime.now()
    total_interactions = sum(len(p.interactions) for p in pages)
    print(f"\n  Crawl complete: {len(pages)} pages, {total_interactions} interactions")

    # AI analysis
    if config.enable_ai and config.anthropic_api_key:
        print(f"  Running AI analysis...")
        analyzer = Analyzer(config.anthropic_api_key, config.model)
        analyses = await analyzer.batch_analyze(pages)
        for page_result, analysis in zip(pages, analyses):
            page_result.analysis = analysis
        print(f"  AI analysis complete.")
    elif config.enable_ai and not config.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set — skipping AI analysis")

    # Build report
    report = Report(
        config=config,
        start_url=config.start_url,
        crawl_started=crawl_started,
        crawl_finished=crawl_finished,
        pages=pages,
        total_pages_crawled=len(pages),
        total_interactions=total_interactions,
        sitemap=sitemap,
        output_dir=config.output_dir,
    )

    # Generate markdown report
    reporter = Reporter(config.output_dir)
    reporter.copy_screenshots(pages)
    report_path = reporter.generate_report(report)
    report.markdown_path = report_path
    print(f"  Report written to: {report_path}\n")

    return report


async def main() -> int:
    """Main CLI entry point."""
    try:
        args = parse_args()
        url = validate_url(args.url)
        delay_min, delay_max = args.delay[0], args.delay[1]

        if delay_min < 0 or delay_max < 0:
            raise ValueError("Delay values must be non-negative")
        if delay_min > delay_max:
            raise ValueError("Minimum delay cannot be greater than maximum delay")

        setup_logging(verbose=args.verbose)

        # Default output: webscope/reports/<domain>
        if args.output is None:
            from urllib.parse import urlparse as _urlparse
            domain = _urlparse(url).netloc.replace(':', '_')
            output_dir = Path(__file__).parent / 'reports' / domain
        else:
            output_dir = args.output

        ensure_dir(output_dir)

        config = CrawlConfig(
            start_url=url,
            output_dir=output_dir,
            max_depth=args.depth,
            max_pages=args.max_pages,
            headless=args.headless,
            delay_min=delay_min,
            delay_max=delay_max,
            include_subdomains=args.include_subdomains,
            enable_ai=not args.no_ai,
            anthropic_api_key=os.getenv('ANTHROPIC_API_KEY'),
            verbose=args.verbose,
        )

        await run_crawl(config)
        return 0

    except KeyboardInterrupt:
        print("\n  Crawl interrupted by user.")
        return 130

    except ValueError as e:
        print(f"  Error: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"  Unexpected error: {e}", file=sys.stderr)
        if '--verbose' in sys.argv:
            import traceback
            traceback.print_exc()
        return 1


def cli() -> None:
    """Entry point for console script."""
    sys.exit(asyncio.run(main()))


if __name__ == '__main__':
    cli()

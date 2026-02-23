"""
WebScope utility functions.

Helpers for URL normalization, filesystem operations, and logging setup.
"""

import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode


def normalize_url(url: str) -> str:
    """
    Normalize URL for deduplication.

    Steps:
    1. Remove fragment (#section)
    2. Remove trailing slash (unless it's just the domain)
    3. Lowercase scheme and domain
    4. Sort query parameters alphabetically
    5. Remove default ports (:80, :443)

    Args:
        url: URL to normalize

    Returns:
        Normalized URL string

    Examples:
        https://Example.com/Page/ → https://example.com/page
        https://site.com/page?b=2&a=1 → https://site.com/page?a=1&b=2
    """
    parsed = urlparse(url)

    # Remove fragment
    parsed = parsed._replace(fragment='')

    # Lowercase scheme and netloc
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove default ports (exact match only)
    if netloc.endswith(':80'):
        netloc = netloc[:-3]
    elif netloc.endswith(':443'):
        netloc = netloc[:-4]

    # Sort query params
    query_dict = parse_qs(parsed.query, keep_blank_values=True)
    sorted_query = urlencode(sorted(query_dict.items()), doseq=True)

    # Normalize path: strip trailing slash, treat empty as /
    path = parsed.path.rstrip('/') or '/'

    return urlunparse((scheme, netloc, path, parsed.params, sorted_query, ''))


def get_root_domain(netloc: str) -> str:
    """
    Extract the root domain from a netloc string.

    Strips port and returns the last two domain segments
    (or last three for two-letter TLDs like .co.uk).

    Examples:
        blog.example.com -> example.com
        app.staging.example.com -> example.com
        example.co.uk -> example.co.uk
        example.com:8080 -> example.com
    """
    host = netloc.lower().split(':')[0]  # strip port
    parts = host.split('.')
    if len(parts) <= 2:
        return host
    # Handle two-letter TLDs like .co.uk, .com.au
    if len(parts[-1]) <= 2 and len(parts[-2]) <= 3:
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])


def is_same_domain(url: str, base_url: str, include_subdomains: bool = False) -> bool:
    """
    Check if URL belongs to the same domain as base URL.

    Args:
        url: URL to check
        base_url: Base/reference URL
        include_subdomains: If True, match on root domain (e.g. blog.example.com matches example.com)

    Returns:
        True if both URLs are on the same domain
    """
    domain1 = urlparse(url).netloc.lower()
    domain2 = urlparse(base_url).netloc.lower()
    if include_subdomains:
        return get_root_domain(domain1) == get_root_domain(domain2)
    return domain1 == domain2


def sanitize_filename(url: str) -> str:
    """
    Convert URL to safe filename for screenshots.

    Removes special characters and keeps only alphanumeric, underscore, hyphen.

    Args:
        url: URL to sanitize

    Returns:
        Safe filename string
    """
    # Remove scheme and domain, keep path
    parsed = urlparse(url)
    path = parsed.path.lstrip('/').rstrip('/')

    # If no path, use domain
    if not path:
        path = parsed.netloc

    # Replace slashes with underscores
    path = path.replace('/', '_')

    # Remove special characters, keep only alphanumeric, underscore, hyphen
    path = re.sub(r'[^a-zA-Z0-9_-]', '', path)

    # Limit length
    if len(path) > 100:
        path = path[:100]

    return path or 'page'


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None) -> None:
    """
    Configure Python logging.

    Args:
        verbose: If True, set level to DEBUG; otherwise INFO
        log_file: Optional path to write logs to

    Format:
        [2025-01-15 10:30:45] INFO: Message here
    """
    level = logging.DEBUG if verbose else logging.INFO
    format_str = '[%(asctime)s] %(levelname)s: %(message)s'

    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=handlers,
        force=True  # Override any existing config
    )


def ensure_dir(path: Path) -> None:
    """
    Create directory if it doesn't exist.

    Args:
        path: Directory path to create
    """
    path.mkdir(parents=True, exist_ok=True)

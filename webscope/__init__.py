"""
WebScope - Web App Reverse-Engineering Crawler

A Python CLI tool that takes a URL, crawls public pages with human-like behavior,
and generates a Markdown report with annotated screenshots and LLM-generated descriptions.
"""

from .models import (
    CrawlConfig,
    ElementInfo,
    InteractionResult,
    CaptureData,
    AnalysisResult,
    PageResult,
    Report,
)
from .analyzer import Analyzer
from .reporter import Reporter

# These will be available once crawler/interactor/stealth are implemented
try:
    from .crawler import Crawler, normalize_url
except ImportError:
    pass

try:
    from .interactor import Interactor
except ImportError:
    pass

try:
    from .stealth import (
        HumanBehavior,
        StealthConfig,
        create_stealth_browser,
        get_user_agent_pool,
    )
except ImportError:
    pass

__version__ = "0.1.0"

__all__ = [
    # Data models
    "CrawlConfig",
    "ElementInfo",
    "InteractionResult",
    "CaptureData",
    "AnalysisResult",
    "PageResult",
    "Report",
    # AI and reporting
    "Analyzer",
    "Reporter",
    # Core components (when available)
    "Crawler",
    "normalize_url",
    "Interactor",
    "HumanBehavior",
    "StealthConfig",
    "create_stealth_browser",
    "get_user_agent_pool",
]

"""
WebScope data models.

All data models use Python dataclasses for type safety and clarity.
These are the shared types that all modules import from.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Literal, Any
from datetime import datetime
from pathlib import Path


@dataclass
class CrawlConfig:
    """Configuration for the entire crawl session."""

    # Core settings
    start_url: str
    output_dir: Path
    max_depth: int = 3
    max_pages: int = 20

    # Browser settings
    headless: bool = True
    viewport_width: int = 1920  # Will be randomized by stealth
    viewport_height: int = 1080

    # Stealth settings
    delay_min: float = 0.5  # Minimum delay between actions (seconds)
    delay_max: float = 2.0  # Maximum delay between actions (seconds)
    mouse_speed: float = 1.0  # Multiplier for mouse movement speed (1.0 = realistic)
    scroll_pause_min: float = 0.3  # Min pause during scroll reading
    scroll_pause_max: float = 1.2  # Max pause during scroll reading

    # Crawler settings
    respect_robots: bool = True
    same_domain_only: bool = True
    include_subdomains: bool = False  # If True, treat subdomains as same domain
    interaction_depth: int = 2  # How many nested interactions to explore per page

    # Analysis settings
    enable_ai: bool = True
    anthropic_api_key: Optional[str] = None
    model: str = "claude-sonnet-4-5-20250929"

    # Logging
    verbose: bool = False
    log_file: Optional[Path] = None


@dataclass
class ElementInfo:
    """Information about a discovered interactive element."""

    selector: str  # CSS selector to reliably find this element
    tag: str  # 'button', 'a', 'input', 'select', etc.
    text_content: str  # Visible text
    aria_label: Optional[str] = None
    role: Optional[str] = None

    # Position on page for mouse movement
    bounding_box: Dict[str, float] = field(default_factory=dict)  # {x, y, width, height}

    # Context
    parent_context: str = ""  # Brief parent element context for disambiguation


@dataclass
class InteractionResult:
    """Result of a single interaction (click, type, etc.)."""

    element: ElementInfo
    action_type: Literal["click", "hover", "type", "select"]
    timestamp: datetime

    # State changes detected
    modal_opened: bool = False
    modal_selector: Optional[str] = None
    url_changed: bool = False
    new_url: Optional[str] = None
    dom_changed: bool = False
    dom_diff_summary: str = ""  # Brief description of changes

    # Capture taken after interaction
    screenshot_path: Optional[Path] = None

    success: bool = True
    error_message: Optional[str] = None


@dataclass
class CaptureData:
    """All captured data for a single page state."""

    url: str
    timestamp: datetime
    screenshot_path: Path
    dom_snapshot: str

    # Visual
    screenshot_full_path: Optional[Path] = None  # Full-page screenshot if different

    # Structure
    title: str = ""
    meta_description: str = ""

    # Styles
    computed_styles: Dict[str, Any] = field(default_factory=dict)
    # Example: {
    #   "colors": ["#FFFFFF", "#000000", ...],
    #   "fonts": ["Inter", "Roboto", ...],
    #   "background_color": "#FAFAFA",
    #   "primary_color": "#0066CC"
    # }

    # Network
    network_requests: List[Dict[str, str]] = field(default_factory=list)
    # Example: [{"url": "...", "method": "GET", "status": 200, "type": "xhr"}, ...]

    # Interactive elements discovered
    interactive_elements: List[ElementInfo] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """LLM-generated analysis of a page."""

    url: str

    # High-level understanding
    page_purpose: str  # "This is a product listing page that..."
    page_type: Literal["landing", "listing", "detail", "form", "dashboard", "auth", "other"]

    # UI breakdown
    components_identified: List[Dict[str, str]] = field(default_factory=list)
    # Example: [
    #   {"name": "Navigation Bar", "description": "Top horizontal nav with...", "location": "top"},
    #   {"name": "Product Grid", "description": "3-column responsive grid...", "location": "main"}
    # ]

    # Design patterns
    layout_pattern: str = ""  # "Two-column layout with fixed sidebar"
    ui_patterns: List[str] = field(default_factory=list)  # ["Card pattern", "Infinite scroll", ...]

    # Technical observations
    framework_hints: List[str] = field(default_factory=list)  # ["React", "Tailwind CSS", ...]

    # Visual design
    design_description: str = ""  # "Modern, minimal design with generous whitespace..."
    color_palette_description: str = ""  # "Blue primary (#0066CC), neutral grays..."


@dataclass
class PageResult:
    """Complete result for a single page."""

    url: str
    depth: int  # How many links away from start_url
    discovered_from: Optional[str] = None  # Parent URL that linked here

    # Primary capture (initial page load)
    initial_capture: Optional['CaptureData'] = None

    # Interactions performed
    interactions: List[InteractionResult] = field(default_factory=list)

    # Captures from interactions (modals, state changes)
    interaction_captures: List[CaptureData] = field(default_factory=list)

    # Links discovered on this page
    outgoing_links: List[str] = field(default_factory=list)

    # LLM analysis
    analysis: Optional[AnalysisResult] = None

    # Metadata
    crawl_timestamp: datetime = field(default_factory=datetime.now)
    processing_time_seconds: float = 0.0


@dataclass
class Report:
    """Final assembled report structure."""

    config: CrawlConfig
    start_url: str
    crawl_started: datetime
    crawl_finished: datetime

    # Results
    pages: List[PageResult]
    total_pages_crawled: int
    total_interactions: int

    # Global analysis
    sitemap: Dict[str, List[str]] = field(default_factory=dict)  # url -> child urls
    global_color_palette: List[str] = field(default_factory=list)
    global_fonts: List[str] = field(default_factory=list)
    common_frameworks: List[str] = field(default_factory=list)

    # Output paths
    output_dir: Path = field(default_factory=Path)
    markdown_path: Optional[Path] = None
    screenshots_dir: Optional[Path] = None

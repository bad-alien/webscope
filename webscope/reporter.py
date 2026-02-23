"""Markdown report generation from crawl results.

This module generates comprehensive Markdown reports with embedded screenshots,
LLM analysis, component inventories, and technical details for each crawled page.
"""

import logging
import shutil
from pathlib import Path
from typing import List, Dict, Set
from urllib.parse import urlparse

from .models import Report, PageResult, AnalysisResult


logger = logging.getLogger(__name__)


class Reporter:
    """
    Generates Markdown report from crawl results.

    Creates a comprehensive report document with screenshots, analysis,
    component descriptions, and technical summaries organized for
    easy reference and replication.
    """

    def __init__(self, output_dir: Path):
        """
        Initialize reporter with output directory.

        Args:
            output_dir: Directory where report and assets will be written
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized Reporter with output directory: {output_dir}")

    def generate_report(self, report: Report) -> Path:
        """
        Generate comprehensive Markdown report.

        Creates a detailed report with sections for each page, including
        screenshots, LLM analysis, component inventories, interaction flows,
        and global technical summaries.

        Args:
            report: Report object with all crawl data

        Returns:
            Path to generated report.md file

        Report structure:
        - Header with metadata (URL, date, page count)
        - Overview section with global stats
        - Sitemap showing page hierarchy
        - Per-page detailed sections
        - Technical summary with aggregated patterns
        """
        logger.info(f"Generating report for {report.total_pages_crawled} pages")

        markdown_path = self.output_dir / "report.md"

        with open(markdown_path, 'w', encoding='utf-8') as f:
            # Header
            self._write_header(f, report)

            # Overview
            self._write_overview(f, report)

            # Sitemap
            self._write_sitemap(f, report)

            # Pages
            self._write_pages_section(f, report)

            # Technical Summary
            self._write_technical_summary(f, report)

        logger.info(f"Report generated successfully: {markdown_path}")
        return markdown_path

    def _write_header(self, f, report: Report) -> None:
        """Write report header with metadata."""
        site_name = self._extract_site_name(report.start_url)

        f.write(f"# {site_name} - Web App Analysis\n\n")
        f.write(f"**Crawled:** {report.start_url}  \n")
        f.write(f"**Date:** {report.crawl_started.strftime('%Y-%m-%d %H:%M')}  \n")
        f.write(f"**Pages analyzed:** {report.total_pages_crawled}  \n")
        f.write(f"**Duration:** {self._format_duration(report.crawl_started, report.crawl_finished)}  \n")
        f.write("\n")

    def _write_overview(self, f, report: Report) -> None:
        """Write overview section with global statistics."""
        f.write("## Overview\n\n")
        f.write(f"- **Total pages:** {report.total_pages_crawled}\n")
        f.write(f"- **Total interactions:** {report.total_interactions}\n")
        f.write(f"- **Max depth:** {report.config.max_depth}\n")

        if report.common_frameworks:
            f.write(f"- **Frameworks detected:** {', '.join(report.common_frameworks)}\n")

        if report.global_color_palette:
            colors_preview = ', '.join(report.global_color_palette[:10])
            if len(report.global_color_palette) > 10:
                colors_preview += f" (+{len(report.global_color_palette) - 10} more)"
            f.write(f"- **Color palette:** {colors_preview}\n")

        if report.global_fonts:
            fonts_preview = ', '.join(report.global_fonts[:5])
            if len(report.global_fonts) > 5:
                fonts_preview += f" (+{len(report.global_fonts) - 5} more)"
            f.write(f"- **Fonts:** {fonts_preview}\n")

        f.write("\n")

    def _write_sitemap(self, f, report: Report) -> None:
        """Write sitemap section showing page hierarchy."""
        f.write("## Sitemap\n\n")
        f.write("```\n")
        sitemap_tree = self._generate_sitemap_tree(report.sitemap, report.start_url)
        f.write(sitemap_tree)
        f.write("```\n\n")

    def _write_pages_section(self, f, report: Report) -> None:
        """Write detailed sections for each page."""
        f.write("## Pages\n\n")

        for i, page in enumerate(report.pages, 1):
            self._write_page_section(f, page, i)

    def _write_page_section(self, f, page: PageResult, index: int) -> None:
        """
        Write detailed section for a single page.

        Includes screenshot, purpose, components, layout, design,
        interactions, and extracted styles.

        Args:
            f: File handle
            page: PageResult to document
            index: Page number for section heading
        """
        # Section heading
        if page.initial_capture:
            title = page.initial_capture.title or 'Untitled Page'
        else:
            title = 'Untitled Page'

        f.write(f"### {index}. {title}\n\n")
        f.write(f"**URL:** {page.url}  \n")

        if page.analysis:
            f.write(f"**Type:** {page.analysis.page_type}  \n")

        f.write(f"**Depth:** {page.depth}  \n")

        if page.discovered_from:
            f.write(f"**Discovered from:** {page.discovered_from}  \n")

        f.write("\n")

        # Screenshot
        if page.initial_capture and page.initial_capture.screenshot_path:
            self._write_screenshot_embed(f, page.initial_capture.screenshot_path)

        # Analysis sections
        if page.analysis:
            self._write_page_analysis(f, page.analysis)

        # Interactions
        if page.interactions:
            self._write_interactions_section(f, page.interactions)

        # Styles
        if page.initial_capture and page.initial_capture.computed_styles:
            self._write_styles_section(f, page.initial_capture.computed_styles)

        # Outgoing links
        if page.outgoing_links:
            f.write("#### Outgoing Links\n\n")
            f.write(f"Discovered {len(page.outgoing_links)} links on this page.\n\n")

        f.write("---\n\n")

    def _write_screenshot_embed(self, f, screenshot_path: Path) -> None:
        """Embed screenshot with relative path."""
        try:
            # Calculate relative path from report.md to screenshot
            rel_path = screenshot_path.relative_to(self.output_dir)
            f.write(f"![Screenshot]({rel_path})\n\n")
        except ValueError:
            # If screenshot is not under output_dir, try to copy it
            logger.warning(f"Screenshot not in output directory: {screenshot_path}")
            f.write(f"*Screenshot not available*\n\n")

    def _write_page_analysis(self, f, analysis: AnalysisResult) -> None:
        """Write LLM analysis sections."""
        # Purpose
        f.write("#### Purpose\n\n")
        f.write(f"{analysis.page_purpose}\n\n")

        # Components
        if analysis.components_identified:
            f.write("#### Components\n\n")
            for comp in analysis.components_identified:
                name = comp.get('name', 'Unknown')
                description = comp.get('description', '')
                location = comp.get('location', '')
                f.write(f"- **{name}**")
                if location:
                    f.write(f" ({location})")
                if description:
                    f.write(f": {description}")
                f.write("\n")
            f.write("\n")

        # Layout
        if analysis.layout_pattern:
            f.write("#### Layout\n\n")
            f.write(f"{analysis.layout_pattern}\n\n")

        # Design
        if analysis.design_description:
            f.write("#### Design\n\n")
            f.write(f"{analysis.design_description}\n\n")

        # UI Patterns
        if analysis.ui_patterns:
            f.write("#### UI Patterns\n\n")
            for pattern in analysis.ui_patterns:
                f.write(f"- {pattern}\n")
            f.write("\n")

        # Framework hints
        if analysis.framework_hints:
            f.write("#### Framework Hints\n\n")
            f.write(f"{', '.join(analysis.framework_hints)}\n\n")

        # Color palette
        if analysis.color_palette_description:
            f.write("#### Color Palette\n\n")
            f.write(f"{analysis.color_palette_description}\n\n")

    def _write_interactions_section(self, f, interactions: List) -> None:
        """Write interactions explored on the page."""
        f.write("#### Interactions Explored\n\n")

        for i, interaction in enumerate(interactions, 1):
            text = interaction.element.text_content[:50]
            if len(interaction.element.text_content) > 50:
                text += "..."

            summary = f'Clicked "{text}"'

            if interaction.modal_opened:
                summary += " → Modal opened"
            elif interaction.url_changed:
                summary += f" → Navigated to {interaction.new_url}"
            elif interaction.dom_changed:
                summary += f" → {interaction.dom_diff_summary}"
            else:
                summary += " → No visible changes"

            if not interaction.success:
                summary += f" (Failed: {interaction.error_message})"

            f.write(f"{i}. {summary}\n")

        f.write("\n")

    def _write_styles_section(self, f, computed_styles: Dict) -> None:
        """Write extracted styles section."""
        f.write("#### Styles\n\n")

        if 'background_color' in computed_styles:
            f.write(f"- **Background:** {computed_styles['background_color']}\n")

        if 'colors' in computed_styles and computed_styles['colors']:
            colors = computed_styles['colors'][:10]  # Limit to first 10
            f.write(f"- **Colors:** {', '.join(colors)}\n")

        if 'fonts' in computed_styles and computed_styles['fonts']:
            fonts = computed_styles['fonts'][:5]  # Limit to first 5
            f.write(f"- **Fonts:** {', '.join(fonts)}\n")

        f.write("\n")

    def _write_technical_summary(self, f, report: Report) -> None:
        """Write aggregated technical summary."""
        f.write("## Technical Summary\n\n")

        # Frameworks
        if report.common_frameworks:
            f.write(f"**Frameworks:** {', '.join(report.common_frameworks)}\n\n")

        # UI Patterns (aggregate from all pages)
        all_patterns = self._aggregate_ui_patterns(report.pages)
        if all_patterns:
            f.write("**UI Patterns:**\n")
            for pattern in sorted(all_patterns):
                f.write(f"- {pattern}\n")
            f.write("\n")

        # Color Palette
        if report.global_color_palette:
            f.write("**Color Palette:**\n")
            for color in report.global_color_palette[:20]:  # Limit to 20
                f.write(f"- {color}\n")
            f.write("\n")

        # Typography
        if report.global_fonts:
            f.write("**Typography:**\n")
            for font in report.global_fonts[:10]:  # Limit to 10
                f.write(f"- {font}\n")
            f.write("\n")

        # Page types breakdown
        page_types = self._count_page_types(report.pages)
        if page_types:
            f.write("**Page Type Distribution:**\n")
            for page_type, count in sorted(page_types.items(), key=lambda x: x[1], reverse=True):
                f.write(f"- {page_type}: {count}\n")
            f.write("\n")

    def _generate_sitemap_tree(
        self,
        sitemap: Dict[str, List[str]],
        root: str,
        indent: int = 0,
        visited: Set[str] = None
    ) -> str:
        """
        Generate ASCII tree of sitemap.

        Args:
            sitemap: URL to children mapping
            root: Current node URL
            indent: Current indentation level
            visited: Set of visited URLs to prevent cycles

        Returns:
            ASCII tree string
        """
        if visited is None:
            visited = set()

        # Prevent infinite loops
        if root in visited:
            return ""

        visited.add(root)

        tree = ""
        prefix = "  " * indent

        if indent == 0:
            # Root node
            tree += f"{self._shorten_url(root)} (Root)\n"
            indent += 1
            prefix = "  " * indent

        children = sitemap.get(root, [])

        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            branch = "└── " if is_last else "├── "

            tree += f"{prefix}{branch}{self._shorten_url(child)}\n"

            # Recurse for children
            if child in sitemap and child not in visited:
                child_indent = indent + 1
                child_tree = self._generate_sitemap_tree(
                    sitemap,
                    child,
                    child_indent,
                    visited
                )
                tree += child_tree

        return tree

    def _shorten_url(self, url: str) -> str:
        """
        Shorten URL for display in sitemap.

        Shows path only for same-domain URLs.

        Args:
            url: Full URL

        Returns:
            Shortened URL (path only or full URL)
        """
        parsed = urlparse(url)
        if parsed.path:
            # Return path (and query if present)
            result = parsed.path
            if parsed.query:
                result += f"?{parsed.query}"
            return result
        return url

    def _extract_site_name(self, url: str) -> str:
        """
        Extract site name from URL.

        Args:
            url: Full URL

        Returns:
            Site name (title-cased domain)
        """
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        # Take first part of domain (before first dot)
        name = domain.split('.')[0]
        return name.title()

    def _format_duration(self, start, end) -> str:
        """
        Format duration between two datetimes.

        Args:
            start: Start datetime
            end: End datetime

        Returns:
            Formatted duration string (e.g., "2m 34s")
        """
        delta = end - start
        total_seconds = int(delta.total_seconds())

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")

        return " ".join(parts)

    def _aggregate_ui_patterns(self, pages: List[PageResult]) -> Set[str]:
        """
        Aggregate all UI patterns from all pages.

        Args:
            pages: List of PageResult objects

        Returns:
            Set of unique UI pattern names
        """
        patterns = set()
        for page in pages:
            if page.analysis and page.analysis.ui_patterns:
                patterns.update(page.analysis.ui_patterns)
        return patterns

    def _count_page_types(self, pages: List[PageResult]) -> Dict[str, int]:
        """
        Count occurrences of each page type.

        Args:
            pages: List of PageResult objects

        Returns:
            Dictionary mapping page type to count
        """
        counts = {}
        for page in pages:
            if page.analysis:
                page_type = page.analysis.page_type
                counts[page_type] = counts.get(page_type, 0) + 1
        return counts

    def copy_screenshots(self, pages: List[PageResult]) -> None:
        """
        Copy screenshots to report output directory.

        Ensures all screenshots are in the output directory's
        screenshots subdirectory with relative paths that work
        in the generated Markdown report.

        Args:
            pages: List of PageResult objects with screenshot paths
        """
        screenshots_dir = self.output_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Copying screenshots to {screenshots_dir}")

        for page in pages:
            if page.initial_capture and page.initial_capture.screenshot_path:
                src = page.initial_capture.screenshot_path

                if src.exists():
                    # Copy to screenshots directory with same filename
                    dst = screenshots_dir / src.name

                    if src != dst:
                        shutil.copy2(src, dst)
                        # Update the path in the capture data
                        page.initial_capture.screenshot_path = dst

                    # Also copy full screenshot if present
                    if page.initial_capture.screenshot_full_path:
                        full_src = page.initial_capture.screenshot_full_path
                        if full_src.exists():
                            full_dst = screenshots_dir / full_src.name
                            if full_src != full_dst:
                                shutil.copy2(full_src, full_dst)
                                page.initial_capture.screenshot_full_path = full_dst

            # Copy interaction screenshots
            for interaction in page.interactions:
                if interaction.screenshot_path and interaction.screenshot_path.exists():
                    src = interaction.screenshot_path
                    dst = screenshots_dir / src.name
                    if src != dst:
                        shutil.copy2(src, dst)
                        interaction.screenshot_path = dst

        logger.info("Screenshot copying complete")

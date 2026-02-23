"""Unit tests for webscope/reporter.py"""

import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from webscope.models import (
    CrawlConfig,
    CaptureData,
    PageResult,
    Report,
    AnalysisResult,
    InteractionResult,
    ElementInfo
)
from webscope.reporter import Reporter


class TestReporter:
    """Test Reporter class."""

    @pytest.fixture
    def reporter(self, tmp_path):
        """Create Reporter instance."""
        return Reporter(tmp_path)

    @pytest.fixture
    def sample_report(self, tmp_path):
        """Create a sample report for testing."""
        config = CrawlConfig(
            start_url="https://example.com",
            output_dir=tmp_path
        )

        # Create sample capture
        screenshot_path = tmp_path / "screenshots" / "page1.png"
        screenshot_path.parent.mkdir(exist_ok=True)
        screenshot_path.write_text("fake screenshot")

        capture = CaptureData(
            url="https://example.com",
            timestamp=datetime.now(),
            screenshot_path=screenshot_path,
            dom_snapshot="<html><body>Test</body></html>",
            title="Test Page",
            meta_description="A test page",
            computed_styles={
                "colors": ["#FFFFFF", "#000000", "#0066CC"],
                "fonts": ["Arial", "Helvetica"],
                "background_color": "#FFFFFF"
            }
        )

        analysis = AnalysisResult(
            url="https://example.com",
            page_purpose="This is a test landing page",
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

        page = PageResult(
            url="https://example.com",
            depth=0,
            initial_capture=capture,
            outgoing_links=["https://example.com/about"],
            analysis=analysis
        )

        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=30)

        return Report(
            config=config,
            start_url="https://example.com",
            crawl_started=start_time,
            crawl_finished=end_time,
            pages=[page],
            total_pages_crawled=1,
            total_interactions=0,
            sitemap={"https://example.com": ["https://example.com/about"]},
            global_color_palette=["#FFFFFF", "#000000", "#0066CC"],
            global_fonts=["Arial", "Helvetica"],
            common_frameworks=["React", "Tailwind CSS"],
            output_dir=tmp_path
        )

    def test_initialization(self, tmp_path):
        """Test Reporter initialization."""
        reporter = Reporter(tmp_path)

        assert reporter.output_dir == tmp_path
        assert tmp_path.exists()

    def test_generate_report(self, reporter, sample_report):
        """Test report generation."""
        report_path = reporter.generate_report(sample_report)

        assert report_path.exists()
        assert report_path.name == "report.md"

        # Read and verify content
        content = report_path.read_text()
        assert "# Example - Web App Analysis" in content
        assert "https://example.com" in content
        assert "Pages analyzed:** 1" in content

    def test_report_contains_overview(self, reporter, sample_report):
        """Test that report contains overview section."""
        report_path = reporter.generate_report(sample_report)
        content = report_path.read_text()

        assert "## Overview" in content
        assert "Total pages:** 1" in content
        assert "Frameworks detected:** React, Tailwind CSS" in content

    def test_report_contains_sitemap(self, reporter, sample_report):
        """Test that report contains sitemap."""
        report_path = reporter.generate_report(sample_report)
        content = report_path.read_text()

        assert "## Sitemap" in content
        assert "/about" in content

    def test_report_contains_pages(self, reporter, sample_report):
        """Test that report contains page sections."""
        report_path = reporter.generate_report(sample_report)
        content = report_path.read_text()

        assert "## Pages" in content
        assert "Test Page" in content
        assert "Type:** landing" in content

    def test_report_contains_analysis(self, reporter, sample_report):
        """Test that report contains LLM analysis."""
        report_path = reporter.generate_report(sample_report)
        content = report_path.read_text()

        assert "#### Purpose" in content
        assert "This is a test landing page" in content
        assert "#### Components" in content
        assert "Header" in content
        assert "Navigation bar" in content

    def test_report_contains_technical_summary(self, reporter, sample_report):
        """Test that report contains technical summary."""
        report_path = reporter.generate_report(sample_report)
        content = report_path.read_text()

        assert "## Technical Summary" in content
        assert "React, Tailwind CSS" in content

    def test_shorten_url(self, reporter):
        """Test URL shortening helper."""
        url = "https://example.com/path/to/page"
        result = reporter._shorten_url(url)
        assert result == "/path/to/page"

    def test_shorten_url_with_query(self, reporter):
        """Test URL shortening with query params."""
        url = "https://example.com/page?key=value"
        result = reporter._shorten_url(url)
        assert result == "/page?key=value"

    def test_shorten_url_root(self, reporter):
        """Test URL shortening for root."""
        url = "https://example.com/"
        result = reporter._shorten_url(url)
        assert result == "/"

    def test_extract_site_name(self, reporter):
        """Test site name extraction."""
        url = "https://example.com"
        result = reporter._extract_site_name(url)
        assert result == "Example"

    def test_extract_site_name_with_www(self, reporter):
        """Test site name extraction with www."""
        url = "https://www.example.com"
        result = reporter._extract_site_name(url)
        assert result == "Example"

    def test_extract_site_name_subdomain(self, reporter):
        """Test site name extraction with subdomain."""
        url = "https://blog.example.com"
        result = reporter._extract_site_name(url)
        assert result == "Blog"

    def test_format_duration_seconds(self, reporter):
        """Test duration formatting for seconds."""
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = datetime(2026, 1, 1, 10, 0, 45)
        result = reporter._format_duration(start, end)
        assert result == "45s"

    def test_format_duration_minutes(self, reporter):
        """Test duration formatting for minutes."""
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = datetime(2026, 1, 1, 10, 2, 30)
        result = reporter._format_duration(start, end)
        assert result == "2m 30s"

    def test_format_duration_hours(self, reporter):
        """Test duration formatting for hours."""
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = datetime(2026, 1, 1, 11, 15, 45)
        result = reporter._format_duration(start, end)
        assert result == "1h 15m 45s"

    def test_format_duration_zero(self, reporter):
        """Test duration formatting for zero duration."""
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = datetime(2026, 1, 1, 10, 0, 0)
        result = reporter._format_duration(start, end)
        assert result == "0s"

    def test_aggregate_ui_patterns(self, reporter, tmp_path):
        """Test UI pattern aggregation."""
        # Create pages with different patterns
        analysis1 = AnalysisResult(
            url="https://example.com/page1",
            page_purpose="Test",
            page_type="landing",
            ui_patterns=["Card grid", "Sticky header"]
        )

        analysis2 = AnalysisResult(
            url="https://example.com/page2",
            page_purpose="Test",
            page_type="listing",
            ui_patterns=["Card grid", "Infinite scroll"]
        )

        page1 = PageResult(url="https://example.com/page1", depth=0, analysis=analysis1)
        page2 = PageResult(url="https://example.com/page2", depth=0, analysis=analysis2)

        patterns = reporter._aggregate_ui_patterns([page1, page2])

        assert "Card grid" in patterns
        assert "Sticky header" in patterns
        assert "Infinite scroll" in patterns
        assert len(patterns) == 3  # Deduplicated

    def test_count_page_types(self, reporter):
        """Test page type counting."""
        analysis1 = AnalysisResult(
            url="https://example.com/1",
            page_purpose="Test",
            page_type="landing"
        )

        analysis2 = AnalysisResult(
            url="https://example.com/2",
            page_purpose="Test",
            page_type="landing"
        )

        analysis3 = AnalysisResult(
            url="https://example.com/3",
            page_purpose="Test",
            page_type="listing"
        )

        page1 = PageResult(url="https://example.com/1", depth=0, analysis=analysis1)
        page2 = PageResult(url="https://example.com/2", depth=0, analysis=analysis2)
        page3 = PageResult(url="https://example.com/3", depth=0, analysis=analysis3)

        counts = reporter._count_page_types([page1, page2, page3])

        assert counts["landing"] == 2
        assert counts["listing"] == 1

    def test_copy_screenshots(self, reporter, tmp_path):
        """Test screenshot copying."""
        # Create source screenshots
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        screenshot1 = src_dir / "page1.png"
        screenshot1.write_text("screenshot 1")

        # Create page with screenshot
        capture = CaptureData(
            url="https://example.com",
            timestamp=datetime.now(),
            screenshot_path=screenshot1,
            dom_snapshot="<html></html>"
        )

        page = PageResult(
            url="https://example.com",
            depth=0,
            initial_capture=capture
        )

        reporter.copy_screenshots([page])

        # Check screenshot was copied
        dest_dir = reporter.output_dir / "screenshots"
        dest_screenshot = dest_dir / "page1.png"

        assert dest_screenshot.exists()
        assert dest_screenshot.read_text() == "screenshot 1"

        # Check path was updated
        assert page.initial_capture.screenshot_path == dest_screenshot

    def test_copy_screenshots_with_interactions(self, reporter, tmp_path):
        """Test copying interaction screenshots."""
        # Create screenshots
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        screenshot1 = src_dir / "interaction1.png"
        screenshot1.write_text("interaction screenshot")

        # Create interaction with screenshot
        element = ElementInfo(selector="#btn", tag="button", text_content="Click")
        interaction = InteractionResult(
            element=element,
            action_type="click",
            timestamp=datetime.now(),
            screenshot_path=screenshot1
        )

        capture = CaptureData(
            url="https://example.com",
            timestamp=datetime.now(),
            screenshot_path=tmp_path / "main.png",
            dom_snapshot="<html></html>"
        )

        page = PageResult(
            url="https://example.com",
            depth=0,
            initial_capture=capture,
            interactions=[interaction]
        )

        reporter.copy_screenshots([page])

        # Check interaction screenshot was copied
        dest_dir = reporter.output_dir / "screenshots"
        dest_screenshot = dest_dir / "interaction1.png"

        assert dest_screenshot.exists()

    def test_generate_sitemap_tree(self, reporter):
        """Test sitemap tree generation."""
        sitemap = {
            "https://example.com": [
                "https://example.com/about",
                "https://example.com/contact"
            ],
            "https://example.com/about": [
                "https://example.com/about/team"
            ]
        }

        tree = reporter._generate_sitemap_tree(
            sitemap,
            "https://example.com"
        )

        assert "/" in tree  # Root
        assert "/about" in tree
        assert "/contact" in tree
        assert "/about/team" in tree
        assert "├──" in tree or "└──" in tree  # Tree structure

    def test_generate_sitemap_tree_prevents_cycles(self, reporter):
        """Test sitemap tree handles cycles."""
        # Create circular reference
        sitemap = {
            "https://example.com/a": ["https://example.com/b"],
            "https://example.com/b": ["https://example.com/a"]  # Cycle
        }

        tree = reporter._generate_sitemap_tree(
            sitemap,
            "https://example.com/a"
        )

        # Should not infinite loop
        assert "/a" in tree
        assert "/b" in tree

    def test_report_with_interactions(self, reporter, tmp_path):
        """Test report generation with interactions."""
        element = ElementInfo(selector="#btn", tag="button", text_content="Click Me")
        interaction = InteractionResult(
            element=element,
            action_type="click",
            timestamp=datetime.now(),
            modal_opened=True,
            dom_changed=True,
            dom_diff_summary="Modal appeared"
        )

        capture = CaptureData(
            url="https://example.com",
            timestamp=datetime.now(),
            screenshot_path=tmp_path / "screenshot.png",
            dom_snapshot="<html></html>"
        )

        page = PageResult(
            url="https://example.com",
            depth=0,
            initial_capture=capture,
            interactions=[interaction]
        )

        config = CrawlConfig(
            start_url="https://example.com",
            output_dir=tmp_path
        )

        report = Report(
            config=config,
            start_url="https://example.com",
            crawl_started=datetime.now(),
            crawl_finished=datetime.now(),
            pages=[page],
            total_pages_crawled=1,
            total_interactions=1,
            output_dir=tmp_path
        )

        report_path = reporter.generate_report(report)
        content = report_path.read_text()

        assert "#### Interactions Explored" in content
        assert "Click Me" in content
        assert "Modal opened" in content

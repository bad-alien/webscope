"""Unit tests for webscope/models.py"""

from datetime import datetime
from pathlib import Path

import pytest

from webscope.models import (
    CrawlConfig,
    ElementInfo,
    InteractionResult,
    CaptureData,
    AnalysisResult,
    PageResult,
    Report
)


class TestCrawlConfig:
    """Test CrawlConfig dataclass."""

    def test_minimal_config(self, tmp_path):
        """Test creating config with minimal required fields."""
        config = CrawlConfig(
            start_url="https://example.com",
            output_dir=tmp_path
        )

        assert config.start_url == "https://example.com"
        assert config.output_dir == tmp_path
        # Check defaults
        assert config.max_depth == 3
        assert config.max_pages == 20
        assert config.headless is True

    def test_full_config(self, tmp_path):
        """Test creating config with all fields."""
        config = CrawlConfig(
            start_url="https://example.com",
            output_dir=tmp_path,
            max_depth=5,
            max_pages=50,
            headless=False,
            viewport_width=1366,
            viewport_height=768,
            delay_min=1.0,
            delay_max=3.0,
            mouse_speed=0.5,
            scroll_pause_min=0.5,
            scroll_pause_max=1.5,
            respect_robots=False,
            same_domain_only=False,
            interaction_depth=3,
            enable_ai=False,
            anthropic_api_key="test-key",
            model="claude-sonnet-4",
            verbose=True,
            log_file=tmp_path / "test.log"
        )

        assert config.max_depth == 5
        assert config.max_pages == 50
        assert config.headless is False
        assert config.viewport_width == 1366
        assert config.delay_min == 1.0
        assert config.delay_max == 3.0
        assert config.mouse_speed == 0.5
        assert config.respect_robots is False
        assert config.same_domain_only is False
        assert config.interaction_depth == 3
        assert config.enable_ai is False
        assert config.anthropic_api_key == "test-key"
        assert config.model == "claude-sonnet-4"
        assert config.verbose is True

    def test_default_values(self, tmp_path):
        """Test all default values are set correctly."""
        config = CrawlConfig(
            start_url="https://example.com",
            output_dir=tmp_path
        )

        assert config.max_depth == 3
        assert config.max_pages == 20
        assert config.headless is True
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert config.delay_min == 0.5
        assert config.delay_max == 2.0
        assert config.mouse_speed == 1.0
        assert config.scroll_pause_min == 0.3
        assert config.scroll_pause_max == 1.2
        assert config.respect_robots is True
        assert config.same_domain_only is True
        assert config.interaction_depth == 2
        assert config.enable_ai is True
        assert config.anthropic_api_key is None
        assert config.model == "claude-opus-4"
        assert config.verbose is False
        assert config.log_file is None


class TestElementInfo:
    """Test ElementInfo dataclass."""

    def test_minimal_element_info(self):
        """Test creating ElementInfo with minimal fields."""
        element = ElementInfo(
            selector="#button",
            tag="button",
            text_content="Click me"
        )

        assert element.selector == "#button"
        assert element.tag == "button"
        assert element.text_content == "Click me"
        assert element.aria_label is None
        assert element.role is None
        assert element.bounding_box == {}
        assert element.parent_context == ""

    def test_full_element_info(self):
        """Test creating ElementInfo with all fields."""
        element = ElementInfo(
            selector="#submit-btn",
            tag="button",
            text_content="Submit Form",
            aria_label="Submit the form",
            role="button",
            bounding_box={"x": 100, "y": 200, "width": 120, "height": 40},
            parent_context="form#contact-form"
        )

        assert element.selector == "#submit-btn"
        assert element.aria_label == "Submit the form"
        assert element.role == "button"
        assert element.bounding_box["x"] == 100
        assert element.parent_context == "form#contact-form"


class TestInteractionResult:
    """Test InteractionResult dataclass."""

    def test_interaction_result_defaults(self, sample_element_info):
        """Test InteractionResult with default values."""
        timestamp = datetime.now()
        result = InteractionResult(
            element=sample_element_info,
            action_type="click",
            timestamp=timestamp
        )

        assert result.element == sample_element_info
        assert result.action_type == "click"
        assert result.timestamp == timestamp
        assert result.modal_opened is False
        assert result.modal_selector is None
        assert result.url_changed is False
        assert result.new_url is None
        assert result.dom_changed is False
        assert result.dom_diff_summary == ""
        assert result.screenshot_path is None
        assert result.success is True
        assert result.error_message is None

    def test_interaction_result_with_changes(self, sample_element_info, tmp_path):
        """Test InteractionResult with detected changes."""
        screenshot_path = tmp_path / "interaction.png"
        result = InteractionResult(
            element=sample_element_info,
            action_type="click",
            timestamp=datetime.now(),
            modal_opened=True,
            modal_selector='[role="dialog"]',
            url_changed=False,
            dom_changed=True,
            dom_diff_summary="Modal content added",
            screenshot_path=screenshot_path
        )

        assert result.modal_opened is True
        assert result.modal_selector == '[role="dialog"]'
        assert result.dom_changed is True
        assert result.dom_diff_summary == "Modal content added"
        assert result.screenshot_path == screenshot_path

    def test_failed_interaction(self, sample_element_info):
        """Test InteractionResult for failed interaction."""
        result = InteractionResult(
            element=sample_element_info,
            action_type="click",
            timestamp=datetime.now(),
            success=False,
            error_message="Element not clickable"
        )

        assert result.success is False
        assert result.error_message == "Element not clickable"


class TestCaptureData:
    """Test CaptureData dataclass."""

    def test_minimal_capture_data(self, tmp_path):
        """Test CaptureData with minimal fields."""
        screenshot_path = tmp_path / "screenshot.png"
        timestamp = datetime.now()

        capture = CaptureData(
            url="https://example.com",
            timestamp=timestamp,
            screenshot_path=screenshot_path,
            dom_snapshot="<html></html>"
        )

        assert capture.url == "https://example.com"
        assert capture.timestamp == timestamp
        assert capture.screenshot_path == screenshot_path
        assert capture.dom_snapshot == "<html></html>"
        assert capture.screenshot_full_path is None
        assert capture.title == ""
        assert capture.meta_description == ""
        assert capture.computed_styles == {}
        assert capture.network_requests == []
        assert capture.interactive_elements == []

    def test_full_capture_data(self, tmp_path, sample_element_info):
        """Test CaptureData with all fields populated."""
        screenshot_path = tmp_path / "screenshot.png"
        full_screenshot = tmp_path / "full_screenshot.png"

        capture = CaptureData(
            url="https://example.com",
            timestamp=datetime.now(),
            screenshot_path=screenshot_path,
            dom_snapshot="<html><body>Test</body></html>",
            screenshot_full_path=full_screenshot,
            title="Test Page",
            meta_description="A test page",
            computed_styles={
                "colors": ["#FFFFFF", "#000000"],
                "fonts": ["Arial"],
                "background_color": "#FFFFFF"
            },
            network_requests=[
                {"url": "https://api.example.com/data", "method": "GET", "status": "200", "type": "xhr"}
            ],
            interactive_elements=[sample_element_info]
        )

        assert capture.title == "Test Page"
        assert capture.meta_description == "A test page"
        assert len(capture.computed_styles["colors"]) == 2
        assert len(capture.network_requests) == 1
        assert len(capture.interactive_elements) == 1


class TestAnalysisResult:
    """Test AnalysisResult dataclass."""

    def test_minimal_analysis_result(self):
        """Test AnalysisResult with minimal fields."""
        analysis = AnalysisResult(
            url="https://example.com",
            page_purpose="Test landing page",
            page_type="landing"
        )

        assert analysis.url == "https://example.com"
        assert analysis.page_purpose == "Test landing page"
        assert analysis.page_type == "landing"
        assert analysis.components_identified == []
        assert analysis.layout_pattern == ""
        assert analysis.ui_patterns == []
        assert analysis.framework_hints == []
        assert analysis.design_description == ""
        assert analysis.color_palette_description == ""

    def test_full_analysis_result(self):
        """Test AnalysisResult with all fields."""
        analysis = AnalysisResult(
            url="https://example.com",
            page_purpose="E-commerce product listing",
            page_type="listing",
            components_identified=[
                {"name": "Header", "description": "Nav bar", "location": "top"},
                {"name": "Product Grid", "description": "3-col grid", "location": "main"}
            ],
            layout_pattern="Grid layout with sidebar",
            ui_patterns=["Infinite scroll", "Card pattern"],
            framework_hints=["React", "Next.js", "Tailwind"],
            design_description="Modern, minimal design",
            color_palette_description="Blue primary with neutral grays"
        )

        assert analysis.page_type == "listing"
        assert len(analysis.components_identified) == 2
        assert len(analysis.ui_patterns) == 2
        assert len(analysis.framework_hints) == 3

    def test_page_type_values(self):
        """Test valid page_type values."""
        valid_types = ["landing", "listing", "detail", "form", "dashboard", "auth", "other"]

        for page_type in valid_types:
            analysis = AnalysisResult(
                url="https://example.com",
                page_purpose="Test",
                page_type=page_type
            )
            assert analysis.page_type == page_type


class TestPageResult:
    """Test PageResult dataclass."""

    def test_minimal_page_result(self):
        """Test PageResult with minimal fields."""
        page = PageResult(
            url="https://example.com",
            depth=0
        )

        assert page.url == "https://example.com"
        assert page.depth == 0
        assert page.discovered_from is None
        assert page.initial_capture is None
        assert page.interactions == []
        assert page.interaction_captures == []
        assert page.outgoing_links == []
        assert page.analysis is None
        assert page.processing_time_seconds == 0.0

    def test_full_page_result(self, sample_capture_data, sample_analysis_result):
        """Test PageResult with all fields."""
        page = PageResult(
            url="https://example.com/about",
            depth=1,
            discovered_from="https://example.com",
            initial_capture=sample_capture_data,
            interactions=[],
            interaction_captures=[],
            outgoing_links=["https://example.com/contact"],
            analysis=sample_analysis_result,
            processing_time_seconds=2.5
        )

        assert page.depth == 1
        assert page.discovered_from == "https://example.com"
        assert page.initial_capture == sample_capture_data
        assert page.analysis == sample_analysis_result
        assert page.processing_time_seconds == 2.5
        assert len(page.outgoing_links) == 1


class TestReport:
    """Test Report dataclass."""

    def test_minimal_report(self, sample_config):
        """Test Report with minimal fields."""
        start_time = datetime.now()
        end_time = datetime.now()

        report = Report(
            config=sample_config,
            start_url="https://example.com",
            crawl_started=start_time,
            crawl_finished=end_time,
            pages=[],
            total_pages_crawled=0,
            total_interactions=0
        )

        assert report.config == sample_config
        assert report.start_url == "https://example.com"
        assert report.crawl_started == start_time
        assert report.crawl_finished == end_time
        assert report.pages == []
        assert report.total_pages_crawled == 0
        assert report.total_interactions == 0
        assert report.sitemap == {}
        assert report.global_color_palette == []
        assert report.global_fonts == []
        assert report.common_frameworks == []
        assert report.markdown_path is None
        assert report.screenshots_dir is None

    def test_full_report(self, sample_config, sample_page_result, tmp_path):
        """Test Report with all fields populated."""
        start_time = datetime.now()
        end_time = datetime.now()
        markdown_path = tmp_path / "report.md"
        screenshots_dir = tmp_path / "screenshots"

        report = Report(
            config=sample_config,
            start_url="https://example.com",
            crawl_started=start_time,
            crawl_finished=end_time,
            pages=[sample_page_result],
            total_pages_crawled=1,
            total_interactions=5,
            sitemap={
                "https://example.com": ["https://example.com/about"]
            },
            global_color_palette=["#FFFFFF", "#000000", "#0066CC"],
            global_fonts=["Arial", "Helvetica"],
            common_frameworks=["React", "Tailwind"],
            output_dir=tmp_path,
            markdown_path=markdown_path,
            screenshots_dir=screenshots_dir
        )

        assert len(report.pages) == 1
        assert report.total_pages_crawled == 1
        assert report.total_interactions == 5
        assert len(report.sitemap) == 1
        assert len(report.global_color_palette) == 3
        assert len(report.global_fonts) == 2
        assert len(report.common_frameworks) == 2
        assert report.output_dir == tmp_path
        assert report.markdown_path == markdown_path
        assert report.screenshots_dir == screenshots_dir

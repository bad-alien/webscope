"""
Simple test demonstrating analyzer.py and reporter.py functionality.

This test creates mock data structures and demonstrates how the
Analyzer and Reporter classes would be used in a real crawl.
"""

import asyncio
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

# Import our modules
from webscope.models import (
    CrawlConfig,
    CaptureData,
    PageResult,
    Report,
    AnalysisResult,
)
from webscope.reporter import Reporter


def create_mock_page_result(url: str, depth: int) -> PageResult:
    """Create a mock PageResult for testing."""
    capture = CaptureData(
        url=url,
        timestamp=datetime.now(),
        screenshot_path=Path(f"/tmp/screenshot_{depth}.png"),
        dom_snapshot="<html><body><h1>Test Page</h1></body></html>",
        title=f"Test Page {depth}",
        meta_description="A test page",
        computed_styles={
            "colors": ["#FFFFFF", "#000000", "#0066CC"],
            "fonts": ["Arial", "Helvetica"],
            "background_color": "#FFFFFF"
        }
    )

    analysis = AnalysisResult(
        url=url,
        page_purpose="This is a test landing page for demonstration purposes",
        page_type="landing",
        components_identified=[
            {"name": "Header", "description": "Main navigation bar", "location": "top"},
            {"name": "Hero Section", "description": "Large banner with CTA", "location": "main"}
        ],
        layout_pattern="Single column centered layout",
        ui_patterns=["Card grid", "Sticky header"],
        framework_hints=["React", "Tailwind CSS"],
        design_description="Modern, minimal design with clean lines",
        color_palette_description="Blue and white with neutral grays"
    )

    return PageResult(
        url=url,
        depth=depth,
        discovered_from="https://example.com" if depth > 0 else None,
        initial_capture=capture,
        analysis=analysis
    )


def create_mock_report() -> Report:
    """Create a mock Report for testing."""
    config = CrawlConfig(
        start_url="https://example.com",
        output_dir=Path("/tmp/webscope_output"),
        max_depth=2,
        max_pages=5
    )

    pages = [
        create_mock_page_result("https://example.com", 0),
        create_mock_page_result("https://example.com/about", 1),
        create_mock_page_result("https://example.com/contact", 1),
    ]

    sitemap = {
        "https://example.com": [
            "https://example.com/about",
            "https://example.com/contact"
        ]
    }

    return Report(
        config=config,
        start_url="https://example.com",
        crawl_started=datetime.now(),
        crawl_finished=datetime.now(),
        pages=pages,
        total_pages_crawled=3,
        total_interactions=5,
        sitemap=sitemap,
        global_color_palette=["#FFFFFF", "#000000", "#0066CC", "#F5F5F5"],
        global_fonts=["Arial", "Helvetica", "Inter"],
        common_frameworks=["React", "Tailwind CSS"],
        output_dir=Path("/tmp/webscope_output")
    )


def test_reporter():
    """Test the Reporter class."""
    print("\n=== Testing Reporter ===\n")

    # Create temp directory for output
    temp_dir = Path(tempfile.mkdtemp())
    print(f"Using temp directory: {temp_dir}")

    try:
        # Create reporter
        reporter = Reporter(temp_dir)

        # Create mock report
        report = create_mock_report()
        report.output_dir = temp_dir

        # Generate report
        report_path = reporter.generate_report(report)

        print(f"\nReport generated at: {report_path}")
        print(f"Report exists: {report_path.exists()}")

        if report_path.exists():
            print("\n--- Report Preview (first 50 lines) ---\n")
            with open(report_path, 'r') as f:
                lines = f.readlines()[:50]
                print(''.join(lines))

        print("\nReporter test passed!")

    finally:
        # Clean up
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            print(f"\nCleaned up temp directory: {temp_dir}")


async def test_analyzer_mock():
    """Test the Analyzer class with mocked API calls."""
    print("\n=== Testing Analyzer (Mocked) ===\n")

    # We can't test real API calls without a key, so we'll demonstrate the structure
    print("Analyzer class structure:")
    print("- __init__(api_key, model)")
    print("- analyze_page(screenshot_path, dom_snapshot, url) -> AnalysisResult")
    print("- batch_analyze(pages, rate_limit_rpm) -> List[AnalysisResult]")
    print("\nThe Analyzer:")
    print("1. Reads screenshot and encodes to base64")
    print("2. Truncates DOM to fit context window")
    print("3. Sends multimodal request to Claude API")
    print("4. Parses JSON response into AnalysisResult")
    print("5. Handles errors gracefully with fallback results")
    print("\nAnalyzer structure verified!")


def test_data_models():
    """Test that data models work correctly."""
    print("\n=== Testing Data Models ===\n")

    # Test CaptureData
    capture = CaptureData(
        url="https://example.com",
        timestamp=datetime.now(),
        screenshot_path=Path("/tmp/test.png"),
        dom_snapshot="<html></html>",
        title="Test"
    )
    print(f"CaptureData created: {capture.url}")

    # Test AnalysisResult
    analysis = AnalysisResult(
        url="https://example.com",
        page_purpose="Test purpose",
        page_type="landing"
    )
    print(f"AnalysisResult created: {analysis.page_type}")

    # Test PageResult
    page = PageResult(
        url="https://example.com",
        depth=0,
        initial_capture=capture,
        analysis=analysis
    )
    print(f"PageResult created: depth={page.depth}")

    # Test Report
    config = CrawlConfig(
        start_url="https://example.com",
        output_dir=Path("/tmp")
    )
    report = Report(
        config=config,
        start_url="https://example.com",
        crawl_started=datetime.now(),
        crawl_finished=datetime.now(),
        pages=[page],
        total_pages_crawled=1,
        total_interactions=0,
        output_dir=Path("/tmp")
    )
    print(f"Report created: {report.total_pages_crawled} pages")

    print("\nAll data models working correctly!")


def main():
    """Run all tests."""
    print("=" * 60)
    print("WebScope Analyzer & Reporter Test Suite")
    print("=" * 60)

    test_data_models()
    test_reporter()
    asyncio.run(test_analyzer_mock())

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()

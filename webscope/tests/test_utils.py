"""Unit tests for webscope/utils.py"""

import logging
from pathlib import Path

import pytest

from webscope.utils import (
    normalize_url,
    is_same_domain,
    sanitize_filename,
    setup_logging,
    ensure_dir
)


class TestNormalizeUrl:
    """Test URL normalization."""

    def test_removes_fragment(self):
        """Test that URL fragments are removed."""
        url = "https://example.com/page#section"
        result = normalize_url(url)
        assert "#section" not in result
        assert result == "https://example.com/page"

    def test_removes_trailing_slash(self):
        """Test trailing slashes are removed from paths."""
        url = "https://example.com/page/"
        result = normalize_url(url)
        assert result == "https://example.com/page"

    def test_keeps_root_slash(self):
        """Test that root path keeps its slash."""
        url = "https://example.com/"
        result = normalize_url(url)
        assert result == "https://example.com/"

    def test_lowercase_scheme_and_domain(self):
        """Test scheme and domain are lowercased."""
        url = "HTTPS://Example.COM/Page"
        result = normalize_url(url)
        assert result == "https://example.com/Page"

    def test_sorts_query_params(self):
        """Test query parameters are sorted alphabetically."""
        url = "https://example.com/page?z=3&a=1&m=2"
        result = normalize_url(url)
        assert "a=1" in result
        assert result.index("a=1") < result.index("m=2") < result.index("z=3")

    def test_removes_default_http_port(self):
        """Test default HTTP port 80 is removed."""
        url = "http://example.com:80/page"
        result = normalize_url(url)
        assert ":80" not in result
        assert result == "http://example.com/page"

    def test_removes_default_https_port(self):
        """Test default HTTPS port 443 is removed."""
        url = "https://example.com:443/page"
        result = normalize_url(url)
        assert ":443" not in result
        assert result == "https://example.com/page"

    def test_keeps_non_default_port(self):
        """Test non-default ports are preserved."""
        url = "https://example.com:8080/page"
        result = normalize_url(url)
        assert ":8080" in result

    def test_complex_url(self):
        """Test normalization of complex URL with multiple features."""
        url = "HTTPS://Example.com:443/Path/?b=2&a=1#fragment"
        result = normalize_url(url)
        assert result == "https://example.com/Path?a=1&b=2"

    def test_url_with_blank_query_values(self):
        """Test URLs with empty query parameter values."""
        url = "https://example.com/page?key1=&key2=value"
        result = normalize_url(url)
        assert "key1=" in result
        assert "key2=value" in result


class TestIsSameDomain:
    """Test domain comparison."""

    def test_same_domain(self):
        """Test two URLs with same domain."""
        url1 = "https://example.com/page1"
        url2 = "https://example.com/page2"
        assert is_same_domain(url1, url2) is True

    def test_different_domains(self):
        """Test two URLs with different domains."""
        url1 = "https://example.com/page"
        url2 = "https://other.com/page"
        assert is_same_domain(url1, url2) is False

    def test_subdomain_different(self):
        """Test that subdomains are considered different."""
        url1 = "https://example.com/page"
        url2 = "https://sub.example.com/page"
        assert is_same_domain(url1, url2) is False

    def test_case_insensitive(self):
        """Test domain comparison is case-insensitive."""
        url1 = "https://Example.COM/page"
        url2 = "https://example.com/page"
        assert is_same_domain(url1, url2) is True

    def test_different_schemes_same_domain(self):
        """Test that scheme differences don't affect domain comparison."""
        url1 = "http://example.com/page"
        url2 = "https://example.com/page"
        assert is_same_domain(url1, url2) is True

    def test_with_ports(self):
        """Test domain comparison with ports."""
        url1 = "https://example.com:8080/page"
        url2 = "https://example.com:9090/page"
        assert is_same_domain(url1, url2) is False


class TestSanitizeFilename:
    """Test filename sanitization."""

    def test_basic_url(self):
        """Test sanitization of basic URL."""
        url = "https://example.com/about"
        result = sanitize_filename(url)
        assert result == "about"

    def test_url_with_multiple_path_segments(self):
        """Test URL with multiple path segments."""
        url = "https://example.com/blog/post/123"
        result = sanitize_filename(url)
        assert result == "blog_post_123"

    def test_removes_special_characters(self):
        """Test special characters are removed."""
        url = "https://example.com/page@#$%"
        result = sanitize_filename(url)
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result
        assert "%" not in result

    def test_keeps_alphanumeric_and_safe_chars(self):
        """Test alphanumeric, underscore, and hyphen are preserved."""
        url = "https://example.com/my-page_123"
        result = sanitize_filename(url)
        assert result == "my-page_123"

    def test_root_url_uses_domain(self):
        """Test root URL uses domain name."""
        url = "https://example.com/"
        result = sanitize_filename(url)
        assert result == "examplecom"

    def test_url_without_path_uses_domain(self):
        """Test URL without path uses domain."""
        url = "https://example.com"
        result = sanitize_filename(url)
        assert result == "examplecom"

    def test_truncates_long_urls(self):
        """Test very long URLs are truncated to 100 characters."""
        long_path = "a" * 150
        url = f"https://example.com/{long_path}"
        result = sanitize_filename(url)
        assert len(result) <= 100

    def test_empty_path_fallback(self):
        """Test fallback for URLs that result in empty filename."""
        url = "https://example.com/@#$%"
        result = sanitize_filename(url)
        assert result  # Should not be empty


class TestSetupLogging:
    """Test logging configuration."""

    def test_setup_logging_default(self):
        """Test default logging setup (INFO level)."""
        setup_logging(verbose=False)
        logger = logging.getLogger()
        assert logger.level == logging.INFO

    def test_setup_logging_verbose(self):
        """Test verbose logging setup (DEBUG level)."""
        setup_logging(verbose=True)
        logger = logging.getLogger()
        assert logger.level == logging.DEBUG

    def test_setup_logging_with_file(self, tmp_path):
        """Test logging setup with log file."""
        log_file = tmp_path / "test.log"
        setup_logging(verbose=False, log_file=log_file)

        # Log a test message
        logger = logging.getLogger()
        logger.info("Test message")

        # Check file was created and contains message
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content

    def test_logging_format(self, tmp_path):
        """Test logging message format."""
        log_file = tmp_path / "test.log"
        setup_logging(verbose=False, log_file=log_file)

        logger = logging.getLogger()
        logger.info("Test message")

        content = log_file.read_text()
        # Should contain timestamp, level, and message
        assert "INFO:" in content
        assert "Test message" in content


class TestEnsureDir:
    """Test directory creation."""

    def test_creates_directory(self, tmp_path):
        """Test that directory is created."""
        new_dir = tmp_path / "new_dir"
        assert not new_dir.exists()

        ensure_dir(new_dir)
        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_creates_nested_directories(self, tmp_path):
        """Test creation of nested directories."""
        nested_dir = tmp_path / "level1" / "level2" / "level3"
        assert not nested_dir.exists()

        ensure_dir(nested_dir)
        assert nested_dir.exists()
        assert nested_dir.is_dir()

    def test_does_not_fail_if_exists(self, tmp_path):
        """Test that it doesn't fail if directory already exists."""
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()

        # Should not raise an exception
        ensure_dir(existing_dir)
        assert existing_dir.exists()

    def test_works_with_path_object(self, tmp_path):
        """Test that it works with Path objects."""
        new_dir = tmp_path / "path_test"
        ensure_dir(new_dir)
        assert new_dir.exists()

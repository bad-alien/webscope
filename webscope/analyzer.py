"""LLM-powered page analysis using Claude API.

This module provides AI-powered analysis of web pages, taking screenshots
and DOM context to generate structured descriptions of UI components,
layout patterns, design systems, and technical frameworks.
"""

import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import List, Optional

from anthropic import Anthropic

from .models import AnalysisResult, PageResult


logger = logging.getLogger(__name__)


class Analyzer:
    """
    Uses Claude API to analyze screenshots and generate descriptions.

    Sends screenshots and DOM context to Claude for multimodal analysis,
    receiving back structured insights about page purpose, UI components,
    layout patterns, and technical implementation.
    """

    def __init__(self, api_key: str, model: str = "claude-opus-4"):
        """
        Initialize the analyzer with Claude API credentials.

        Args:
            api_key: Anthropic API key for Claude
            model: Model name to use (default: claude-opus-4)
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model
        logger.info(f"Initialized Analyzer with model: {model}")

    async def analyze_page(
        self,
        screenshot_path: Path,
        dom_snapshot: str,
        url: str
    ) -> AnalysisResult:
        """
        Analyze a single page using multimodal LLM.

        Sends screenshot and DOM structure to Claude for analysis,
        requesting structured insights about the page's purpose,
        components, design, and technical implementation.

        Args:
            screenshot_path: Path to screenshot image file
            dom_snapshot: Simplified HTML structure of the page
            url: Page URL for context

        Returns:
            AnalysisResult with LLM-generated insights

        Raises:
            FileNotFoundError: If screenshot doesn't exist
            ValueError: If API returns invalid JSON
        """
        logger.info(f"Analyzing page: {url}")

        # Read and encode screenshot
        if not screenshot_path.exists():
            raise FileNotFoundError(f"Screenshot not found: {screenshot_path}")

        with open(screenshot_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')

        # Truncate DOM to fit context window
        dom_excerpt = self._truncate_dom(dom_snapshot, max_length=2000)

        # Build analysis prompt
        prompt = self._build_analysis_prompt(url, dom_excerpt)

        try:
            # Call Claude API with image + text
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )

            # Extract and parse JSON response
            response_text = response.content[0].text
            analysis_data = self._parse_analysis_response(response_text)

            # Build AnalysisResult
            result = AnalysisResult(
                url=url,
                page_purpose=analysis_data.get('purpose', 'Unknown purpose'),
                page_type=analysis_data.get('page_type', 'other'),
                components_identified=analysis_data.get('components', []),
                layout_pattern=analysis_data.get('layout_pattern', ''),
                ui_patterns=analysis_data.get('ui_patterns', []),
                framework_hints=analysis_data.get('framework_hints', []),
                design_description=analysis_data.get('design_description', ''),
                color_palette_description=analysis_data.get('color_palette_description', '')
            )

            logger.info(f"Successfully analyzed page: {url} (type: {result.page_type})")
            return result

        except Exception as e:
            logger.error(f"Failed to analyze {url}: {e}")
            # Return minimal result on failure
            return AnalysisResult(
                url=url,
                page_purpose=f"Analysis failed: {str(e)}",
                page_type="other"
            )

    async def batch_analyze(
        self,
        pages: List[PageResult],
        rate_limit_rpm: int = 50
    ) -> List[AnalysisResult]:
        """
        Analyze multiple pages with rate limiting.

        Processes pages sequentially with delays to respect API rate limits.
        Shows progress logging for long-running batch operations.

        Args:
            pages: List of PageResult objects to analyze
            rate_limit_rpm: Requests per minute limit (default: 50)

        Returns:
            List of AnalysisResult objects in same order as input
        """
        delay = 60.0 / rate_limit_rpm
        results = []

        logger.info(f"Starting batch analysis of {len(pages)} pages (rate limit: {rate_limit_rpm} RPM)")

        for i, page in enumerate(pages, 1):
            if page.initial_capture is None:
                logger.warning(f"Skipping page {i}/{len(pages)} - no initial capture: {page.url}")
                # Create a minimal failed result
                results.append(AnalysisResult(
                    url=page.url,
                    page_purpose="No capture data available",
                    page_type="other"
                ))
                continue

            logger.info(f"Analyzing page {i}/{len(pages)}: {page.url}")

            try:
                result = await self.analyze_page(
                    page.initial_capture.screenshot_path,
                    page.initial_capture.dom_snapshot,
                    page.url
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error analyzing page {i}/{len(pages)}: {e}")
                # Add failed result to maintain list alignment
                results.append(AnalysisResult(
                    url=page.url,
                    page_purpose=f"Analysis error: {str(e)}",
                    page_type="other"
                ))

            # Rate limiting delay (skip for last item)
            if i < len(pages):
                await asyncio.sleep(delay)

        logger.info(f"Batch analysis complete: {len(results)} pages processed")
        return results

    def _truncate_dom(self, dom_snapshot: str, max_length: int = 2000) -> str:
        """
        Truncate DOM snapshot to fit in context window.

        Args:
            dom_snapshot: Full DOM HTML
            max_length: Maximum characters to keep

        Returns:
            Truncated DOM with ellipsis if needed
        """
        if len(dom_snapshot) <= max_length:
            return dom_snapshot
        return dom_snapshot[:max_length] + "\n... (truncated)"

    def _build_analysis_prompt(self, url: str, dom_excerpt: str) -> str:
        """
        Build the analysis prompt for Claude.

        Creates a structured prompt asking for specific insights about
        the page's purpose, components, design, and technical stack.

        Args:
            url: Page URL
            dom_excerpt: Truncated DOM structure

        Returns:
            Formatted prompt string
        """
        return f"""Analyze this web page screenshot and structure.

URL: {url}

DOM structure (excerpt):
```html
{dom_excerpt}
```

Please provide a comprehensive analysis:

1. **Purpose**: What is this page for? What problem does it solve for users? (1-2 sentences)
2. **Page type**: Classify as one of: landing | listing | detail | form | dashboard | auth | other
3. **Components**: Identify key UI components visible on the page (navigation, headers, cards, forms, etc.)
4. **Layout**: Describe the overall layout pattern and grid structure
5. **Design**: Describe the visual design style, aesthetic, and approach
6. **Framework hints**: What technologies and frameworks might this be built with? (React, Vue, Tailwind, etc.)
7. **Colors & fonts**: Describe the color palette and typography system observed

Format your response as valid JSON:
{{
  "purpose": "Clear 1-2 sentence description of page purpose",
  "page_type": "landing|listing|detail|form|dashboard|auth|other",
  "components": [
    {{"name": "Component Name", "description": "What it does and how it looks", "location": "top|main|sidebar|footer"}},
    {{"name": "Another Component", "description": "Description", "location": "main"}}
  ],
  "layout_pattern": "Description of layout structure",
  "ui_patterns": ["Pattern 1", "Pattern 2", "Pattern 3"],
  "framework_hints": ["Technology 1", "Technology 2"],
  "design_description": "Overall design style and aesthetic",
  "color_palette_description": "Primary colors, accent colors, backgrounds observed"
}}

Provide only the JSON response, no additional text."""

    def _parse_analysis_response(self, response_text: str) -> dict:
        """
        Parse Claude's JSON response.

        Extracts JSON from response, handling cases where Claude
        includes markdown code blocks or additional text.

        Args:
            response_text: Raw response from Claude

        Returns:
            Parsed JSON as dictionary

        Raises:
            ValueError: If response is not valid JSON
        """
        # Try to extract JSON from markdown code blocks
        if '```json' in response_text:
            # Extract content between ```json and ```
            start = response_text.find('```json') + 7
            end = response_text.find('```', start)
            json_text = response_text[start:end].strip()
        elif '```' in response_text:
            # Extract content between ``` and ```
            start = response_text.find('```') + 3
            end = response_text.find('```', start)
            json_text = response_text[start:end].strip()
        else:
            # Assume entire response is JSON
            json_text = response_text.strip()

        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {response_text}")
            # Return minimal valid structure
            return {
                "purpose": "Failed to parse analysis",
                "page_type": "other",
                "components": [],
                "layout_pattern": "",
                "ui_patterns": [],
                "framework_hints": [],
                "design_description": "",
                "color_palette_description": ""
            }

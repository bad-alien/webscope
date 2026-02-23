"""Interactive element discovery and exploration."""

import logging
from datetime import datetime
from typing import List

from playwright.async_api import Page, ElementHandle

from .models import ElementInfo, InteractionResult, CrawlConfig
from .stealth import HumanBehavior

logger = logging.getLogger(__name__)


class Interactor:
    """
    Discovers and interacts with clickable elements to reveal dynamic content.
    """

    def __init__(self, human: HumanBehavior, config: CrawlConfig):
        self.human = human
        self.config = config

    async def discover_interactive_elements(self, page: Page) -> List[ElementInfo]:
        """
        Find all interactive elements on the page.

        Discovers elements via:
        1. Semantic selectors (button, input, select, role-based)
        2. Elements with cursor:pointer computed style (catches styled divs, spans, etc.)
        3. Elements with click-related classes (cursor-pointer, clickable, etc.)
        4. Anchor tags with href

        Returns:
            List of ElementInfo objects sorted by visual position (top-left first)
        """
        logger.debug("Starting interactive element discovery")

        # Phase 1: Semantic selectors (fast, reliable)
        semantic_selectors = [
            "button",
            "a[href]",
            "a[onclick]",
            'input[type="submit"]',
            'input[type="button"]',
            "select",
            '[role="button"]',
            '[role="tab"]',
            '[role="menuitem"]',
            '[role="link"]',
            "[onclick]",
            "[tabindex]",
        ]

        elements = []
        seen_positions = set()

        for selector in semantic_selectors:
            try:
                handles = await page.query_selector_all(selector)
                logger.debug(f"Found {len(handles)} elements for selector: {selector}")
                for handle in handles:
                    info = await self._handle_to_element_info(handle, seen_positions)
                    if info:
                        elements.append(info)
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue

        # Phase 2: Elements with cursor:pointer computed style
        # This catches divs, spans, and other non-semantic clickable elements
        try:
            pointer_handles = await page.evaluate_handle("""() => {
                const results = [];
                const all = document.querySelectorAll('*');
                for (const el of all) {
                    const style = getComputedStyle(el);
                    if (style.cursor === 'pointer') {
                        // Skip tiny elements, invisible elements, and standard interactive tags
                        const rect = el.getBoundingClientRect();
                        const tag = el.tagName.toLowerCase();
                        const skip = ['a', 'button', 'input', 'select', 'option', 'label'];
                        if (rect.width > 10 && rect.height > 10 && !skip.includes(tag)) {
                            results.push(el);
                        }
                    }
                }
                return results;
            }""")

            # Convert JSHandle array to element handles
            length = await pointer_handles.evaluate("arr => arr.length")
            logger.debug(f"Found {length} cursor:pointer elements")

            for i in range(min(length, 30)):  # Cap at 30 to avoid slowness
                try:
                    handle = await pointer_handles.evaluate_handle(f"arr => arr[{i}]")
                    element_handle = handle.as_element()
                    if element_handle:
                        info = await self._handle_to_element_info(element_handle, seen_positions)
                        if info:
                            elements.append(info)
                except Exception as e:
                    logger.debug(f"Error processing cursor:pointer element {i}: {e}")
                    continue
        except Exception as e:
            logger.debug(f"cursor:pointer discovery failed: {e}")

        # Sort by position (top to bottom, left to right)
        elements.sort(key=lambda e: (
            e.bounding_box.get("y", 0),
            e.bounding_box.get("x", 0),
        ))

        logger.debug(f"Discovered {len(elements)} interactive elements total")
        return elements

    async def _handle_to_element_info(
        self, handle: ElementHandle, seen_positions: set
    ) -> ElementInfo | None:
        """Convert an ElementHandle to ElementInfo, deduplicating by position."""
        try:
            box = await handle.bounding_box()
            if not box or box["width"] < 1 or box["height"] < 1:
                return None

            # Deduplicate by position + size
            position_key = (
                round(box["x"]),
                round(box["y"]),
                round(box["width"]),
                round(box["height"]),
            )
            if position_key in seen_positions:
                return None
            seen_positions.add(position_key)

            text = ""
            try:
                text = (await handle.inner_text()).strip()
            except Exception:
                pass

            aria = await handle.get_attribute("aria-label")
            role = await handle.get_attribute("role")
            tag = await handle.evaluate("el => el.tagName.toLowerCase()")
            elem_selector = await self._generate_selector(handle)

            return ElementInfo(
                selector=elem_selector,
                tag=tag,
                text_content=text[:100],
                aria_label=aria,
                role=role,
                bounding_box=box,
            )
        except Exception as e:
            logger.debug(f"Error converting handle to ElementInfo: {e}")
            return None

    async def explore_interactions(
        self, page: Page, elements: List[ElementInfo], depth: int = 0
    ) -> List[InteractionResult]:
        """
        Interact with elements and detect state changes.

        After each click that causes a DOM change, re-discovers links on the page
        so newly revealed navigation can be crawled.

        Limits to 20 interactions per depth level to avoid infinite loops.
        """
        logger.debug(f"Starting explore_interactions with {len(elements)} elements at depth {depth}")
        results = []

        if depth >= self.config.interaction_depth:
            logger.debug(f"Reached max interaction depth {self.config.interaction_depth}")
            return results

        for i, element in enumerate(elements[:20]):
            logger.debug(f"Interaction {i+1}/{min(len(elements), 20)}: Clicking {element.selector} ({element.text_content[:30]})")
            try:
                # Before state
                dom_before = await page.content()
                url_before = page.url

                # Click with timeout
                try:
                    await self.human.click(element.selector, timeout=5000)
                except Exception as click_error:
                    logger.warning(f"Click failed for {element.selector}: {click_error}")
                    results.append(
                        InteractionResult(
                            element=element,
                            action_type="click",
                            timestamp=datetime.now(),
                            success=False,
                            error_message=f"Click failed: {click_error}",
                        )
                    )
                    continue

                await page.wait_for_timeout(800)  # Wait for animations/transitions

                # After state
                dom_after = await page.content()
                url_after = page.url

                # Detect changes
                modal_opened = await self._detect_modal(page)
                url_changed = url_before != url_after
                dom_changed = dom_before != dom_after

                logger.debug(f"Changes detected - modal: {modal_opened}, url: {url_changed}, dom: {dom_changed}")

                result = InteractionResult(
                    element=element,
                    action_type="click",
                    timestamp=datetime.now(),
                    modal_opened=modal_opened,
                    url_changed=url_changed,
                    new_url=url_after if url_changed else None,
                    dom_changed=dom_changed,
                    dom_diff_summary=(
                        self._summarize_dom_diff(dom_before, dom_after)
                        if dom_changed
                        else ""
                    ),
                )

                results.append(result)

                # Close modal if opened
                if modal_opened:
                    logger.debug("Closing modal")
                    await self._close_modal(page)

                # If URL changed, navigate back
                if url_changed:
                    logger.debug(f"URL changed to {url_after}, navigating back")
                    try:
                        await page.go_back(wait_until="domcontentloaded", timeout=10000)
                        await page.wait_for_timeout(500)
                    except Exception as back_error:
                        logger.warning(f"go_back failed: {back_error}")
                        try:
                            await page.goto(url_before, wait_until="domcontentloaded", timeout=10000)
                        except Exception as goto_error:
                            logger.error(f"Failed to return to original URL: {goto_error}")

            except Exception as e:
                logger.warning(f"Interaction failed for {element.selector}: {e}")
                results.append(
                    InteractionResult(
                        element=element,
                        action_type="click",
                        timestamp=datetime.now(),
                        success=False,
                        error_message=str(e),
                    )
                )

        logger.debug(f"Completed explore_interactions with {len(results)} results")
        return results

    async def discover_new_links(self, page: Page) -> List[str]:
        """
        Discover all <a href> links currently visible on the page.

        Called after interactions to find navigation that was revealed
        by clicking (e.g., hamburger menus, splash screen transitions).

        Returns:
            List of href URLs found on the page
        """
        try:
            links = await page.eval_on_selector_all(
                "a[href]", "elements => elements.map(el => el.href)"
            )
            logger.debug(f"Discovered {len(links)} links after interactions")
            return links
        except Exception as e:
            logger.warning(f"Link discovery after interaction failed: {e}")
            return []

    async def _detect_modal(self, page: Page) -> bool:
        """Check if a modal/dialog appeared."""
        modal_selectors = [
            '[role="dialog"]',
            '[role="alertdialog"]',
            ".modal",
            '[aria-modal="true"]',
        ]

        for selector in modal_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    box = await element.bounding_box()
                    if box:
                        return True
            except Exception:
                continue
        return False

    async def _close_modal(self, page: Page) -> None:
        """Try to close modal (ESC key or close button)."""
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
        except Exception:
            pass

    async def _generate_selector(self, handle: ElementHandle) -> str:
        """Generate reliable CSS selector for element."""
        try:
            elem_id = await handle.get_attribute("id")
            if elem_id:
                return f"#{elem_id}"

            test_id = await handle.get_attribute("data-testid")
            if test_id:
                return f'[data-testid="{test_id}"]'

            name = await handle.get_attribute("name")
            if name:
                tag = await handle.evaluate("el => el.tagName.toLowerCase()")
                return f'{tag}[name="{name}"]'

            classes = await handle.get_attribute("class")
            if classes:
                class_list = classes.strip().split()
                if class_list:
                    tag = await handle.evaluate("el => el.tagName.toLowerCase()")
                    # Use at most 3 classes, prefer short meaningful ones
                    short_classes = [c for c in class_list if len(c) < 30][:3]
                    if short_classes:
                        return f"{tag}.{'.'.join(short_classes)}"

            tag = await handle.evaluate("el => el.tagName.toLowerCase()")
            return tag

        except Exception:
            return "button"

    def _summarize_dom_diff(self, before: str, after: str) -> str:
        """Summarize DOM changes."""
        before_count = before.count("<")
        after_count = after.count("<")
        diff = after_count - before_count

        if diff > 50:
            return f"Large DOM change: +{diff} elements"
        elif diff > 0:
            return f"Small DOM change: +{diff} elements"
        elif diff < -50:
            return f"Large DOM reduction: {diff} elements"
        elif diff < 0:
            return f"Small DOM reduction: {diff} elements"
        else:
            return "Content updated (same element count)"

"""Course scraping utilities for enrolled Qalam courses."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any
from urllib.parse import urljoin

from playwright.async_api import Page
from playwright.async_api import Error as PlaywrightError


CoursePayload = dict[str, Any]


async def _human_delay(min_seconds: float = 0.3, max_seconds: float = 0.9) -> None:
    """Sleep a short randomized interval to mimic user pacing."""
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))


async def extract_courses(page: Page, logger: logging.Logger) -> list[CoursePayload]:
    """Extract all enrolled courses from Qalam dashboard (#hierarchical_show2)."""
    logger.info("Waiting for courses container on dashboard")

    # Wait for the hierarchical courses container to appear
    try:
        await page.wait_for_selector("#hierarchical_show2", timeout=15000, state="visible")
        logger.info("Courses container #hierarchical_show2 found")
    except PlaywrightError:
        logger.warning("Courses container #hierarchical_show2 not found")
        return []

    await _human_delay()

    # Select ALL direct child divs inside the hierarchical container
    # (courses have varying classes: uk-row-first, empty, uk-grid-margin, etc.)
    course_containers = page.locator("#hierarchical_show2 > div")
    container_count = await course_containers.count()
    logger.info(f"Found {container_count} total containers in #hierarchical_show2")

    seen_names: set[str] = set()
    courses: list[CoursePayload] = []

    for index in range(container_count):
        try:
            container = course_containers.nth(index)

            # Skip containers without an <a> tag
            link_elem = container.locator("a").first
            if await link_elem.count() == 0:
                continue  # empty container, skip

            # Extract course URL
            href = await link_elem.get_attribute("href")
            if not href:
                continue
            course_url = urljoin(page.url, href.strip())

            # Extract course name
            name_elem = container.locator(".card-header span").first
            course_name = ""
            if await name_elem.count() > 0:
                course_name = (await name_elem.inner_text()).strip()
            if not course_name or course_name in seen_names:
                continue

            # Extract instructor
            instructor_elem = container.locator(".card-body h6.card-title").first
            instructor = None
            if await instructor_elem.count() > 0:
                text = (await instructor_elem.inner_text()).strip()
                if text:
                    instructor = text

            seen_names.add(course_name)
            courses.append(
                {"name": course_name, "url": course_url, "instructor": instructor}
            )

            logger.info(
                f"Course extracted successfully: '{course_name}' | Instructor: '{instructor or 'Not specified'}' | URL: {course_url}'"
            )

            await _human_delay(0.1, 0.3)

        except PlaywrightError as exc:
            logger.error(f"Failed to extract course at index {index}: {exc}")
            continue
        except Exception as exc:
            logger.exception(f"Unexpected error extracting course at index {index}: {exc}")
            continue

    logger.info(f"Courses extraction complete. Total courses found: {len(courses)}")
    return courses
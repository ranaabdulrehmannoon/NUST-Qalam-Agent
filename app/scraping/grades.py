"""Grade scraping utilities for quizzes and assignments in Qalam/Odoo LMS."""

from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import Any
from urllib.parse import urljoin

from playwright.async_api import Locator, Page
from playwright.async_api import Error as PlaywrightError


GradeItemPayload = dict[str, Any]
GradesPayload = dict[str, list[GradeItemPayload]]


async def _human_delay(min_seconds: float = 0.25, max_seconds: float = 0.8) -> None:
    """Sleep a short randomized interval to mimic user pacing."""
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))


def _parse_connect_selector(data_attr: str | None) -> str | None:
    """Parse the uk-tab connect target selector from data-uk-tab."""
    if not data_attr:
        return None
    match = re.search(r"connect:\s*'([^']+)'", data_attr)
    if match:
        return match.group(1)
    return None


def _parse_percentage(text: str) -> float | None:
    """Extract percentage from text patterns such as 75.00% or 75% or 75.00."""
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    return float(match.group(1))


def _parse_marks_from_fraction(text: str) -> tuple[float | None, float | None]:
    """Extract obtained/total marks from text patterns such as 7.50 / 10.0."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", text)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def _extract_numeric(text: str) -> float | None:
    """Extract the first numeric value from text."""
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    return float(match.group(1))


async def _extract_assessment_items(
    root: Locator | Page, assessment_type: str, logger: logging.Logger, assessment_scope: str
) -> list[GradeItemPayload]:
    """
    Extract assessment items (quizzes/assignments) from Odoo gradebook table.
    
    Finds toggle links for specific assessment type, clicks to expand hidden rows,
    then extracts data ONLY from that specific section.
    """
    try:
        results: list[GradeItemPayload] = []
        seen_titles: set[str] = set()
        
        logger.info(f"Starting {assessment_type} extraction")
        
        # Find all toggle links
        toggle_links = root.locator("a.js-toggle-children-row")
        link_count = await toggle_links.count()
        
        logger.debug(f"Found {link_count} toggle links on page")
        
        for link_idx in range(link_count):
            try:
                link = toggle_links.nth(link_idx)
                link_text = (await link.inner_text()).strip()
                
                logger.info(f"Toggle link {link_idx}: '{link_text}'")
                
                # Strict check: the toggle link text MUST match the assessment type
                if assessment_type.lower() == "quiz":
                    if "quiz" not in link_text.lower() or "assignment" in link_text.lower():
                        logger.debug(f"Skipping '{link_text}' - not a Quiz link")
                        continue
                elif assessment_type.lower() == "assignment":
                    if "assignment" not in link_text.lower():
                        logger.debug(f"Skipping '{link_text}' - not an Assignment link")
                        continue
                else:
                    logger.warning(f"Unknown assessment type: {assessment_type}")
                    continue
                
                logger.debug(f"Processing {assessment_type} section: {link_text}")
                
                # Get the parent <li> element - this scopes all subsequent queries
                # This is critical to avoid cross-contamination between Quiz and Assignment sections
                parent_li = link.locator("xpath=ancestor::li[1]").first
                if await parent_li.count() == 0:
                    logger.warning(f"Could not find parent li for {link_text}")
                    continue
                
                # Click toggle to expand this section ONLY
                await link.click()
                await _human_delay(0.4, 0.7)
                
                # Find the table within THIS specific <li>
                table = parent_li.locator("table").first
                if await table.count() == 0:
                    logger.debug(f"No table found in this section")
                    await link.click()  # collapse before continuing
                    continue
                
                # Get rows ONLY from this specific table (scoped to parent_li)
                tbody = table.locator("tbody").first
                if await tbody.count() == 0:
                    logger.debug(f"No tbody in table")
                    await link.click()
                    continue
                
                rows = tbody.locator("tr")
                row_count = await rows.count()
                logger.debug(f"Found {row_count} rows (skipping header row at index 0)")
                
                # Skip first row (header with th elements), process child data rows
                for row_idx in range(1, row_count):
                    try:
                        row = rows.nth(row_idx)
                        row_class = await row.get_attribute("class") or ""
                        
                        # Only process table-child-row entries
                        if "table-child-row" not in row_class:
                            logger.debug(f"Row {row_idx}: skipping (class={row_class})")
                            continue
                        
                        columns = row.locator("td")
                        col_count = await columns.count()
                        
                        if col_count < 5:
                            logger.debug(f"Row {row_idx}: only {col_count} columns, need >=5")
                            continue
                        
                        # Extract from columns: [0] name, [1] max_mark, [2] obtained_marks, [3] class_avg, [4] percentage
                        assessment_name = (await columns.nth(0).inner_text()).strip()
                        total_mark_text = (await columns.nth(1).inner_text()).strip()
                        obtained_mark_text = (await columns.nth(2).inner_text()).strip()
                        class_avg_text = (await columns.nth(3).inner_text()).strip()
                        percentage_text = (await columns.nth(4).inner_text()).strip()
                        
                        logger.debug(
                            f"Row {row_idx} raw data",
                            extra={
                                "name": assessment_name,
                                "total": total_mark_text,
                                "obtained": obtained_mark_text,
                                "avg": class_avg_text,
                                "pct": percentage_text,
                            }
                        )
                        
                        if not assessment_name:
                            continue
                        
                        # Final filter: ensure assessment name matches type
                        if assessment_type.lower() == "quiz":
                            if not assessment_name.lower().startswith("quiz"):
                                logger.debug(f"Filtering: '{assessment_name}' is not a Quiz")
                                continue
                        elif assessment_type.lower() == "assignment":
                            if not assessment_name.lower().startswith("assignment"):
                                logger.debug(f"Filtering: '{assessment_name}' is not an Assignment")
                                continue
                        
                        if assessment_name in seen_titles:
                            logger.debug(f"Already processed: {assessment_name}")
                            continue
                        
                        seen_titles.add(assessment_name)
                        
                        # Parse values
                        total_mark = _extract_numeric(total_mark_text)
                        obtained_mark = _extract_numeric(obtained_mark_text)
                        class_average = _extract_numeric(class_avg_text)
                        percentage = _parse_percentage(percentage_text)
                        
                        result = {
                            "title": assessment_name,
                            "assessment_type": assessment_scope,
                            "obtained_mark": obtained_mark,
                            "total_mark": total_mark,
                            "class_average": class_average,
                            "percentage": percentage,
                        }
                        
                        results.append(result)
                        logger.info(
                            f"Extracted {assessment_type}: {assessment_name}",
                            extra={
                                "obtained_mark": obtained_mark,
                                "total_mark": total_mark,
                                "class_average": class_average,
                                "percentage": percentage,
                            }
                        )
                        
                    except Exception as exc:
                        logger.debug(f"Error on row {row_idx}: {exc}")
                        continue
                
                # Collapse this section
                await link.click()
                await _human_delay(0.2, 0.4)
                
            except Exception as exc:
                logger.warning(f"Error processing link {link_idx}: {exc}")
                continue
        
        logger.info(f"Extracted {len(results)} {assessment_type} items total")
        return results
        
    except Exception as exc:
        logger.error(f"Failed to extract {assessment_type} items: {exc}")
        return []


async def extract_grades(page: Page, course: dict[str, str], logger: logging.Logger) -> GradesPayload:
    """
    Extract quizzes and assignments for a specific course from Qalam gradebook.
    
    Navigates to the course gradebook URL and extracts:
    - Quizzes with marks and percentages
    - Assignments with marks and percentages
    """
    try:
        # Try to navigate to gradebook page
        # The course URL might be /student/course/info/{id}, convert it to /student/course/gradebook/{id}
        course_url = course["url"]
        
        # Extract course ID from URL (e.g., 2146957)
        course_id_match = re.search(r"/course/(?:info|gradebook)/(\d+)", course_url)
        if course_id_match:
            course_id = course_id_match.group(1)
            gradebook_url = f"/student/course/gradebook/{course_id}"
            # Make absolute URL
            base_url = course_url.split("/student/")[0]
            gradebook_url = urljoin(base_url, gradebook_url)
        else:
            # Fall back to the provided URL
            gradebook_url = course_url
        
        logger.info(f"Navigating to course gradebook: {gradebook_url}")
        await page.goto(gradebook_url, wait_until="domcontentloaded", timeout=15000)
        await _human_delay()
        
        tab_list = page.locator("ul.uk-tab").first
        tab_count = await tab_list.count()
        lab_payload: GradesPayload | None = None

        if tab_count > 0:
            data_attr = await tab_list.get_attribute("data-uk-tab")
            connect_selector = _parse_connect_selector(data_attr)
            switcher = page.locator(connect_selector).first if connect_selector else page.locator("ul.uk-switcher").first
            switcher_count = await switcher.count()

            if switcher_count > 0:
                tabs = tab_list.locator("li")
                tabs_count = await tabs.count()
                visible_index = 0
                lecture_payload = None

                for i in range(tabs_count):
                    tab = tabs.nth(i)
                    tab_class = await tab.get_attribute("class") or ""
                    if "uk-tab-responsive" in tab_class:
                        continue

                    tab_text = (await tab.inner_text()).strip()
                    content = switcher.locator("li").nth(visible_index)
                    visible_index += 1

                    if "Lecture" in tab_text or "Lab" in tab_text:
                        await tab.locator("a").click()
                        await _human_delay(0.3, 0.6)

                        scope_label = "Lab" if "Lab" in tab_text else "Lecture"
                        quizzes = await _extract_assessment_items(content, "Quiz", logger, scope_label)
                        assignments = await _extract_assessment_items(content, "Assignment", logger, scope_label)

                        if "Lab" in tab_text:
                            lab_payload = {
                                "quizzes": quizzes,
                                "assignments": assignments,
                            }
                        else:
                            lecture_payload = {
                                "quizzes": quizzes,
                                "assignments": assignments,
                            }

                if lecture_payload is not None:
                    if lab_payload:
                        lecture_payload["quizzes"].extend(lab_payload.get("quizzes", []))
                        lecture_payload["assignments"].extend(lab_payload.get("assignments", []))
                    logger.info(
                        "Grades extracted successfully",
                        extra={
                            "course": course["name"],
                            "quiz_count": len(lecture_payload["quizzes"]),
                            "assignment_count": len(lecture_payload["assignments"]),
                            "lab_present": bool(lab_payload),
                        },
                    )
                    return lecture_payload

        quizzes = await _extract_assessment_items(page, "Quiz", logger, "Lecture")
        assignments = await _extract_assessment_items(page, "Assignment", logger, "Lecture")

        logger.info(
            "Grades extracted successfully",
            extra={
                "course": course["name"],
                "quiz_count": len(quizzes),
                "assignment_count": len(assignments),
                "lab_present": False,
            },
        )

        return {
            "quizzes": quizzes,
            "assignments": assignments,
        }
        
    except PlaywrightError as exc:
        logger.error(f"Playwright error during grade extraction: {exc}")
        return {"quizzes": [], "assignments": []}
    except Exception as exc:
        logger.exception(f"Unexpected error during grade extraction: {exc}")
        return {"quizzes": [], "assignments": []}

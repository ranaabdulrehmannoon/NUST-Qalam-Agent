"""Attendance scraping utilities for Qalam/Odoo LMS courses."""

from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

from playwright.async_api import Locator, Page
from playwright.async_api import Error as PlaywrightError


AttendanceRecordPayload = dict[str, Any]
AttendancePayload = dict[str, Any]


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


async def _extract_attendance_from_container(
    container: Locator,
    logger: logging.Logger,
    session_type: str,
) -> tuple[float | None, list[AttendanceRecordPayload], str | None, str | None]:
    """Extract attendance percentage, records, and course metadata from a scoped container."""
    attendance_percentage = None
    course_name: str | None = None
    course_code: str | None = None

    try:
        li_items = container.locator("li")
        li_count = await li_items.count()
        for i in range(li_count):
            li = li_items.nth(i)
            b_tag = li.locator("b").first
            if await b_tag.count() == 0:
                continue
            label = (await b_tag.inner_text()).strip()
            span = li.locator("span").first
            span_text = (await span.inner_text()).strip() if await span.count() > 0 else ""

            if "Course" in label and "Code" not in label and ":" in label:
                if span_text:
                    course_name = span_text
            elif "Course Code" in label:
                if span_text:
                    course_code = span_text
            elif "Attendance Percentage" in label:
                try:
                    attendance_percentage = float(span_text)
                except ValueError:
                    continue
    except Exception as exc:
        logger.debug(f"Error extracting attendance header info: {exc}")

    records: list[AttendanceRecordPayload] = []

    try:
        tables = container.locator("table")
        table_count = await tables.count()
        logger.info(f"Found {table_count} tables in attendance container")

        for table_idx in range(table_count):
            table = tables.nth(table_idx)
            tbody = table.locator("tbody").first
            if await tbody.count() == 0:
                continue

            rows = tbody.locator("tr")
            row_count = await rows.count()

            for row_index in range(row_count):
                try:
                    row = rows.nth(row_index)
                    columns = row.locator("td")
                    col_count = await columns.count()

                    if col_count < 3:
                        continue

                    session_text = (await columns.nth(0).inner_text()).strip() if col_count > 0 else ""
                    date_text = (await columns.nth(1).inner_text()).strip() if col_count > 1 else ""
                    status_text = (await columns.nth(2).inner_text()).strip() if col_count > 2 else ""

                    try:
                        session_num = int(session_text)
                    except (ValueError, TypeError):
                        session_num = 1

                    if not date_text or not status_text:
                        continue

                    normalized_date = _normalize_date(date_text)
                    if not normalized_date:
                        continue

                    records.append({
                        "attendance_date": normalized_date,
                        "session_number": session_num,
                        "session_type": session_type,
                        "status": status_text,
                    })
                except Exception as exc:
                    logger.debug(f"Error processing attendance row {row_index}: {exc}")
                    continue

            if records:
                break
    except Exception as exc:
        logger.debug(f"Error extracting attendance records: {exc}")

    return attendance_percentage, records, course_name, course_code


def _parse_percentage(text: str) -> float | None:
    """Extract attendance percentage from visible text patterns like 85.50% or 85%."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if not match:
        return None
    return float(match.group(1))


def _normalize_date(raw_date: str) -> str | None:
    """Normalize common date formats to ISO date string (YYYY-MM-DD)."""
    if not raw_date:
        return None
    
    raw_date = raw_date.strip()
    
    # Try to parse different date formats
    for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y-%m"):
        try:
            parsed = datetime.strptime(raw_date, fmt)
            return parsed.date().isoformat()
        except ValueError:
            continue
    
    # If it looks like YYYY-MM-DD already, return as is
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw_date):
        return raw_date
    
    return None


def _extract_course_id_from_url(url: str) -> str | None:
    """Extract course ID from URLs like /student/course/info/2146962."""
    match = re.search(r"/course/(?:info|gradebook|attendance)/(\d+)", url)
    if match:
        return match.group(1)
    return None


async def extract_attendance(page: Page, course: dict[str, str], logger: logging.Logger) -> AttendancePayload:
    """
    Extract attendance percentage and daily attendance records for a Qalam course.
    
    Navigates to /student/course/attendance/{course_id} and extracts:
    - Overall attendance percentage
    - Daily attendance records with dates and status (Present/Absent/etc.)
    """
    try:
        # Extract course ID from the course URL
        course_id = _extract_course_id_from_url(course["url"])
        if not course_id:
            logger.warning(f"Could not extract course ID from URL: {course['url']}")
            return {"attendance_percentage": None, "records": []}
        
        # Navigate to the attendance page for this course
        attendance_url = f"/student/course/attendance/{course_id}"
        base_url = page.url.split("/student/")[0]  # Extract base domain
        full_attendance_url = urljoin(base_url, attendance_url)
        
        logger.info(f"Navigating to attendance page: {full_attendance_url}")
        try:
            await page.goto(full_attendance_url, wait_until="domcontentloaded", timeout=15000)
        except PlaywrightError as e:
            logger.warning(f"Could not navigate to attendance page: {e}")
            return {"attendance_percentage": None, "records": []}
        
        await _human_delay()
        
        tab_list = page.locator("ul.uk-tab").first
        tab_count = await tab_list.count()
        lab_payload: AttendancePayload | None = None

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

                    if "Lecture" in tab_text:
                        lecture_percentage, lecture_records, _, _ = await _extract_attendance_from_container(
                            content,
                            logger,
                            "Lecture",
                        )
                        lecture_payload = {
                            "attendance_percentage": lecture_percentage,
                            "records": lecture_records,
                        }
                    elif "Lab" in tab_text:
                        lab_percentage, lab_records, lab_course_name, lab_course_code = await _extract_attendance_from_container(
                            content,
                            logger,
                            "Lab",
                        )
                        lab_payload = {
                            "attendance_percentage": lab_percentage,
                            "records": lab_records,
                            "course_name": lab_course_name,
                            "course_code": lab_course_code,
                        }

                if lecture_payload is not None:
                    if lab_payload:
                        lecture_payload["records"].extend(lab_payload.get("records", []))
                        if lecture_payload["attendance_percentage"] is None:
                            lecture_payload["attendance_percentage"] = lab_payload.get("attendance_percentage")
                    logger.info(
                        "Attendance extracted successfully",
                        extra={
                            "course": course["name"],
                            "record_count": len(lecture_payload["records"]),
                            "attendance_percentage": lecture_payload["attendance_percentage"],
                            "lab_present": bool(lab_payload),
                        },
                    )
                    return lecture_payload

        attendance_percentage, records, _, _ = await _extract_attendance_from_container(
            page.locator("body"),
            logger,
            "Lecture",
        )

        logger.info(
            "Attendance extracted successfully",
            extra={
                "course": course["name"],
                "record_count": len(records),
                "attendance_percentage": attendance_percentage,
                "lab_present": False,
            },
        )

        return {
            "attendance_percentage": attendance_percentage,
            "records": records,
        }
        
    except PlaywrightError as exc:
        logger.error(f"Playwright error during attendance extraction: {exc}")
        return {"attendance_percentage": None, "records": []}
    except Exception as exc:
        logger.exception(f"Unexpected error during attendance extraction: {exc}")
        return {"attendance_percentage": None, "records": []}

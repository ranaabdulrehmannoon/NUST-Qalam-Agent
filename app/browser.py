"""Playwright browser lifecycle management."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright


@dataclass
class BrowserSession:
    """Container for Playwright session objects."""

    playwright: Playwright
    browser: Browser
    context: BrowserContext


async def launch_browser(*, headless: bool, logger: logging.Logger) -> BrowserSession:
    """Launch and return a configured Chromium browser session."""
    logger.info("Launching browser", extra={"headless": headless})
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(ignore_https_errors=False)
    return BrowserSession(playwright=playwright, browser=browser, context=context)


async def close_browser(session: BrowserSession, logger: logging.Logger) -> None:
    """Safely close browser resources without raising shutdown errors."""
    try:
        await session.context.close()
    except Exception:
        logger.exception("Context close failed")

    try:
        await session.browser.close()
    except Exception:
        logger.exception("Browser close failed")

    try:
        await session.playwright.stop()
    except Exception:
        logger.exception("Playwright stop failed")

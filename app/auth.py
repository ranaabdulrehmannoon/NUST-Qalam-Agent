"""Authentication workflow for Qalam LMS."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Iterable

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from .config import Settings


class AuthenticationError(RuntimeError):
    """Raised when login to Qalam LMS fails."""


def _safe_login_url(url: str) -> str:
    """Return URL without query params/fragments for safer logging."""
    return url.split("?", 1)[0].split("#", 1)[0]


async def _wait_for_first_selector(
    page: Page,
    selectors: Iterable[str],
    timeout_ms: int,
) -> str:
    """Wait for the first visible selector and return it."""
    per_selector_timeout = max(1000, timeout_ms // max(1, len(list(selectors))))

    for selector in selectors:
        try:
            await page.wait_for_selector(
                selector,
                state="visible",
                timeout=per_selector_timeout,
            )
            return selector
        except PlaywrightError:
            continue

    raise AuthenticationError(
        "Authentication failed. Login form elements not found."
    )


async def _human_delay(
    min_seconds: float = 0.4,
    max_seconds: float = 1.1,
) -> None:
    """Sleep a small random duration to mimic human pacing."""
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))


async def login(
    page: Page,
    settings: Settings,
    logger: logging.Logger,
) -> None:
    """Perform secure Qalam login and verify dashboard transition."""

    login_url = _safe_login_url(settings.qalam_login_url)
    logger.info("Navigating to login page", extra={"url": login_url})

    try:
        await page.goto(
            settings.qalam_login_url,
            wait_until="domcontentloaded",
            timeout=settings.login_timeout_ms,
        )

        await _human_delay()

        # -----------------------------
        # UPDATED SELECTORS (CRITICAL FIX)
        # -----------------------------

        username_selector = await _wait_for_first_selector(
            page,
            selectors=(
                "input[name='login']",
                "input[id='login']",
                "input[placeholder='Username']",
            ),
            timeout_ms=settings.login_timeout_ms,
        )

        password_selector = await _wait_for_first_selector(
            page,
            selectors=(
                "input[name='pass']",
                "input[id='password']",
                "input[type='password']",
            ),
            timeout_ms=settings.login_timeout_ms,
        )

        logger.info("Login form located")

        await page.fill(username_selector, settings.qalam_username)
        await _human_delay()

        await page.fill(password_selector, settings.qalam_password)
        await _human_delay()

        submit_selector = await _wait_for_first_selector(
            page,
            selectors=(
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Login')",
                "button:has-text('Sign in')",
            ),
            timeout_ms=settings.login_timeout_ms,
        )

        logger.info("Submitting login form")
        await page.click(submit_selector)

        # -----------------------------
        # SUCCESS DETECTION
        # -----------------------------

        login_origin = settings.qalam_login_url.rstrip("/")

        dashboard_selectors = (
            "nav",
            "#page-header",
            "[data-region='drawer']",
            "a:has-text('Dashboard')",
            "h1:has-text('Dashboard')",
        )

        success = False
        deadline = asyncio.get_running_loop().time() + (
            settings.login_timeout_ms / 1000
        )

        while asyncio.get_running_loop().time() < deadline:
            current_url = page.url.rstrip("/")

            # URL changed away from login page
            if current_url and not current_url.startswith(login_origin):
                success = True
                break

            # Or dashboard element visible
            for selector in dashboard_selectors:
                try:
                    if await page.locator(selector).first.is_visible():
                        success = True
                        break
                except PlaywrightError:
                    continue

            if success:
                break

            await asyncio.sleep(0.5)

        if not success:
            raise AuthenticationError(
                "Authentication failed. Dashboard not detected."
            )

        logger.info("Login confirmed successfully")

    except AuthenticationError:
        raise

    except Exception as exc:
        logger.error("Login process encountered unexpected error")
        raise AuthenticationError(
            "Authentication failed due to unexpected error."
        ) from exc


async def logout(page: Page, logger: logging.Logger, timeout_ms: int = 10000) -> None:
    """Log out from Qalam by opening the avatar menu and clicking Log out."""
    logger.info("Attempting logout")

    try:
        avatar_selector = "a.user_heading_avatar"
        logout_selector = "a[href*='/web/session/logout']"

        await page.wait_for_selector(avatar_selector, state="visible", timeout=timeout_ms)
        await page.click(avatar_selector)
        await _human_delay(0.2, 0.6)

        await page.wait_for_selector(logout_selector, state="visible", timeout=timeout_ms)
        await page.click(logout_selector)

        await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        logger.info("Logout completed")
    except PlaywrightError as exc:
        logger.warning(f"Logout attempt failed: {exc}")
    except Exception as exc:
        logger.exception(f"Unexpected error during logout: {exc}")
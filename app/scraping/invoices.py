"""Invoices scraping utilities for Qalam/Odoo LMS."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from playwright.async_api import Page
from playwright.async_api import Error as PlaywrightError


InvoicePayload = dict[str, Any]


def _parse_date(date_str: str) -> str | None:
    """Parse date string to ISO format (YYYY-MM-DD)."""
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # Try common date formats
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.date().isoformat()
        except ValueError:
            continue
    
    return None


def _parse_amount(amount_str: str) -> float | None:
    """Parse amount string to float, handling commas and special characters."""
    if not amount_str:
        return None
    
    amount_str = amount_str.strip().replace(",", "")
    
    try:
        # Handle currency symbols and extra text
        # Extract just the numeric part
        import re
        match = re.search(r"[\d.]+", amount_str)
        if match:
            return float(match.group())
    except (ValueError, AttributeError):
        pass
    
    return None


async def extract_invoices(page: Page, logger: logging.Logger) -> dict[str, Any]:
    """
    Extract student invoices from the invoices page.
    
    Returns the latest/most recent unpaid invoice or the most recent invoice overall.
    """
    try:
        # Navigate to invoices page
        invoices_url = "https://qalam.nust.edu.pk/student/invoices"
        logger.info(f"Navigating to invoices page: {invoices_url}")
        
        try:
            await page.goto(invoices_url, wait_until="domcontentloaded", timeout=15000)
        except PlaywrightError as e:
            logger.warning(f"Could not navigate to invoices page: {e}")
            return {"invoices": []}
        
        await page.wait_for_timeout(1000)  # Wait for page to load
        
        # Find the invoices table
        table = page.locator("table").first
        
        if await table.count() == 0:
            logger.info("No invoices table found")
            return {"invoices": []}
        
        tbody = table.locator("tbody").first
        if await tbody.count() == 0:
            logger.info("No table body found")
            return {"invoices": []}
        
        rows = tbody.locator("tr")
        row_count = await rows.count()
        logger.info(f"Found {row_count} invoice rows")
        
        invoices = []
        
        for row_idx in range(row_count):
            try:
                row = rows.nth(row_idx)
                cols = row.locator("td")
                col_count = await cols.count()
                
                logger.info(f"Row {row_idx}: col_count={col_count}")
                
                if col_count < 12:  # Changed from 13 to 12
                    logger.info(f"  → Skipping: only {col_count} columns")
                    continue
                
                # Extract fields from columns
                # Actual column order: Invoice Date[0], Due Date[1], Term[2], Semester[3], 
                # Challan Type[4], Challan ID[5], Scholarship %[6], Payable Amount[7],
                # Status[8], Print/Save[9], Action[10], Paid Date[11]
                invoice_date_str = (await cols.nth(0).inner_text()).strip()
                due_date_str = (await cols.nth(1).inner_text()).strip()
                term = (await cols.nth(2).inner_text()).strip()
                challan_type = (await cols.nth(4).inner_text()).strip()
                challan_id = (await cols.nth(5).inner_text()).strip()
                scholarship_str = (await cols.nth(6).inner_text()).strip()
                payable_str = (await cols.nth(7).inner_text()).strip()  # Changed from 8 to 7
                status = (await cols.nth(8).inner_text()).strip()
                paid_date_str = (await cols.nth(11).inner_text()).strip()  # Changed from 12 to 11
                
                logger.info(f"  → Date={invoice_date_str}, ID={challan_id}, Amount={payable_str}, Status={status}")
                
                if not challan_id:
                    logger.info(f"  → Skipping: Empty challan_id")
                    continue
                
                # Parse values
                invoice_date = _parse_date(invoice_date_str)
                due_date = _parse_date(due_date_str)
                scholarship_pct = _parse_amount(scholarship_str)
                payable_amount = _parse_amount(payable_str)
                paid_date = _parse_date(paid_date_str) if paid_date_str else None
                
                invoice_data = {
                    "invoice_date": invoice_date,
                    "due_date": due_date,
                    "term": term,
                    "challan_type": challan_type,
                    "challan_id": challan_id,
                    "scholarship_percentage": scholarship_pct,
                    "payable_amount": payable_amount,
                    "status": status,
                    "paid_date": paid_date,
                }
                
                logger.info(
                    f"✓ Invoice {challan_id}: {term}, {status}, Amount: {payable_amount}"
                )
                invoices.append(invoice_data)
                
            except Exception as exc:
                logger.debug(f"Error processing invoice row {row_idx}: {exc}")
                continue
        
        # Return all invoices
        logger.info(f"Extracted {len(invoices)} invoices total")
        
        return {"invoices": invoices}
        
    except Exception as exc:
        logger.exception(f"Unexpected error during invoices extraction: {exc}")
        return {"invoices": []}

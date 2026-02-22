"""Email reporting utility for daily Qalam student data summaries."""

from __future__ import annotations

import logging
import re
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.config import get_settings
from app.security.validation import ValidationError, validate_email


class EmailReportError(Exception):
    """Raised when email sending fails."""


_SMTP_TLS_PORTS: set[int] = {465, 587}
_SMTP_HOST_PATTERN = re.compile(r"^[A-Za-z0-9.-]+$")


def _sanitize_header_value(value: str, field_name: str) -> str:
    """Prevent header injection by rejecting newline characters."""
    if not isinstance(value, str):
        raise EmailReportError(f"Invalid header value type for {field_name}")

    cleaned = value.strip()
    if "\r" in cleaned or "\n" in cleaned:
        raise EmailReportError(f"Header injection detected in {field_name}")
    return cleaned


def _validate_smtp_settings(smtp_server: str, smtp_port: int) -> tuple[str, int]:
    """Validate SMTP host and port values."""
    host = _sanitize_header_value(smtp_server, "smtp_server")
    if not host:
        raise EmailReportError("SMTP host must not be empty")
    if not _SMTP_HOST_PATTERN.fullmatch(host):
        raise EmailReportError("SMTP host contains invalid characters")
    if host.startswith(".") or host.endswith(".") or ".." in host:
        raise EmailReportError("SMTP host is invalid")
    if not isinstance(smtp_port, int) or smtp_port not in _SMTP_TLS_PORTS:
        raise EmailReportError("SMTP port must be 465 (implicit TLS) or 587 (STARTTLS)")
    return host, smtp_port


def _send_message_secure(
    message: MIMEMultipart,
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    smtp_server: str,
    smtp_port: int,
    logger: logging.Logger,
) -> None:
    """Send an email using TLS-secured SMTP transport only."""
    logger.info("Connecting to SMTP server", extra={"smtp_host": smtp_server, "smtp_port": smtp_port})
    tls_context = ssl.create_default_context()

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10, context=tls_context) as server:
            server.ehlo()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [recipient_email], message.as_string())
        return

    with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
        server.ehlo()
        server.starttls(context=tls_context)
        server.ehlo()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, [recipient_email], message.as_string())


def _html_escape(text: str | None) -> str:
    """Escape HTML special characters."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _get_status_color(status: str) -> str:
    """Return color code based on status."""
    status_lower = str(status).lower()
    if "paid" in status_lower:
        return "#4CAF50"  # Green
    elif "unpaid" in status_lower:
        return "#FF9800"  # Orange
    elif "canceled" in status_lower:
        return "#F44336"  # Red
    else:
        return "#9E9E9E"  # Grey


def _format_currency(amount: float | None) -> str:
    """Format amount as currency."""
    if amount is None:
        return "N/A"
    if amount == 0:
        return "Paid"
    return f"PKR {amount:,.2f}"


def _format_grade(value: float | None) -> str:
    """Format grade value."""
    if value is None:
        return "-"
    return f"{value:.2f}"


def _build_html_report(
    student_name: str,
    courses: list[dict[str, Any]],
    attendance_data: dict[str, Any],
    unpaid_invoices: list[dict[str, Any]],
) -> str:
    """Build professional HTML email report."""
    
    today = datetime.now().strftime("%B %d, %Y")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #112B4F 0%, #1a3a6a 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 28px;
                font-weight: 600;
            }}
            .header p {{
                margin: 8px 0 0 0;
                opacity: 0.95;
            }}
            .content {{
                padding: 30px;
            }}
            .section {{
                margin-bottom: 30px;
            }}
            .section-title {{
                font-size: 18px;
                font-weight: 600;
                color: #112B4F;
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 3px solid #112B4F;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
            }}
            thead {{
                background-color: #f8f9fa;
            }}
            th {{
                padding: 12px;
                text-align: left;
                font-weight: 600;
                color: #112B4F;
                border-bottom: 2px solid #dee2e6;
            }}
            td {{
                padding: 12px;
                border-bottom: 1px solid #dee2e6;
            }}
            tr:hover {{
                background-color: #f8f9fa;
            }}
            .card {{
                background: #f8f9fa;
                border-left: 4px solid #112B4F;
                padding: 15px;
                margin-bottom: 12px;
                border-radius: 6px;
                page-break-inside: avoid;
            }}
            .card-title {{
                font-weight: 600;
                color: #112B4F;
                margin: 0 0 10px 0;
                font-size: 14px;
            }}
            .card-row {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
                font-size: 13px;
            }}
            .card-label {{
                color: #666;
                font-weight: 500;
            }}
            .card-value {{
                color: #333;
                font-weight: 600;
            }}
            .attendance-card {{
                background: #f8f9fa;
                border-radius: 6px;
                padding: 15px;
                margin-bottom: 12px;
                border-left: 4px solid #112B4F;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .attendance-course {{
                font-weight: 600;
                color: #112B4F;
                flex: 1;
            }}
            .invoice-card {{
                background: #f8f9fa;
                border-left: 4px solid #FF9800;
                padding: 15px;
                margin-bottom: 12px;
                border-radius: 6px;
                page-break-inside: avoid;
            }}
            .invoice-card.paid {{
                border-left-color: #4CAF50;
            }}
            .invoice-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
                padding-bottom: 10px;
                border-bottom: 1px solid #ddd;
            }}
            .invoice-id {{
                font-weight: 700;
                color: #112B4F;
                font-size: 14px;
            }}
            .invoice-row {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
                font-size: 13px;
            }}
            .invoice-label {{
                color: #666;
            }}
            .invoice-value {{
                color: #333;
                font-weight: 600;
            }}
            .status-badge {{
                display: inline-block;
                padding: 6px 12px;
                border-radius: 20px;
                color: white;
                font-weight: 500;
                font-size: 12px;
            }}
            .status-present {{
                background-color: #4CAF50;
            }}
            .status-absent {{
                background-color: #F44336;
            }}
            .status-paid {{
                background-color: #4CAF50;
            }}
            .status-unpaid {{
                background-color: #FF9800;
            }}
            .status-canceled {{
                background-color: #F44336;
            }}
            .metric {{
                display: inline-block;
                margin-right: 20px;
                padding: 15px;
                background-color: #f8f9fa;
                border-radius: 6px;
                border-left: 4px solid #112B4F;
            }}
            .metric-label {{
                font-size: 12px;
                color: #666;
                text-transform: uppercase;
            }}
            .metric-value {{
                font-size: 24px;
                font-weight: 600;
                color: #112B4F;
            }}
            .warning {{
                background-color: #FFF3CD;
                border: 1px solid #FFE69C;
                padding: 15px;
                border-radius: 6px;
                margin-bottom: 20px;
                color: #663C00;
            }}
            .footer {{
                background-color: #f8f9fa;
                padding: 20px 30px;
                text-align: center;
                font-size: 12px;
                color: #666;
            }}
            .no-data {{
                text-align: center;
                color: #999;
                padding: 20px;
                font-style: italic;
            }}
            .table-wrapper {{
                overflow-x: auto;
                display: block;
                width: 100%;
                margin-bottom: 15px;
            }}
            @media (max-width: 768px) {{
                body {{
                    padding: 10px;
                }}
                .content {{
                    padding: 15px;
                }}
                .table-wrapper {{
                    overflow-x: auto;
                    display: block;
                    width: 100%;
                    -webkit-overflow-scrolling: auto;
                }}
                table {{
                    min-width: 500px;
                }}
                th, td {{
                    padding: 8px;
                    font-size: 13px;
                }}
                .metric {{
                    display: block;
                    margin-bottom: 10px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>NUST Qalam Agent - Daily Report</h1>
                <p>Student: {_html_escape(student_name)}</p>
                <p>Date: {today}</p>
            </div>
            
            <div class="content">
    """
    
    # Academic Performance Section - Filter courses with grades only
    courses_with_grades = [
        c for c in courses
        if c.get("quizzes") or c.get("assignments")
    ]
    
    if courses_with_grades:
        html += """
                <div class="section">
                    <h2 class="section-title">📚 Academic Performance</h2>
        """
        
        for course in courses_with_grades:
            course_name = _html_escape(course.get("course_name", "Unknown"))
            html += f"""
                    <div style="margin-bottom: 20px;">
                        <h3 style="margin: 0 0 15px 0; color: #112B4F; font-size: 15px;">{course_name}</h3>
            """
            
            # Quizzes
            quizzes = course.get("quizzes", [])
            for quiz in quizzes:
                title = _html_escape(quiz.get("title", "Quiz"))
                obtained = _format_grade(quiz.get("obtained_mark"))
                total = _format_grade(quiz.get("total_mark"))
                avg = _format_grade(quiz.get("class_average"))
                pct = _format_grade(quiz.get("percentage"))
                html += f"""
                        <div class="card">
                            <div class="card-title">{title}</div>
                            <div class="card-row">
                                <span class="card-label">Your Mark:</span>
                                <span class="card-value">{obtained} / {total}</span>
                            </div>
                            <div class="card-row">
                                <span class="card-label">Class Average:</span>
                                <span class="card-value">{avg}</span>
                            </div>
                            <div class="card-row">
                                <span class="card-label">Percentage:</span>
                                <span class="card-value">{pct}%</span>
                            </div>
                        </div>
                """
            
            # Assignments
            assignments = course.get("assignments", [])
            for assignment in assignments:
                title = _html_escape(assignment.get("title", "Assignment"))
                obtained = _format_grade(assignment.get("obtained_mark"))
                total = _format_grade(assignment.get("total_mark"))
                avg = _format_grade(assignment.get("class_average"))
                pct = _format_grade(assignment.get("percentage"))
                html += f"""
                        <div class="card">
                            <div class="card-title">{title}</div>
                            <div class="card-row">
                                <span class="card-label">Your Mark:</span>
                                <span class="card-value">{obtained} / {total}</span>
                            </div>
                            <div class="card-row">
                                <span class="card-label">Class Average:</span>
                                <span class="card-value">{avg}</span>
                            </div>
                            <div class="card-row">
                                <span class="card-label">Percentage:</span>
                                <span class="card-value">{pct}%</span>
                            </div>
                        </div>
                """
            
            html += """
                    </div>
            """
        
        html += """
                </div>
        """
    
    # Attendance Section
    if attendance_data:
        overall_pct = attendance_data.get("overall_percentage")
        today_attendance = attendance_data.get("today_attendance", [])
        
        html += f"""
                <div class="section">
                    <h2 class="section-title">📅 Attendance Status</h2>
                    <div style="margin-bottom: 20px;">
                        <div class="metric">
                            <div class="metric-label">Overall Attendance</div>
                            <div class="metric-value">{overall_pct if overall_pct else 'N/A'}</div>
                        </div>
                    </div>
        """
        
        if today_attendance:
            html += """
                    <div>
            """
            
            for att in today_attendance:
                course_name = _html_escape(att.get("course_name", "Unknown"))
                status = att.get("status", "Unknown")
                status_class = "status-present" if status.lower() == "present" else "status-absent"
                html += f"""
                        <div class="attendance-card">
                            <span class="attendance-course">{course_name}</span>
                            <span class="status-badge {status_class}">{status}</span>
                        </div>
            """
            
            html += """
                    </div>
            """
        
        html += """
                </div>
        """
    
    # Unpaid Invoices Section
    if unpaid_invoices:
        html += f"""
                <div class="section">
                    <h2 class="section-title">💰 Unpaid Invoices</h2>
                    <div class="warning">
                        <strong>⚠️ Action Required:</strong> You have {len(unpaid_invoices)} unpaid invoice(s). Please settle payments before the due date.
                    </div>
        """
        
        for invoice in unpaid_invoices:
            inv_date = invoice.get("invoice_date", "N/A")
            challan_id = _html_escape(invoice.get("challan_id", "N/A"))
            term = _html_escape(invoice.get("term", "N/A"))
            due_date = invoice.get("due_date", "N/A")
            amount = _format_currency(invoice.get("payable_amount"))
            status = invoice.get("status", "Unknown")
            
            html += f"""
                    <div class="invoice-card">
                        <div class="invoice-header">
                            <span class="invoice-id">Challan: {challan_id}</span>
                            <span class="status-badge status-unpaid">{status}</span>
                        </div>
                        <div class="invoice-row">
                            <span class="invoice-label">Term:</span>
                            <span class="invoice-value">{term}</span>
                        </div>
                        <div class="invoice-row">
                            <span class="invoice-label">Invoice Date:</span>
                            <span class="invoice-value">{inv_date}</span>
                        </div>
                        <div class="invoice-row">
                            <span class="invoice-label">Due Date:</span>
                            <span class="invoice-value" style="color: #d32f2f; font-weight: 700;">{due_date}</span>
                        </div>
                        <div class="invoice-row">
                            <span class="invoice-label">Amount Due:</span>
                            <span class="invoice-value" style="color: #d32f2f; font-weight: 700;">{amount}</span>
                        </div>
                    </div>
            """
        
        html += """
                </div>
        """
    
    # Footer
    html += """
            </div>
            
            <div class="footer">
                <p>This is an automated report from NUST Qalam Agent.
                   Do not reply to this email. For support, contact the Agent administrator.</p>
                <p style="margin-top: 10px; opacity: 0.7;">© 2026 NUST Qalam Agent. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


async def send_daily_report_email(
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    student_name: str,
    smtp_server: str,
    smtp_port: int = 587,
    courses: list[dict[str, Any]] | None = None,
    attendance_data: dict[str, Any] | None = None,
    unpaid_invoices: list[dict[str, Any]] | None = None,
    logger: logging.Logger | None = None,
) -> bool:
    """
    Send a professional daily report email with Qalam student data.
    
    Args:
        sender_email: Email address of the sender
        sender_password: SMTP password or app password
        recipient_email: Email address of the recipient (student)
        student_name: Full name of the student
        smtp_server: SMTP server address (e.g., 'smtp.gmail.com')
        smtp_port: SMTP port (default 587 for TLS)
        courses: List of course dictionaries with grades, assignments, quizzes
        attendance_data: Dictionary with overall_percentage and today_attendance list
        unpaid_invoices: List of unpaid invoice dictionaries
        logger: Optional logger instance
    
    Returns:
        True if email sent successfully, False otherwise
    """
    
    if logger is None:
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger("email_reporter")
    
    try:
        # Prepare data with defaults
        courses = courses or []
        attendance_data = attendance_data or {}
        unpaid_invoices = unpaid_invoices or []

        smtp_server, smtp_port = _validate_smtp_settings(smtp_server, smtp_port)
        sender_email = validate_email(_sanitize_header_value(sender_email, "From"))
        recipient_email = validate_email(_sanitize_header_value(recipient_email, "To"))
        subject = _sanitize_header_value("NUST Qalam Agent - Daily Report", "Subject")
        safe_student_name = _sanitize_header_value(student_name, "student_name")
        
        # Build HTML content
        html_content = _build_html_report(
            student_name=safe_student_name,
            courses=courses,
            attendance_data=attendance_data,
            unpaid_invoices=unpaid_invoices,
        )
        
        # Create email message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = sender_email
        message["To"] = recipient_email
        
        # Attach HTML content
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)
        
        _send_message_secure(
            message=message,
            sender_email=sender_email,
            sender_password=sender_password,
            recipient_email=recipient_email,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            logger=logger,
        )
        logger.info("Email sent successfully")
        
        return True
        
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed")
        return False
        
    except smtplib.SMTPException as exc:
        logger.error(f"SMTP error occurred: {exc}")
        return False

    except (ValidationError, EmailReportError) as exc:
        logger.error(f"Email validation/security error: {exc}")
        return False
        
    except TimeoutError as exc:
        logger.error(f"SMTP connection timeout: {exc}")
        return False
        
    except Exception:
        logger.exception("Unexpected error sending email")
        return False


# Synchronous wrapper for non-async usage
def send_daily_report_email_sync(
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    student_name: str,
    smtp_server: str,
    smtp_port: int = 587,
    courses: list[dict[str, Any]] | None = None,
    attendance_data: dict[str, Any] | None = None,
    unpaid_invoices: list[dict[str, Any]] | None = None,
    logger: logging.Logger | None = None,
) -> bool:
    """
    Synchronous wrapper for send_daily_report_email.
    Use this if you don't have an event loop.
    """
    
    if logger is None:
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger("email_reporter")
    
    try:
        # Prepare data with defaults
        courses = courses or []
        attendance_data = attendance_data or {}
        unpaid_invoices = unpaid_invoices or []

        smtp_server, smtp_port = _validate_smtp_settings(smtp_server, smtp_port)
        sender_email = validate_email(_sanitize_header_value(sender_email, "From"))
        recipient_email = validate_email(_sanitize_header_value(recipient_email, "To"))
        subject = _sanitize_header_value("NUST Qalam Agent - Daily Report", "Subject")
        safe_student_name = _sanitize_header_value(student_name, "student_name")
        
        # Build HTML content
        html_content = _build_html_report(
            student_name=safe_student_name,
            courses=courses,
            attendance_data=attendance_data,
            unpaid_invoices=unpaid_invoices,
        )
        
        # Create email message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = sender_email
        message["To"] = recipient_email
        
        # Attach HTML content
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)
        
        _send_message_secure(
            message=message,
            sender_email=sender_email,
            sender_password=sender_password,
            recipient_email=recipient_email,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            logger=logger,
        )
        logger.info("Email sent successfully")
        
        return True
        
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed")
        return False
        
    except smtplib.SMTPException as exc:
        logger.error(f"SMTP error occurred: {exc}")
        return False

    except (ValidationError, EmailReportError) as exc:
        logger.error(f"Email validation/security error: {exc}")
        return False
        
    except TimeoutError as exc:
        logger.error(f"SMTP connection timeout: {exc}")
        return False
        
    except Exception:
        logger.exception("Unexpected error sending email")
        return False


def send_daily_report_from_config(
    student_name: str,
    courses: list[dict[str, Any]] | None = None,
    attendance_data: dict[str, Any] | None = None,
    unpaid_invoices: list[dict[str, Any]] | None = None,
    logger: logging.Logger | None = None,
) -> bool:
    """
    Send a daily report email using configuration from .env file.
    
    This is a convenience wrapper that automatically loads SMTP settings from config.
    
    Args:
        student_name: Full name of the student
        courses: List of course dictionaries with grades, assignments, quizzes
        attendance_data: Dictionary with overall_percentage and today_attendance list
        unpaid_invoices: List of unpaid invoice dictionaries
        logger: Optional logger instance
    
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        settings = get_settings()
        
        return send_daily_report_email_sync(
            sender_email=settings.smtp_from,
            sender_password=settings.smtp_password,
            recipient_email=settings.smtp_to,
            student_name=student_name,
            smtp_server=settings.smtp_host,
            smtp_port=settings.smtp_port,
            courses=courses,
            attendance_data=attendance_data,
            unpaid_invoices=unpaid_invoices,
            logger=logger,
        )
    except Exception as exc:
        if logger:
            logger.exception(f"Failed to load configuration for email: {exc}")
        else:
            print(f"Error: Failed to load configuration for email: {exc}")
        return False

"""Application entry point for Qalam login validation."""

from __future__ import annotations

import asyncio
import logging

from .auth import AuthenticationError, login, logout
from .browser import BrowserSession, close_browser, launch_browser
from .config import ConfigError, get_settings
from .db.models import Course, Invoice
from .db.repository import (
    RepositoryError,
    save_assignments,
    save_attendance,
    save_course,
    save_invoices,
    save_quizzes,
)
from .db.session import create_db_engine, get_session_factory
from .email_reporter import send_daily_report_from_config
from .logger import mask_secret, setup_logger
from .scraping.attendance import extract_attendance
from .scraping.courses import extract_courses
from .scraping.grades import extract_grades
from .scraping.invoices import extract_invoices


async def run() -> None:
    """Run login, scraping, and persistence workflow."""
    logger = setup_logger()

    try:
        settings = get_settings()
    except ConfigError:
        logger.error("Configuration error. Check required .env variables.")
        raise

    logger.info(
        "Configuration loaded",
        extra={
            "headless": settings.headless,
            "qalam_username": mask_secret(settings.qalam_username),
        },
    )

    engine = create_db_engine(settings=settings, logger=logger)
    session_factory = get_session_factory(engine)

    session: BrowserSession | None = None
    db_session = None
    page = None
    try:
        db_session = session_factory()

        session = await launch_browser(headless=settings.headless, logger=logger)
        page = await session.context.new_page()

        await login(page=page, settings=settings, logger=logger)
        logger.info("Login successful. Starting scraping workflow")
        print("Login Successful")

        courses = await extract_courses(page=page, logger=logger)
        for course_payload in courses:
            course_name = course_payload.get("name", "Unknown")
            try:
                grades_payload = await extract_grades(page=page, course=course_payload, logger=logger)
                attendance_payload = await extract_attendance(page=page, course=course_payload, logger=logger)

                logger.info(f"Attendance payload received: {len(attendance_payload.get('records', []))} records, {attendance_payload.get('attendance_percentage')}%")

                course = save_course(db_session, course_payload)
                save_quizzes(db_session, course, grades_payload["quizzes"])
                save_assignments(db_session, course, grades_payload["assignments"])
                save_attendance(
                    db_session,
                    course,
                    attendance_percentage=attendance_payload.get("attendance_percentage"),
                    records=attendance_payload.get("records", []),
                )

                db_session.commit()

                logger.info("Course processed successfully", extra={"course": course_name})
            except (RepositoryError, Exception):
                db_session.rollback()
                logger.exception("Course processing failed", extra={"course": course_name})

        # Extract and save invoices (once at the end for all courses)
        try:
            invoices_payload = await extract_invoices(page=page, logger=logger)
            if invoices_payload.get("invoices"):
                save_invoices(db_session, invoices_payload["invoices"])
                db_session.commit()
                logger.info(f"Invoices processed successfully: {len(invoices_payload['invoices'])} invoices saved")
        except (RepositoryError, Exception):
            db_session.rollback()
            logger.exception("Invoices processing failed")

        # Send daily report email with all collected data
        try:
            logger.info("Preparing daily report email")
            
            # Fetch all courses with grades and attendance
            courses_data = []
            all_courses = db_session.query(Course).all()
            
            for course in all_courses:
                course_dict = {
                    "course_name": course.course_name,
                    "quizzes": [
                        {
                            "title": q.title,
                            "obtained_mark": float(q.obtained_mark) if q.obtained_mark else None,
                            "total_mark": float(q.total_mark) if q.total_mark else None,
                            "class_average": float(q.class_average) if q.class_average else None,
                            "percentage": float(q.percentage) if q.percentage else None,
                        }
                        for q in course.quizzes
                    ],
                    "assignments": [
                        {
                            "title": a.title,
                            "obtained_mark": float(a.obtained_mark) if a.obtained_mark else None,
                            "total_mark": float(a.total_mark) if a.total_mark else None,
                            "class_average": float(a.class_average) if a.class_average else None,
                            "percentage": float(a.percentage) if a.percentage else None,
                        }
                        for a in course.assignments
                    ],
                }
                courses_data.append(course_dict)
            
            # Fetch attendance data
            attendance_data = {}
            if all_courses:
                overall_percentages = [float(c.attendance_percentage) for c in all_courses if c.attendance_percentage]
                if overall_percentages:
                    avg_attendance = sum(overall_percentages) / len(overall_percentages)
                    attendance_data["overall_percentage"] = f"{avg_attendance:.1f}%"
                
                # Get today's attendance
                from datetime import datetime
                today = datetime.now().date()
                today_attendance = []
                for course in all_courses:
                    today_records = [r for r in course.attendance_records if r.attendance_date == today]
                    if today_records:
                        today_attendance.append({
                            "course_name": course.course_name,
                            "status": today_records[0].status,
                        })
                attendance_data["today_attendance"] = today_attendance
            
            # Fetch unpaid invoices
            unpaid_invoices = db_session.query(Invoice).filter(Invoice.status == "Unpaid").all()
            unpaid_invoices_data = [
                {
                    "invoice_date": str(inv.invoice_date) if inv.invoice_date else "N/A",
                    "challan_id": inv.challan_id,
                    "term": inv.term,
                    "due_date": str(inv.due_date) if inv.due_date else "N/A",
                    "payable_amount": float(inv.payable_amount) if inv.payable_amount else 0,
                    "status": inv.status,
                }
                for inv in unpaid_invoices
            ]
            
            # Get student name from username in lowercase format for email display
            student_name = settings.qalam_username.replace("_", " ").lower()
            
            # Send email
            email_result = send_daily_report_from_config(
                student_name=student_name,
                courses=courses_data,
                attendance_data=attendance_data,
                unpaid_invoices=unpaid_invoices_data,
                logger=logger,
            )
            
            if email_result:
                logger.info("Daily report email sent successfully")
            else:
                logger.warning("Failed to send daily report email")
        except Exception:
            logger.exception("Error sending daily report email")

        # Logout after invoices and email reporting
        await logout(page=page, logger=logger)

    except AuthenticationError:
        logger.error("Authentication failed")
        raise
    except Exception:
        logger.exception("Unexpected application error")
        raise
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                logger.exception("Page close failed")
        if db_session is not None:
            db_session.close()
        if session is not None:
            await close_browser(session, logger)


def main() -> None:
    """Synchronous runner for asyncio app."""
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    asyncio.run(run())


if __name__ == "__main__":
    main()

# NUST Qalam Agent

Automated monitoring agent for NUST Qalam that logs in, scrapes academic and finance data, stores results in MySQL, and sends a daily HTML email report.

## Features

- Secure login flow with Playwright.
- Course discovery and per-course data extraction.
- Grade scraping for quizzes and assignments.
- Attendance scraping with daily records and percentages.
- Invoice scraping and unpaid invoice reporting.
- SQLAlchemy persistence with Alembic migrations.
- Professional HTML email reporting over TLS-secured SMTP.
- Built-in log redaction for sensitive values.

## Tech Stack

- Python 3.11+
- Playwright
- SQLAlchemy 2.x
- PyMySQL
- Alembic
- python-dotenv
- SMTP (`smtplib`, `email.mime`)

## Project Structure

```text
NUST Qalam Agent/
├── alembic.ini
├── db_connection_check.py
├── mysql_schema.sql
├── security_scan.py
├── requirements.txt
├── README.md
├── .env.example
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
└── app/
    ├── auth.py
    ├── browser.py
    ├── config.py
    ├── email_reporter.py
    ├── logger.py
    ├── main.py
    ├── db/
    │   ├── base.py
    │   ├── models.py
    │   ├── repository.py
    │   └── session.py
    └── scraping/
        ├── attendance.py
        ├── courses.py
        ├── grades.py
        └── invoices.py
```

## Setup

### 1) Create and activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
pip install -r requirements.txt
playwright install chromium
```

### 3) Configure environment variables

Copy `.env.example` to `.env` and update placeholder values.

```powershell
Copy-Item .env.example .env
```

Required variables are defined in `.env.example`:

- `FERNET_KEY`
- `QALAM_USERNAME`, `QALAM_PASSWORD`, `QALAM_LOGIN_URL`, `QALAM_HEADLESS`, `QALAM_LOGIN_TIMEOUT_MS`
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TO`

## Running

### Main app

```powershell
python -m app.main
```

### Database connection check

```powershell
python db_connection_check.py
```

### Secret scanning helper

```powershell
python security_scan.py
```

## Database Migrations

Apply latest migrations:

```powershell
alembic upgrade head
```

Create a new migration:

```powershell
alembic revision --autogenerate -m "describe_change"
```

## Email Reporting

- SMTP transport is TLS-only (`465` or `587`).
- Header values are sanitized to prevent injection.
- Credentials are loaded from environment variables.
- Sensitive values are redacted in logs.



# QuizBlitz

A self-hosted assessment platform built for academic institutions. Supports structured course hierarchies, timed quizzes with crash recovery, manual Q&A grading, and passive anti-cheat monitoring.

---

## Overview

QuizBlitz is a web-based quiz and assessment system designed to run on a single VPS/shared hosting. It handles three roles - admin, teacher, and student - each with distinct responsibilities and access boundaries.

Students self-register under a department, semester, and class. Teachers create and assign quizzes to their assigned classes, grade written answers, and review session results. The admin manages the institutional structure and user accounts.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| Database | MySQL 8 / MariaDB 10.6+ |
| ORM | SQLAlchemy |
| Auth | JWT HS256 + bcrypt |
| Frontend | Vue 3 (CDN) |
| Process | systemd |

---

## Features

**Organisation**
- Departments, programs, semesters, and classes managed by admin
- Semesters are global but activated per-department (e.g. Summer 2025 only exists for certain departments)
- Subjects belong to departments and are assigned to specific classes
- Classes and semesters are deactivated via `is_active` (not hard-deleted)

**Users**
- Admin account seeded as user ID 1 on first run
- Teachers created by admin, assigned to specific class-subject combinations
- Students self-register and can enroll in class

**Quizzes**
- Created by teachers for a subject
- Assignable to one or multiple classes
- Per-quiz settings: shuffle questions, show answers after submission, attempt limit, time window, pass percentage

**Question Types**
- MCQ: auto-graded on submission
- Q&A: manually graded by the assigned teacher

**Result Logic**
- Pure MCQ quiz: result released immediately when time expires or student submits
- Any Q&A present: result held until teacher grades all written answers
- Score override: teacher or admin can override a computed score with a reason (original score preserved)

**Timing and Crash Recovery**
- Timer is server-side: `expires_at` written to the database at session start
- On browser crash or reconnect, the resume endpoint returns remaining seconds computed as `expires_at - now()`
- Answers are saved per-question immediately (idempotent upsert), not on final submit
- If time expires while a student is disconnected, the session is auto-submitted on their next API call

**Anti-Cheat**
- Optional per quiz, enabled by default
- Browser monitors: tab switch, window blur, copy attempt, fullscreen exit, devtools heuristic, rapid submit
- Events logged silently to `cheat_events` table with timestamps
- Student sees no indication; teacher sees a timestamped event log on the results page
- System never auto-fails anyone - evidence only, human decision

---

## Project Structure

```
quiz-system/
├── backend/
│   ├── main.py              # FastAPI app, startup, CORS
│   ├── database.py          # MySQL engine, session factory
│   ├── models.py            # SQLAlchemy ORM models (16 tables)
│   ├── schemas.py           # Pydantic DTOs
│   ├── auth.py              # JWT, bcrypt, registration_id validation
│   ├── seed.py              # Creates admin user ID=1 on first run
│   ├── routers/
│   │   ├── public.py        # /departments, /auth/*
│   │   ├── student.py       # /quizzes, /sessions/*
│   │   ├── teacher.py       # /teacher/*
│   │   └── admin.py         # /admin/*
│   ├── services/
│   │   ├── quiz_service.py  # Session logic, shuffle, scoring, auto-submit
│   │   ├── grade_service.py # Q&A grading, result release
│   │   └── cheat_service.py # Event logging, flag count
│   └── requirements.txt
├── static/                  # Served directly by Apache
│   ├── index.html
│   ├── register.html
│   ├── dashboard.html
│   ├── quiz.html
│   ├── result.html
│   ├── teacher/
│   │   ├── dashboard.html
│   │   ├── quiz-create.html
│   │   ├── questions.html
│   │   └── grade.html
│   ├── admin/
│   │   ├── dashboard.html
│   │   ├── departments.html
│   │   ├── classes.html
│   │   ├── teachers.html
│   │   └── results.html
│   └── js/
│       ├── api.js
│       ├── config.js
│       └── navbar.js
└── quiz.service                # systemd unit file (example)
```

---

## Database Schema

16 tables across 4 domains:

- **Organisation**: `departments`, `programs`, `semesters`, `dept_semesters`, `classes`, `subjects`, `class_subjects`
- **Identity**: `users`, `teacher_assignments`, `student_classes`
- **Assessment**: `quizzes`, `quiz_classes`, `questions`
- **Execution**: `quiz_sessions`, `answers`, `cheat_events`

---

## Installation

### Requirements

- Python 3.11+
- MySQL 8+ or MariaDB 10.6+
- Apache 2.4 with `mod_proxy` and `mod_proxy_http` enabled

### 1. Database

```sql
CREATE DATABASE QuizBlitzdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'QuizBlitz'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON QuizBlitzdb.* TO 'QuizBlitz'@'localhost';
FLUSH PRIVILEGES;
```

### 2. Backend

```bash
cd /home/quiz/public_html

python3 -m venv venv
./venv/bin/pip install -r backend/requirements.txt

# Copy and edit environment config
cp .env.example .env
# Set at least: DATABASE_URL, SECRET_KEY

# Ensure DB schema (creates tables if missing; does not alter existing tables)
python3 -m backend.migrations

# Seed admin user (ID = 1) if missing
python3 -m backend.seed
```

### 3. systemd Service

The included `quiz.service` runs `uvicorn backend.main:app` on `127.0.0.1:8008`.

```bash
cp quiz.service /etc/systemd/system/quiz.service
sudo systemctl daemon-reload
sudo systemctl enable quiz.service
sudo systemctl restart quiz.service

# Verify
sudo systemctl status quiz.service
curl http://127.0.0.1:8008/api/health
```

### 4. Apache VirtualHost

Add the following inside your `quiz.yourdomain.com` VirtualHost block in Virtualmin:

```apache
ProxyPreserveHost On
ProxyPass        /api/  http://127.0.0.1:8008/api/
ProxyPassReverse /api/  http://127.0.0.1:8008/api/

DocumentRoot /home/quiz/public_html
```

Note: keep the trailing slashes exactly as shown for `/api/` to avoid redirect issues with `POST` requests (e.g. login).

Enable required modules if not already active:

```bash
a2enmod proxy proxy_http
systemctl reload apache2
```

SSL is managed by Virtualmin as normal.

---

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy MySQL connection string | `mysql+pymysql://user:pass@localhost:3306/quiz_system` |
| `SECRET_KEY` | Secret key for signing JWT tokens | any long random string |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry in minutes | `480` |

---

## Database Setup / Migrations

There is no Alembic migration workflow yet. For a fresh database, the backend provides a simple table bootstrap using SQLAlchemy models (`Base.metadata.create_all()`).

Run it anytime (safe to run multiple times):

```bash
python3 -m backend.migrations
```

Note: this does not alter existing tables/columns. If you change models after the DB is created, you must apply schema changes manually (or introduce Alembic).

## API

All endpoints are under `/api/`. Authentication via `Authorization: Bearer <token>` header.

**Public** (no auth): `GET /api/departments`, `POST /api/auth/register`, `POST /api/auth/login`

**Student**: `GET /api/student/quizzes`, `POST /api/student/quizzes/{id}/start`, `GET /api/student/sessions/{id}/resume`, `POST /api/student/sessions/{id}/answer`, `POST /api/student/sessions/{id}/cheat`, `POST /api/student/sessions/{id}/submit`, `GET /api/student/sessions/{id}/result`

**Teacher**: `GET /api/teacher/quizzes`, `POST /api/teacher/quizzes`, `POST /api/teacher/quizzes/{id}/questions`, `POST /api/teacher/quizzes/{id}/assign`, `GET /api/teacher/quizzes/{id}/results`, `GET /api/teacher/sessions/{id}/grade`, `POST /api/teacher/answers/{id}/grade`

**Admin**: `POST /api/admin/departments`, `POST /api/admin/semesters`, `POST /api/admin/classes`, `POST /api/admin/teachers`, `POST /api/admin/faculty-assignments`, `POST /api/admin/students/bulk-move`, `GET /api/admin/global-results`, `GET /api/admin/users`

Full OpenAPI docs available at `/api/docs` when the server is running.

---

## Development Notes

This is still in development phase, so expect breaking changes.

---

## License

The MIT License (MIT). Please see [License File](LICENSE) for more information.

## Credits

- [Jabir Khan](https://github.com/jabirmayar)

## Support

[Support the Project](https://jabirmayar.gumroad.com/coffee)

If you discover any security-related issues, please email hello@jabirkhan.com.

Built by DAA Creators (daacreators.com)

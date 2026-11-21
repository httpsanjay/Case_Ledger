# CaseLedger - Secure Document Management System

**A secure document management system for police and legal case files.**

CaseLedger helps investigation teams store case documents, track every version, get them approved, sign them digitally, and prove later that nothing was changed.

![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=flat&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.x-092E20?style=flat&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=flat&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-Queue-DC382D?style=flat&logo=redis&logoColor=white)
![Status](https://img.shields.io/badge/Status-Academic%20Prototype-orange?style=flat)

---

## Table of Contents

1. [The Problem](#the-problem)
2. [What CaseLedger Does](#what-caseledger-does)
3. [User Roles](#user-roles)
4. [How a Document Moves Through the System](#how-a-document-moves-through-the-system)
5. [Security Design](#security-design)
6. [Tech Stack](#tech-stack)
7. [Project Structure](#project-structure)
8. [Getting Started](#getting-started)
9. [Environment Variables](#environment-variables)
10. [Deployment](#deployment)
11. [Limitations](#limitations)
12. [Future Work](#future-work)
13. [Authors](#authors)

---

## The Problem

Police and legal teams handle many important documents: FIRs, witness statements, forensic reports, charge sheets and more. When these are managed by hand, it is hard to:

- find the latest version of a document,
- control who can see a case,
- prove that a file was not changed after approval,
- know who approved a document, and when.

CaseLedger solves this by keeping every document inside a **case**, controlling access by **role and police station**, and recording every important action.

---

## What CaseLedger Does

### Case and document management
- Create cases with a case number, type, status and description.
- Add documents to a case (FIR, Witness Statement, Evidence, Investigation Report, Charge Sheet, Forensic Report, Court Filing, Other).
- Assign officers to a case.
- Search and filter cases by number, title, status, type or assigned officer.
- Download selected case documents as a ZIP file.

### Document versioning
- Every upload creates a new **version**. Old versions are never overwritten.
- A signed version cannot be replaced.

### Review and approval
- An Investigating Officer (IO) submits a document for review.
- A Station House Officer (SHO) approves or rejects it. A rejection can include a reason.

### Digital signatures
- Only an SHO can sign, and only after approving the document.
- Each SHO gets their own RSA-4096 key pair.
- The signature covers the document ID, version number, file hash and SHO ID.

### Integrity checking
- A SHA-256 hash is calculated for every uploaded file and stored.
- Anyone with access can run **Verify** on a version. The system recalculates the hash and checks the signature, then reports whether the file is unchanged.

### OCR and text extraction
- Scanned PDFs and images are processed with OCR (Tesseract).
- OCR runs in the background (Celery + Redis), so uploads stay fast.
- The status of each file is tracked: Pending, Processing, Completed or Failed.
- The extracted text is saved with the document version.

### Secure sharing
An SHO can share specific document versions with:
- another **police station**,
- a **lawyer** (found by registration number),
- a **court** account (found by registration number).

Each share has a permission level (**View**, **Download**, or **View + Download**), can have an expiry date, and can be revoked at any time. Recipients see shared documents under **Shared With Me**.

### Audit trail
Important actions are saved with the user, time and IP address, including:
logins, case creation, uploads, submissions, approvals, rejections, signing, verification, sharing, revoking, and shared-document views and downloads.

### Internal MCP endpoints
CaseLedger includes read-only internal JSON endpoints (under `/internal/mcp/`) for case search, document search, case details and OCR text. They are protected by a secret token and are meant for an external MCP or AI service to read data from CaseLedger.

---

## User Roles

| Role | What they can do |
| --- | --- |
| **Administrator** | Full access to all cases. |
| **Investigating Officer (IO)** | Create cases, upload documents and versions, and submit documents for review. Sees only cases they created or are assigned to. |
| **Station House Officer (SHO)** | Sees all cases in their station. Approves or rejects documents, signs documents, assigns officers and shares documents. |
| **Forensic Officer** | Works on assigned cases in their station. |
| **Lawyer** | Views or downloads only the documents shared with them. |
| **Court Official** | Views or downloads only the documents shared with them. |

Access is also limited by **police station**. An officer cannot open a case from another station unless a document has been shared with them.

---

## How a Document Moves Through the System

```text
IO uploads document  ->  Version saved (status: DRAFT)
                              |
                              |  SHA-256 hash created
                              |  OCR queued in background
                              v
IO submits for review  ->  PENDING_REVIEW
                              |
                 +------------+------------+
                 |                         |
            SHO rejects               SHO approves
                 |                         |
              REJECTED                  APPROVED
        (IO uploads a new version)         |
                                     SHO signs
                                           |
                                        SIGNED
                                (file can no longer be changed)
```

Document version statuses: `DRAFT`, `PENDING_REVIEW`, `REJECTED`, `APPROVED`, `SIGNED`.

---

## Security Design

| Layer | How it works |
| --- | --- |
| **Role-based access** | Every view checks the user's role and police station. |
| **File hashing** | SHA-256 hash stored for each version; any change to the file is detected. |
| **Digital signature** | RSA-4096 with PSS padding and SHA-256, created by the SHO. |
| **Protected private keys** | Private keys are stored encrypted, using `SIGNING_KEY_ENCRYPTION_PASSWORD`. |
| **Immutable signed files** | A signed version cannot have its file replaced. |
| **Audit log** | Actions are recorded with user, time and IP address. |
| **Share controls** | Shares have permissions, optional expiry and can be revoked. |
| **Production settings** | When `DEBUG=False`: HTTPS redirect, HSTS, secure cookies, `X-Frame-Options: DENY` and nosniff headers. |
| **MCP endpoints** | Require a secret token and are compared in constant time. |

---

## Tech Stack

| Area | Technology |
| --- | --- |
| Backend | Python, Django |
| Database | PostgreSQL |
| Background tasks | Celery with Redis |
| OCR | Tesseract (`pytesseract`), `pdf2image`, Pillow |
| Cryptography | `cryptography` library (RSA-4096, SHA-256) |
| Filtering | `django-filter` |
| Static files | WhiteNoise |
| Server | Gunicorn with Uvicorn worker |
| Frontend | Django templates, HTML, CSS, JavaScript |
| Container | Docker |

---

## Project Structure

```text
Case_Ledger/
├── accounts/        Users, roles, login, registration, dashboard
├── cases/           Cases, documents, versions, signing, sharing, OCR, MCP endpoints
│   ├── models.py        Case, Document, DocumentVersion, DocumentShare, PoliceStation, UserSigningKey
│   ├── views.py         Main application logic
│   ├── permissions.py   Access rules
│   ├── utils.py         Hashing, key generation, signing and verification
│   ├── tasks.py         Celery task for OCR
│   ├── ocr.py           Text extraction
│   ├── filters.py       Case search and filters
│   ├── mcp_views.py     Internal read-only endpoints
│   └── management/commands/seed_police_stations.py
├── audit/           Audit log model, helper and page
├── case_ledger/     Project settings, URLs, Celery setup
├── templates/       Shared layouts and components
├── static/          CSS
├── Dockerfile
├── build.sh
├── requirements.txt
└── manage.py
```

---

## Getting Started

### Requirements

- Python 3.14 (or a compatible version)
- PostgreSQL database
- Redis server
- **Tesseract OCR** and **Poppler** installed on the system (needed for OCR)

### 1. Clone the repository

```bash
git clone https://github.com/httpsanjay/Case_Ledger.git
cd Case_Ledger
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a `.env` file

Copy the values from the [Environment Variables](#environment-variables) section and fill in your own.

### 5. Set up the database

```bash
python manage.py migrate
python manage.py seed_police_stations
python manage.py createsuperuser
```

`seed_police_stations` adds sample Bengaluru police stations so you can start testing.

### 6. Start the web server

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

### 7. Start the background worker

In a second terminal (with the virtual environment active):

```bash
celery -A case_ledger worker --loglevel=info
```

Without the worker, uploaded files will stay in the **Pending** OCR state.

### 8. Run tests

```bash
python manage.py test
```

---

## Environment Variables

```env
# Required
SECRET_KEY=your-django-secret-key
DATABASE_URL=postgres://user:password@host:5432/dbname
REDIS_URL=redis://localhost:6379/0
SIGNING_KEY_ENCRYPTION_PASSWORD=a-long-random-password

# General
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=
MEDIA_ROOT=media
SESSION_COOKIE_AGE=1209600
SESSION_EXPIRE_AT_BROWSER_CLOSE=False

# Optional: internal MCP endpoints
DJANGO_INTERNAL_TOKEN=a-long-random-token
```

Notes:

- `DATABASE_URL` and `REDIS_URL` (or `CELERY_BROKER_URL`) are required. The app will not start without them.
- `SECRET_KEY` is required when `DEBUG=False`.
- Keep `SIGNING_KEY_ENCRYPTION_PASSWORD` safe. If it is lost, existing signing keys cannot be unlocked.
- The database connection uses SSL (`sslmode=require`).
- Never commit your `.env` file.

---

## Deployment

The project includes:

- **`Dockerfile`**: runs the app with Gunicorn and a Uvicorn worker on port `8000`.
- **`build.sh`**: installs dependencies, collects static files and runs migrations (useful for platforms like Render).

For production:

1. Set `DEBUG=False` and a strong `SECRET_KEY`.
2. Serve the app over HTTPS.
3. Run a separate Celery worker process.
4. Use persistent storage for uploaded files (`MEDIA_ROOT`).
5. Install Tesseract and Poppler in the server or container image. The current `Dockerfile` does not install them yet.

---

## Limitations

- This is an **academic prototype**. It is not certified for real confidential police or court data without more security review, compliance work and infrastructure hardening.
- Uploaded files are stored on the local file system. They are not encrypted at rest.
- The internal MCP endpoints use one shared token and are not filtered by individual user.
- OCR quality depends on the quality of the scanned file.

---

## Future Work

- Cloud object storage for files
- Encryption of files at rest
- Stronger key management (for example, a hardware security module or key vault)
- Per-user access control on MCP endpoints
- AI-assisted case summaries and document search
- Better OCR handling
- Security testing and monitoring
- Backup and disaster recovery

---

## Authors

- **Sri Sanjay K**: B.Tech Computer Science Engineering, CMR University
- **Vinutha NJ**: B.Tech Computer Science Engineering, CMR University
- **Yashaswini DN**: B.Tech Computer Science Engineering, CMR University

---

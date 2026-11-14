# LifeLink — Smart Blood Donor & Emergency Blood Availability Portal

> A responsive healthcare web platform that bridges blood donors and emergency patients through real-time availability tracking, smart ABO/Rh compatibility matching, and urgent transfusion dispatch.

---

## 1. Technology Stack

- **Backend:** Python 3.10+ & Flask 3.x (Application Factory Pattern with Modular Blueprints)
- **Database:** MySQL 8.0+ / MariaDB via pure-Python `PyMySQL` driver
- **Security:** Strict Parameterized SQL Queries, PBKDF2/scrypt Password Hashing (`Werkzeug`), Role-Based Access Control (RBAC), Session Protection (HttpOnly, SameSite)
- **Frontend:** Semantic HTML5, CSS3 Custom Properties Design System, Vanilla ES6+ JavaScript
- **Typography & Icons:** Google Fonts (Poppins & Inter), Lucide Icons
- **Testing:** Unit & Integration test suite via `pytest` / `unittest`

---

## 2. Professional Project Structure

```
d:\project\
├── app/                             # Core Application Package
│   ├── __init__.py                  # Application Factory (create_app, error handlers, context processors)
│   ├── config.py                    # Environment Configuration (Dev, Prod, Test)
│   ├── extensions.py                # Shared extensions & connection bindings
│   │
│   ├── models/                      # Database Layer (Strictly Parameterized DAOs)
│   │   ├── __init__.py              # Model exports
│   │   ├── user.py                  # User account DAO & authentication
│   │   ├── donor.py                 # Donor profile DAO & multi-criteria search
│   │   ├── blood_request.py         # Transfusion request DAO & urgency sorting
│   │   ├── response.py              # Donor response & volunteer tracking DAO
│   │   └── message.py               # Contact inquiry & audit log DAOs
│   │
│   ├── routes/                      # Route Blueprints (Controllers)
│   │   ├── __init__.py              # Blueprint registration (register_blueprints)
│   │   ├── public.py                # Public routes (Home, Search, About, Contact)
│   │   ├── auth.py                  # Authentication routes (Login, Register, Logout)
│   │   ├── donor.py                 # Donor portal routes (Dashboard, Availability, History)
│   │   ├── patient.py               # Patient portal routes (Dashboard, Requests)
│   │   ├── requests.py              # Emergency request routes (Create, View, Volunteer)
│   │   └── admin.py                 # Admin routes (Control Center, Moderation)
│   │
│   ├── services/                    # Business Logic Layer
│   │   ├── __init__.py              # Service exports
│   │   ├── matching_service.py      # Biological ABO/Rh compatibility matrix
│   │   ├── donor_service.py         # 90-day cooldown interval & eligibility rules
│   │   └── auth_service.py          # Session management & @role_required decorators
│   │
│   ├── templates/                   # Reusable Jinja2 Templates
│   │   ├── base.html                # Master HTML5 layout
│   │   ├── partials/                # Reusable partials (navbar, footer, alerts)
│   │   ├── components/              # Structural UI components
│   │   ├── public/                  # Public views (index, search, about)
│   │   ├── auth/                    # Auth views (login, register)
│   │   ├── donor/                   # Donor portal views (dashboard)
│   │   ├── patient/                 # Patient views
│   │   ├── requests/                # Emergency request views (create)
│   │   ├── admin/                   # Admin views (dashboard)
│   │   └── errors/                  # Custom HTTP error pages (403, 404, 500)
│   │
│   └── static/                      # Static Assets
│       ├── css/                     # CSS stylesheets (main, components, dashboard, responsive)
│       ├── js/                      # Frontend JavaScript (main.js, Lucide init, toast alerts)
│       └── images/                  # Brand vectors and graphics
│
├── tests/                           # Automated Test Suite
│   ├── __init__.py
│   ├── test_factory.py              # Application factory & blueprint mounting tests
│   ├── test_matching.py             # ABO/Rh blood compatibility unit tests
│   └── test_donor_service.py        # Clinical donor eligibility unit tests
│
├── migrations/                      # Database Schema Migrations
│   ├── 001_initial_schema.sql       # Initial database DDL schema
│   └── README.md                    # Migration guide
│
├── preview/                         # Standalone HTML Previews (Zero dependency viewing)
│   ├── index.html                   # Home page static preview
│   ├── dashboard.html               # Donor dashboard static preview
│   ├── search.html                  # Donor search static preview
│   └── emergency-request.html       # Emergency request form preview
│
├── database/
│   └── schema.sql                   # Standalone DDL initialization script
│
├── .env.example                     # Environment configuration template
├── .gitignore                       # Git exclusions (venv, .env, pycache, OS files)
├── requirements.txt                 # Project dependencies
├── run.py                           # Application bootstrap and server entry point
├── test_db_connection.py            # Standalone safe MySQL diagnostic tool
└── README.md                        # Documentation
```

---

## 3. Separation of Concerns Architecture

1. **Models Layer (`app/models/`):**
   * Encapsulates all SQL execution.
   * Route functions **never** write raw SQL; they interact strictly through model methods (e.g. `Donor.search(...)`, `BloodRequest.create(...)`).
   * Guarantees 100% parameterized query execution (`%s`), completely preventing SQL injection.

2. **Services Layer (`app/services/`):**
   * Encapsulates domain logic independent of HTTP requests:
     * `matching_service.py`: Biological ABO and Rh(D) compatibility matrix.
     * `donor_service.py`: Evaluates the 90-day cooldown interval, age, and weight requirements.
     * `auth_service.py`: Enforces role-based route protection (`@login_required`, `@role_required`).

3. **Routes Layer (`app/routes/`):**
   * Modularized into dedicated Flask Blueprints:
     * `public_bp` (`/`, `/find-donors`, `/about`, `/contact`)
     * `auth_bp` (`/auth/login`, `/auth/register`, `/auth/logout`)
     * `donor_bp` (`/donor/dashboard`, `/donor/availability`, `/donor/history`)
     * `patient_bp` (`/patient/dashboard`)
     * `request_bp` (`/requests`, `/requests/new`, `/requests/<id>/volunteer`)
     * `admin_bp` (`/admin`, `/admin/donors/verify`)

---

## 4. Windows Setup & Running Instructions

### Step 1: Install Python 3.11+
Download from [python.org/downloads](https://www.python.org/downloads/) and ensure **"Add python.exe to PATH"** is checked.

### Step 2: Setup Virtual Environment & Install Dependencies
```powershell
cd d:\project
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Step 3: Configure Environment
```powershell
Copy-Item .env.example .env
```
Update `.env` with your MySQL credentials:
```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=lifelink_db
DB_USER=root
DB_PASSWORD=your_mysql_password
```

### Step 4: Apply Database Schema
```powershell
mysql -u root -p lifelink_db < migrations/001_initial_schema.sql
```

### Step 5: Test Database Connection
```powershell
python test_db_connection.py
```

### Step 6: Run Automated Tests
```powershell
pytest
# or using built-in unittest
python -m unittest discover tests
```

### Step 7: Launch LifeLink Server
```powershell
python run.py
```
Open in your browser:
* **Web Portal:** `http://127.0.0.1:5000/`
* **Health Check Endpoint:** `http://127.0.0.1:5000/health`
* **Static Preview (No server needed):** Open `d:\project\preview\index.html` directly in any web browser.

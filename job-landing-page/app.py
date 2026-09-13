"""
Job Landing Page + Admin Panel
================================
Flask + SQLite backend for an Arabic (RTL) job announcement landing page
with a protected admin panel that edits the page content (including the
WhatsApp group link) without touching any code.

Run:
    python app.py

See README.md for full setup / deployment instructions.
"""

import os
import sqlite3
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, g
)
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")

# NOTE: These are demo credentials only.
# Change ADMIN_USERNAME / ADMIN_PASSWORD via environment variables
# before deploying online. See README.md -> "Security before you deploy".
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
ADMIN_PASSWORD_HASH = generate_password_hash(ADMIN_PASSWORD)

# Flask secret key (used to sign the session cookie).
# Change this via the SECRET_KEY environment variable before deploying.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-this-before-production")

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY

# Default content used to seed the database on first run.
DEFAULT_SETTINGS = {
    "company_name": "YOUR COMPANY",
    "job_title": "خدمة عملاء / تيلي سيلز",
    "location": "القاهرة، مصر",
    "working_hours": "3:00 مساءً – 11:00 مساءً",
    "days_off": "السبت والأحد",
    "whatsapp_link": "https://chat.whatsapp.com/XXXXXXXX",
    "benefits": (
        "مرتب تنافسي + حوافز حسب الأداء\n"
        "عمولات حسب الأداء\n"
        "تدريب مدفوع\n"
        "فرص للتطور والترقي\n"
        "بيئة عمل احترافية"
    ),
    "requirements": (
        "مستوى جيد في اللغة الإنجليزية\n"
        "مهارات تواصل جيدة والعمل ضمن فريق\n"
        "شخصية إيجابية واحترافية\n"
        "القدرة على الالتزام بمواعيد العمل\n"
        "الخبرة ميزة إضافية حسب الوظيفة"
    ),
}

# Fields editable from the admin panel that must never be left empty.
REQUIRED_TEXT_FIELDS = [
    "company_name", "job_title", "location",
    "working_hours", "days_off",
]

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    """Return a request-scoped SQLite connection."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the settings table and seed default values if needed."""
    db = sqlite3.connect(DATABASE)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    db.commit()

    existing = {row[0] for row in db.execute("SELECT key FROM settings")}
    for key, value in DEFAULT_SETTINGS.items():
        if key not in existing:
            db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
    db.commit()
    db.close()


def get_settings():
    """Return all settings as a plain dict."""
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    settings = {row["key"]: row["value"] for row in rows}
    # Guard against a missing key (e.g. DB created by an older version).
    for key, default_value in DEFAULT_SETTINGS.items():
        settings.setdefault(key, default_value)
    return settings


def update_settings(new_values: dict):
    """Upsert a dict of key/value pairs into the settings table."""
    db = get_db()
    for key, value in new_values.items():
        db.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
    db.commit()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    settings = get_settings()
    benefits = [line.strip() for line in settings["benefits"].splitlines() if line.strip()]
    requirements = [line.strip() for line in settings["requirements"].splitlines() if line.strip()]
    return render_template(
        "index.html",
        settings=settings,
        benefits=benefits,
        requirements=requirements,
    )


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route("/admin")
@login_required
def admin_dashboard():
    settings = get_settings()
    return render_template("admin.html", settings=settings)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("logged_in"):
        return redirect(url_for("admin_dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("admin_dashboard"))

        error = "اسم المستخدم أو كلمة المرور غير صحيحة"

    return render_template("login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin/update", methods=["POST"])
@login_required
def admin_update():
    """AJAX endpoint: validates and saves the landing page content."""
    data = request.get_json(silent=True) or request.form

    values = {
        "company_name": (data.get("company_name") or "").strip(),
        "job_title": (data.get("job_title") or "").strip(),
        "location": (data.get("location") or "").strip(),
        "working_hours": (data.get("working_hours") or "").strip(),
        "days_off": (data.get("days_off") or "").strip(),
        "whatsapp_link": (data.get("whatsapp_link") or "").strip(),
        "benefits": (data.get("benefits") or "").strip(),
        "requirements": (data.get("requirements") or "").strip(),
    }

    errors = {}

    for field in REQUIRED_TEXT_FIELDS:
        if not values[field]:
            errors[field] = "هذا الحقل مطلوب"

    if not values["whatsapp_link"]:
        errors["whatsapp_link"] = "رابط جروب واتساب مطلوب"
    elif not values["whatsapp_link"].startswith("https://"):
        errors["whatsapp_link"] = "الرابط يجب أن يبدأ بـ https://"

    if not values["benefits"]:
        errors["benefits"] = "أضف ميزة واحدة على الأقل"

    if not values["requirements"]:
        errors["requirements"] = "أضف متطلب واحد على الأقل"

    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    update_settings(values)
    return jsonify({"success": True, "message": "تم حفظ التعديلات بنجاح"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

init_db()

if __name__ == "__main__":
    # debug=True is convenient for local development only.
    # Turn it off (or remove it) before deploying online.
    app.run(debug=True, use_reloader=False)

import hmac
import os
import re
import secrets
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import database, security

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Cybersecurity Lab - Password Hash Cracking Simulation", debug=False)

SESSION_SECRET = os.environ.get("SESSION_SECRET")
if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_hex(32)
    print(
        "[warning] SESSION_SECRET is not set. Using a random development-only key "
        "for this process. Sessions will not survive a restart, and every restart "
        "invalidates existing sessions. Set SESSION_SECRET in Codespaces Secrets "
        "for a real class deployment (see README.md)."
    )

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="lab_session",
    same_site="lax",
    https_only=os.environ.get("HTTPS_ONLY", "false").lower() == "true",
)

templates = Jinja2Templates(directory=BASE_DIR / "templates")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
STUDENT_ID_RE = re.compile(r"^[0-9]{5,20}$")
MAX_PASSWORD_LEN = 128
MAX_NAME_LEN = 100


@app.on_event("startup")
def on_startup() -> None:
    database.init_db()


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return PlainTextResponse(
        "An unexpected error occurred. Please contact the instructor.",
        status_code=500,
    )


def is_authenticated(request: Request) -> Optional[str]:
    return request.session.get("authenticated_username")


def is_admin(request: Request) -> bool:
    return bool(request.session.get("is_admin"))


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------

@app.get("/")
def root(request: Request):
    return RedirectResponse(url="/login", status_code=303)


@app.get("/login")
def login_form(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/success", status_code=303)
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": None, "username": ""}
    )


@app.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    generic_error = "Incorrect username or password. Please try again."

    username = username.strip()[:64]
    password = password[:MAX_PASSWORD_LEN]

    if not USERNAME_RE.match(username):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": generic_error, "username": username},
            status_code=401,
        )

    user = database.get_user_by_username(username)

    # Always exercise a hash+compare even for unknown usernames, using a fixed
    # dummy algorithm/hash, so response behavior doesn't hint whether the
    # username exists.
    if user is not None:
        valid = security.verify_password(password, user["password_hash"], user["hash_algorithm"])
    else:
        security.verify_password(password, "0" * 64, "sha256")
        valid = False

    if not valid:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": generic_error, "username": username},
            status_code=401,
        )

    request.session.clear()
    request.session["authenticated_username"] = user["username"]
    return RedirectResponse(url="/success", status_code=303)


# --------------------------------------------------------------------------
# Success / student submission
# --------------------------------------------------------------------------

@app.get("/success")
def success_page(request: Request):
    username = is_authenticated(request)
    if not username:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "success.html",
        {"request": request, "username": username, "error": None, "student_id": "", "student_name": ""},
    )


@app.post("/submit")
def submit_result(
    request: Request,
    student_id: str = Form(...),
    student_name: str = Form(...),
):
    username = is_authenticated(request)
    if not username:
        return RedirectResponse(url="/login", status_code=303)

    student_id = student_id.strip()
    student_name = student_name.strip()[:MAX_NAME_LEN]

    error = None
    if not STUDENT_ID_RE.match(student_id):
        error = "Student ID must be numeric (5-20 digits)."
    elif not student_name:
        error = "Full Name is required."

    if error:
        return templates.TemplateResponse(
            "success.html",
            {
                "request": request,
                "username": username,
                "error": error,
                "student_id": student_id,
                "student_name": student_name,
            },
            status_code=400,
        )

    try:
        database.create_submission(student_id, student_name, username)
    except sqlite3.IntegrityError:
        return templates.TemplateResponse(
            "success.html",
            {
                "request": request,
                "username": username,
                "error": "This Student ID has already submitted a result.",
                "student_id": student_id,
                "student_name": student_name,
            },
            status_code=409,
        )

    request.session.clear()
    return templates.TemplateResponse("result.html", {"request": request})


# --------------------------------------------------------------------------
# Admin / instructor view
# --------------------------------------------------------------------------

@app.get("/admin")
def admin_page(request: Request):
    if not is_admin(request):
        return templates.TemplateResponse(
            "admin.html", {"request": request, "authenticated": False, "error": None}
        )
    submissions = database.get_all_submissions()
    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "authenticated": True, "submissions": submissions},
    )


@app.post("/admin/login")
def admin_login(request: Request, admin_password: str = Form(...)):
    expected = os.environ.get("ADMIN_PASSWORD")

    if not expected:
        return templates.TemplateResponse(
            "admin.html",
            {
                "request": request,
                "authenticated": False,
                "error": "Admin login is not configured. Set ADMIN_PASSWORD on the server.",
            },
            status_code=503,
        )

    if not hmac.compare_digest(admin_password, expected):
        return templates.TemplateResponse(
            "admin.html",
            {"request": request, "authenticated": False, "error": "Incorrect admin password."},
            status_code=401,
        )

    request.session["is_admin"] = True
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/logout")
def admin_logout(request: Request):
    request.session.pop("is_admin", None)
    return RedirectResponse(url="/admin", status_code=303)

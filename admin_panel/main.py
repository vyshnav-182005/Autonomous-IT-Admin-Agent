"""
OpsPilot AI — Mock IT Admin Dashboard
FastAPI application serving the admin panel with Jinja2 templates.
"""

import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database.db import init_db, get_all_users, get_user_by_email, create_user, reset_password, disable_user, get_action_log

# ── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    yield


# ── App Setup ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="OpsPilot Admin Panel",
    description="Mock IT Administration Dashboard",
    lifespan=lifespan,
)

# Static files & templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect root to users page."""
    return RedirectResponse(url="/users", status_code=302)


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, q: str = "", message: str = "", msg_type: str = "success"):
    """
    Users listing page with optional search and flash messages.
    """
    users = await get_all_users(query=q if q else None)
    return templates.TemplateResponse("users.html", {
        "request": request,
        "users": users,
        "search_query": q,
        "message": message,
        "msg_type": msg_type,
    })


@app.get("/create-user", response_class=HTMLResponse)
async def create_user_page(request: Request, message: str = "", msg_type: str = ""):
    """Display create user form."""
    return templates.TemplateResponse("create_user.html", {
        "request": request,
        "message": message,
        "msg_type": msg_type,
    })


@app.post("/create-user", response_class=HTMLResponse)
async def handle_create_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
):
    """Handle create user form submission."""
    # Validation
    if not name.strip():
        return templates.TemplateResponse("create_user.html", {
            "request": request,
            "message": "Name is required.",
            "msg_type": "error",
        })

    if not email.strip() or "@" not in email:
        return templates.TemplateResponse("create_user.html", {
            "request": request,
            "message": "Please enter a valid email address.",
            "msg_type": "error",
        })

    if role not in ("Admin", "Employee"):
        return templates.TemplateResponse("create_user.html", {
            "request": request,
            "message": "Invalid role selected.",
            "msg_type": "error",
        })

    try:
        await create_user(name.strip(), email.strip().lower(), role)
        return RedirectResponse(
            url=f"/users?message=User+'{name.strip()}'+created+successfully&msg_type=success",
            status_code=302,
        )
    except ValueError as e:
        return templates.TemplateResponse("create_user.html", {
            "request": request,
            "message": str(e),
            "msg_type": "error",
        })


@app.post("/reset-password/{user_id}")
async def handle_reset_password(user_id: int):
    """Handle password reset for a user."""
    try:
        user = await reset_password(user_id)
        return RedirectResponse(
            url=f"/users?message=Password+reset+for+'{user['name']}'.+Temporary+password+sent.&msg_type=success",
            status_code=302,
        )
    except ValueError as e:
        return RedirectResponse(
            url=f"/users?message={str(e)}&msg_type=error",
            status_code=302,
        )


@app.post("/disable-user/{user_id}")
async def handle_disable_user(user_id: int):
    """Handle disabling a user account."""
    try:
        user = await disable_user(user_id)
        return RedirectResponse(
            url=f"/users?message=User+'{user['name']}'+has+been+disabled.&msg_type=success",
            status_code=302,
        )
    except ValueError as e:
        return RedirectResponse(
            url=f"/users?message={str(e)}&msg_type=error",
            status_code=302,
        )


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """View action log."""
    logs = await get_action_log()
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "logs": logs,
    })

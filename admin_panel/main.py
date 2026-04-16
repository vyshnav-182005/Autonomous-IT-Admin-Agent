"""
OpsPilot AI — Mock IT Admin Dashboard
FastAPI application serving the admin panel with Jinja2 templates.
"""

import sys
import os
import logging
import asyncio

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database.db import init_db, get_all_users, get_user_by_email, create_user, reset_password, disable_user, delete_user, get_action_log
from config import config
from agent.llm_wrapper import LLMWrapper
from agent.browser_controller import BrowserController
from agent.agent import OpsPilotAgent

logger = logging.getLogger("opspilot.admin")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

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


@app.post("/delete-user/{user_id}")
async def handle_delete_user(user_id: int):
    """Handle permanent deletion of a user account."""
    try:
        user = await delete_user(user_id)
        return RedirectResponse(
            url=f"/users?message=User+'{user['name']}'+has+been+deleted.&msg_type=success",
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


def get_llm() -> LLMWrapper:
    """Initialize the LLM wrapper based on config."""
    provider = config.LLM_PROVIDER

    if provider == "openai":
        api_key = config.OPENAI_API_KEY
        model = config.OPENAI_MODEL
        if not api_key or api_key.startswith("sk-your"):
            raise ValueError("OPENAI_API_KEY is not set. Please configure it in .env.")
    elif provider == "anthropic":
        api_key = config.ANTHROPIC_API_KEY
        model = config.ANTHROPIC_MODEL
        if not api_key or api_key.startswith("sk-ant-your"):
            raise ValueError("ANTHROPIC_API_KEY is not set. Please configure it in .env.")
    else:
        raise ValueError(f"Unknown LLM provider: '{provider}'")

    return LLMWrapper(provider=provider, api_key=api_key, model=model)


async def _execute_agent_tasks_async(tasks: list[str], use_headless: bool) -> list[dict]:
    """Execute tasks through one browser session and return per-task results."""
    llm = get_llm()
    browser = BrowserController()
    results = []

    try:
        await browser.start(headless=use_headless)
        agent = OpsPilotAgent(
            llm=llm,
            browser=browser,
            admin_url=config.ADMIN_PANEL_URL,
            max_iterations=config.AGENT_MAX_ITERATIONS,
        )

        for task in tasks:
            result = await agent.execute_task(task)
            results.append({
                "task": task,
                "success": bool(result.get("success")),
                "message": result.get("message", "No message"),
                "iterations": result.get("iterations", 0),
            })
    finally:
        await browser.stop()

    return results


def _execute_agent_tasks_sync(tasks: list[str], use_headless: bool) -> list[dict]:
    """
    Run async Playwright execution in a dedicated loop.
    On Windows, force a Proactor loop because Playwright needs subprocess support.
    """
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_execute_agent_tasks_async(tasks, use_headless))
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
            asyncio.set_event_loop(None)

    return asyncio.run(_execute_agent_tasks_async(tasks, use_headless))


@app.get("/agent-tasks", response_class=HTMLResponse)
async def agent_tasks_page(request: Request, message: str = "", msg_type: str = ""):
    """Display the agent task runner page."""
    return templates.TemplateResponse("agent_tasks.html", {
        "request": request,
        "message": message,
        "msg_type": msg_type,
        "task_input": "",
        "results": [],
        "executed_count": 0,
        "headless": config.AGENT_HEADLESS,
    })


@app.post("/agent-tasks", response_class=HTMLResponse)
async def run_agent_tasks(
    request: Request,
    task_input: str = Form(...),
    headless: str = Form("false"),
):
    """Execute one or more natural-language tasks via the autonomous agent."""
    tasks = [line.strip() for line in task_input.splitlines() if line.strip()]
    use_headless = headless.lower() == "true"

    if not tasks:
        return templates.TemplateResponse("agent_tasks.html", {
            "request": request,
            "message": "Please enter at least one task.",
            "msg_type": "error",
            "task_input": task_input,
            "results": [],
            "executed_count": 0,
            "headless": use_headless,
        })

    try:
        results = await run_in_threadpool(_execute_agent_tasks_sync, tasks, use_headless)
    except ValueError as e:
        return templates.TemplateResponse("agent_tasks.html", {
            "request": request,
            "message": str(e),
            "msg_type": "error",
            "task_input": task_input,
            "results": [],
            "executed_count": 0,
            "headless": use_headless,
        })

    except Exception as e:
        logger.exception("Agent task execution failed")
        results = [{
            "task": "System",
            "success": False,
            "message": f"Execution failed: {e}",
            "iterations": 0,
        }]

    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)
    if success_count == total_count:
        message = f"All {total_count} task(s) completed successfully."
        msg_type = "success"
    elif success_count == 0:
        message = "No tasks completed successfully."
        msg_type = "error"
    else:
        message = f"Completed {success_count} of {total_count} task(s)."
        msg_type = "error"

    return templates.TemplateResponse("agent_tasks.html", {
        "request": request,
        "message": message,
        "msg_type": msg_type,
        "task_input": task_input,
        "results": results,
        "executed_count": total_count,
        "headless": use_headless,
    })

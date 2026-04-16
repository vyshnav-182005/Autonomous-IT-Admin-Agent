# ⚡ OpsPilot AI — Autonomous IT Admin Agent

An AI agent that takes natural language IT support requests and executes them by **interacting with a mock admin panel via browser automation** — not via APIs. The agent visibly navigates pages, clicks buttons, fills forms, and reads page content just like a human operator.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     User (CLI / REPL)                        │
│          "Reset password for john@company.com"               │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    AI Agent (agent.py)                       │
│                                                              │
│  1. Parse Intent ────► LLM Wrapper ────► OpenAI / Claude     │
│  2. Generate Plan     (planner.py)                           │
│  3. Agent Loop:                                              │
│     👁 Observe ──► 🤔 Decide (LLM) ──► 🖱 Act ──► 🔁 Repeat |
│                                                              │
│  browser_controller.py (Playwright)                          │
└─────────────────────────┬────────────────────────────────────┘
                          │ Browser Automation
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                Admin Panel (FastAPI + Jinja2)                │
│                                                              │
│  /users          ──► User table with actions                 │
│  /create-user    ──► Create user form                        │
│  /logs           ──► Action history                          │
│  SQLite DB       ──► Persistent storage                      │
└──────────────────────────────────────────────────────────────┘
```

### Agent Loop (Observe → Decide → Act)

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│ OBSERVE │────►│ DECIDE  │────►│   ACT   │──┐
│ (Page)  │     │ (LLM)   │     │(Browser)│  │
└─────────┘     └─────────┘     └─────────┘  │
     ▲                                        │
     └────────────────────────────────────────┘
                    Repeat until done
```

---

## 📋 Supported Tasks

| Task | Example Prompt |
|------|---------------|
| 🔑 Reset Password | `"Reset password for john@company.com"` |
| ➕ Create User | `"Create a new user jane@company.com as admin"` |
| 🚫 Disable User | `"Disable user mark@company.com"` |
| 🔄 Smart (Bonus) | `"If sarah@company.com exists, reset password, otherwise create her"` |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Jinja2 |
| Database | SQLite (aiosqlite) |
| Browser Automation | Playwright |
| LLM | OpenAI / Anthropic (modular) |
| Logging | Rich (colored console) |
| Frontend | HTML + Vanilla CSS + JS |

---

## 🚀 Setup

### Prerequisites

- **Python 3.10+**
- **API Key**: OpenAI (`gpt-4o-mini`) or Anthropic (`claude-sonnet`) API key

### 1. Clone & Install

```bash
# Clone the repository
git clone https://github.com/your-username/Autonomous-IT-Admin-Agent.git
cd Autonomous-IT-Admin-Agent

# Create virtual environment
python -m venv venv
source venv/bin/activate     # Linux/macOS
venv\Scripts\activate        # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Configure Environment

```bash
# Copy the example env file
cp .env.example .env

# Edit .env with your API key
# Set OPENAI_API_KEY=sk-your-actual-key
# Or set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY=sk-ant-your-key
```

---

## ▶️ Running

### Step 1: Start the Admin Panel

```bash
python run_admin.py
```

The admin panel will be available at [http://localhost:8000](http://localhost:8000).

### Step 2: Run the Agent

**Single task:**
```bash
python run_agent.py --task "Reset password for john@company.com"
```

**Interactive mode:**
```bash
python run_agent.py
```

Then type tasks at the `opspilot>` prompt.

**Headless mode (no visible browser):**
```bash
python run_agent.py --headless --task "Create user test@company.com as Employee"
```

### Step 3: Run Tasks from the Admin UI

Open **Agent Tasks** in the top navigation (`/agent-tasks`), then:

1. Enter one natural-language task per line
2. Choose visible or headless browser mode
3. Click **Run Tasks**

The page executes tasks sequentially and shows per-task status, message, and iteration count.

---

## 📁 Project Structure

```
Autonomous-IT-Admin-Agent/
├── admin_panel/                 # Mock IT Admin Dashboard
│   ├── main.py                  # FastAPI application & routes
│   ├── static/
│   │   ├── styles.css           # Dark admin theme
│   │   └── app.js               # Client-side interactions
│   └── templates/
│       ├── base.html            # Base layout template
│       ├── users.html           # Users listing page
│       ├── create_user.html     # Create user form
│       ├── logs.html            # Action log viewer
│       └── agent_tasks.html     # Agent task runner UI
│
├── agent/                       # AI Agent
│   ├── agent.py                 # Core agent loop (observe→decide→act)
│   ├── planner.py               # Intent parser & plan generator
│   ├── browser_controller.py    # Playwright browser automation
│   └── llm_wrapper.py           # Modular OpenAI/Anthropic wrapper
│
├── database/                    # Data Layer
│   ├── db.py                    # SQLite operations & seed data
│   └── models.py                # Pydantic data models
│
├── config.py                    # Central configuration
├── run_admin.py                 # Start admin panel
├── run_agent.py                 # Start agent (CLI/REPL)
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variable template
└── README.md                    # This file
```

---

## 📊 Logging

The agent produces detailed, color-coded logs at every stage:

```
🤔 Thinking: Parsing intent from "Reset password for john@company.com"
🎯 Intent: {"action": "reset_password", "email": "john@company.com"}
📋 Plan: 1) Navigate to users page  2) Search for user  3) Click reset
👁️ Observing: URL=/users, 5 users visible
🖱️ Action: Clicking 'reset-btn-john@company.com'
✅ Result: Password reset for 'John Doe'. Temporary password sent.
```

---

## 🔑 Key Design Decisions

1. **Browser-first**: The agent NEVER calls backend APIs directly. All actions go through the browser, simulating a real human operator.

2. **data-testid attributes**: Every interactive element has a `data-testid` for reliable element targeting by the agent.

3. **LLM-driven decisions**: The agent uses an LLM at two points:
   - **Intent parsing**: Convert natural language → structured intent
   - **Action selection**: Given page state + goal → next browser action

4. **Modular LLM wrapper**: Swap between OpenAI and Anthropic with a single config change.

5. **Confirmation dialogs**: Destructive actions (reset/disable) require confirmation, which the agent handles automatically.

---

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.

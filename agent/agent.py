"""
OpsPilot AI — Core Agent
Autonomous agent loop: Observe → Decide (LLM) → Act → Repeat
Executes IT admin tasks by interacting with the admin panel via browser automation.
"""

import json
import asyncio
import logging
from typing import Optional
from agent.llm_wrapper import LLMWrapper
from agent.planner import Planner
from agent.browser_controller import BrowserController

logger = logging.getLogger("opspilot.agent")

# ── Agent System Prompt ─────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """You are an autonomous IT admin agent controlling a web browser. You interact with an IT admin panel to complete tasks like resetting passwords, creating users, disabling accounts, and deleting users.

You receive:
1. The current GOAL (what you need to accomplish)
2. The current PLAN (step-by-step breakdown)
3. The current PAGE STATE (what's visible on the page)
4. ACTION HISTORY (what you've already done)

You must respond with ONLY a JSON object describing your next action. Available actions:

1. Navigate to a page:
   {"action": "navigate", "url": "/users"}
   {"action": "navigate", "url": "/create-user"}

2. Click a button or link by visible text:
   {"action": "click", "target": "Create User"}
   {"action": "click", "target": "Search"}
   {"action": "click", "target": "Run Tasks"}

3. Click a user-row action by email + button text:
   {"action": "row_action", "email": "john@company.com", "button": "Reset Password"}
   {"action": "row_action", "email": "mark@company.com", "button": "Disable"}
   {"action": "row_action", "email": "mark@company.com", "button": "Delete"}

4. Fill an input field by field label/name:
   {"action": "fill", "target": "Full Name", "value": "John Doe"}
   {"action": "fill", "target": "Email Address", "value": "john@company.com"}
   {"action": "fill", "target": "Search", "value": "john@company.com"}

5. Select dropdown option:
   {"action": "select", "target": "Role", "value": "Admin"}

6. Confirm a modal dialog:
   {"action": "confirm_modal"}

7. Task complete:
   {"action": "done", "result": "success", "message": "Password reset successfully"}
   {"action": "done", "result": "failure", "message": "User not found"}

Rules:
- Respond with ONLY a JSON object. No extra text.
- Interact like a human: use visible labels, button text, and row context (email text).
- For reset_password/disable_user/delete_user: navigate to /users, search for the user, then click the appropriate button.
- For create_user: navigate to /create-user, fill the form, and submit.
- After clicking a destructive button (reset/disable/delete), a confirmation modal will appear — you must confirm it.
- After form submission or button click, check for flash messages to verify success.
- If a flash message contains "success" or "created" or "reset" or "disabled" or "deleted", the task is done.
- If the user is not found, report failure.
- Take the most direct path to complete the task.
"""


class OpsPilotAgent:
    """
    Autonomous IT admin agent that uses browser automation
    to complete tasks on the admin panel.
    """

    def __init__(
        self,
        llm: LLMWrapper,
        browser: BrowserController,
        admin_url: str = "http://localhost:8000",
        max_iterations: int = 15,
    ):
        self.llm = llm
        self.browser = browser
        self.planner = Planner(llm)
        self.admin_url = admin_url.rstrip("/")
        self.max_iterations = max_iterations

    async def execute_task(self, user_input: str) -> dict:
        """
        Main entry point. Takes a natural language request and executes it.

        Args:
            user_input: Natural language IT support request.

        Returns:
            Result dict with 'success', 'message', and 'actions_taken'.
        """
        logger.info("=" * 60)
        logger.info(f"📝 New Task: \"{user_input}\"")
        logger.info("=" * 60)

        # Phase 1: Parse Intent
        try:
            intent = self.planner.parse_intent(user_input)
        except Exception as e:
            logger.error(f"❌ Failed to parse intent: {e}")
            return {"success": False, "message": f"Failed to understand request: {e}", "actions_taken": []}

        # Phase 2: Generate Plan
        plan = self.planner.generate_plan(intent)
        goal = self._describe_goal(intent)

        # Phase 3: Execute via Agent Loop
        result = await self._agent_loop(goal, plan, intent)

        logger.info("=" * 60)
        if result["success"]:
            logger.info(f"✅ Task completed: {result['message']}")
        else:
            logger.error(f"❌ Task failed: {result['message']}")
        logger.info("=" * 60)

        return result

    async def _agent_loop(self, goal: str, plan: list[str], intent: dict) -> dict:
        """
        Core agent loop: Observe → Decide → Act → Repeat.

        Args:
            goal: Human-readable goal description.
            plan: Step-by-step plan.
            intent: Structured intent dict.

        Returns:
            Result dict.
        """
        action_history = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"\n--- Iteration {iteration}/{self.max_iterations} ---")

            # Step 1: OBSERVE
            logger.info("👁️  Observing page state...")
            observation = await self._observe()
            logger.info(f"   URL: {observation['url']}")
            if "flash_message" in observation:
                logger.info(f"   Flash: {observation['flash_message']}")
            if "user_count" in observation:
                logger.info(f"   Users visible: {observation['user_count']}")

            # Step 2: DECIDE
            logger.info("🤔 Thinking: Deciding next action...")
            try:
                decision = await self._decide(observation, goal, plan, action_history, intent)
            except Exception as e:
                logger.error(f"❌ Decision error: {e}")
                action_history.append({"action": "error", "error": str(e)})
                continue

            action_type = decision.get("action", "unknown")
            logger.info(f"🎯 Decision: {json.dumps(decision)}")

            # Step 3: CHECK IF DONE
            if action_type == "done":
                result_status = decision.get("result", "unknown")
                message = decision.get("message", "Task completed")
                return {
                    "success": result_status == "success",
                    "message": message,
                    "actions_taken": action_history,
                    "iterations": iteration,
                }

            # Step 4: ACT
            try:
                await self._act(decision)
                action_history.append(decision)
                logger.info(f"✅ Action executed: {action_type}")
            except Exception as e:
                logger.error(f"❌ Action failed: {e}")
                action_history.append({"action": action_type, "error": str(e)})

            # Brief pause for UI to update
            await self.browser.wait_short(300)

        # Max iterations reached
        return {
            "success": False,
            "message": f"Max iterations ({self.max_iterations}) reached without completing the task.",
            "actions_taken": action_history,
            "iterations": iteration,
        }

    async def _observe(self) -> dict:
        """Get the current page state as a structured snapshot."""
        try:
            return await self.browser.get_page_snapshot()
        except Exception as e:
            logger.error(f"Observation error: {e}")
            return {"url": await self.browser.get_current_url(), "error": str(e)}

    async def _decide(
        self,
        observation: dict,
        goal: str,
        plan: list[str],
        history: list[dict],
        intent: dict,
    ) -> dict:
        """
        Use the LLM to decide the next action based on the current state.
        """
        # Build context for the LLM
        context = f"""## GOAL
{goal}

## INTENT
{json.dumps(intent, indent=2)}

## PLAN
{chr(10).join(f'{i+1}. {s}' for i, s in enumerate(plan))}

## CURRENT PAGE STATE
{json.dumps(observation, indent=2)}

## ACTION HISTORY (what you've already done)
{json.dumps(history[-5:], indent=2) if history else "No actions taken yet."}

Based on the current state and goal, what is your next action? Respond with ONLY a JSON object."""

        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        return self.llm.chat_json(messages, temperature=0.1)

    async def _act(self, decision: dict):
        """
        Execute a browser action based on the LLM's decision.

        Args:
            decision: Action dict from the LLM.
        """
        action = decision.get("action", "")

        if action == "navigate":
            url = decision.get("url", "/users")
            if url.startswith("/"):
                url = self.admin_url + url
            await self.browser.navigate(url)

        elif action == "click":
            target = decision.get("target", "")
            await self.browser.click(target)

        elif action == "row_action":
            email = decision.get("email", "")
            button = decision.get("button", "")
            await self.browser.click_user_row_action(email, button)

        elif action == "fill":
            target = decision.get("target", "")
            value = decision.get("value", "")
            await self.browser.fill(target, value)

        elif action == "select":
            target = decision.get("target", "")
            value = decision.get("value", "")
            await self.browser.select_option(target, value)

        elif action == "confirm_modal":
            await self.browser.click_confirm_modal()

        elif action == "submit":
            target = decision.get("target", "")
            await self.browser.submit_form(target)

        elif action == "wait":
            ms = decision.get("ms", 500)
            await self.browser.wait_short(ms)

        elif action == "screenshot":
            path = decision.get("path", "screenshot.png")
            await self.browser.screenshot(path)

        else:
            raise ValueError(f"Unknown action: '{action}'")

    @staticmethod
    def _describe_goal(intent: dict) -> str:
        """Convert an intent dict into a human-readable goal description."""
        action = intent.get("action", "unknown")
        email = intent.get("email", "unknown")

        if action == "reset_password":
            return f"Reset the password for user with email '{email}'"
        elif action == "create_user":
            name = intent.get("name", "Unknown")
            role = intent.get("role", "Employee")
            return f"Create a new user: name='{name}', email='{email}', role='{role}'"
        elif action == "disable_user":
            return f"Disable the user account with email '{email}'"
        elif action == "delete_user":
            return f"Permanently delete the user account with email '{email}'"
        elif action == "ensure_user":
            return f"If user '{email}' exists, reset their password. Otherwise, create the user."
        else:
            return f"Perform '{action}' for '{email}'"

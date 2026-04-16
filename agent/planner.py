"""
OpsPilot AI — Intent Planner
Parses natural language into structured intents and generates step-by-step plans.
"""

import json
import logging
import re
from agent.llm_wrapper import LLMWrapper

logger = logging.getLogger("opspilot.planner")

# ── System Prompts ──────────────────────────────────────────────

INTENT_SYSTEM_PROMPT = """You are an IT operations assistant. Your job is to parse natural language IT support requests into structured JSON intents.

You MUST respond with ONLY a valid JSON object (no extra text, no markdown fences).

Supported actions and their required fields:

1. reset_password — Reset a user's password
   Required: email
   Example: {"action": "reset_password", "email": "john@company.com"}

2. create_user — Create a new user account
   Required: email, name, role (Admin or Employee)
   Example: {"action": "create_user", "email": "jane@company.com", "name": "Jane Doe", "role": "Admin"}

3. disable_user — Disable a user's account
   Required: email
   Example: {"action": "disable_user", "email": "mark@company.com"}

4. ensure_user — Check if user exists; if yes reset password, if not create them
   Required: email, name (optional), role (optional, default Employee)
   Example: {"action": "ensure_user", "email": "sarah@company.com", "name": "Sarah Connor", "role": "Employee"}

Rules:
- Extract the email address from the input. If only a name is given, infer the email as firstname@company.com.
- For create_user, if no name is given, infer from the email prefix.
- For create_user, if no role is given, default to "Employee".
- If the request says something like "if user exists, reset password, otherwise create", use "ensure_user".
- Always lowercase the email.
- ONLY return the JSON object, nothing else.
"""


PLAN_TEMPLATES = {
    "reset_password": [
        "Navigate to the users page",
        "Search for user with email '{email}'",
        "Locate the user row for '{email}'",
        "Click the 'Reset Password' button for that user",
        "Handle confirmation dialog if present",
        "Verify success message appears",
    ],
    "create_user": [
        "Navigate to the create user page",
        "Fill in the name field with '{name}'",
        "Fill in the email field with '{email}'",
        "Select the role '{role}' from the dropdown",
        "Click the submit button",
        "Verify success message appears",
    ],
    "disable_user": [
        "Navigate to the users page",
        "Search for user with email '{email}'",
        "Locate the user row for '{email}'",
        "Click the 'Disable' button for that user",
        "Handle confirmation dialog if present",
        "Verify success message appears",
    ],
    "ensure_user": [
        "Navigate to the users page",
        "Search for user with email '{email}'",
        "Check if the user exists in the table",
        "IF user exists: click 'Reset Password' and handle confirmation",
        "IF user does NOT exist: navigate to create user page and create them",
        "Verify success message appears",
    ],
}


class Planner:
    """Parses natural language into intents and generates execution plans."""

    def __init__(self, llm: LLMWrapper):
        self.llm = llm

    def parse_intent(self, user_input: str) -> dict:
        """
        Parse a natural language IT request into a structured intent.

        Args:
            user_input: Natural language request string.

        Returns:
            Dict with 'action' and action-specific fields.
        """
        logger.info(f"🤔 Thinking: Parsing intent from → \"{user_input}\"")

        messages = [
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ]

        raw_intent = self.llm.chat_json(messages)
        intent = self._normalize_intent(raw_intent, user_input)
        logger.info(f"🎯 Intent parsed: {json.dumps(intent, indent=2)}")
        return intent

    def generate_plan(self, intent: dict) -> list[str]:
        """
        Generate a step-by-step plan for executing the given intent.

        Args:
            intent: Structured intent dict from parse_intent().

        Returns:
            List of step description strings.
        """
        action = intent.get("action", "")
        template = PLAN_TEMPLATES.get(action)

        if not template:
            logger.warning(f"No plan template for action '{action}', using generic plan")
            return [
                "Navigate to the users page",
                f"Perform '{action}' action",
                "Verify result",
            ]

        # Fill template with intent values
        plan = []
        for step in template:
            try:
                filled = step.format(**intent)
            except KeyError:
                filled = step
            plan.append(filled)

        logger.info("📋 Plan generated:")
        for i, step in enumerate(plan, 1):
            logger.info(f"   {i}. {step}")

        return plan

    def _normalize_intent(self, intent: dict, user_input: str) -> dict:
        """Normalize and backfill intent fields so downstream steps always have required values."""
        if not isinstance(intent, dict):
            raise ValueError("Intent must be a JSON object.")

        normalized = dict(intent)
        action = str(normalized.get("action", "")).strip().lower()

        if not action:
            text = user_input.lower()
            if "create" in text and "user" in text:
                action = "create_user"
            elif "reset" in text and "password" in text:
                action = "reset_password"
            elif "disable" in text and "user" in text:
                action = "disable_user"
            elif "if" in text and "exists" in text and "create" in text:
                action = "ensure_user"

        normalized["action"] = action

        email = self._extract_email(user_input) or str(normalized.get("email", "")).strip().lower()
        name = str(normalized.get("name", "")).strip() or self._extract_name(user_input)
        role = str(normalized.get("role", "")).strip() or "Employee"
        role = "Admin" if role.lower() == "admin" else "Employee"

        if action in ("create_user", "ensure_user"):
            if not email and name:
                first_name = name.split()[0].lower()
                email = f"{first_name}@company.com"
            if not name and email:
                name = self._name_from_email(email)
            if not email or not name:
                raise ValueError("Could not infer required user details (name/email) for user creation.")
            normalized["email"] = email.lower()
            normalized["name"] = name
            normalized["role"] = role
            return normalized

        if action in ("reset_password", "disable_user"):
            if not email and name:
                first_name = name.split()[0].lower()
                email = f"{first_name}@company.com"
            if not email:
                raise ValueError("Could not infer user email for this action.")
            normalized["email"] = email.lower()
            return normalized

        if action:
            return normalized

        raise ValueError("Could not determine requested action.")

    @staticmethod
    def _extract_email(text: str) -> str:
        match = re.search(r"\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b", text)
        return match.group(1).lower() if match else ""

    @staticmethod
    def _extract_name(text: str) -> str:
        lower_text = text.lower()
        patterns = [
            r"\bnamed\s+([a-z][a-z\s'.-]*)$",
            r"\bname\s+is\s+([a-z][a-z\s'.-]*)$",
            r"\buser\s+named\s+([a-z][a-z\s'.-]*)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, lower_text)
            if match:
                raw_name = match.group(1).strip(" .,!?:;")
                if raw_name:
                    return " ".join(part.capitalize() for part in raw_name.split())
        return ""

    @staticmethod
    def _name_from_email(email: str) -> str:
        local_part = email.split("@", 1)[0]
        tokens = re.split(r"[._-]+", local_part)
        tokens = [t for t in tokens if t]
        if not tokens:
            return "Unknown User"
        return " ".join(token.capitalize() for token in tokens)

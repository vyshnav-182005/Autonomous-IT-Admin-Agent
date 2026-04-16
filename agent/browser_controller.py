"""
OpsPilot AI — Browser Controller
Playwright-based browser automation for interacting with the admin panel.
All agent actions are performed through this controller — no direct API calls.
"""

import asyncio
import logging
import re
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

logger = logging.getLogger("opspilot.browser")


class BrowserController:
    """
    High-level browser automation controller built on Playwright.
    Provides methods for navigation, clicking, filling forms, and reading page content.
    """

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._page

    async def start(self, headless: bool = False):
        """Launch the browser and open a new page."""
        logger.info(f"🌐 Starting browser (headless={headless})")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
        )
        self._page = await self._context.new_page()

        # Handle dialog boxes (confirms, alerts)
        self._page.on("dialog", self._handle_dialog)
        self._pending_dialog = None
        logger.info("✅ Browser started successfully")

    async def stop(self):
        """Close the browser and clean up resources."""
        logger.info("🔒 Closing browser")
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

    async def _handle_dialog(self, dialog):
        """Auto-accept dialogs (confirmation modals)."""
        logger.info(f"💬 Dialog detected: '{dialog.message}' — accepting")
        self._pending_dialog = dialog.message
        await dialog.accept()

    # ── Navigation ────────────────────────────────────────────────

    async def navigate(self, url: str):
        """Navigate to a URL."""
        logger.info(f"🔗 Navigating to: {url}")
        await self.page.goto(url, wait_until="domcontentloaded")
        await self.page.wait_for_load_state("networkidle")
        logger.info(f"📄 Page loaded: {self.page.url}")

    async def get_current_url(self) -> str:
        """Get the current page URL."""
        return self.page.url

    # ── Page Content ──────────────────────────────────────────────

    async def get_page_text(self) -> str:
        """Get all visible text on the page."""
        return await self.page.inner_text("body")

    async def get_page_title(self) -> str:
        """Get the page title."""
        return await self.page.title()

    async def get_page_snapshot(self) -> dict:
        """
        Get a structured snapshot of the page for the LLM.
        Returns information about forms, buttons, tables, and messages.
        """
        snapshot = {
            "url": self.page.url,
            "title": await self.page.title(),
        }

        # Flash messages
        flash = await self.page.query_selector(".flash-message")
        if flash:
            snapshot["flash_message"] = await flash.inner_text()

        # Table data (human-readable extraction, no test-id dependency)
        rows = await self.page.query_selector_all("table tbody tr")
        if rows:
            users = []
            for row in rows:
                cells = await row.query_selector_all("td")
                if len(cells) >= 4:
                    name_text = await cells[0].inner_text()
                    email_text = await cells[1].inner_text()
                    role_text = await cells[2].inner_text()
                    status_text = await cells[3].inner_text()
                    users.append({
                        "email": email_text.strip(),
                        "name": name_text.strip().split("\n")[-1].strip(),
                        "role": role_text.strip(),
                        "status": status_text.strip(),
                    })
            if users:
                snapshot["users_table"] = users
                snapshot["user_count"] = len(users)

        # Form fields
        forms = await self.page.query_selector_all("form")
        if forms:
            form_info = []
            for form in forms:
                action = await form.get_attribute("action") or ""
                labels = await form.query_selector_all("label")
                label_texts = [((await label.inner_text()).strip()) for label in labels]
                inputs = await form.query_selector_all("input, select")
                fields = []
                for inp in inputs:
                    inp_type = await inp.get_attribute("type") or "text"
                    inp_name = await inp.get_attribute("name") or ""
                    placeholder = await inp.get_attribute("placeholder") or ""
                    if inp_name and inp_type != "hidden":
                        fields.append({"name": inp_name, "type": inp_type, "placeholder": placeholder})
                if fields or label_texts:
                    form_info.append({"action": action, "labels": label_texts, "fields": fields})
            snapshot["forms"] = form_info

        # Buttons and links by visible text
        buttons = await self.page.query_selector_all("button, a.btn")
        btn_list = []
        for btn in buttons:
            text = await btn.inner_text()
            disabled = await btn.is_disabled()
            normalized = re.sub(r"\s+", " ", text).strip()
            if normalized:
                btn_list.append({"text": normalized, "disabled": disabled})
        if btn_list:
            snapshot["buttons"] = btn_list

        # Confirmation modal
        modal = await self.page.query_selector(".modal-overlay")
        if modal:
            snapshot["confirmation_modal_visible"] = True

        return snapshot

    # ── Interactions ──────────────────────────────────────────────

    async def click(self, target: str):
        """
        Click an element by visible button/link/text.

        Args:
            target: Visible text to click.
        """
        logger.info(f"🖱️  Clicking: {target}")

        # Try button by accessible name
        try:
            await self.page.get_by_role("button", name=target, exact=False).first.click()
            await asyncio.sleep(0.3)
            return
        except Exception:
            pass

        # Try link by accessible name
        try:
            await self.page.get_by_role("link", name=target, exact=False).first.click()
            await asyncio.sleep(0.3)
            return
        except Exception:
            pass

        # Fallback by visible text
        try:
            await self.page.get_by_text(target, exact=False).first.click()
            await asyncio.sleep(0.3)
            return
        except Exception:
            pass

        raise ValueError(f"Could not find element to click: '{target}'")

    async def fill(self, field: str, value: str):
        """
        Fill an input field by semantic field description (label/name/placeholder).

        Args:
            field: field descriptor such as "Name", "Email", or "Search".
            value: Text to type into the field.
        """
        logger.info(f"⌨️  Filling '{field}' with: {value}")

        # Try associated label first
        try:
            locator = self.page.get_by_label(field, exact=False).first
            await locator.fill(value)
            await asyncio.sleep(0.15)
            return
        except Exception:
            pass

        field_key = field.strip().lower()
        if "name" in field_key:
            selector = "input[name='name']"
        elif "email" in field_key:
            selector = "input[name='email']"
        elif "search" in field_key or field_key == "q":
            selector = "input[name='q']"
        else:
            selector = f"input[placeholder*='{field}']"

        element = await self.page.query_selector(selector)
        if not element:
            raise ValueError(f"Could not find input field: '{field}'")

        await element.scroll_into_view_if_needed()
        await element.fill(value)
        await asyncio.sleep(0.15)

    async def select_option(self, field: str, value: str):
        """
        Select an option from a dropdown by label/name.

        Args:
            field: select field descriptor, e.g. "Role".
            value: The option value to select.
        """
        logger.info(f"📋 Selecting '{value}' in '{field}'")

        try:
            locator = self.page.get_by_label(field, exact=False).first
            await locator.select_option(value=value)
            await asyncio.sleep(0.15)
            return
        except Exception:
            pass

        field_key = field.strip().lower()
        selector = "select[name='role']" if "role" in field_key else "select"
        element = await self.page.query_selector(selector)
        if not element:
            raise ValueError(f"Could not find select field: '{field}'")

        await element.select_option(value=value)
        await asyncio.sleep(0.15)

    async def submit_form(self, button_text: str):
        """
        Submit a form by clicking a visible submit button.

        Args:
            button_text: Visible text on submit button.
        """
        logger.info(f"📨 Submitting form via: {button_text}")
        await self.click(button_text)
        await self.page.wait_for_load_state("networkidle")

    async def click_confirm_modal(self):
        """Click the confirm button in a confirmation modal."""
        logger.info("✅ Confirming modal dialog")
        try:
            await self.page.get_by_role("button", name="Confirm", exact=False).first.click()
            await self.page.wait_for_load_state("networkidle")
        except Exception:
            logger.warning("No confirmation modal found")

    async def click_user_row_action(self, email: str, button_text: str):
        """
        Click an action button inside a specific user row, identified by email text.
        This mimics how a human locates a row then clicks its action.
        """
        logger.info(f"🧭 Row action: email='{email}', button='{button_text}'")
        row = self.page.locator("table tbody tr").filter(has=self.page.get_by_text(email, exact=True)).first
        if await row.count() == 0:
            raise ValueError(f"Could not find user row for email: '{email}'")

        button = row.get_by_role("button", name=button_text, exact=False).first
        if await button.count() == 0:
            raise ValueError(f"Could not find '{button_text}' button for '{email}'")

        await button.click()
        await asyncio.sleep(0.3)

    # ── Waiting & Verification ────────────────────────────────────

    async def wait_for_text(self, text: str, timeout: int = 5000) -> bool:
        """
        Wait for specific text to appear on the page.

        Args:
            text: Text to wait for.
            timeout: Maximum wait time in milliseconds.

        Returns:
            True if text appeared, False if timed out.
        """
        try:
            await self.page.wait_for_selector(f"text={text}", timeout=timeout)
            logger.info(f"✅ Text found: '{text}'")
            return True
        except Exception:
            logger.warning(f"⏱️  Timed out waiting for text: '{text}'")
            return False

    async def has_text(self, text: str) -> bool:
        """Check if text is visible on the page."""
        page_text = await self.get_page_text()
        return text.lower() in page_text.lower()

    async def screenshot(self, path: str = "screenshot.png"):
        """Save a screenshot of the current page."""
        await self.page.screenshot(path=path)
        logger.info(f"📸 Screenshot saved: {path}")

    async def wait_short(self, ms: int = 500):
        """Wait for a short period (simulate human delay)."""
        await asyncio.sleep(ms / 1000)

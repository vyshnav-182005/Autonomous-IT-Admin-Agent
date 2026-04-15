"""
OpsPilot AI — Browser Controller
Playwright-based browser automation for interacting with the admin panel.
All agent actions are performed through this controller — no direct API calls.
"""

import asyncio
import logging
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
        flash = await self.page.query_selector("[data-testid='flash-message']")
        if flash:
            snapshot["flash_message"] = await flash.inner_text()

        # Table data
        rows = await self.page.query_selector_all("[data-testid^='user-row-']")
        if rows:
            users = []
            for row in rows:
                test_id = await row.get_attribute("data-testid")
                email = test_id.replace("user-row-", "") if test_id else ""
                cells = await row.query_selector_all("td")
                if len(cells) >= 4:
                    name_text = await cells[0].inner_text()
                    role_text = await cells[2].inner_text()
                    status_text = await cells[3].inner_text()
                    users.append({
                        "email": email,
                        "name": name_text.strip(),
                        "role": role_text.strip(),
                        "status": status_text.strip(),
                    })
            snapshot["users_table"] = users
            snapshot["user_count"] = len(users)

        # Form fields
        forms = await self.page.query_selector_all("form")
        if forms:
            form_info = []
            for form in forms:
                action = await form.get_attribute("action") or ""
                test_id = await form.get_attribute("data-testid") or ""
                inputs = await form.query_selector_all("input, select")
                fields = []
                for inp in inputs:
                    inp_type = await inp.get_attribute("type") or "text"
                    inp_name = await inp.get_attribute("name") or ""
                    inp_testid = await inp.get_attribute("data-testid") or ""
                    if inp_name and inp_type != "hidden":
                        fields.append({"name": inp_name, "type": inp_type, "testid": inp_testid})
                if fields or test_id:
                    form_info.append({"action": action, "testid": test_id, "fields": fields})
            snapshot["forms"] = form_info

        # Buttons
        buttons = await self.page.query_selector_all("button[data-testid]")
        btn_list = []
        for btn in buttons:
            test_id = await btn.get_attribute("data-testid") or ""
            text = await btn.inner_text()
            disabled = await btn.is_disabled()
            if test_id:
                btn_list.append({"testid": test_id, "text": text.strip(), "disabled": disabled})
        if btn_list:
            snapshot["buttons"] = btn_list

        # Confirmation modal
        modal = await self.page.query_selector("[data-testid='confirm-modal']")
        if modal:
            snapshot["confirmation_modal_visible"] = True

        return snapshot

    # ── Interactions ──────────────────────────────────────────────

    async def click(self, target: str):
        """
        Click an element by data-testid or text content.

        Args:
            target: Either a data-testid value or visible text to click.
        """
        logger.info(f"🖱️  Clicking: {target}")

        # Try by data-testid first
        element = await self.page.query_selector(f"[data-testid='{target}']")
        if element:
            await element.scroll_into_view_if_needed()
            await element.click()
            await asyncio.sleep(0.3)  # Small delay for UI response
            return

        # Try by text
        try:
            await self.page.get_by_text(target, exact=False).first.click()
            await asyncio.sleep(0.3)
            return
        except Exception:
            pass

        # Try by role
        try:
            await self.page.get_by_role("button", name=target).click()
            await asyncio.sleep(0.3)
            return
        except Exception:
            pass

        raise ValueError(f"Could not find element to click: '{target}'")

    async def fill(self, target: str, value: str):
        """
        Fill an input field by data-testid.

        Args:
            target: data-testid of the input element.
            value: Text to type into the field.
        """
        logger.info(f"⌨️  Filling '{target}' with: {value}")
        element = await self.page.query_selector(f"[data-testid='{target}']")
        if not element:
            raise ValueError(f"Could not find input with testid: '{target}'")
        
        await element.scroll_into_view_if_needed()
        await element.fill(value)
        await asyncio.sleep(0.15)

    async def select_option(self, target: str, value: str):
        """
        Select an option from a dropdown by data-testid.

        Args:
            target: data-testid of the select element.
            value: The option value to select.
        """
        logger.info(f"📋 Selecting '{value}' in '{target}'")
        await self.page.select_option(f"[data-testid='{target}']", value=value)
        await asyncio.sleep(0.15)

    async def submit_form(self, target: str):
        """
        Submit a form by clicking its submit button (by data-testid).

        Args:
            target: data-testid of the submit button.
        """
        logger.info(f"📨 Submitting form via: {target}")
        await self.click(target)
        await self.page.wait_for_load_state("networkidle")

    async def click_confirm_modal(self):
        """Click the confirm button in a confirmation modal."""
        logger.info("✅ Confirming modal dialog")
        modal_confirm = await self.page.query_selector("[data-testid='modal-confirm-btn']")
        if modal_confirm:
            await modal_confirm.click()
            await self.page.wait_for_load_state("networkidle")
        else:
            logger.warning("No confirmation modal found")

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

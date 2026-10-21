"""Login form (also hosts the error message shown on bad credentials)."""
from __future__ import annotations

from playwright.sync_api import expect

from src.pages.base_page import BasePage


class LoginPage(BasePage):
    def login_with(self, email: str, password: str) -> None:
        self.fill("email_field", email)
        self.fill("password_field", password)
        self.click("login_submit")

    def expect_error(self, fragment: str) -> None:
        # free-text assertion: not in registry (assertions are never healed)
        expect(self.page.get_by_text(fragment, exact=False)).to_be_visible()

    def expect_form_visible(self) -> None:
        expect(self.locator("email_field")).to_be_visible()
        expect(self.locator("password_field")).to_be_visible()

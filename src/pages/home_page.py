"""Home page: top nav + 'Signup / Login' entry."""
from __future__ import annotations

from playwright.sync_api import expect

from src.pages.base_page import BasePage
from src.pages.login_page import LoginPage


class HomePage(BasePage):
    def open(self) -> "HomePage":
        # domcontentloaded: ad-heavy demo site never reaches full "load"
        self.page.goto(self.base_url, wait_until="domcontentloaded", timeout=45_000)
        return self

    def go_to_signup_login(self) -> LoginPage:
        self.click("signup_login_btn")
        return LoginPage(self.page, self.base_url)

    def go_to_products(self):
        from src.pages.products_page import ProductsPage  # local import: no cycle

        self.click("products_nav")
        self.page.wait_for_load_state("domcontentloaded")
        return ProductsPage(self.page, self.base_url)

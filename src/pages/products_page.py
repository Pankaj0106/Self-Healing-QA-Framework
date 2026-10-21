"""Products page: nav, search, results heading."""
from __future__ import annotations

from playwright.sync_api import expect

from src.pages.base_page import BasePage


class ProductsPage(BasePage):
    def open_products(self) -> "ProductsPage":
        return self

    def search(self, term: str) -> "ProductsPage":
        self.fill("search_input", term)
        self.click("search_button")
        return self

    def expect_results(self) -> None:
        expect(self.page.get_by_text("Searched Products", exact=False)).to_be_visible()

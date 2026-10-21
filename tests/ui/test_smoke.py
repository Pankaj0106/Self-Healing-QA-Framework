"""Smoke: login form behavior + product search (FR-02 flows 1 & 3)."""
from __future__ import annotations

import pytest

from src.pages.home_page import HomePage
from src.pages.products_page import ProductsPage

pytestmark = [pytest.mark.smoke]


def test_login_form_visible(page, settings):
    HomePage(page, settings.base_url).open().go_to_signup_login().expect_form_visible()


def test_login_invalid_password_shows_error(page, settings):
    home = HomePage(page, settings.base_url).open()
    login = home.go_to_signup_login()
    login.login_with("qa_nonexistent_user@example.com", "wrong-password-123")
    login.expect_error("Your email or password is incorrect!")


def test_product_search_returns_results(page, settings):
    HomePage(page, settings.base_url).open() \
        .go_to_products() \
        .search("top") \
        .expect_results()

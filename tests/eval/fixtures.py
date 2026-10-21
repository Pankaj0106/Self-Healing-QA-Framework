"""Offline HTML fixtures for the heal-quality benchmark (FR-11).

5 page templates x 4 mutation kinds = 20 cases, mirroring the ways real UI
redesigns break test locators:

  attr_rename   - the stable attribute is renamed by the design system
  text_rename   - only the visible label changes
  redesign      - attr AND label both change (hardest)
  distractors   - extra same-kind elements try to misroute the healer

Every case states:
  intent  - the human purpose, handed to the provider (actions shouldn't
            depend on knowing HOW the element is built)
  action  - click | fill  (drives which tag families are searched)
  marker  - Playwright selector that uniquely identifies the CORRECT target
            on the mutated page (ground truth used for grading)

Verdicts mirror live behaviour:
  true_positive   - healed onto the intended element
  false_positive  - healed onto A different element (worse than missing!)
  miss            - no candidate survived the uniqueness/confidence guards

Run offline:  pytest tests/eval -v   (no network, no site, ~seconds)
"""
from __future__ import annotations

_LOGIN = """<div class="login-form">
  <input data-qa="login-email" type="email" placeholder="Email"/>
  <input data-qa="login-password" type="password" placeholder="Password"/>
  <button {attr} class="btn btn-default">{text}</button>
</div>{extras}"""

_SIGNUP = """<div class="signup-form">
  <input data-qa="signup-name" type="text" placeholder="Name"/>
  <input data-qa="signup-email" type="email" placeholder="Email"/>
  <button {attr} class="btn btn-default">{text}</button>
</div>{extras}"""

_PRODUCTS = """<div class="products-list">
  <input id="search_product" placeholder="Search"/>
  <button {attr} id-hint="submit_search" class="btn">{text}</button>
  <a class="add-to-cart">Add to cart</a>
</div>{extras}"""

_CART = """<div class="cart">
  <a class="cart-link">Cart summary</a>
  <a {attr} class="btn btn-wi">{text}</a>
</div>{extras}"""

_CONTACT = """<div class="contact-form">
  {extra}
  <button type="submit" {attr} class="contact-btn">{text}</button>
</div>"""


def _login(attr: str, text: str, extras: str = "") -> str:
    return _LOGIN.format(attr=attr, text=text, extras=extras)


def _signup(attr: str, text: str, extras: str = "") -> str:
    return _SIGNUP.format(attr=attr, text=text, extras=extras)


def _products(attr: str, text: str, extras: str = "") -> str:
    return _PRODUCTS.format(attr=attr, text=text, extras=extras)


def _cart(attr: str, text: str, extras: str = "") -> str:
    return _CART.format(attr=attr, text=text, extras=extras)


def _contact(attr: str, text: str, extra: str = "") -> str:
    return _CONTACT.format(attr=attr, text=text, extra=extra)


INTENT = {
    "login": "Submit the login form",
    "signup": "Create an account via the signup form",
    "products": "Submit the product search form",
    "cart": "Proceed to checkout",
    "contact": "Submit the contact form",
}


def _case(page: str, kind: str, action: str, html: str, marker: str,
          intent: str | None = None) -> dict:
    return {
        "key": f"{page}_{kind}",
        "intent": intent or INTENT[page],
        "action": action,
        "html": html,
        "marker": marker,
    }


def build_cases() -> list[dict]:
    c: list[dict] = []

    # ---------------- login (4) ----------------
    c += [
        _case("login", "attr_rename", "click",
              _login('data-cy="auth-submit"', "Login"),
              'button:has-text("Login")'),
        _case("login", "text_rename", "click",
              _login('data-qa="login-button"', "Sign in"),
              '[data-qa="login-button"]'),
        _case("login", "redesign", "click",
              _login('class="btn-ui-submit"', "Sign in"),
              'button:has-text("Sign in")'),
        _case("login", "distractors", "click",
              _login('data-qa="login-button"', "Login",
                     extras='<button class="chip">Forgot password?</button>'
                            '<a href="/blog">My login activity</a>'),
              '[data-qa="login-button"]'),
    ]

    # ---------------- signup (4) ----------------
    c += [
        _case("signup", "attr_rename", "click",
              _signup('data-cy="signup-submit"', "Signup"),
              'button:has-text("Signup")'),
        _case("signup", "text_rename", "click",
              _signup('data-qa="signup-button"', "Join free"),
              '[data-qa="signup-button"]'),
        _case("signup", "redesign", "click",
              _signup('class="btn-ui-cta"', "Join"),
              'button:has-text("Join")'),
        _case("signup", "distractors", "click",
              _signup('data-qa="signup-button"', "Signup",
                      extras='<button class="chip">Newsletter signup</button>'
                             '<a href="/terms">Terms of service</a>'),
              '[data-qa="signup-button"]'),
    ]

    # ---------------- products / search (4) ----------------
    c += [
        _case("products", "attr_rename", "click",
              _products('id="find-products"', "Search"),
              'button:has-text("Search")'),
        _case("products", "text_rename", "click",
              _products('id="submit_search"', "Go"),
              '[id="submit_search"]'),
        _case("products", "redesign", "click",
              _products('id="go"', "Go"),
              'button:has-text("Go")'),
        _case("products", "distractors", "click",
              _products('id="submit_search"', "Search",
                        extras='<button class="chip">Product filters</button>'),
              '[id="submit_search"]'),
    ]

    # ---------------- cart / checkout (4) ----------------
    c += [
        _case("cart", "attr_rename", "click",
              _cart('data-cy="go-checkout"', "Proceed to checkout"),
              'a:has-text("Proceed to checkout")'),
        _case("cart", "text_rename", "click",
              _cart('data-qa="checkout"', "Complete purchase"),
              '[data-qa="checkout"]'),
        _case("cart", "redesign", "click",
              _cart('class="btn-primary"', "Complete purchase"),
              '[class="btn-primary"]'),
        _case("cart", "distractors", "click",
              _cart('data-qa="checkout"', "Proceed to checkout",
                    extras='<a href="/history">Checkout history</a>'),
              '[data-qa="checkout"]'),
    ]

    # ---------------- contact (4) ----------------
    c += [
        _case("contact", "input_fill", "fill",
              _contact('data-qa="contact-message"', "Send message",
                       extra='<input name="your_message" placeholder="Your message"/>'),
              'input[name="your_message"]',
              intent="Type your message into the contact form box"),
        _case("contact", "no_attr_button", "click",
              _contact('', "Send message"),
              'button[type="submit"]'),
        _case("contact", "redesign", "click",
              _contact('class="ui-submit"', "Get in touch"),
              'button:has-text("Get in touch")'),
        _case("contact", "distractors", "click",
              _contact('', "Send message",
                       extra='<input name="your_message" placeholder="Your message"/>'
                             '<a href="/tickets">Submit a ticket</a>'),
              'button[type="submit"]'),
    ]

    return c


CASES = build_cases()
assert len(CASES) == 20, f"benchmark scope drift: {len(CASES)} != 20"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NanoBanana Pro API — Core Bot Engine
Created by: @Ok_Sidra

Handles browser automation via Playwright to generate images
from nanobanana-2.ai — all logic kept identical to original bot.
"""

import time
import random
import string
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ─────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────

BASE_URL    = "https://nanobanana-2.ai"
GEN_TIMEOUT = 210   # seconds — max wait for image (user requested 220s max)
ELEM_WAIT   = 15_000

ASPECT_MAP: dict[str, str] = {
    "1:1":  "1:1",
    "2:3":  "2:3",
    "3:2":  "3:2",
    "3:4":  "3:4",
    "4:3":  "4:3",
    "4:5":  "4:5",
    "5:4":  "5:4",
    "9:16": "9:16",
    "16:9": "16:9",
    "21:9": "21:9",
}

VALID_MODELS: dict[str, str] = {
    "nano-banana-pro": "Nano Banana Pro",
    "nano-banana":     "Nano Banana",
}

DEFAULT_ASPECT = "1:1"
DEFAULT_MODEL  = "nano-banana-pro"


# ─────────────────────────────────────────────
#  Helpers — identical to original bot
# ─────────────────────────────────────────────

def _random_credentials() -> tuple[str, str, str]:
    """Generate random email / password / name for auto-registration."""
    slug  = "".join(random.choices(string.ascii_lowercase, k=8))
    num   = random.randint(10, 9999)
    email = f"{slug}{num}@gmail.com"
    chars = (
        random.choices(string.ascii_uppercase, k=2)
        + random.choices(string.ascii_lowercase, k=5)
        + random.choices(string.digits, k=3)
    )
    random.shuffle(chars)
    return email, "".join(chars), slug.capitalize()


def _find_task_id(data, _keys: set | None = None) -> str | None:
    """Recursively search response JSON for a task/job ID."""
    if _keys is None:
        _keys = {
            "taskId", "task_id", "id", "jobId", "job_id",
            "requestId", "generationId", "uuid", "token",
        }
    if isinstance(data, dict):
        for k, v in data.items():
            if k in _keys and isinstance(v, str) and len(v) > 5:
                return v
            found = _find_task_id(v, _keys)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_task_id(item, _keys)
            if found:
                return found
    return None


def _find_image_url(data) -> str | None:
    """Recursively search response JSON for an image URL."""
    EXTS = (".png", ".jpg", ".jpeg", ".webp")
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, str) and (
                "image.nanobanana" in v
                or (v.startswith("https://") and any(v.endswith(e) for e in EXTS))
            ):
                return v
            found = _find_image_url(v)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_image_url(item)
            if found:
                return found
    return None


# ─────────────────────────────────────────────
#  Main Generate Function
# ─────────────────────────────────────────────

def generate(
    prompt: str,
    aspect: str = DEFAULT_ASPECT,
    model:  str = DEFAULT_MODEL,
) -> dict:
    """
    Launch headless Chromium, auto-register an account on nanobanana-2.ai,
    submit the generation request, and return the raw image URL.

    Args:
        prompt : Image description text.
        aspect : Aspect ratio key — must be one of ASPECT_MAP keys.
        model  : Model key — must be one of VALID_MODELS keys.

    Returns:
        dict with keys: success, image_url, task_id, model, aspect, prompt

    Raises:
        ValueError   : Invalid aspect or model value.
        TimeoutError : Image not ready within GEN_TIMEOUT seconds.
        RuntimeError : Any unexpected browser / site error.
    """
    if aspect not in ASPECT_MAP:
        raise ValueError(
            f"Invalid aspect ratio '{aspect}'. "
            f"Valid options: {', '.join(sorted(ASPECT_MAP.keys()))}"
        )
    if model not in VALID_MODELS:
        raise ValueError(
            f"Invalid model '{model}'. "
            f"Valid options: {', '.join(VALID_MODELS.keys())}"
        )

    model_label = VALID_MODELS[model]
    ratio       = ASPECT_MAP[aspect]
    events: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
            ],
        )
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) "
                "Gecko/20100101 Firefox/148.0"
            ),
            ignore_https_errors=True,
        )
        page = ctx.new_page()
        page.on("dialog", lambda d: d.dismiss())

        # ── Network listener — capture generate & query responses ──
        def _on_response(resp):
            try:
                if "/api/ai/generate" in resp.url and resp.status in (200, 201):
                    events.append({"t": "generate", "d": resp.json()})
                elif "/api/ai/query" in resp.url and resp.status == 200:
                    events.append({"t": "query", "d": resp.json()})
            except Exception:
                pass

        page.on("response", _on_response)

        try:
            # ── STEP 1 — Open home page ──────────────────────────
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(1800)

            # ── STEP 2 — Auto-register random account ────────────
            email, pw_val, name = _random_credentials()
            page.goto(f"{BASE_URL}/sign-up", wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_timeout(1500)

            for sel in [
                "input[name='name']",
                "input[placeholder*='name' i]",
                "input[placeholder*='Full' i]",
            ]:
                try:
                    el = page.locator(sel).first
                    el.wait_for(state="visible", timeout=5000)
                    el.fill(name)
                    break
                except Exception:
                    continue

            page.wait_for_timeout(400)

            for sel in ["input[type='email']", "input[name='email']"]:
                try:
                    el = page.locator(sel).first
                    el.wait_for(state="visible", timeout=5000)
                    el.fill(email)
                    break
                except Exception:
                    continue

            page.wait_for_timeout(400)

            pwd_fields = page.locator("input[type='password']")
            for i in range(pwd_fields.count()):
                try:
                    pwd_fields.nth(i).fill(pw_val)
                except Exception:
                    pass

            page.wait_for_timeout(500)

            for sel in [
                "button[type='submit']",
                "button:has-text('Sign up')",
                "button:has-text('Create account')",
                "button:has-text('Register')",
                "button:has-text('Get started')",
            ]:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        break
                except Exception:
                    continue

            page.wait_for_timeout(3500)

            # ── STEP 3 — Open image generator ────────────────────
            page.goto(
                f"{BASE_URL}/ai-image-generator",
                wait_until="domcontentloaded",
                timeout=20_000,
            )
            page.wait_for_timeout(2500)

            # ── STEP 4 — Click "Text to Image" tab ───────────────
            tab = page.locator("button:has-text('Text to Image')").first
            tab.wait_for(state="visible", timeout=ELEM_WAIT)
            tab.click()
            page.wait_for_timeout(700)

            # ── STEP 5 — Select model ─────────────────────────────
            dropdown_btn = page.locator("button:has-text('Nano Banana')").first
            dropdown_btn.wait_for(state="visible", timeout=ELEM_WAIT)
            dropdown_btn.click()
            page.wait_for_timeout(600)

            option = page.locator(f"text={model_label}").first
            option.wait_for(state="visible", timeout=ELEM_WAIT)
            option.click()
            page.wait_for_timeout(600)

            # ── STEP 6 — Select aspect ratio ──────────────────────
            page.mouse.wheel(0, 300)
            page.wait_for_timeout(600)

            aspect_btn = page.locator(
                "button:has-text('1:1'), button:has-text('2:3'), "
                "button:has-text('3:2'), button:has-text('3:4'), "
                "button:has-text('4:3'), button:has-text('4:5'), "
                "button:has-text('5:4'), button:has-text('9:16'), "
                "button:has-text('16:9'), button:has-text('21:9')"
            ).first
            aspect_btn.wait_for(state="visible", timeout=ELEM_WAIT)
            aspect_btn.scroll_into_view_if_needed()
            page.wait_for_timeout(400)
            aspect_btn.click()
            page.mouse.wheel(0, 150)
            page.wait_for_timeout(500)

            # Try three different selection strategies (same as original bot)
            try:
                opt = page.get_by_role("option", name=ratio, exact=True)
                opt.wait_for(state="visible", timeout=3000)
                opt.scroll_into_view_if_needed()
                opt.click()
            except Exception:
                try:
                    opt2 = page.locator(
                        f"li:has-text('{ratio}'), "
                        f"[role='menuitem']:has-text('{ratio}'), "
                        f"[role='option']:has-text('{ratio}')"
                    ).filter(has_text=ratio).first
                    opt2.scroll_into_view_if_needed()
                    opt2.click()
                except Exception:
                    page.locator(f"text={ratio}").last.click()

            page.wait_for_timeout(600)

            # ── STEP 7 — Inject prompt via JS (bypasses React re-render) ──
            prompt = prompt[:2000]  # max 2000 chars
            page.wait_for_selector("#image-prompt", state="visible", timeout=ELEM_WAIT)
            for _ in range(3):
                try:
                    page.evaluate("""
                        (prompt) => {
                            const el = document.querySelector('#image-prompt');
                            el.value = prompt;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    """, prompt)
                    break
                except Exception:
                    page.wait_for_timeout(1000)
            page.wait_for_timeout(500)

            # ── STEP 8 — Click "Generate Images" ─────────────────
            btn_gen = page.locator("button:has-text('Generate Images')").first
            btn_gen.wait_for(state="visible", timeout=ELEM_WAIT)
            if btn_gen.get_attribute("disabled") is not None:
                page.wait_for_timeout(2000)
            btn_gen.click()
            page.wait_for_timeout(500)

            # ── STEP 9 — Poll until image URL appears ─────────────
            start     = time.time()
            image_url = None
            task_id   = None

            while True:
                elapsed = int(time.time() - start)
                if elapsed >= GEN_TIMEOUT:
                    break

                # Extract task ID from first generate event
                if task_id is None:
                    for ev in events:
                        if ev["t"] == "generate":
                            task_id = _find_task_id(ev["d"])
                            if task_id:
                                break

                # Check query events for image URL
                for ev in events:
                    if ev["t"] == "query":
                        url = _find_image_url(ev["d"])
                        if url:
                            image_url = url
                            break

                if image_url:
                    break

                # Fallback: check DOM for rendered <img>
                try:
                    img = page.locator(
                        "img[src*='image.nanobanana-2.ai'], img[src*='ai-generated']"
                    ).first
                    src = img.get_attribute("src", timeout=500) or ""
                    if src.startswith("http") and len(src) > 40:
                        image_url = src
                        break
                except Exception:
                    pass

                time.sleep(2)

            if not image_url:
                raise TimeoutError(
                    f"Image generation timed out after {GEN_TIMEOUT} seconds. "
                    "Please try again."
                )

            return {
                "success":  True,
                "image_url": image_url,
                "task_id":  task_id or "unknown",
                "model":    model,
                "aspect":   aspect,
                "prompt":   prompt,
            }

        finally:
            try:
                browser.close()
            except Exception:
                pass

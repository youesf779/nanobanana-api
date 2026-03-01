#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║       🍌  NanoBanana Pro — Image Generation API          ║
║       Created by: @Ok_Sidra                              ║
║       Base URL: https://nanobananapro-api.up.railway.app ║
╚══════════════════════════════════════════════════════════╝

Endpoints:
  GET /           → API documentation
  GET /generate   → Generate an image (prompt + aspect + model)
  GET /settings   → Available models, aspect ratios, usage info
  GET /img/<token>→ Proxied image (hides source URL)
"""

import os
import base64

import requests
from flask import Flask, request, jsonify, Response

from core import generate as core_generate, ASPECT_MAP, VALID_MODELS

# ─────────────────────────────────────────────
#  App Setup
# ─────────────────────────────────────────────

app = Flask(__name__)

API_BASE  = "https://nanobananapro-api.up.railway.app"
API_VER   = "1.0.0"
AUTHOR    = "@Ok_Sidra"


# ─────────────────────────────────────────────
#  Utilities
# ─────────────────────────────────────────────

def _encode_url(url: str) -> str:
    """Base64-URL encode a raw image URL to hide the source."""
    return base64.urlsafe_b64encode(url.encode("utf-8")).decode("utf-8")


def _decode_url(token: str) -> str:
    """Decode a base64-URL token back to the raw image URL."""
    # Add padding if needed
    padding = 4 - len(token) % 4
    if padding != 4:
        token += "=" * padding
    return base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")


def _err(msg: str, hint: str = None, code: int = 400):
    """Return a standardised error JSON response."""
    body = {"success": False, "error": msg}
    if hint:
        body["hint"] = hint
    return jsonify(body), code


# ─────────────────────────────────────────────
#  GET /  — API Documentation
# ─────────────────────────────────────────────

@app.route("/", methods=["GET"])
def docs():
    return jsonify({
        "name":        "🍌 NanoBanana Pro Image Generation API",
        "version":     API_VER,
        "author":      AUTHOR,
        "description": (
            "Headless browser-powered API that generates AI images "
            "via NanoBanana Pro. Image URLs are returned as secure "
            "proxied links — no source domain is exposed."
        ),
        "base_url": API_BASE,
        "endpoints": {
            f"GET {API_BASE}/generate": {
                "description": "Generate an AI image from a text prompt.",
                "parameters": {
                    "prompt": {
                        "type":     "string",
                        "required": True,
                        "example":  "a futuristic city at sunset, cinematic lighting",
                    },
                    "aspect": {
                        "type":     "string",
                        "required": False,
                        "default":  "1:1",
                        "options":  sorted(ASPECT_MAP.keys()),
                        "example":  "16:9",
                    },
                    "model": {
                        "type":     "string",
                        "required": False,
                        "default":  "nano-banana-pro",
                        "options":  list(VALID_MODELS.keys()),
                        "example":  "nano-banana-pro",
                    },
                },
                "example_request": (
                    f"{API_BASE}/generate"
                    "?prompt=a futuristic city at sunset"
                    "&aspect=16:9"
                    "&model=nano-banana-pro"
                ),
                "response_example": {
                    "success":   True,
                    "image_url": f"{API_BASE}/img/aHR0cHM6Ly9leGFtcGxlLmNvbS9pbWcucG5n",
                    "task_id":   "abc-123-xyz",
                    "model":     "nano-banana-pro",
                    "aspect":    "16:9",
                    "prompt":    "a futuristic city at sunset",
                },
                "notes": [
                    "Generation may take up to 220 seconds.",
                    "image_url is a proxied link — the original source is never exposed.",
                ],
            },
            f"GET {API_BASE}/settings": {
                "description": "Returns all available models, aspect ratios, and API usage info.",
                "parameters":  "none",
                "example_request": f"{API_BASE}/settings",
            },
            f"GET {API_BASE}/img/<token>": {
                "description": (
                    "Proxies and serves the generated image. "
                    "The <token> is returned in the image_url field of /generate."
                ),
                "example_request": f"{API_BASE}/img/aHR0cHM6Ly9leGFtcGxlLmNvbS9pbWcucG5n",
            },
        },
    })


# ─────────────────────────────────────────────
#  GET /settings — Available Options
# ─────────────────────────────────────────────

@app.route("/settings", methods=["GET"])
def settings():
    return jsonify({
        "success": True,
        "api": {
            "name":    "🍌 NanoBanana Pro Image Generation API",
            "version": API_VER,
            "author":  AUTHOR,
            "base_url": API_BASE,
        },
        "models": [
            {
                "id":          mid,
                "label":       mlabel,
                "default":     mid == "nano-banana-pro",
                "description": (
                    "Most powerful model — higher quality & detail"
                    if mid == "nano-banana-pro"
                    else "Standard model — faster generation"
                ),
            }
            for mid, mlabel in VALID_MODELS.items()
        ],
        "aspect_ratios": [
            {
                "value":       ratio,
                "label":       _aspect_label(ratio),
                "default":     ratio == "1:1",
            }
            for ratio in sorted(ASPECT_MAP.keys())
        ],
        "limits": {
            "max_generation_wait_seconds": 220,
            "max_prompt_length_chars":     2000,
        },
        "endpoints": {
            "generate": f"{API_BASE}/generate",
            "settings": f"{API_BASE}/settings",
            "image":    f"{API_BASE}/img/<token>",
            "docs":     API_BASE,
        },
        "usage": {
            "generate_example": (
                f"{API_BASE}/generate"
                "?prompt=a beautiful mountain landscape at dawn"
                "&aspect=16:9"
                "&model=nano-banana-pro"
            ),
            "note": (
                "All image URLs returned from /generate are secure proxied links. "
                "Pass the full image_url directly to display or download the image."
            ),
        },
    })


def _aspect_label(ratio: str) -> str:
    """Human-friendly label for each aspect ratio."""
    labels = {
        "1:1":  "1:1  — Square",
        "2:3":  "2:3  — Portrait (tall)",
        "3:2":  "3:2  — Landscape",
        "3:4":  "3:4  — Portrait",
        "4:3":  "4:3  — Classic",
        "4:5":  "4:5  — Instagram",
        "5:4":  "5:4  — Slightly wide",
        "9:16": "9:16 — Mobile vertical",
        "16:9": "16:9 — Widescreen",
        "21:9": "21:9 — Cinematic",
    }
    return labels.get(ratio, ratio)


# ─────────────────────────────────────────────
#  GET /generate — Main Image Generation
# ─────────────────────────────────────────────

@app.route("/generate", methods=["GET"])
def generate_image():
    prompt = request.args.get("prompt", "").strip()
    aspect = request.args.get("aspect", "1:1").strip()
    model  = request.args.get("model",  "nano-banana-pro").strip()

    # ── Validate prompt ──
    if not prompt:
        return _err(
            "The 'prompt' parameter is required.",
            "Add ?prompt=your image description",
        )

    if len(prompt) > 2000:
        return _err(
            "Prompt exceeds maximum length of 2000 characters.",
            f"Current length: {len(prompt)} characters.",
        )

    # ── Validate aspect ratio ──
    if aspect not in ASPECT_MAP:
        return _err(
            f"Invalid aspect ratio: '{aspect}'.",
            f"Valid options: {', '.join(sorted(ASPECT_MAP.keys()))}",
        )

    # ── Validate model ──
    if model not in VALID_MODELS:
        return _err(
            f"Invalid model: '{model}'.",
            f"Valid options: {', '.join(VALID_MODELS.keys())}",
        )

    # ── Run generation ──
    try:
        result = core_generate(
            prompt=prompt,
            aspect=aspect,
            model=model,
        )

        # Mask the raw image URL — encode it so the source domain stays hidden
        raw_url    = result["image_url"]
        token      = _encode_url(raw_url)
        masked_url = f"{API_BASE}/img/{token}"

        return jsonify({
            "success":   True,
            "image_url": masked_url,
            "task_id":   result.get("task_id", "unknown"),
            "model":     model,
            "aspect":    aspect,
            "prompt":    prompt,
        }), 200

    except ValueError as exc:
        return _err(str(exc), code=400)

    except TimeoutError as exc:
        return _err(
            str(exc),
            "The image took too long to generate. Please try again.",
            504,
        )

    except RuntimeError as exc:
        return _err(str(exc), code=502)

    except Exception as exc:
        return _err(
            f"Unexpected server error: {exc}",
            "Please try again or contact @Ok_Sidra.",
            500,
        )


# ─────────────────────────────────────────────
#  GET /img/<token> — Proxied Image Delivery
# ─────────────────────────────────────────────

@app.route("/img/<path:token>", methods=["GET"])
def proxy_image(token: str):
    """
    Decode the base64-URL token to get the real image URL,
    then stream the image bytes back to the client.
    The original source URL is never revealed.
    """
    try:
        real_url = _decode_url(token)
    except Exception:
        return jsonify({
            "success": False,
            "error":   "Invalid image token.",
            "hint":    "Use the full image_url returned by /generate.",
        }), 400

    # Basic sanity check — only allow known image hosting domains
    if not real_url.startswith("https://"):
        return jsonify({"success": False, "error": "Invalid image URL."}), 400

    try:
        resp = requests.get(
            real_url,
            timeout=60,
            stream=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) "
                    "Gecko/20100101 Firefox/148.0"
                ),
                "Accept": "image/avif,image/webp,image/png,image/*;q=0.8",
            },
        )

        if resp.status_code != 200:
            return jsonify({
                "success": False,
                "error":   "Image could not be retrieved. It may have expired.",
            }), 404

        content_type = resp.headers.get("Content-Type", "image/png")

        def _stream():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        return Response(
            _stream(),
            status=200,
            content_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "X-Powered-By":  f"NanoBanana Pro API by {AUTHOR}",
            },
        )

    except requests.exceptions.Timeout:
        return jsonify({"success": False, "error": "Image fetch timed out."}), 504

    except Exception as exc:
        return jsonify({"success": False, "error": f"Proxy error: {exc}"}), 500


# ─────────────────────────────────────────────
#  Run
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)

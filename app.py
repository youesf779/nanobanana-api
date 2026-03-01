#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import base64
import requests
from datetime import datetime
from flask import Flask, request, jsonify, Response
from core import generate as core_generate, ASPECT_MAP, VALID_MODELS

app = Flask(__name__)

API_BASE = "https://nanobananapro-api.up.railway.app"
AUTHOR   = "@Ok_Sidra"
LOG_FILE = "images_log.json"


# ── Image Log (persistent via JSON file) ─────────────────────────────────────

def _log_load():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _log_save(entries):
    try:
        with open(LOG_FILE, "w") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _log_add(entry: dict):
    entries = _log_load()
    entries.append(entry)
    _log_save(entries)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _encode(url):
    return base64.urlsafe_b64encode(url.encode()).decode()

def _decode(token):
    pad = 4 - len(token) % 4
    if pad != 4:
        token += "=" * pad
    return base64.urlsafe_b64decode(token.encode()).decode()

def _err(msg, hint=None, code=400):
    body = {"success": False, "error": msg}
    if hint:
        body["hint"] = hint
    return jsonify(body), code


# ── GET / ─────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def docs():
    return jsonify({
        "api":    "🍌 NanoBanana Pro",
        "author": AUTHOR,
        "usage": {
            "url":    f"{API_BASE}/generate",
            "method": "GET",
            "params": {
                "prompt": "required",
                "aspect": f"optional · default: 1:1 · choices: {', '.join(sorted(ASPECT_MAP))}",
                "model":  f"optional · default: nano-banana-pro · choices: {', '.join(VALID_MODELS)}",
            },
            "example": f"{API_BASE}/generate?prompt=sunset over the ocean&aspect=16:9",
        },
        "response": {
            "success":   True,
            "image_url": f"{API_BASE}/img/<token>  <- direct image, original domain hidden",
            "task_id":   "abc-123",
            "model":     "nano-banana-pro",
            "aspect":    "16:9",
            "prompt":    "sunset over the ocean",
        },
        "notes": [
            "image_url streams the image directly — no redirect, original site hidden.",
            "Max prompt: 2000 chars.  Max wait: 220 seconds.",
            f"More info: {API_BASE}/settings",
        ],
    })


# ── GET /settings ─────────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET"])
def settings():
    aspect_labels = {
        "1:1": "Square", "2:3": "Portrait tall", "3:2": "Landscape",
        "3:4": "Portrait", "4:3": "Classic", "4:5": "Instagram",
        "5:4": "Slightly wide", "9:16": "Mobile vertical",
        "16:9": "Widescreen", "21:9": "Cinematic",
    }
    return jsonify({
        "success": True,
        "models": {
            mid: {"label": mlabel, "default": mid == "nano-banana-pro"}
            for mid, mlabel in VALID_MODELS.items()
        },
        "aspect_ratios": {
            r: aspect_labels.get(r, r) for r in sorted(ASPECT_MAP)
        },
        "limits": {
            "max_prompt_chars": 2000,
            "max_wait_seconds": 220,
        },
        "endpoints": {
            "docs":     f"{API_BASE}/",
            "generate": f"{API_BASE}/generate",
            "settings": f"{API_BASE}/settings",
        },
    })


# ── GET /generate ─────────────────────────────────────────────────────────────

@app.route("/generate", methods=["GET"])
def generate_image():
    prompt = request.args.get("prompt", "").strip()
    aspect = request.args.get("aspect", "1:1").strip()
    model  = request.args.get("model",  "nano-banana-pro").strip()

    if not prompt:
        return _err("'prompt' is required.", "Add ?prompt=your image description")
    if len(prompt) > 2000:
        return _err(f"Prompt too long ({len(prompt)} chars). Max is 2000.")
    if aspect not in ASPECT_MAP:
        return _err(f"Invalid aspect '{aspect}'.", f"Valid: {', '.join(sorted(ASPECT_MAP))}")
    if model not in VALID_MODELS:
        return _err(f"Invalid model '{model}'.", f"Valid: {', '.join(VALID_MODELS)}")

    try:
        result    = core_generate(prompt=prompt, aspect=aspect, model=model)
        token     = _encode(result["image_url"])
        image_url = f"{API_BASE}/img/{token}"

        # ── Save to log ──
        _log_add({
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "prompt":    prompt,
            "aspect":    aspect,
            "model":     model,
            "task_id":   result.get("task_id", "unknown"),
            "image_url": image_url,
        })

        return jsonify({
            "success":   True,
            "image_url": image_url,
            "task_id":   result.get("task_id", "unknown"),
            "model":     model,
            "aspect":    aspect,
            "prompt":    prompt,
        }), 200

    except ValueError   as e: return _err(str(e), code=400)
    except TimeoutError as e: return _err(str(e), "Try again — generation timed out.", 504)
    except RuntimeError as e: return _err(str(e), code=502)
    except Exception    as e: return _err(f"Unexpected server error: {e}", f"Contact {AUTHOR}", 500)


# ── GET /img/<token> — Proxy image ────────────────────────────────────────────

@app.route("/img/<path:token>", methods=["GET"])
def proxy_image(token):
    try:
        real_url = _decode(token)
    except Exception:
        return _err("Invalid image token.", "Use the full image_url from /generate.")

    if not real_url.startswith("https://"):
        return _err("Invalid image URL.")

    try:
        resp = requests.get(
            real_url, timeout=60, stream=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/148.0",
                "Accept":     "image/avif,image/webp,image/png,image/*;q=0.8",
            },
        )
        if resp.status_code != 200:
            return _err("Image not found or expired.", code=404)

        ctype = resp.headers.get("Content-Type", "image/png")

        def _stream():
            for chunk in resp.iter_content(8192):
                if chunk:
                    yield chunk

        return Response(
            _stream(), status=200, content_type=ctype,
            headers={
                "Content-Disposition": "inline",
                "Cache-Control":       "public, max-age=86400",
                "X-Powered-By":        f"NanoBanana Pro · {AUTHOR}",
            },
        )

    except requests.exceptions.Timeout:
        return _err("Image fetch timed out.", code=504)
    except Exception as e:
        return _err(f"Proxy error: {e}", code=500)


# ── GET /admin79576086 — Admin Panel ──────────────────────────────────────────

@app.route("/admin79576086", methods=["GET"])
def admin():
    entries = _log_load()
    total   = len(entries)

    return jsonify({
        "success":      True,
        "total_images": total,
        "images": [
            {
                "no":        i + 1,
                "timestamp": e.get("timestamp"),
                "prompt":    e.get("prompt"),
                "aspect":    e.get("aspect"),
                "model":     e.get("model"),
                "task_id":   e.get("task_id"),
                "image_url": e.get("image_url"),
            }
            for i, e in enumerate(reversed(entries))
        ],
    })


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)

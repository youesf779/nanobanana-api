from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import time
import random
import string
import re
import hashlib
import base64
import os

app = Flask(__name__)
CORS(app)

SITE     = "https://nanobananaimg.com"
SB_URL   = "https://gfoafqcjhfqigdwtxwqt.supabase.co"
SB_ANON  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imdmb2FmcWNqaGZxaWdkd3R4d3F0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTUzNTY1NDksImV4cCI6MjA3MDkzMjU0OX0.Qe1pmu-LTkQNqNjKEqcARyfqhtlL758eu2gakrz66Og"
MAIL_API = "https://api.mail.tm"

UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Mobile Safari/537.36"

HEADERS = {
    "User-Agent":         UA,
    "sec-ch-ua":          '"Not(A:Brand";v="8", "Chromium";v="144", "Brave";v="144"',
    "sec-ch-ua-mobile":   "?1",
    "sec-ch-ua-platform": '"Android"',
    "sec-gpc":            "1",
    "accept-language":    "ar-EG,ar;q=0.6",
    "origin":             SITE,
    "referer":            f"{SITE}/",
}

SB_HDRS = {
    "User-Agent":             UA,
    "Content-Type":           "application/json",
    "authorization":          f"Bearer {SB_ANON}",
    "apikey":                 SB_ANON,
    "x-supabase-api-version": "2024-01-01",
    "x-client-info":          "supabase-ssr/0.6.1 createBrowserClient",
    "origin":                 SITE,
    "referer":                f"{SITE}/",
}


def rand_str(n=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))


def gen_pkce():
    verifier  = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b'=').decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b'=').decode()
    return verifier, challenge


def get_auth_cookie():
    """Create new account and return auth cookie"""
    # 1. Create email
    r = requests.get(f"{MAIL_API}/domains", timeout=10)
    domains = [d["domain"] for d in r.json().get("hydra:member", [])]
    email = password = mail_token = None

    for domain in domains:
        e  = f"{rand_str()}@{domain}"
        p  = "Pass" + rand_str(6)
        r2 = requests.post(f"{MAIL_API}/accounts", json={"address": e, "password": p}, timeout=10)
        if r2.status_code not in (200, 201):
            continue
        r3 = requests.post(f"{MAIL_API}/token", json={"address": e, "password": p}, timeout=10)
        if r3.status_code != 200:
            continue
        email, password, mail_token = e, p, r3.json()["token"]
        break

    if not email:
        raise Exception("فشل إنشاء الإيميل")

    # 2. Send OTP
    verifier, challenge = gen_pkce()
    redirect = f"{SITE}/auth/callback?next=%2F"
    requests.post(
        f"{SB_URL}/auth/v1/otp",
        params={"redirect_to": redirect},
        headers=SB_HDRS,
        json={
            "email":                  email,
            "data":                   {},
            "create_user":            True,
            "gotrue_meta_security":   {},
            "code_challenge":         challenge,
            "code_challenge_method":  "s256"
        },
        timeout=15
    )

    # 3. Wait for magic link
    hdrs_mail = {"Authorization": f"Bearer {mail_token}"}
    token_hash = None

    for _ in range(24):
        time.sleep(5)
        r    = requests.get(f"{MAIL_API}/messages", headers=hdrs_mail, timeout=10)
        msgs = r.json().get("hydra:member", [])
        if msgs:
            r2   = requests.get(f"{MAIL_API}/messages/{msgs[0]['id']}", headers=hdrs_mail, timeout=10)
            body = r2.json().get("text", "") or str(r2.json().get("html", [""])[0])
            m    = re.search(r'token_hash=(pkce_[^&\s"<]+)', body)
            if m:
                token_hash = m.group(1)
                break

    if not token_hash:
        raise Exception("لم يصل OTP")

    # 4. Verify
    rv = requests.post(
        f"{SB_URL}/auth/v1/verify",
        headers=SB_HDRS,
        json={"token_hash": token_hash, "type": "email", "code_verifier": verifier},
        timeout=15
    )
    rj            = rv.json()
    access_token  = rj.get("access_token")
    refresh_token = rj.get("refresh_token")
    expires_at    = rj.get("expires_at")
    user          = rj.get("user", {})

    if not access_token:
        rx = requests.post(
            f"{SB_URL}/auth/v1/token",
            params={"grant_type": "pkce"},
            headers=SB_HDRS,
            json={"auth_code": token_hash, "code_verifier": verifier},
            timeout=15
        )
        rj            = rx.json()
        access_token  = rj.get("access_token")
        refresh_token = rj.get("refresh_token")
        expires_at    = rj.get("expires_at")
        user          = rj.get("user", {})

    if not access_token:
        raise Exception("فشل التفعيل")

    auth_cookie = "base64-" + base64.b64encode(json.dumps({
        "access_token":  access_token,
        "token_type":    "bearer",
        "expires_in":    3600,
        "expires_at":    expires_at,
        "refresh_token": refresh_token,
        "user":          user
    }).encode()).decode()

    return auth_cookie


def poll_task(task_id, gen_hdrs, timeout=240):
    """Poll task until completed or failed"""
    for _ in range(timeout // 4):
        time.sleep(4)
        rs     = requests.get(
            f"{SITE}/api/image/task-status?taskId={task_id}",
            headers=gen_hdrs,
            timeout=15
        )
        data   = rs.json()
        status = data.get("status", "")
        if status == "completed":
            urls = data.get("imageUrls", [])
            return urls[0] if urls else None
        if status == "failed":
            raise Exception(data.get("failedReason", "فشل التوليد"))
    raise Exception("انتهى وقت الانتظار")


# ═══════════════════════════════════════════
# POST /generate
# Body: { "prompt": "...", "aspect_ratio": "1:1" }
# ═══════════════════════════════════════════
@app.route("/generate", methods=["POST"])
def generate():
    data         = request.get_json()
    prompt       = data.get("prompt", "").strip()
    aspect_ratio = data.get("aspect_ratio", "1:1")

    if not prompt:
        return jsonify({"error": "prompt مطلوب"}), 400

    try:
        auth_cookie = get_auth_cookie()
        gen_hdrs = {
            **HEADERS,
            "Content-Type":   "application/json",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "Cookie":         f"sb-gfoafqcjhfqigdwtxwqt-auth-token={auth_cookie}; NEXT_LOCALE=en"
        }

        payload = {
            "prompt":       prompt,
            "generateType": "text-to-image",
            "modelId":      "nano-banana-pro",
            "aspectRatio":  aspect_ratio,
            "resolution":   "4K"
        }

        rg      = requests.post(f"{SITE}/api/image/kie/generate",
                                headers=gen_hdrs, json=payload, timeout=30)
        task_id = rg.json().get("taskId")

        if not task_id:
            return jsonify({"error": "فشل بدء التوليد", "details": rg.text}), 500

        image_url = poll_task(task_id, gen_hdrs)
        return jsonify({"success": True, "image_url": image_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════
# POST /edit
# Body: { "prompt": "...", "image_url": "https://..." }
# OR multipart with image file
# ═══════════════════════════════════════════
@app.route("/edit", methods=["POST"])
def edit():
    prompt      = None
    image_url   = None
    image_bytes = None

    if request.content_type and "multipart" in request.content_type:
        prompt = request.form.get("prompt", "").strip()
        file   = request.files.get("image")
        if file:
            image_bytes = file.read()
    else:
        data      = request.get_json()
        prompt    = data.get("prompt", "").strip()
        image_url = data.get("image_url", "").strip()

    if not prompt:
        return jsonify({"error": "prompt مطلوب"}), 400
    if not image_url and not image_bytes:
        return jsonify({"error": "image_url أو image file مطلوب"}), 400

    try:
        auth_cookie = get_auth_cookie()
        gen_hdrs = {
            **HEADERS,
            "Content-Type":   "application/json",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "Cookie":         f"sb-gfoafqcjhfqigdwtxwqt-auth-token={auth_cookie}; NEXT_LOCALE=en"
        }

        # If we have bytes, upload them first to get presigned URL
        if image_bytes:
            # Step 1: Get presigned URL
            rp         = requests.post(
                f"{SITE}/api/upload/image/presigned-url",
                headers=gen_hdrs, json={}, timeout=15
            )
            pj         = rp.json()
            signed_url = pj.get("signedUrl")
            image_url  = pj.get("url")

            if not signed_url:
                return jsonify({"error": "فشل الحصول على presigned URL"}), 500

            # Step 2: Upload image
            requests.put(
                signed_url,
                data=image_bytes,
                headers={"Content-Type": "image/jpeg"},
                timeout=30
            )

        # Step 3: Generate with image-to-image
        payload = {
            "prompt":          prompt,
            "generateType":    "image-to-image",
            "modelId":         "nano-banana-pro",
            "aspectRatio":     "1:1",
            "resolution":      "4K",
            "sourceImageUrls": [image_url]
        }

        rg      = requests.post(f"{SITE}/api/image/kie/generate",
                                headers=gen_hdrs, json=payload, timeout=30)
        task_id = rg.json().get("taskId")

        if not task_id:
            return jsonify({"error": "فشل بدء التعديل", "details": rg.text}), 500

        result_url = poll_task(task_id, gen_hdrs)
        return jsonify({"success": True, "image_url": result_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "name": "NanoBananaImg API",
        "rights": "@BOTATKILWA | @x1_v5",
        "endpoints": {
            "POST /edit": {
                "image_url": "str (or multipart image file)",
                "prompt": "str"
            },
            "POST /generate": {
                "aspect_ratio": "1:1 | 16:9 | 9:16",
                "prompt": "str"
            }
        }
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

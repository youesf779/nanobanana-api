from flask import Flask, request, jsonify
from flask_cors import CORS
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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

SITE      = "https://nanobananaimg.com"
SB_URL    = "https://gfoafqcjhfqigdwtxwqt.supabase.co"
SB_ANON   = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imdmb2FmcWNqaGZxaWdkd3R4d3F0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTUzNTY1NDksImV4cCI6MjA3MDkzMjU0OX0.Qe1pmu-LTkQNqNjKEqcARyfqhtlL758eu2gakrz66Og"
MAIL_API  = "https://api.mail.tm"
IMGBB_KEY = "b37210104f155800c8b4d358c75a8ec7"

PROXY = {
    "http":  "http://brd-customer-hl_43f07ec8-zone-isp_proxy1-ip-178.171.83.16:e0zlux04lzwo@brd.superproxy.io:33335",
    "https": "http://brd-customer-hl_43f07ec8-zone-isp_proxy1-ip-178.171.83.16:e0zlux04lzwo@brd.superproxy.io:33335",
}

UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Mobile Safari/537.36"

HEADERS = {
    "User-Agent":         UA,
    "sec-ch-ua":          '"Not(A:Brand";v="8", "Chromium";v="144", "Brave";v="144"',
    "sec-ch-ua-mobile":   "?1",
    "sec-ch-ua-platform": '"Android"',
    "sec-gpc":            "1",
    "accept-language":    "ar-EG,ar;q=0.6",
    "origin":             SITE,
    "referer":            SITE + "/",
}

SB_HDRS = {
    "User-Agent":             UA,
    "Content-Type":           "application/json",
    "authorization":          "Bearer " + SB_ANON,
    "apikey":                 SB_ANON,
    "x-supabase-api-version": "2024-01-01",
    "x-client-info":          "supabase-ssr/0.6.1 createBrowserClient",
    "origin":                 SITE,
    "referer":                SITE + "/",
}


def make_session(use_proxy=False):
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    if use_proxy:
        session.proxies.update(PROXY)
    return session


def rand_str(n=10):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def gen_pkce():
    verifier  = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def get_auth_cookie():
    session = make_session(use_proxy=True)

    # 1. جلب الدومينات
    r       = session.get(MAIL_API + "/domains", timeout=15)
    domains = [d["domain"] for d in r.json().get("hydra:member", [])]
    email   = password = mail_token = None

    # 2. إنشاء إيميل
    for domain in domains:
        e  = rand_str() + "@" + domain
        p  = "Pass" + rand_str(6)
        r2 = session.post(MAIL_API + "/accounts",
                          json={"address": e, "password": p}, timeout=15)
        if r2.status_code not in (200, 201):
            continue
        r3 = session.post(MAIL_API + "/token",
                          json={"address": e, "password": p}, timeout=15)
        if r3.status_code != 200:
            continue
        email, password, mail_token = e, p, r3.json()["token"]
        break

    if not email:
        raise Exception("فشل إنشاء الإيميل")

    # 3. إرسال OTP
    verifier, challenge = gen_pkce()
    session.post(
        SB_URL + "/auth/v1/otp",
        params={"redirect_to": SITE + "/auth/callback?next=%2F"},
        headers=SB_HDRS,
        json={
            "email":                 email,
            "data":                  {},
            "create_user":           True,
            "gotrue_meta_security":  {},
            "code_challenge":        challenge,
            "code_challenge_method": "s256",
        },
        timeout=15,
    )

    # 4. انتظار الرسالة — 3 ثواني بدلاً من 5 — max 20 محاولة = 60 ثانية
    hdrs_mail  = {"Authorization": "Bearer " + mail_token}
    token_hash = None

    for _ in range(20):
        time.sleep(3)
        r    = session.get(MAIL_API + "/messages", headers=hdrs_mail, timeout=15)
        msgs = r.json().get("hydra:member", [])
        if msgs:
            r2   = session.get(MAIL_API + "/messages/" + msgs[0]["id"],
                               headers=hdrs_mail, timeout=15)
            body = r2.json().get("text", "") or str(r2.json().get("html", [""])[0])
            m    = re.search(r"token_hash=(pkce_[^&\s\"<]+)", body)
            if m:
                token_hash = m.group(1)
                break

    if not token_hash:
        raise Exception("لم يصل OTP")

    # 5. التحقق
    rv = session.post(
        SB_URL + "/auth/v1/verify",
        headers=SB_HDRS,
        json={"token_hash": token_hash, "type": "email", "code_verifier": verifier},
        timeout=15,
    )
    rj            = rv.json()
    access_token  = rj.get("access_token")
    refresh_token = rj.get("refresh_token")
    expires_at    = rj.get("expires_at")
    user          = rj.get("user", {})

    if not access_token:
        rx = session.post(
            SB_URL + "/auth/v1/token",
            params={"grant_type": "pkce"},
            headers=SB_HDRS,
            json={"auth_code": token_hash, "code_verifier": verifier},
            timeout=15,
        )
        rj            = rx.json()
        access_token  = rj.get("access_token")
        refresh_token = rj.get("refresh_token")
        expires_at    = rj.get("expires_at")
        user          = rj.get("user", {})

    if not access_token:
        raise Exception("فشل التفعيل")

    cookie_val = "base64-" + base64.b64encode(json.dumps({
        "access_token":  access_token,
        "token_type":    "bearer",
        "expires_in":    3600,
        "expires_at":    expires_at,
        "refresh_token": refresh_token,
        "user":          user,
    }).encode()).decode()

    return cookie_val


def poll_task(task_id, gen_hdrs, timeout=240):
    for _ in range(timeout // 4):
        time.sleep(4)
        try:
            rs     = requests.get(
                SITE + "/api/image/task-status?taskId=" + task_id,
                headers=gen_hdrs,
                timeout=20,
            )
            data   = rs.json()
            status = data.get("status", "")
            if status == "completed":
                urls = data.get("imageUrls", [])
                return urls[0] if urls else None
            if status == "failed":
                raise Exception(data.get("failedReason", "فشل التوليد"))
        except Exception as ex:
            if "فشل التوليد" in str(ex):
                raise
            continue
    raise Exception("انتهى وقت الانتظار")


def upload_to_catbox(image_bytes):
    r   = requests.post(
        "https://catbox.moe/user/api.php",
        data={"reqtype": "fileupload"},
        files={"fileToUpload": ("image.jpg", image_bytes, "image/jpeg")},
        timeout=60,
    )
    url = r.text.strip()
    if url.startswith("https://"):
        return url
    raise Exception("catbox فشل: " + url[:100])


def upload_to_imgbb(image_bytes):
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    r   = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": IMGBB_KEY, "image": b64},
        timeout=60,
    )
    rj = r.json()
    if rj.get("success"):
        return rj["data"]["url"]
    raise Exception("imgbb فشل: " + str(rj.get("error", {}).get("message", "")))


def upload_image(image_bytes):
    try:
        return upload_to_catbox(image_bytes)
    except Exception as e1:
        try:
            return upload_to_imgbb(image_bytes)
        except Exception as e2:
            raise Exception("فشل الرفع — catbox: " + str(e1) + " | imgbb: " + str(e2))


def result_to_cdn(nano_url):
    r = requests.get(nano_url, timeout=60)
    r.raise_for_status()
    return upload_image(r.content)


# ═══════════════════════════════════════════
# POST /generate
# ═══════════════════════════════════════════
@app.route("/generate", methods=["POST"])
def generate():
    data         = request.get_json(force=True)
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
            "Cookie": "sb-gfoafqcjhfqigdwtxwqt-auth-token=" + auth_cookie + "; NEXT_LOCALE=en",
        }
        payload = {
            "prompt":       prompt,
            "generateType": "text-to-image",
            "modelId":      "nano-banana-pro",
            "aspectRatio":  aspect_ratio,
            "resolution":   "4K",
        }
        rg      = requests.post(SITE + "/api/image/kie/generate",
                                headers=gen_hdrs, json=payload, timeout=30)
        task_id = rg.json().get("taskId")
        if not task_id:
            return jsonify({"error": "فشل بدء التوليد", "details": rg.text}), 500

        nano_url  = poll_task(task_id, gen_hdrs)
        image_url = result_to_cdn(nano_url)
        return jsonify({"success": True, "image_url": image_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════
# POST /edit
# ═══════════════════════════════════════════
@app.route("/edit", methods=["POST"])
def edit():
    prompt      = None
    image_url   = None
    image_bytes = None

    if request.content_type and "multipart" in request.content_type:
        prompt = request.form.get("prompt", "").strip()
        f      = request.files.get("image")
        if f:
            image_bytes = f.read()
    else:
        data      = request.get_json(force=True)
        prompt    = data.get("prompt", "").strip()
        image_url = data.get("image_url", "").strip()

    if not prompt:
        return jsonify({"error": "prompt مطلوب"}), 400
    if not image_url and not image_bytes:
        return jsonify({"error": "image_url أو image file مطلوب"}), 400

    try:
        if image_bytes:
            image_url = upload_image(image_bytes)

        auth_cookie = get_auth_cookie()
        gen_hdrs = {
            **HEADERS,
            "Content-Type":   "application/json",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "Cookie": "sb-gfoafqcjhfqigdwtxwqt-auth-token=" + auth_cookie + "; NEXT_LOCALE=en",
        }
        payload = {
            "prompt":          prompt,
            "generateType":    "image-to-image",
            "modelId":         "nano-banana-pro",
            "aspectRatio":     "1:1",
            "resolution":      "4K",
            "sourceImageUrls": [image_url],
        }
        rg      = requests.post(SITE + "/api/image/kie/generate",
                                headers=gen_hdrs, json=payload, timeout=30)
        task_id = rg.json().get("taskId")
        if not task_id:
            return jsonify({"error": "فشل بدء التعديل", "details": rg.text}), 500

        nano_url   = poll_task(task_id, gen_hdrs)
        result_url = result_to_cdn(nano_url)
        return jsonify({"success": True, "image_url": result_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "name":   "NanoBananaImg API",
        "rights": "@BOTATKILWA | @x1_v5",
        "endpoints": {
            "POST /generate": {"prompt": "str", "aspect_ratio": "1:1 | 16:9 | 9:16"},
            "POST /edit":     {"prompt": "str", "image_url": "str (or multipart image file)"},
        },
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

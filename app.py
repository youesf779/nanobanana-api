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
IMGBB_KEY = "b37210104f155800c8b4d358c75a8ec7"

# temp-mail.io internal API — بدون API key
TMAIL_API  = "https://api.internal.temp-mail.io/api/v3"
TMAIL_DOMAINS = ["rfcdrive.com", "mailnull.com", "spamgourmet.com", "yomail.info"]

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

TMAIL_HDRS = {
    "User-Agent":   UA,
    "Content-Type": "application/json",
    "Accept":       "application/json",
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


def safe_request(method, url, max_tries=4, use_proxy=True, **kwargs):
    """
    يعيد المحاولة بـ session جديدة عند أي خطأ اتصال
    يغطي: ConnectionAborted, RemoteDisconnected, ConnectionReset, Timeout
    """
    last_err = None
    for attempt in range(max_tries):
        if attempt > 0:
            time.sleep(2 * attempt)
        try:
            session = make_session(use_proxy=use_proxy)
            fn = session.get if method == "GET" else session.post
            return fn(url, **kwargs)
        except Exception as e:
            last_err = e
            continue
    raise Exception("فشل الاتصال بعد " + str(max_tries) + " محاولات: " + str(last_err))


def rand_str(n=10):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def gen_pkce():
    verifier  = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


# ══════════════════════════════════════════════════
# إنشاء إيميل مؤقت عبر temp-mail.io internal API
# ══════════════════════════════════════════════════
def create_temp_email():
    """
    إنشاء إيميل مؤقت باستخدام temp-mail.io internal API
    Returns: (email_address, token)
    """
    name = rand_str(10)

    for domain in TMAIL_DOMAINS:
        try:
            r = safe_request(
                "POST",
                TMAIL_API + "/email/new",
                headers=TMAIL_HDRS,
                json={"name": name, "domain": domain},
                timeout=15,
                use_proxy=True,
            )
            rj = r.json()
            email   = rj.get("email", "")
            token   = rj.get("token", "")
            if email and "@" in email:
                return email, token
        except Exception:
            continue

    raise Exception("فشل إنشاء الإيميل المؤقت")


def wait_for_otp_message(email, token, max_tries=20, interval=3):
    """
    انتظار وصول رسالة OTP من temp-mail.io
    Returns: body_text of first message
    """
    for _ in range(max_tries):
        time.sleep(interval)
        try:
            r = safe_request(
                "GET",
                TMAIL_API + "/email/" + email + "/messages",
                headers=TMAIL_HDRS,
                timeout=15,
                use_proxy=True,
            )
            messages = r.json().get("messages", [])
            if messages:
                body = messages[0].get("body_text", "") or messages[0].get("body_html", "")
                return body
        except Exception:
            continue

    raise Exception("لم تصل رسالة OTP")


def get_auth_cookie():
    """إنشاء حساب جديد وإرجاع auth cookie"""

    # 1. إنشاء إيميل مؤقت
    email, mail_token = create_temp_email()

    # 2. إرسال OTP من Supabase
    verifier, challenge = gen_pkce()
    safe_request(
        "POST",
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
        use_proxy=False,
    )

    # 3. انتظار وصول الرسالة
    body = wait_for_otp_message(email, mail_token)

    # 4. استخراج token_hash
    m = re.search(r"token_hash=(pkce_[^&\s\"<\]]+)", body)
    if not m:
        raise Exception("لم يُعثر على token_hash في الرسالة")
    token_hash = m.group(1)

    # 5. التحقق
    rv = safe_request(
        "POST",
        SB_URL + "/auth/v1/verify",
        headers=SB_HDRS,
        json={"token_hash": token_hash, "type": "email", "code_verifier": verifier},
        timeout=15,
        use_proxy=False,
    )
    rj            = rv.json()
    access_token  = rj.get("access_token")
    refresh_token = rj.get("refresh_token")
    expires_at    = rj.get("expires_at")
    user          = rj.get("user", {})

    if not access_token:
        rx = safe_request(
            "POST",
            SB_URL + "/auth/v1/token",
            params={"grant_type": "pkce"},
            headers=SB_HDRS,
            json={"auth_code": token_hash, "code_verifier": verifier},
            timeout=15,
            use_proxy=False,
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

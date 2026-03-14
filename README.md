# 🍌 NanoBananaImg API

API لتوليد وتعديل الصور باستخدام NanoBananaImg.

---

## 📁 هيكل المشروع

```
nanobanana-api/
├── app.py            ← السيرفر الرئيسي (Flask)
├── requirements.txt  ← المكتبات المطلوبة
├── Procfile          ← أمر التشغيل (Railway)
├── nixpacks.toml     ← إعدادات Railway
└── .gitignore
```

---

## 🚀 خطوات الرفع على Railway (مضمون 100%)

### الخطوة 1 — رفع المشروع على GitHub

افتح Terminal في مجلد المشروع ونفذ هذه الأوامر بالترتيب:

```bash
git init
git add .
git commit -m "NanoBananaImg API v1.0"
git branch -M main
git remote add origin https://github.com/USERNAME/nanobanana-api.git
git push -u origin main
```

> **ملاحظة:** غيّر `USERNAME` باسم حسابك على GitHub.
> إذا لم يكن عندك repo، أنشئه أولاً على https://github.com/new

---

### الخطوة 2 — Deploy على Railway

1. اذهب إلى https://railway.com
2. سجّل دخول بحساب GitHub
3. اضغط **"New Project"**
4. اختر **"Deploy from GitHub repo"**
5. اختر الـ repo اللي رفعته
6. اضغط **"Deploy Now"**
7. انتظر حتى يكتمل البناء (دقيقتين تقريباً)

---

### الخطوة 3 — توليد الدومين

1. افتح الـ Service المنشأ
2. اذهب إلى **Settings** → **Networking**
3. اضغط **"Generate Domain"**
4. ستحصل على رابط مثل: `https://nanobanana-api-production.up.railway.app`

---

## 📡 استخدام الـ API

### توليد صورة من نص

```bash
curl -X POST https://YOUR-APP.up.railway.app/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a beautiful sunset over the ocean", "aspect_ratio": "16:9"}'
```

**الاستجابة:**
```json
{
  "success": true,
  "image_url": "https://..."
}
```

---

### تعديل صورة (برابط)

```bash
curl -X POST https://YOUR-APP.up.railway.app/edit \
  -H "Content-Type: application/json" \
  -d '{"prompt": "make it more vibrant", "image_url": "https://example.com/image.jpg"}'
```

---

### تعديل صورة (برفع ملف)

```bash
curl -X POST https://YOUR-APP.up.railway.app/edit \
  -F "prompt=make it more vibrant" \
  -F "image=@/path/to/image.jpg"
```

---

## ⚙️ المعاملات المتاحة

| المعامل | القيم | الوصف |
|---------|-------|-------|
| `prompt` | نص | وصف الصورة المطلوبة (مطلوب) |
| `aspect_ratio` | `1:1`, `16:9`, `9:16` | نسبة أبعاد الصورة (افتراضي: `1:1`) |
| `image_url` | رابط URL | صورة المصدر للتعديل |

---

## 🔧 حل المشاكل الشائعة

| المشكلة | الحل |
|---------|------|
| `Application failed to respond` | تأكد من وجود `Procfile` في المجلد الرئيسي |
| `ModuleNotFoundError` | تأكد من وجود جميع المكتبات في `requirements.txt` |
| Timeout بعد 60 ثانية | Railway يدعم حتى 600 ثانية، تأكد من `--timeout 600` في Procfile |
| PORT error | الكود يستخدم `os.environ.get("PORT")` تلقائياً |

---

**Rights:** @BOTATKILWA | @x1_v5

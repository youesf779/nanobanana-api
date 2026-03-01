# 🍌 NanoBanana Pro — Image Generation API

> Created by **@Ok_Sidra**  
> Base URL: `https://nanobananapro-api.up.railway.app`

A headless browser-powered REST API that generates AI images.  
All image URLs are returned as **secure proxied links** — the original source domain is never exposed to the caller.

---

## 📡 Endpoints

### `GET /generate` — Generate an Image

| Parameter | Type   | Required | Default          | Description                        |
|-----------|--------|----------|------------------|------------------------------------|
| `prompt`  | string | ✅ Yes   | —                | Text description of the image      |
| `aspect`  | string | ❌ No    | `1:1`            | Aspect ratio (see /settings)       |
| `model`   | string | ❌ No    | `nano-banana-pro`| Model ID (see /settings)           |

**Example request:**
```
https://nanobananapro-api.up.railway.app/generate?prompt=a futuristic city at sunset&aspect=16:9&model=nano-banana-pro
```

**Example response:**
```json
{
  "success": true,
  "image_url": "https://nanobananapro-api.up.railway.app/img/aHR0cHM6Ly...",
  "task_id": "abc-123-xyz",
  "model": "nano-banana-pro",
  "aspect": "16:9",
  "prompt": "a futuristic city at sunset"
}
```

> ⏱ Generation takes up to **220 seconds**. Be patient!

---

### `GET /settings` — Available Models & Options

Returns all available models, aspect ratios, and API info.

```
https://nanobananapro-api.up.railway.app/settings
```

---

### `GET /img/<token>` — Proxied Image

Streams the generated image. The `<token>` comes from the `image_url` field in `/generate`.  
Use this URL directly in `<img>` tags or download the image.

```
https://nanobananapro-api.up.railway.app/img/<token>
```

---

### `GET /` — API Documentation

Full JSON documentation of all endpoints.

```
https://nanobananapro-api.up.railway.app/
```

---

## 🚀 Deploy on Railway.app

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "NanoBanana Pro API v1.0 by @Ok_Sidra"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/nanobanana-pro-api.git
git push -u origin main
```

### 2. Deploy on Railway

1. Go to [railway.app](https://railway.app) → Sign in with GitHub
2. **New Project** → **Deploy from GitHub repo**
3. Select your repo → Click **Deploy**
4. Railway will auto-detect the **Dockerfile** and build it
5. Go to **Settings → Domains → Generate Domain**

Your API will be live at:  
`https://nanobananapro-api.up.railway.app`

> ⚠️ **Important:** Railway must use the **Dockerfile** (not Nixpacks) because Playwright needs system-level Chromium dependencies. If Railway tries Nixpacks, go to **Settings → Builder → Switch to Dockerfile**.

---

## ⚙️ Aspect Ratios

| Value   | Description          |
|---------|----------------------|
| `1:1`   | Square               |
| `2:3`   | Portrait (tall)      |
| `3:2`   | Landscape            |
| `3:4`   | Portrait             |
| `4:3`   | Classic              |
| `4:5`   | Instagram            |
| `5:4`   | Slightly wide        |
| `9:16`  | Mobile vertical      |
| `16:9`  | Widescreen           |
| `21:9`  | Cinematic            |

## 🤖 Models

| ID                 | Label             | Description                |
|--------------------|-------------------|----------------------------|
| `nano-banana-pro`  | Nano Banana Pro   | Highest quality (default)  |
| `nano-banana`      | Nano Banana       | Standard, faster           |

---

## 🛠 Troubleshooting

| Problem | Solution |
|---------|----------|
| Build fails on Railway | Make sure Railway uses **Dockerfile** not Nixpacks |
| Timeout errors (504) | Generation can take up to 220s, retry the request |
| Invalid token on /img | Use the exact `image_url` returned by `/generate` |
| Workers / memory issues | Keep `--workers 1` in Dockerfile CMD |

---

*Created by @Ok_Sidra*

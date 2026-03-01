# ─────────────────────────────────────────────────────────────
#  NanoBanana Pro API — Dockerfile
#  Uses Microsoft's official Playwright base image (includes
#  Chromium + all OS dependencies pre-installed).
#  Created by: @Ok_Sidra
# ─────────────────────────────────────────────────────────────

FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# Set working directory
WORKDIR /app

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
RUN playwright install chromium

# Copy application source
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port (Railway sets $PORT automatically)
EXPOSE 8000

# ─────────────────────────────────────────────────────────────
#  Gunicorn settings:
#    --timeout 700  → allows up to ~11 min per request
#                     (generation needs up to 220s + browser startup ~60s)
#    --workers 1    → Playwright is heavy; 1 worker avoids OOM
#    --threads 2    → Handle concurrent non-blocking requests
# ─────────────────────────────────────────────────────────────
CMD gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --timeout 700 \
    --workers 1 \
    --threads 2 \
    --log-level info

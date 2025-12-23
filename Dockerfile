# Base image with Playwright and browsers preinstalled (Chromium)
FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

# System settings
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Copy metadata and requirements first (better layer caching)
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && pip install -r requirements.txt

# Copy project files
COPY pyproject.toml .
COPY src ./src
COPY scraper.py ./
COPY docs ./docs
COPY .env.example ./

# Default command: run scraper entrypoint
CMD ["python", "scraper.py"]

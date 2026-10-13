# PC Tracker: the web app and the scheduled job run from this one image.
# Built from the repository root: docker compose -f docker/docker-compose.yml build
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BROWSER_CHANNEL=msedge \
    DATABASE_PATH=/data/tracker.db \
    HOST=0.0.0.0 \
    PORT=5000

WORKDIR /app
COPY requirements.txt .
# The store pages are read with a real browser. It has to be Edge: Croma, ASUS and Acer turn away
# Playwright's own Chromium. Edge for Linux is built for x86-64 only, so the image is too.
# waitress serves the app here in place of Flask's built-in server.
RUN pip install --no-cache-dir -r requirements.txt waitress \
    && playwright install --with-deps msedge \
    && rm -rf /var/lib/apt/lists/*

COPY run.py .
COPY tracker tracker
COPY tools tools
COPY docker/job.py .

# The database lives on a volume so it outlasts the container.
VOLUME /data
EXPOSE 5000
CMD ["waitress-serve", "--host=0.0.0.0", "--port=5000", "run:app"]

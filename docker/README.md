# PC Tracker in containers

Everything needed to run the tracker in Docker lives in this folder; the app itself is unchanged and still runs with `python run.py`.

Two jobs run from one image and share the database on a volume:

- **web**: the website. Its built-in schedule is switched off.
- **job**: one round of price checks and searches, then it exits. A timer starts it every few hours (cron on a server, Task Scheduler on Windows), so nothing has to stay busy between rounds.

Run these from the repository root:

```
docker compose -f docker/docker-compose.yml up -d --build web     # the website, on http://localhost:5000
docker compose -f docker/docker-compose.yml run --rm job          # one round, then it exits
docker compose -f docker/docker-compose.yml down                  # stop; add -v to wipe the database too
```

Set `PORT` first to use another port, for example when the app is already running on 5000. To check prices even if the interval has not passed, end the `run` line with `python job.py --force`.

The container starts with its own empty database, separate from `tracker.db`. Alert credentials come from `.env` in the repository root, which is read at run time and never copied into the image.

| File | What it is |
|---|---|
| `Dockerfile` | The image: Python, the app, Microsoft Edge and the waitress web server |
| `Dockerfile.dockerignore` | Keeps `.env`, `tracker.db` and logs out of the image |
| `docker-compose.yml` | The two services and the shared volume |
| `job.py` | One round of scheduled work, then exit |

The image uses Edge because Croma, ASUS and Acer turn away Playwright's own Chromium: 8 of 11 stores answered with Chromium, 11 of 11 with Edge (October 2026, from a home connection in India). Edge for Linux is x86-64 only, so the image does not build for ARM servers.

# Deploy SaverFrom to Hostinger (via GitHub)

This app is FastAPI. On Hostinger shared/cloud hosting it runs through **Passenger** using the WSGI file at the repo root: `passenger_wsgi.py`.

## 1. Push to GitHub

From the project folder:

```
git add .
git commit -m "Ready for Hostinger"
git push
```

Do **not** commit `.env` (secrets). Keep `.env.example`.

## 2. Connect GitHub in hPanel

1. hPanel → **Git** → import this repository into the domain folder (usually `public_html` or a subdomain folder).
2. Application files must sit at the **application root** (`passenger_wsgi.py`, `backend/`, `frontend/`).

## 3. Setup Python App

hPanel → **Advanced** → **Setup Python App**:

| Field | Value |
|---|---|
| Python version | 3.11 (or 3.12) |
| Application root | the folder that contains `passenger_wsgi.py` |
| Application URL | `/` (or your domain) |
| Application startup file | `passenger_wsgi.py` |
| Application entry point | `application` |
| Passenger log | optional |

Then **Install** dependencies from `backend/requirements.txt` (or the root `requirements.txt`).

## 4. Environment

Copy `.env.example` to `.env` on the server if you need custom paths:

```
ENVIRONMENT=production
DOWNLOADS_DIR=/home/USER/domains/YOURDOMAIN/downloads
```

Create the downloads folder and make it writable. FFmpeg is optional (needed for MP3 conversion). YouTube video download works without FFmpeg.

## 5. Restart

After every Git pull, click **Restart** on the Python app in hPanel.

## VPS instead of shared hosting

Skip Passenger. Run:

```
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

and reverse-proxy with nginx/Apache (see comments in `.htaccess`).

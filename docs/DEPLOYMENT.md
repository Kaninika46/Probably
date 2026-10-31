# Deployment Guide

*Probably High-Value?* is designed as a self-contained, cloud-ready single container that serves both the **FastAPI analytical backend** and the **compiled React SPA** alongside the embedded read-only DuckDB database (`app/app.duckdb`).

---

## Architecture Overview

```
                      +---------------------------------------+
                      |               Internet                |
                      +-------------------+-------------------+
                                          |
                                          v  HTTPS (:443) / HTTP (:PORT)
+-----------------------------------------------------------------------------------+
| Container / Host                                                                  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | FastAPI Web Service (api/main.py on Uvicorn)                                |  |
|  |                                                                             |  |
|  |   * Client-side routes (/, /segments, /lapse, /quality, /about)             |  |
|  |     --> Serves compiled React SPA (web/dist/index.html & assets)            |  |
|  |                                                                             |  |
|  |   * API endpoints (/api/meta, /api/ask, /api/segments, /api/customers/*)   |  |
|  |     --> Executes SQL templates & natural language parsing                   |  |
|  +--------------------------+---------------------------+----------------------+  |
|                             |                           |                         |
|                             v                           v                         |
|                 +-----------------------+   +-----------------------+             |
|                 | app/app.duckdb        |   | reports/tables/*.csv  |             |
|                 | (1.85 MB, Read-Only)  |   | (Audited benchmarks)  |             |
|                 +-----------------------+   +-----------------------+             |
+-----------------------------------------------------------------------------------+
```

Because `app/app.duckdb` and the audited evaluation tables in `reports/tables/` are pre-compiled and committed to the repository, the cloud deployment requires **no data pipeline re-runs, external databases, or object storage credentials**.

---

## Option 1: Render.com (Recommended Free Cloud Hosting)

Render provides free hosting for containerized web services connected directly to your GitHub repository. Whenever you push changes to `main`, Render rebuilds and redeploys automatically.

### Method A: Connect Repository (Quickest UI Setup)

1. Sign up or log in at **[render.com](https://render.com/)**.
2. Click **New +** at the top right and select **Web Service**.
3. Under **Connect a repository**, choose **GitHub** and select `Kaninika46/Probably` (or paste `https://github.com/Kaninika46/Probably`).
4. Configure the service settings:
   - **Name:** `probably-high-value`
   - **Region:** Any (e.g. *Oregon, US* or *Frankfurt, EU*)
   - **Branch:** `main`
   - **Language / Runtime:** **Docker**
   - **Dockerfile Path:** `./Dockerfile`
   - **Instance Type:** **Free**
5. Click **Deploy Web Service**.
6. Render will run the multi-stage Docker build:
   - Node 20 compiles the React frontend (`npm run build`).
   - Python 3.12 installs dependencies and prepares the FastAPI server.
7. Once the build completes, your application is live at a public URL:
   `https://probably-high-value.onrender.com`

### Method B: Render Blueprint (Infrastructure-as-Code)

This repository includes [`render.yaml`](../render.yaml).

1. In Render Dashboard, click **New +** -> **Blueprint**.
2. Connect `https://github.com/Kaninika46/Probably`.
3. Render automatically discovers `render.yaml` and sets up the service with health checks at `/api/health`.
4. Click **Apply**.

---

## Option 2: Hugging Face Spaces (Permanent Free CPU Hosting)

Hugging Face Spaces offers a generous, permanent free tier (2 vCPU, 16 GB RAM) that never spins down or sleeps after 15 minutes.

1. Create a free account at **[huggingface.co](https://huggingface.co/)**.
2. Navigate to **[huggingface.co/new-space](https://huggingface.co/new-space)**.
3. Configure the Space:
   - **Space Name:** `probably-high-value`
   - **Space SDK:** **Docker** -> **Blank**
   - **Space Hardware:** **Free (2 vCPU, 16 GB RAM)**
   - **Visibility:** Public
4. Link your GitHub repository:
   - Go to your Space settings -> **GitHub Repository Sync** (or push directly using git: `git remote add space https://huggingface.co/spaces/<username>/probably-high-value && git push space main`).
5. The container builds and launches on port `7860` (our `Dockerfile` dynamically respects the `$PORT` environment variable provided by Hugging Face).

---

## Option 3: Railway.app / Koyeb / Fly.io

Because this repository provides a standard multi-stage `Dockerfile` and binds to `0.0.0.0:$PORT`:

1. Log in to [railway.app](https://railway.app/) or [koyeb.com](https://www.koyeb.com/).
2. Select **New Project** -> **Deploy from GitHub repo** -> `Kaninika46/Probably`.
3. The platform automatically detects `Dockerfile`, builds the image, and provisions an HTTPS domain.

---

## Option 4: Local Docker Run

To run the containerized application on a machine with Docker installed:

```bash
# 1. Clone repository
git clone https://github.com/Kaninika46/Probably.git
cd Probably

# 2. Build the Docker image
docker build -t probably-high-value .

# 3. Run the container on port 8000
docker run -d -p 8000:8000 --name probably-app probably-high-value

# 4. Open in browser
open http://localhost:8000
```

To stop the container:
```bash
docker stop probably-app && docker rm probably-app
```

---

## Option 5: Local Native Production Run (No Docker Required)

On Windows without Docker:

```cmd
# Rebuilds the frontend bundle and runs FastAPI on http://localhost:8000
run_app.bat
```

Or manually:
```bash
# Build React SPA
cd web
npm ci
npm run build
cd ..

# Run FastAPI server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## Post-Deployment Smoke Test Checklist

Once deployed to any cloud host, verify the following endpoints:

| Check | URL / Action | Expected Result |
| :--- | :--- | :--- |
| **Health Check** | `GET /api/health` | `{"status": "ok"}` with HTTP 200 |
| **Metadata** | `GET /api/meta` | HTTP 200 with 3,961 customers, Okabe-Ito colors, and calibrated gate metrics |
| **React SPA** | `GET /` | Loads Overview page with KPIs, executive summary, and live status pill |
| **Segments Page** | `GET /segments` | Renders Okabe-Ito cards, GMM vs. K-Means selector, and 3,961-dot scatter plot |
| **Customer Drawer**| Click any customer row | Slides in customer profile with RFM, GMM posterior, and tree rule trace |
| **Lapse Watchlist**| `GET /lapse` | Displays calibration reliability curve (ECE = 0.0416) and customer table |
| **Ask Engine (NL)**| `POST /api/ask` on `/ask` | Questions like *"Which customers are probably Champions?"* parse in <15ms with probabilistic SQL |
| **Quality Page** | `GET /quality` | Displays full cleaning funnel, bootstrap stability histogram, and gate scorecard |
| **About Page** | `GET /about` | Shows offline system architecture diagram and verified citations |

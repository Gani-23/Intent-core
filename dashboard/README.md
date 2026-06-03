# Dashboard

Separate Vite frontend for Living Systems Auditor.

## Stack

- React
- Vite
- anime.js
- Lenis
- Three.js via `@react-three/fiber` and `@react-three/drei`

## Local

Backend:

```bash
cd /Users/gani/Desktop/Intent-drive/living-systems-auditor
./.venv/bin/python -m uvicorn lsa.api.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd /Users/gani/Desktop/Intent-drive/living-systems-auditor/dashboard
npm install
npm run dev -- --host 127.0.0.1
```

Open:

- [http://127.0.0.1:5173/](http://127.0.0.1:5173/)
- [http://127.0.0.1:5173/command](http://127.0.0.1:5173/command)

## Environment

Copy `.env.example` if the frontend is deployed separately:

```bash
cp .env.example .env
```

- `VITE_API_BASE_URL` points at the FastAPI backend.

For backend CORS in a deployed split setup:

- `LSA_API_ALLOWED_ORIGINS=http://localhost:5173,https://your-frontend-host`

## Current scope

- cinematic landing page
- command center for health, readiness, analytics, queues, alerts
- actor/API-key config sheet for protected routes
- direct actions for runtime rehearsal, operational validation, and alert emission

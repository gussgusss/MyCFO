# MyCFO

API-first CFO copilot for a hackathon MVP: org-scoped auth, workspaces, deterministic ingest, metrics, forecasts, scenarios, and alerts.

## MVP scope

- Flask API deployed through Vercel
- Neon Postgres in production
- JWT auth with organization scoping
- Stripe `export` ingest only for MVP
- Expense ingest
- Metrics, forecasts, scenarios, and alerts
- AI layer deferred until the deterministic engine is stable

## Quickstart

1. Create a virtualenv and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment variables:

```bash
cp .env.example .env
```

3. Initialize the database:

```bash
export FLASK_APP=api/index.py
flask init-db
```

4. Run locally:

```bash
flask run
```

## Required environment variables

- `DATABASE_URL`
- `JWT_SECRET`
- `JWT_ACCESS_TTL_SECONDS`

## Notes

- `DATABASE_URL` defaults to `sqlite:///mycfo.db` for local scaffolding only.
- Production should use Neon Postgres.
- Live Stripe API pull is intentionally not implemented in-app for MVP. Document it as a future extension after the export-based demo flow is solid.

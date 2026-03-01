# MyCFO

API-first CFO copilot for a hackathon MVP: org-scoped auth, workspaces, deterministic ingest, metrics, forecasts, scenarios, and alerts.

## MVP scope

- Flask API deployed through Vercel
- Neon Postgres in production
- JWT auth with organization scoping
- Stripe `export` ingest only for MVP
- Expense ingest
- Metrics, forecasts, scenarios, and alerts
- AI suggestions grounded in computed alerts via Hugging Face inference

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

## Useful development commands

Initialize the schema:

```bash
python -m flask init-db
```

Reset all tables in development only:

```bash
python -m flask reset-db --yes
```

## Required environment variables

- `DATABASE_URL`
- `JWT_SECRET`
- `JWT_ACCESS_TTL_SECONDS`
- `HUGGINGFACE_API_KEY` for AI suggestions

## Optional AI configuration

- `HUGGINGFACE_MODEL`
- `HUGGINGFACE_TIMEOUT_SECONDS`

## Notes

- `DATABASE_URL` defaults to `sqlite:///mycfo.db` for local scaffolding only.
- Production should use Neon Postgres.
- Live Stripe API pull is intentionally not implemented in-app for MVP. Document it as a future extension after the export-based demo flow is solid.
- AI suggestions are advisory only and are grounded on alert and metric outputs already computed by the API.

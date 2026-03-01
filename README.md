# MyCFO

API-first CFO copilot: organization-scoped auth, workspaces, deterministic ingest, metrics, forecasts, scenarios, alerts, and AI-powered recommendations.

## Links

- **API Base URL:** https://my-cfo-sigma.vercel.app/
- **API Docs (GitHub Pages):** https://gussgusss.github.io/MyCFO

## Overview

MyCFO is a backend Web API that helps teams track burn, revenue, runway, and recurring metrics.  
It supports structured financial ingest, Stripe integration, and alert-driven AI suggestions.

## Core Features

- Flask API deployed through Vercel
- Neon Postgres in production
- JWT auth with organization scoping
- Manual expense ingest
- Manual revenue ingest
- Live Stripe API ingest using a Stripe secret key
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
- Stripe API pull is implemented in-app through `POST /v1/workspaces/<workspace_id>/ingest/stripe` and expects `stripe_api_key` in the request body.
- AI suggestions are advisory only and are grounded on alert and metric outputs already computed by the API.

## Metric Definitions

- `burn_cents_30d`: total 30-day expenses minus net revenue
- `recurring_burn_cents_30d`: recurring 30-day expenses minus net revenue
- `runway_months`: `cash_on_hand_cents / recurring_burn_cents_30d` when recurring burn is positive; otherwise `null`
- `mrr_cents`: recurring revenue only, including manual `recurring` revenue and recurring Stripe invoice revenue

## Ingest Modes

- `POST /v1/workspaces/<workspace_id>/ingest/expenses`: manual expense events
- `POST /v1/workspaces/<workspace_id>/ingest/revenue`: manual revenue events with subtype `recurring` or `one_time`
- `POST /v1/workspaces/<workspace_id>/ingest/stripe`: live Stripe pull using the provided `stripe_api_key`

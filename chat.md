
# CLAUDE.md — MyCFO API (Flask + Vercel + Neon Postgres + JWT)

MyCFO is an **API-only CFO copilot**: ingest revenue (Stripe snapshot) + expenses + assumptions and return **CFO-grade metrics, forecasts, alerts, and recommendations**, with optional AI-generated memos grounded in computed results.

This project is judged on API craftsmanship: clarity, predictable behavior, correctness, great errors, and great docs. :contentReference[oaicite:0]{index=0}

---

## 0) Decisions locked in
- Backend: **Flask**
- Deployment: **Vercel** (serverless)
- DB: **Neon Postgres**
- Auth: **JWT (Bearer tokens)** with **Organizations**
- Docs: **Static HTML/CSS on GitHub Pages** + README cURL examples

---

## 1) Product goal (1 sentence)
Provide a secure API for businesses to compute CFO metrics (MRR/ARR/burn/runway/churn), produce forecasts (base/best/worst), run what-if scenarios, and emit alerts—using deterministic calculations, plus optional AI summaries grounded in stored outputs.

---

## 2) Non-goals
- No UI
- No accounting compliance claims
- No “LLM does the math” (AI is only narrative on top of computed data)
- No full Stripe Connect OAuth in MVP

---

## 3) Architecture overview (serverless-friendly)
### Key constraints on Vercel
- Serverless is stateless → **all state in Postgres**
- Avoid long-running work → ingest should be synchronous or “fake async” (return `202` but complete quickly)
- DB connections can explode → use safe connection strategy (see §8)

### Runtime layout
- Flask app exposed as a single Vercel function entrypoint
- Postgres stores all org/workspace/transactions/forecasts/scenarios/alerts/idempotency
- Optional AI endpoint uses computed outputs only (no raw private context outside org scope)

---

## 4) Authentication + Organizations (JWT)
### Principles
- Every request (except register/login) requires:
 `Authorization: Bearer <access_token>`
- Data isolation via `org_id` derived from JWT.
- JWT is short-lived; refresh token is optional (recommended).

### Roles
- `owner`, `admin`, `member`
MVP authorization:
- Owner/admin can ingest + forecast + scenarios
- Member can read metrics/forecasts (optional; keep simple)

### Endpoints
#### Register (creates org + first user)
`POST /v1/auth/register`
Body:
```json
{
 "org_name": "Acme Inc",
 "email": "ceo@acme.com",
 "password": "..."
}
Returns:
{ "user": {...}, "org": {...}, "access_token": "...", "refresh_token": "..." }
Login
POST /v1/auth/login
Body:
{ "email": "ceo@acme.com", "password": "..." }
Refresh (optional but good)
POST /v1/auth/refresh
Body:
{ "refresh_token": "..." }
Logout (optional)
POST /v1/auth/logout
Security notes
Password hashing: argon2id preferred, bcrypt ok.
Store refresh tokens hashed (never plaintext).
JWT claims: sub (user_id), org_id, role, exp, iat.

5) Core resources
Workspace: company “model” within an org (useful if org manages multiple products/brands)
Transactions: normalized revenue/expense events
ForecastRun: saved forecast outputs
Scenario: what-if deltas vs a baseline forecast
Alert: computed warnings (runway low, MRR drop, etc.)
Idempotency records: cache responses for safe retries

6) API surface (v1)
Workspaces
Create workspace
POST /v1/workspaces
Body:
{ "name": "Cerestial Farms" }
List workspaces
GET /v1/workspaces?limit=20&starting_after=ws_...
Get workspace
GET /v1/workspaces/{workspace_id}

Ingest (Stripe snapshot + expenses)
Ingest Stripe snapshot (hackathon-friendly)
POST /v1/workspaces/{workspace_id}/ingest/stripe
Body (export mode):
{
 "mode": "export",
 "payload": { "invoices": [], "subscriptions": [], "charges": [], "refunds": [] }
}
Returns:
{ "ingest_id": "ing_123", "status": "completed", "inserted": 120, "duplicates": 5 }
Optional later: mode="api_key" to pull with Stripe SDK (not required for MVP).
Ingest expenses
POST /v1/workspaces/{workspace_id}/ingest/expenses
Body:
{
 "expenses": [
   { "subtype": "recurring_expense", "amount_cents": 120000, "currency": "USD", "occurred_at": "2026-02-01", "vendor": "AWS" },
   { "subtype": "one_time_expense", "amount_cents": 500000, "currency": "USD", "occurred_at": "2026-02-15", "vendor": "Contractor" }
 ]
}

CFO Outputs
Metrics (core value)
GET /v1/workspaces/{workspace_id}/metrics?as_of=YYYY-MM-DD
Returns (example):
{
 "as_of": "2026-02-27",
 "currency": "USD",
 "mrr_cents": 2150000,
 "arr_cents": 25800000,
 "gross_revenue_cents_30d": 2400000,
 "refunds_cents_30d": -80000,
 "net_revenue_cents_30d": 2320000,
 "burn_cents_30d": 1500000,
 "cash_on_hand_cents": 5000000,
 "runway_months": 3.33,
 "logo_churn_pct_month": 3.0,
 "revenue_churn_pct_month": 2.1,
 "arpa_cents": 43000,
 "warnings": [
   { "code": "missing_cash", "message": "cash_on_hand not provided; runway may be null." }
 ]
}
Forecast
POST /v1/workspaces/{workspace_id}/forecasts
Body:
{
 "as_of": "2026-02-27",
 "horizon_months": 12,
 "assumptions": {
   "mrr_growth_pct": 6,
   "monthly_logo_churn_pct": 3,
   "gross_margin_pct": 85,
   "starting_cash_cents": 5000000
 },
 "variants": {
   "base": {},
   "best": { "mrr_growth_pct": 9, "monthly_logo_churn_pct": 2 },
   "worst": { "mrr_growth_pct": 3, "monthly_logo_churn_pct": 5 }
 }
}
Returns:
{
 "id": "fc_123",
 "workspace_id": "ws_123",
 "as_of": "2026-02-27",
 "horizon_months": 12,
 "assumptions": { ... },
 "series": {
   "months": ["2026-03","2026-04"],
   "base": { "mrr_cents": [..], "cash_cents":[..], "runway_months":[..] },
   "best": { ... },
   "worst": { ... }
 }
}
List forecasts
GET /v1/workspaces/{workspace_id}/forecasts?limit=20&starting_after=fc_...
Get forecast
GET /v1/workspaces/{workspace_id}/forecasts/{forecast_id}

Actions
Create scenario (what-if)
POST /v1/workspaces/{workspace_id}/scenarios
Body:
{
 "baseline_forecast_id": "fc_123",
 "delta": { "type": "price_change", "pct": 0.10 }
}
Other delta examples:
{ "type": "churn_change", "delta_pp": 1.0 }
{ "type": "hire", "role": "eng", "monthly_cost_cents": 1200000, "start_month": "2026-04" }
Alerts
GET /v1/workspaces/{workspace_id}/alerts?limit=50
Rules (MVP):
runway < 6 months → warn
MRR down > 8% WoW → warn
refunds > 2x previous 30d → warn
churn above threshold → warn/critical

Optional AI (grounded)
Board memo (AI narrative, grounded in computed IDs)
POST /v1/workspaces/{workspace_id}/ai/board_memo
Body:
{ "forecast_id": "fc_123", "scenario_ids": ["sc_1","sc_2"] }
Returns:
{
 "source_forecast_id": "fc_123",
 "memo": "...",
 "bullets": ["..."],
 "risks": ["..."],
 "recommended_actions": [
   { "action": "Increase price by 10%", "expected_runway_months_gain": 0.4 }
 ]
}

7) Conventions: idempotency, pagination, errors (judge candy)
These align with evaluation expectations: predictable behavior, correct status codes, good DX.
stripe_track
Idempotency
All POSTs that create/modify state support:
Idempotency-Key: <string>
Behavior:
Same key + same request body → return cached response
Same key + different body → 409 idempotency_key_reuse
Pagination (lists)
Query params:
limit (default 20, max 100)
starting_after
Response shape:
{ "data": [...], "has_more": true }
Error schema (single format everywhere)
{
 "error": {
   "type": "invalid_request",
   "code": "missing_field",
   "message": "starting_cash_cents is required for forecasts",
   "param": "assumptions.starting_cash_cents",
   "request_id": "req_..."
 }
}
Status codes
200 OK (reads)
201 Created (create)
202 Accepted (optional for ingest)
400 Bad Request (malformed JSON)
401 Unauthorized (no/invalid token)
403 Forbidden (wrong org / role)
404 Not Found
409 Conflict (idempotency mismatch)
422 Unprocessable Entity (validation)
429 Too Many Requests (optional)
500 Internal Error
Request IDs
Return X-Request-Id header on all responses; include request_id in error bodies.

8) Neon Postgres + Vercel specifics (don’t get burned)
Env vars (Vercel Project Settings)
Required:
DATABASE_URL (Neon connection string)
JWT_SECRET
JWT_ACCESS_TTL_SECONDS (e.g., 1800)
Optional:
OPENAI_API_KEY (only if AI memo)
STRIPE_API_KEY (only if API-pull ingest)
APP_ENV=production|development
DB connection strategy for serverless
Create a global connection pool object that can be reused when the function instance is warm.
Always close cursors; never leak connections.
Prefer a serverless-friendly driver/ORM configuration.
Implementation guidance:
If using SQLAlchemy: configure pool_pre_ping=True, modest pool_size, and safe recycling.
Alternatively use psycopg/psycopg2 directly with a small pool.
Migrations
Pick one:
Flask-Migrate (Alembic)
A single schema.sql run once (fastest hackathon approach)

9) Database schema (minimal but solid)
organizations
id (uuid, pk)
name (text)
created_at (timestamptz)
users
id (uuid, pk)
org_id (fk organizations)
email (text, unique)
password_hash (text)
role (text)
created_at (timestamptz)
refresh_tokens (optional)
id (uuid, pk)
user_id (fk users)
token_hash (text)
expires_at (timestamptz)
revoked_at (timestamptz, nullable)
workspaces
id (text like ws_..., pk)
org_id (fk organizations)
name (text)
created_at
transactions
id (text txn_..., pk)
org_id (fk organizations) // or rely on workspace join; org_id is convenient for scoping
workspace_id (fk workspaces)
type (revenue|expense)
subtype (invoice|charge|refund|recurring_expense|one_time_expense)
amount_cents (bigint, signed)
currency (text)
occurred_at (timestamptz)
external_source (stripe|manual)
external_id (text, nullable) // e.g., in_..., ch_...
customer_ref (text, nullable)
metadata (jsonb)
Indexes/constraints:
UNIQUE(workspace_id, external_source, external_id) where external_id not null
index on (workspace_id, occurred_at)
index on (workspace_id, subtype)
forecasts
id (text fc_..., pk)
org_id
workspace_id
as_of (date)
horizon_months (int)
assumptions (jsonb)
series (jsonb) // store time series arrays
created_at
scenarios
id (text sc_..., pk)
org_id
workspace_id
baseline_forecast_id (fk forecasts)
delta (jsonb)
impact (jsonb)
series (jsonb)
created_at
alerts
id (text al_..., pk)
org_id
workspace_id
type (text)
severity (text)
message (text)
payload (jsonb)
created_at
idempotency_keys
id (uuid, pk)
org_id
key (text)
request_hash (text)
response_status (int)
response_body (jsonb)
created_at
Constraint:
UNIQUE(org_id, key)

10) Deterministic calculation definitions (document these)
Revenue (30d): sum of revenue transactions in [as_of-30d, as_of]
Refunds (30d): sum of refund transactions (negative)
Net revenue (30d): gross + refunds
Burn (30d): expenses (positive) - net revenue (or define consistently; choose one and document)
Runway: cash_on_hand / monthly_burn (if burn <= 0 → runway = null or very large; document)
MRR: derived from Stripe invoices/subscriptions OR from recurring revenue events; document method.
Churn: based on subscription end/cancel events if available; otherwise approximate (document approximation).
Put all formulas in services/metrics.py with unit tests.

11) Docs (GitHub Pages) + README checklist
Minimum docs in README required; hosted docs is bonus.
stripe_track
Docs must include:
Quickstart (run locally)
Auth: register/login + bearer token example
Error schema + examples
Idempotency rules
Pagination rules
Endpoint reference + cURL for each endpoint
Example: end-to-end flow (register → create workspace → ingest → metrics → forecast → scenario)

12) Local development
Use .env with:
DATABASE_URL (Neon)
JWT_SECRET
Provide make dev or flask run
Provide scripts/seed_demo.py:
creates org/user/workspace
ingests sample expenses + sample Stripe export fixture
prints metrics + forecast id

13) Vercel deployment checklist
Add DATABASE_URL + auth secrets in Vercel env vars
Ensure Flask entrypoint works with Vercel routing
Confirm all endpoints work on localhost (minimum requirement)
 stripe_track
Smoke test with cURL

14) Testing requirements
Unit tests:
metrics math
forecast math
scenario deltas
idempotency behavior
JWT auth middleware (org scoping)
Integration tests:
register/login
create workspace
ingest expenses + stripe export
metrics
forecast
scenario
Golden fixtures:
fixtures/stripe_export_min.json
fixtures/expenses_min.json
fixtures/expected_metrics.json

15) Implementation order (do not deviate)
DB schema + migrations
Auth: register/login + JWT middleware + org scoping
Workspaces CRUD
Ingest expenses (easy deterministic)
Metrics endpoint (core)
Forecast endpoint (store result)
Scenarios (1–2 delta types)
Alerts (2 rules)
AI board memo (optional, last)

16) Quality bar reminders
Every endpoint must return 2xx on valid input and informative errors otherwise
 stripe_track
Keep naming consistent (/v1/workspaces/..., plural nouns)
Don’t leak data across orgs (403/404 as appropriate)
Prefer “boring and correct” over “magical and vague”

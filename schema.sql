CREATE TABLE IF NOT EXISTS organizations (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS workspaces (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES organizations (id),
  name TEXT NOT NULL,
  settings JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES organizations (id),
  workspace_id TEXT NOT NULL REFERENCES workspaces (id),
  type TEXT NOT NULL,
  subtype TEXT NOT NULL,
  amount_cents BIGINT NOT NULL,
  currency TEXT NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,
  external_source TEXT,
  external_id TEXT,
  customer_ref TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_workspace_external_record UNIQUE (workspace_id, external_source, external_id)
);

CREATE INDEX IF NOT EXISTS ix_transactions_workspace_occurred_at
  ON transactions (workspace_id, occurred_at);

CREATE INDEX IF NOT EXISTS ix_transactions_workspace_subtype
  ON transactions (workspace_id, subtype);

CREATE TABLE IF NOT EXISTS forecasts (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES organizations (id),
  workspace_id TEXT NOT NULL REFERENCES workspaces (id),
  as_of DATE NOT NULL,
  horizon_months INTEGER NOT NULL,
  assumptions JSONB NOT NULL,
  series JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS scenarios (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES organizations (id),
  workspace_id TEXT NOT NULL REFERENCES workspaces (id),
  baseline_forecast_id TEXT NOT NULL REFERENCES forecasts (id),
  delta JSONB NOT NULL,
  impact JSONB NOT NULL,
  series JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES organizations (id),
  workspace_id TEXT NOT NULL REFERENCES workspaces (id),
  type TEXT NOT NULL,
  severity TEXT NOT NULL,
  message TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES organizations (id),
  key TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  response_status INTEGER NOT NULL,
  response_body JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_org_idempotency_key UNIQUE (org_id, key)
);

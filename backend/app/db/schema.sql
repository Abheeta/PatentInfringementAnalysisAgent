CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  system_prompt TEXT DEFAULT '',
  chart_uploaded INTEGER DEFAULT 0,
  generated INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rows (
  id INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  claim_element TEXT NOT NULL,
  product_feature TEXT NOT NULL,
  ai_reasoning TEXT NOT NULL,
  confidence TEXT CHECK(confidence IN ('Strong','Moderate','Weak')),

  flagged INTEGER DEFAULT 0,

  previous_product_feature TEXT,
  previous_ai_reasoning TEXT,
  previous_confidence TEXT,

  pending_value TEXT,
  pending_reasoning TEXT,
  pending_confidence TEXT
);

CREATE TABLE IF NOT EXISTS evidence_docs (
  id INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  source_type TEXT CHECK(source_type IN ('upload','url')),
  source_label TEXT,
  content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  role TEXT CHECK(role IN ('user','assistant')),
  content TEXT NOT NULL,
  row_id INTEGER REFERENCES rows(id),
  created_at TEXT DEFAULT (datetime('now'))
);

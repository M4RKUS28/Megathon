from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import Settings, get_settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  target_audience TEXT NOT NULL,
  language TEXT NOT NULL,
  difficulty TEXT NOT NULL,
  desired_duration_minutes INTEGER NOT NULL,
  company_context TEXT NOT NULL,
  compliance_requirements TEXT NOT NULL,
  source_material TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  approved_at TEXT
);

CREATE TABLE IF NOT EXISTS course_plans (
  id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL REFERENCES courses(id),
  plan_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS course_specs (
  id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL REFERENCES courses(id),
  spec_markdown TEXT NOT NULL,
  spec_json TEXT NOT NULL,
  asset_manifest_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL REFERENCES courses(id),
  template_link TEXT NOT NULL,
  type TEXT NOT NULL,
  dimensions TEXT NOT NULL,
  description TEXT NOT NULL,
  purpose TEXT NOT NULL,
  status TEXT NOT NULL,
  final_url TEXT,
  validation_result TEXT,
  source TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devin_jobs (
  id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL REFERENCES courses(id),
  phase TEXT NOT NULL,
  devin_session_id TEXT,
  devin_job_id TEXT,
  prompt TEXT NOT NULL,
  status TEXT NOT NULL,
  branch TEXT,
  commit_sha TEXT,
  pr_url TEXT,
  transcript_summary TEXT,
  raw_status_payload TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS devin_events (
  id TEXT PRIMARY KEY,
  course_id TEXT,
  devin_job_id TEXT,
  event_type TEXT NOT NULL,
  status TEXT NOT NULL,
  message TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generated_prompts (
  id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL REFERENCES courses(id),
  phase TEXT NOT NULL,
  prompt TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS qa_results (
  id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL REFERENCES courses(id),
  status TEXT NOT NULL,
  results_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hosted_outputs (
  id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL REFERENCES courses(id),
  course_url TEXT NOT NULL,
  iframe_url TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lms_progress (
  id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL REFERENCES courses(id),
  learner_name TEXT NOT NULL,
  role TEXT NOT NULL,
  progress_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""


def _sqlite_path(database_url: str) -> str:
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// DATABASE_URL values are supported for the local demo")
    return database_url.removeprefix("sqlite:///")


def _connect(settings: Settings | None = None) -> sqlite3.Connection:
    settings = settings or get_settings()
    path = _sqlite_path(settings.database_url)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db(settings: Settings | None = None) -> Iterator[sqlite3.Connection]:
    conn = _connect(settings)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(settings: Settings | None = None) -> None:
    with db(settings) as conn:
        conn.executescript(SCHEMA)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def loads_json(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)

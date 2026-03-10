import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data.db"


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def get_connection():
    connection = _connect()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workspaces (
                workspace_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                industry TEXT NOT NULL,
                owner_user_id TEXT NOT NULL,
                plan_name TEXT NOT NULL DEFAULT 'Starter',
                quota_limit INTEGER NOT NULL DEFAULT 30,
                quota_used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(owner_user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS memberships (
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                PRIMARY KEY(workspace_id, user_id),
                FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );


            CREATE TABLE IF NOT EXISTS brand_profiles (
                brand_profile_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL UNIQUE,
                brand_name TEXT NOT NULL,
                industry TEXT NOT NULL,
                tone_of_voice TEXT NOT NULL,
                target_audience TEXT,
                value_proposition TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
                FOREIGN KEY(created_by) REFERENCES users(user_id),
                FOREIGN KEY(updated_by) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS social_accounts (
                social_account_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                account_handle TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
                FOREIGN KEY(created_by) REFERENCES users(user_id),
                FOREIGN KEY(updated_by) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS analytics_events (
                event_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                metric_date TEXT NOT NULL,
                reach INTEGER NOT NULL DEFAULT 0,
                likes INTEGER NOT NULL DEFAULT 0,
                comments INTEGER NOT NULL DEFAULT 0,
                clicks INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
                FOREIGN KEY(created_by) REFERENCES users(user_id)
            );
            CREATE TABLE IF NOT EXISTS campaigns (
                campaign_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                name TEXT NOT NULL,
                objective TEXT NOT NULL,
                status TEXT NOT NULL,
                budget_monthly REAL NOT NULL DEFAULT 0,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
                FOREIGN KEY(created_by) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                campaign_id TEXT,
                name TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                status TEXT NOT NULL,
                winner_variant_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS experiment_variants (
                variant_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                label TEXT NOT NULL,
                hook TEXT NOT NULL,
                cta TEXT NOT NULL,
                impressions INTEGER NOT NULL DEFAULT 0,
                clicks INTEGER NOT NULL DEFAULT 0,
                conversions INTEGER NOT NULL DEFAULT 0,
                score REAL NOT NULL DEFAULT 0,
                FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS lead_events (
                lead_event_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                source TEXT NOT NULL,
                contact_handle TEXT NOT NULL,
                intent TEXT NOT NULL,
                status TEXT NOT NULL,
                score INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS content_plans (
                item_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                day INTEGER NOT NULL,
                platform TEXT NOT NULL,
                topic TEXT NOT NULL,
                hook TEXT NOT NULL,
                cta TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
            );


            CREATE TABLE IF NOT EXISTS content_assets (
                asset_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                post_idea TEXT NOT NULL,
                photo_brief TEXT NOT NULL,
                caption_options TEXT NOT NULL,
                selected_caption TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(workspace_id, item_id),
                FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
                FOREIGN KEY(item_id) REFERENCES content_plans(item_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS content_reviews (
                review_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                risk_score REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                resolved_by TEXT,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
                FOREIGN KEY(item_id) REFERENCES content_plans(item_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS idempotency_keys (
                workspace_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                action TEXT NOT NULL,
                response_payload TEXT NOT NULL,
                PRIMARY KEY(workspace_id, idempotency_key, action)
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                audit_id TEXT PRIMARY KEY,
                workspace_id TEXT,
                user_id TEXT,
                action TEXT NOT NULL,
                metadata TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS feature_flag_overrides (
                workspace_id TEXT NOT NULL,
                flag_key TEXT NOT NULL,
                flag_value TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(workspace_id, flag_key),
                FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
                FOREIGN KEY(updated_by) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS rate_limits (
                key TEXT PRIMARY KEY,
                window_start INTEGER NOT NULL,
                request_count INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS publish_jobs (
                job_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                status TEXT NOT NULL,
                retry_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                processing_started_at TEXT,
                next_attempt_at TEXT,
                provider_response TEXT,
                idempotency_key TEXT,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
                FOREIGN KEY(item_id) REFERENCES content_plans(item_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS dead_letter_jobs (
                dlq_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                moved_at TEXT NOT NULL
            );


            CREATE TABLE IF NOT EXISTS trace_events (
                trace_event_id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                duration_ms REAL NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ai_decisions (
                decision_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
            );
            """
        )

        if not _column_exists(conn, "publish_jobs", "retry_count"):
            conn.execute("ALTER TABLE publish_jobs ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")
        if not _column_exists(conn, "publish_jobs", "last_error"):
            conn.execute("ALTER TABLE publish_jobs ADD COLUMN last_error TEXT")
        if not _column_exists(conn, "publish_jobs", "processing_started_at"):
            conn.execute("ALTER TABLE publish_jobs ADD COLUMN processing_started_at TEXT")
        if not _column_exists(conn, "publish_jobs", "next_attempt_at"):
            conn.execute("ALTER TABLE publish_jobs ADD COLUMN next_attempt_at TEXT")
        if not _column_exists(conn, "publish_jobs", "provider_response"):
            conn.execute("ALTER TABLE publish_jobs ADD COLUMN provider_response TEXT")
        if not _column_exists(conn, "publish_jobs", "idempotency_key"):
            conn.execute("ALTER TABLE publish_jobs ADD COLUMN idempotency_key TEXT")

        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_publish_jobs_idempotency ON publish_jobs(idempotency_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_analytics_workspace_date ON analytics_events(workspace_id, metric_date)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_social_accounts_workspace_platform_handle ON social_accounts(workspace_id, platform, account_handle)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_social_accounts_workspace_platform ON social_accounts(workspace_id, platform)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trace_events_created_at ON trace_events(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feature_flag_overrides_workspace ON feature_flag_overrides(workspace_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_content_assets_workspace_item ON content_assets(workspace_id, item_id)")


def reset_db() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()


init_db()

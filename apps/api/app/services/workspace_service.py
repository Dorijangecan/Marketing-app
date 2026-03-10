from datetime import datetime, timezone
from uuid import uuid4

from ..db.sqlite_store import get_connection


class WorkspaceService:
    def create_workspace(self, user_id: str, name: str, industry: str, plan_name: str = "Starter") -> dict:
        workspace_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        quota_limit = {"Starter": 30, "Pro": 100, "Agency": 1000000}.get(plan_name, 30)

        with get_connection() as conn:
            user_exists = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if not user_exists:
                raise ValueError("User not found")

            conn.execute(
                """
                INSERT INTO workspaces(workspace_id, name, industry, owner_user_id, plan_name, quota_limit, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (workspace_id, name, industry, user_id, plan_name, quota_limit, created_at),
            )
            conn.execute(
                "INSERT INTO memberships(workspace_id, user_id, role) VALUES (?, ?, 'owner')",
                (workspace_id, user_id),
            )

        return {
            "workspace_id": workspace_id,
            "name": name,
            "industry": industry,
            "owner_user_id": user_id,
            "plan_name": plan_name,
            "quota_limit": quota_limit,
        }

    def get_workspace(self, workspace_id: str, user_id: str) -> dict:
        self.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT w.workspace_id, w.name, w.industry, w.owner_user_id, w.plan_name, w.quota_limit, w.quota_used, m.role
                FROM workspaces w
                JOIN memberships m ON m.workspace_id = w.workspace_id
                WHERE w.workspace_id = ? AND m.user_id = ?
                """,
                (workspace_id, user_id),
            ).fetchone()
        if row is None:
            raise ValueError("Workspace not found")
        return dict(row)

    def list_user_workspaces(self, user_id: str) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT w.workspace_id, w.name, w.industry, w.owner_user_id, w.plan_name, w.quota_limit, w.quota_used, m.role
                FROM workspaces w
                JOIN memberships m ON m.workspace_id = w.workspace_id
                WHERE m.user_id = ?
                ORDER BY w.created_at DESC
                """,
                (user_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    def list_members(self, workspace_id: str, user_id: str) -> list[dict]:
        self.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT m.user_id, u.email, u.full_name, m.role
                FROM memberships m
                JOIN users u ON u.user_id = m.user_id
                WHERE m.workspace_id = ?
                ORDER BY m.role ASC, u.email ASC
                """,
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_member(self, workspace_id: str, email: str, role: str, actor_user_id: str) -> dict:
        if role not in {"owner", "editor", "viewer"}:
            raise ValueError("Invalid membership role")

        self.assert_workspace_role(workspace_id, actor_user_id, {"owner"})

        with get_connection() as conn:
            user = conn.execute("SELECT user_id, email, full_name FROM users WHERE email = ?", (email,)).fetchone()
            if user is None:
                raise ValueError("User with this email does not exist")

            existing = conn.execute(
                "SELECT role FROM memberships WHERE workspace_id = ? AND user_id = ?",
                (workspace_id, user["user_id"]),
            ).fetchone()

            if existing is None:
                conn.execute(
                    "INSERT INTO memberships(workspace_id, user_id, role) VALUES (?, ?, ?)",
                    (workspace_id, user["user_id"], role),
                )
            else:
                conn.execute(
                    "UPDATE memberships SET role = ? WHERE workspace_id = ? AND user_id = ?",
                    (role, workspace_id, user["user_id"]),
                )

            row = conn.execute(
                """
                SELECT m.user_id, u.email, u.full_name, m.role
                FROM memberships m
                JOIN users u ON u.user_id = m.user_id
                WHERE m.workspace_id = ? AND m.user_id = ?
                """,
                (workspace_id, user["user_id"]),
            ).fetchone()
        return dict(row)

    def assert_workspace_role(self, workspace_id: str, user_id: str, allowed_roles: set[str]) -> None:
        with get_connection() as conn:
            member = conn.execute(
                "SELECT role FROM memberships WHERE workspace_id = ? AND user_id = ?",
                (workspace_id, user_id),
            ).fetchone()
        if member is None or member["role"] not in allowed_roles:
            raise PermissionError("Insufficient workspace permissions")

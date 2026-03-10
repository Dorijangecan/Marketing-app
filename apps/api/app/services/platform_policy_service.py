from ..db.sqlite_store import get_connection
from .workspace_service import WorkspaceService


class PlatformPolicyService:
    POLICY_MATRIX = {
        "Instagram": {
            "max_chars": 2200,
            "blocked_terms": ["guaranteed", "100% cure", "instant results"],
            "requires_connected_account": True,
        },
        "LinkedIn": {
            "max_chars": 3000,
            "blocked_terms": ["guaranteed", "no risk"],
            "requires_connected_account": True,
        },
        "TikTok": {
            "max_chars": 2200,
            "blocked_terms": ["guaranteed", "instant results"],
            "requires_connected_account": False,
        },
        "YouTube": {
            "max_chars": 5000,
            "blocked_terms": ["100% cure", "guaranteed"],
            "requires_connected_account": False,
        },
    }

    def __init__(self) -> None:
        self.workspace = WorkspaceService()

    def get_matrix(self, workspace_id: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        return {"workspace_id": workspace_id, "platforms": self.POLICY_MATRIX}

    def validate_content_item(self, workspace_id: str, item_id: str, platform: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        policy = self.POLICY_MATRIX.get(platform)
        if policy is None:
            raise ValueError("Unsupported platform for policy check")

        with get_connection() as conn:
            row = conn.execute(
                "SELECT topic, hook, cta FROM content_plans WHERE workspace_id = ? AND item_id = ?",
                (workspace_id, item_id),
            ).fetchone()
        if row is None:
            raise ValueError("Content item not found")

        text = f"{row['topic']} {row['hook']} {row['cta']}"
        normalized = text.lower()
        violations: list[str] = []

        if len(text) > int(policy["max_chars"]):
            violations.append("max_chars_exceeded")

        hits = [term for term in policy["blocked_terms"] if term in normalized]
        if hits:
            violations.append("blocked_terms")

        return {
            "workspace_id": workspace_id,
            "item_id": item_id,
            "platform": platform,
            "policy": policy,
            "violations": violations,
            "blocked_terms_hits": hits,
            "pass": len(violations) == 0,
        }

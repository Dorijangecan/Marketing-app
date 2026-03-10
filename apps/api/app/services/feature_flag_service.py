from datetime import datetime, timezone

from ..db.sqlite_store import get_connection
from .audit_service import AuditService
from .workspace_service import WorkspaceService


class FeatureFlagService:
    PLAN_FLAGS = {
        "Starter": {
            "max_social_accounts": 1,
            "trend_analysis": False,
            "competitor_tracking": False,
            "advanced_optimization": False,
        },
        "Pro": {
            "max_social_accounts": 3,
            "trend_analysis": True,
            "competitor_tracking": False,
            "advanced_optimization": True,
        },
        "Agency": {
            "max_social_accounts": 10,
            "trend_analysis": True,
            "competitor_tracking": True,
            "advanced_optimization": True,
        },
    }

    def __init__(self) -> None:
        self.workspace = WorkspaceService()
        self.audit = AuditService()

    def get_workspace_features(self, workspace_id: str, user_id: str) -> dict:
        workspace = self.workspace.get_workspace(workspace_id, user_id)
        plan_name = workspace["plan_name"]
        features = dict(self.PLAN_FLAGS.get(plan_name, self.PLAN_FLAGS["Starter"]))
        self._apply_overrides(workspace_id, features)
        return {
            "workspace_id": workspace_id,
            "plan_name": plan_name,
            "features": features,
        }


    def set_workspace_feature_override(self, workspace_id: str, flag_key: str, value: bool | int, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner"})
        default_features = self.PLAN_FLAGS["Agency"]
        if flag_key not in default_features:
            raise ValueError("Unknown feature flag")

        expected_type = type(default_features[flag_key])
        if expected_type is bool and not isinstance(value, bool):
            raise ValueError("Feature flag expects boolean value")
        if expected_type is int and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValueError("Feature flag expects integer value")
        if expected_type is int and value <= 0:
            raise ValueError("Feature flag integer value must be greater than zero")

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO feature_flag_overrides(workspace_id, flag_key, flag_value, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, flag_key)
                DO UPDATE SET flag_value = excluded.flag_value, updated_by = excluded.updated_by, updated_at = excluded.updated_at
                """,
                (workspace_id, flag_key, str(value).lower() if isinstance(value, bool) else str(value), user_id, datetime.now(timezone.utc).isoformat()),
            )

        self.audit.log(
            action="feature_flag_override_set",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"flag_key": flag_key, "value": value},
        )
        return self.get_workspace_features(workspace_id, user_id)

    @staticmethod
    def _apply_overrides(workspace_id: str, features: dict) -> None:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT flag_key, flag_value FROM feature_flag_overrides WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchall()

        for row in rows:
            key = row["flag_key"]
            if key not in features:
                continue
            current = features[key]
            raw = row["flag_value"]
            parsed = FeatureFlagService._parse_override_value(key, raw, {key: current})
            if parsed is None:
                continue
            features[key] = parsed


    def list_workspace_feature_overrides(self, workspace_id: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT flag_key, flag_value, updated_by, updated_at FROM feature_flag_overrides WHERE workspace_id = ? ORDER BY updated_at DESC",
                (workspace_id,),
            ).fetchall()

        parsed_items = []
        default_features = self.PLAN_FLAGS["Agency"]
        for row in rows:
            key = row["flag_key"]
            raw = row["flag_value"]
            parsed_value = self._parse_override_value(key, raw, default_features)
            parsed_items.append(
                {
                    "flag_key": key,
                    "raw_value": raw,
                    "parsed_value": parsed_value,
                    "updated_by": row["updated_by"],
                    "updated_at": row["updated_at"],
                }
            )

        return {"workspace_id": workspace_id, "items": parsed_items}

    def clear_workspace_feature_override(self, workspace_id: str, flag_key: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner"})
        if flag_key not in self.PLAN_FLAGS["Agency"]:
            raise ValueError("Unknown feature flag")

        with get_connection() as conn:
            deleted = conn.execute(
                "DELETE FROM feature_flag_overrides WHERE workspace_id = ? AND flag_key = ?",
                (workspace_id, flag_key),
            ).rowcount

        if deleted == 0:
            raise ValueError("Feature override not found")

        self.audit.log(
            action="feature_flag_override_cleared",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"flag_key": flag_key},
        )
        return self.get_workspace_features(workspace_id, user_id)

    @staticmethod
    def _parse_override_value(flag_key: str, raw_value: str, defaults: dict) -> bool | int | None:
        if flag_key not in defaults:
            return None
        default = defaults[flag_key]
        if isinstance(default, bool):
            normalized = raw_value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            return None
        if isinstance(default, int):
            try:
                parsed = int(raw_value)
            except ValueError:
                return None
            return parsed if parsed > 0 else None
        return None

from datetime import datetime, timezone
from uuid import uuid4

from ..db.sqlite_store import get_connection
from .audit_service import AuditService
from .workspace_service import WorkspaceService


class ExperimentService:
    def __init__(self) -> None:
        self.workspace = WorkspaceService()
        self.audit = AuditService()

    def create_experiment(
        self,
        workspace_id: str,
        campaign_id: str | None,
        name: str,
        hypothesis: str,
        variants: list[dict],
        user_id: str,
    ) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        experiment = {
            "experiment_id": str(uuid4()),
            "workspace_id": workspace_id,
            "campaign_id": campaign_id,
            "name": name,
            "hypothesis": hypothesis,
            "status": "running",
            "winner_variant_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        created_variants = []
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO experiments(experiment_id, workspace_id, campaign_id, name, hypothesis, status, winner_variant_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment["experiment_id"],
                    workspace_id,
                    campaign_id,
                    name,
                    hypothesis,
                    "running",
                    None,
                    experiment["created_at"],
                ),
            )
            for v in variants:
                variant = {
                    "variant_id": str(uuid4()),
                    "label": v["label"],
                    "hook": v["hook"],
                    "cta": v["cta"],
                    "score": 0.0,
                }
                conn.execute(
                    "INSERT INTO experiment_variants(variant_id, experiment_id, label, hook, cta, score) VALUES (?, ?, ?, ?, ?, 0)",
                    (variant["variant_id"], experiment["experiment_id"], variant["label"], variant["hook"], variant["cta"]),
                )
                created_variants.append(variant)

        self.audit.log(
            "experiment_created",
            {"experiment_id": experiment["experiment_id"], "variants": len(created_variants)},
            user_id=user_id,
            workspace_id=workspace_id,
        )
        return {**experiment, "variants": created_variants}

    def score_variant(self, workspace_id: str, variant_id: str, impressions: int, clicks: int, conversions: int, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        ctr = (clicks / impressions) if impressions > 0 else 0
        cvr = (conversions / clicks) if clicks > 0 else 0
        score = round((ctr * 0.6 + cvr * 0.4) * 100, 4)

        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT ev.variant_id, ev.experiment_id
                FROM experiment_variants ev
                JOIN experiments e ON e.experiment_id = ev.experiment_id
                WHERE ev.variant_id = ? AND e.workspace_id = ?
                """,
                (variant_id, workspace_id),
            ).fetchone()
            if row is None:
                raise ValueError("Variant not found")

            conn.execute(
                "UPDATE experiment_variants SET impressions = ?, clicks = ?, conversions = ?, score = ? WHERE variant_id = ?",
                (impressions, clicks, conversions, score, variant_id),
            )

            top = conn.execute(
                "SELECT variant_id, score FROM experiment_variants WHERE experiment_id = ? ORDER BY score DESC LIMIT 1",
                (row["experiment_id"],),
            ).fetchone()
            conn.execute(
                "UPDATE experiments SET winner_variant_id = ? WHERE experiment_id = ?",
                (top["variant_id"], row["experiment_id"]),
            )

        self.audit.log(
            "experiment_variant_scored",
            {"variant_id": variant_id, "score": score},
            user_id=user_id,
            workspace_id=workspace_id,
        )
        return {"variant_id": variant_id, "score": score}

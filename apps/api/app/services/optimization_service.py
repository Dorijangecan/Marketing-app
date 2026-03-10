import json
from datetime import datetime, timezone
from uuid import uuid4

from ..db.sqlite_store import get_connection
from .workspace_service import WorkspaceService


class OptimizationService:
    def __init__(self) -> None:
        self.workspace = WorkspaceService()

    def generate_recommendations(self, workspace_id: str, user_id: str, persist: bool = True) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        snapshot = self._build_recommendation_snapshot(workspace_id)

        if persist:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO ai_decisions(decision_id, workspace_id, decision_type, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        str(uuid4()),
                        workspace_id,
                        "optimization_recommendation",
                        json.dumps(snapshot, ensure_ascii=False),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

        return snapshot

    def _build_recommendation_snapshot(self, workspace_id: str) -> dict:
        with get_connection() as conn:
            content_totals = conn.execute(
                "SELECT COUNT(*) AS total, SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) AS published FROM content_plans WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()
            lead_totals = conn.execute(
                "SELECT COUNT(*) AS total, SUM(CASE WHEN status = 'qualified' THEN 1 ELSE 0 END) AS qualified FROM lead_events WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()
            job_totals = conn.execute(
                "SELECT COUNT(*) AS total, SUM(CASE WHEN status = 'dead_letter' THEN 1 ELSE 0 END) AS dead_letter FROM publish_jobs WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()
            experiment_top = conn.execute(
                "SELECT variant_id, score FROM experiment_variants ev JOIN experiments e ON e.experiment_id = ev.experiment_id WHERE e.workspace_id = ? ORDER BY ev.score DESC LIMIT 1",
                (workspace_id,),
            ).fetchone()

        total_content = int(content_totals["total"] or 0)
        published_content = int(content_totals["published"] or 0)
        publish_rate = (published_content / total_content) if total_content > 0 else 0

        total_leads = int(lead_totals["total"] or 0)
        qualified_leads = int(lead_totals["qualified"] or 0)
        qualification_rate = (qualified_leads / total_leads) if total_leads > 0 else 0

        total_jobs = int(job_totals["total"] or 0)
        dlq_jobs = int(job_totals["dead_letter"] or 0)
        dlq_rate = (dlq_jobs / total_jobs) if total_jobs > 0 else 0

        recs: list[dict] = []

        if publish_rate < 0.5:
            recs.append(
                {
                    "priority": "high",
                    "type": "publish_ops",
                    "message": "Nizak publish rate. Povećati review throughput i smanjiti blokade prije schedulinga.",
                }
            )

        if dlq_rate > 0.1:
            recs.append(
                {
                    "priority": "high",
                    "type": "reliability",
                    "message": "DLQ rate je visok. Provjeriti platform mapping i replayati dead-letter jobove.",
                }
            )

        if total_leads == 0 or qualification_rate < 0.25:
            recs.append(
                {
                    "priority": "medium",
                    "type": "conversion",
                    "message": "Nizak lead qualification. Dodati jače CTA varijante i DM follow-up flow.",
                }
            )

        if experiment_top is not None:
            recs.append(
                {
                    "priority": "medium",
                    "type": "experiments",
                    "message": f"Top variant {experiment_top['variant_id']} ima score {experiment_top['score']}. Skalirati hook/copy pattern.",
                }
            )
        else:
            recs.append(
                {
                    "priority": "low",
                    "type": "experiments",
                    "message": "Nema dovoljno eksperimenata. Pokrenuti barem 2 A/B testa tjedno.",
                }
            )

        return {
            "workspace_id": workspace_id,
            "publish_rate": round(publish_rate, 4),
            "qualification_rate": round(qualification_rate, 4),
            "dlq_rate": round(dlq_rate, 4),
            "recommendations": recs,
        }

    def execute_autopilot_optimization(
        self,
        workspace_id: str,
        user_id: str,
        days: int = 30,
        min_reallocation_pct: float = 5.0,
    ) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})

        with get_connection() as conn:
            latest_strategy = conn.execute(
                """
                SELECT payload, created_at
                FROM ai_decisions
                WHERE workspace_id = ? AND decision_type = 'autopilot_strategy'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (workspace_id,),
            ).fetchone()
            if latest_strategy is None:
                raise ValueError("Autopilot strategy not found. Generate strategy first.")

            analytics_rows = conn.execute(
                """
                SELECT platform, SUM(reach) AS reach, SUM(clicks) AS clicks
                FROM analytics_events
                WHERE workspace_id = ?
                GROUP BY platform
                """,
                (workspace_id,),
            ).fetchall()

        strategy_payload = json.loads(latest_strategy["payload"])
        current_mix = strategy_payload.get("channel_mix", [])
        if not current_mix:
            raise ValueError("Autopilot strategy has no channel mix")

        performance = {}
        for row in analytics_rows:
            reach = int(row["reach"] or 0)
            clicks = int(row["clicks"] or 0)
            ctr = (clicks / reach) if reach > 0 else 0.0
            performance[row["platform"]] = {"reach": reach, "clicks": clicks, "ctr": round(ctr, 4)}

        # fallback baseline performance when analytics not present
        if not performance:
            for item in current_mix:
                performance[item["platform"]] = {"reach": 0, "clicks": 0, "ctr": 0.01}

        scores = {}
        for item in current_mix:
            platform = item["platform"]
            ctr = performance.get(platform, {"ctr": 0.0})["ctr"]
            # keep non-zero score so every channel can stay in exploration mode
            scores[platform] = max(ctr, 0.01)

        score_total = sum(scores.values()) or 1
        target_weights = {platform: score / score_total for platform, score in scores.items()}

        changes = []
        optimized_mix = []
        total_budget = round(sum(float(item["budget"]) for item in current_mix), 2)
        for item in current_mix:
            platform = item["platform"]
            old_alloc = float(item["allocation_pct"])
            new_alloc = round(target_weights[platform] * 100, 1)
            delta = round(new_alloc - old_alloc, 1)
            new_budget = round(total_budget * (new_alloc / 100), 2)

            optimized_mix.append(
                {
                    "platform": platform,
                    "allocation_pct": new_alloc,
                    "budget": new_budget,
                    "previous_allocation_pct": old_alloc,
                }
            )

            if abs(delta) >= min_reallocation_pct:
                action = "increase" if delta > 0 else "decrease"
                changes.append(
                    {
                        "platform": platform,
                        "action": action,
                        "delta_allocation_pct": delta,
                        "reason": f"CTR signal {performance.get(platform, {'ctr': 0.0})['ctr']} over last {days}d",
                    }
                )

        execution_plan = {
            "workspace_id": workspace_id,
            "window_days": days,
            "previous_mix": current_mix,
            "optimized_mix": optimized_mix,
            "platform_performance": performance,
            "changes": changes,
            "model_source": "local:autopilot-optimizer-v1",
        }

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO ai_decisions(decision_id, workspace_id, decision_type, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    str(uuid4()),
                    workspace_id,
                    "autopilot_budget_optimization",
                    json.dumps(execution_plan, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        return execution_plan



    def generate_executive_scorecard(self, workspace_id: str, user_id: str, days: int = 30) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})

        with get_connection() as conn:
            strategy_row = conn.execute(
                """
                SELECT payload, created_at
                FROM ai_decisions
                WHERE workspace_id = ? AND decision_type = 'autopilot_strategy'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (workspace_id,),
            ).fetchone()
            optimization_row = conn.execute(
                """
                SELECT payload, created_at
                FROM ai_decisions
                WHERE workspace_id = ? AND decision_type = 'autopilot_budget_optimization'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (workspace_id,),
            ).fetchone()
            analytics_row = conn.execute(
                """
                SELECT SUM(reach) AS reach, SUM(clicks) AS clicks, SUM(likes) AS likes, SUM(comments) AS comments
                FROM analytics_events
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()
            jobs_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) AS published,
                    SUM(CASE WHEN status = 'dead_letter' THEN 1 ELSE 0 END) AS dead_letter
                FROM publish_jobs
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()
            leads_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'qualified' THEN 1 ELSE 0 END) AS qualified
                FROM lead_events
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()

        strategy_score = 0.0
        strategy_status = "missing"
        if strategy_row is not None:
            payload = json.loads(strategy_row["payload"])
            strategy_score = float(payload.get("quality_gate", {}).get("score", 0.0))
            strategy_status = str(payload.get("quality_gate", {}).get("decision", "unknown"))

        optimization_changes = 0
        if optimization_row is not None:
            opt_payload = json.loads(optimization_row["payload"])
            optimization_changes = len(opt_payload.get("changes", []))

        total_reach = int(analytics_row["reach"] or 0)
        total_clicks = int(analytics_row["clicks"] or 0)
        total_likes = int(analytics_row["likes"] or 0)
        total_comments = int(analytics_row["comments"] or 0)
        ctr = (total_clicks / total_reach) if total_reach > 0 else 0.0
        engagement_rate = ((total_likes + total_comments) / total_reach) if total_reach > 0 else 0.0

        total_jobs = int(jobs_row["total"] or 0)
        published_jobs = int(jobs_row["published"] or 0)
        dlq_jobs = int(jobs_row["dead_letter"] or 0)
        publish_success_rate = (published_jobs / total_jobs) if total_jobs > 0 else 0.0
        dlq_rate = (dlq_jobs / total_jobs) if total_jobs > 0 else 0.0

        total_leads = int(leads_row["total"] or 0)
        qualified_leads = int(leads_row["qualified"] or 0)
        lead_quality_rate = (qualified_leads / total_leads) if total_leads > 0 else 0.0

        strategy_component = min(strategy_score, 1.0)
        execution_component = max(0.0, (publish_success_rate * 0.8) + ((1 - dlq_rate) * 0.2))
        demand_component = max(0.0, min(1.0, (ctr * 8) + (engagement_rate * 2)))
        revenue_component = lead_quality_rate

        weighted_score = (
            strategy_component * 0.30
            + execution_component * 0.30
            + demand_component * 0.20
            + revenue_component * 0.20
        )
        overall_score = int(round(weighted_score * 100))

        blockers = []
        if strategy_status != "approved":
            blockers.append("Strategy quality gate not approved")
        if publish_success_rate < 0.8:
            blockers.append("Publish reliability below enterprise threshold")
        if lead_quality_rate < 0.25:
            blockers.append("Lead quality conversion is low")
        if optimization_changes == 0:
            blockers.append("No budget reallocation actions generated")

        next_actions = [
            "Regenerate autopilot strategy with stricter ICP and offer detail",
            "Connect missing channels and replay failed publish jobs",
            "Run weekly autopilot optimization and review allocation deltas",
        ]

        return {
            "workspace_id": workspace_id,
            "window_days": days,
            "overall_score": overall_score,
            "grade": self._grade_from_score(overall_score),
            "pillars": {
                "strategy_quality": round(strategy_component * 100, 1),
                "execution_reliability": round(execution_component * 100, 1),
                "demand_generation": round(demand_component * 100, 1),
                "revenue_readiness": round(revenue_component * 100, 1),
            },
            "signals": {
                "strategy_status": strategy_status,
                "publish_success_rate": round(publish_success_rate, 4),
                "dlq_rate": round(dlq_rate, 4),
                "ctr": round(ctr, 4),
                "engagement_rate": round(engagement_rate, 4),
                "lead_quality_rate": round(lead_quality_rate, 4),
                "optimization_changes": optimization_changes,
            },
            "blockers": blockers,
            "next_actions": next_actions,
            "model_source": "local:executive-scorecard-v1",
        }

    @staticmethod
    def _grade_from_score(score: int) -> str:
        if score >= 85:
            return "A"
        if score >= 70:
            return "B"
        if score >= 55:
            return "C"
        return "D"



    def generate_operating_review(self, workspace_id: str, user_id: str, days: int = 30) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})

        scorecard = self.generate_executive_scorecard(workspace_id, user_id, days=days)
        recommendation_snapshot = self.generate_recommendations(workspace_id, user_id, persist=False)

        high_priority = [r for r in recommendation_snapshot.get("recommendations", []) if r.get("priority") == "high"]
        readiness = "go"
        if scorecard["grade"] in {"C", "D"} or len(scorecard.get("blockers", [])) >= 2 or high_priority:
            readiness = "no-go"

        payload = {
            "workspace_id": workspace_id,
            "window_days": days,
            "readiness": readiness,
            "executive_scorecard": scorecard,
            "optimization_snapshot": recommendation_snapshot,
            "high_priority_issues": high_priority,
            "operating_decision": {
                "approved_for_scale": readiness == "go",
                "requires_human_review": readiness != "go",
            },
        }

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO ai_decisions(decision_id, workspace_id, decision_type, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    str(uuid4()),
                    workspace_id,
                    "operating_review",
                    json.dumps(payload, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        return payload

    def list_operating_review_history(self, workspace_id: str, user_id: str) -> list[dict]:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT decision_id, decision_type, payload, created_at FROM ai_decisions WHERE workspace_id = ? AND decision_type = 'operating_review' ORDER BY created_at DESC LIMIT 50",
                (workspace_id,),
            ).fetchall()
        return [dict(r) for r in rows]



    def get_operating_review_trend(self, workspace_id: str, user_id: str, limit: int = 10) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})

        rows = self.list_operating_review_history(workspace_id, user_id)[: max(2, min(limit, 50))]
        if len(rows) < 2:
            raise ValueError("Not enough operating review history for trend analysis")

        parsed = []
        for row in rows:
            payload = json.loads(row["payload"])
            score = int(payload.get("executive_scorecard", {}).get("overall_score", 0))
            readiness = str(payload.get("readiness", "unknown"))
            parsed.append(
                {
                    "decision_id": row["decision_id"],
                    "created_at": row["created_at"],
                    "overall_score": score,
                    "readiness": readiness,
                }
            )

        newest = parsed[0]
        oldest = parsed[-1]
        delta = newest["overall_score"] - oldest["overall_score"]
        trend = "flat"
        if delta >= 3:
            trend = "improving"
        elif delta <= -3:
            trend = "declining"

        go_count = sum(1 for item in parsed if item["readiness"] == "go")
        go_ratio = round(go_count / len(parsed), 4)

        return {
            "workspace_id": workspace_id,
            "window_reviews": len(parsed),
            "trend": trend,
            "score_delta": delta,
            "go_ratio": go_ratio,
            "latest": newest,
            "baseline": oldest,
            "series": list(reversed(parsed)),
        }



    def list_decision_timeline(
        self,
        workspace_id: str,
        user_id: str,
        limit: int = 100,
        decision_type: str | None = None,
    ) -> list[dict]:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        safe_limit = max(1, min(limit, 200))

        with get_connection() as conn:
            if decision_type:
                rows = conn.execute(
                    "SELECT decision_id, decision_type, payload, created_at FROM ai_decisions WHERE workspace_id = ? AND decision_type = ? ORDER BY created_at DESC LIMIT ?",
                    (workspace_id, decision_type, safe_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT decision_id, decision_type, payload, created_at FROM ai_decisions WHERE workspace_id = ? ORDER BY created_at DESC LIMIT ?",
                    (workspace_id, safe_limit),
                ).fetchall()

        return [dict(r) for r in rows]

    def list_recommendation_history(self, workspace_id: str, user_id: str) -> list[dict]:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT decision_id, decision_type, payload, created_at FROM ai_decisions WHERE workspace_id = ? AND decision_type = 'optimization_recommendation' ORDER BY created_at DESC LIMIT 50",
                (workspace_id,),
            ).fetchall()
        return [dict(r) for r in rows]

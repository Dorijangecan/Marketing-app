import json
from datetime import datetime, timezone
from uuid import uuid4

from ..db.sqlite_store import get_connection
from .audit_service import AuditService
from .platform_policy_service import PlatformPolicyService
from .social_account_service import SocialAccountService
from .workspace_service import WorkspaceService


class ContentService:
    SUPPORTED_PUBLISH_PLATFORMS = {"Instagram", "TikTok", "LinkedIn", "YouTube"}

    def __init__(self) -> None:
        self.audit = AuditService()
        self.workspace = WorkspaceService()
        self.platform_policy = PlatformPolicyService()
        self.social_accounts = SocialAccountService()

    def generate_30_day_plan(
        self,
        workspace_id: str,
        brand_name: str,
        industry: str,
        tone_of_voice: str,
        user_id: str,
        idempotency_key: str,
    ) -> list[dict]:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})

        cached_payload = self._get_idempotent_payload(workspace_id, idempotency_key, "generate_plan")
        if cached_payload is not None:
            return cached_payload

        with get_connection() as conn:
            workspace = conn.execute(
                "SELECT quota_limit, quota_used FROM workspaces WHERE workspace_id = ?", (workspace_id,)
            ).fetchone()
            if workspace is None:
                raise ValueError("Workspace not found")
            if workspace["quota_used"] >= workspace["quota_limit"]:
                raise ValueError("Quota exceeded for workspace")

        pillars = ["Education", "Tips", "Offer", "Testimonial", "Behind the scenes"]
        platforms = ["Instagram", "TikTok", "LinkedIn"]
        items: list[dict] = []

        with get_connection() as conn:
            conn.execute("DELETE FROM content_plans WHERE workspace_id = ?", (workspace_id,))
            for day in range(1, 31):
                pillar = pillars[(day - 1) % len(pillars)]
                platform = platforms[(day - 1) % len(platforms)]
                item = {
                    "item_id": str(uuid4()),
                    "day": day,
                    "platform": platform,
                    "topic": f"{brand_name}: {pillar} for {industry}",
                    "hook": f"Day {day}: Ovo je ključna stvar koju većina brendova propušta.",
                    "cta": f"Javite se za ponudu prilagođenu tonu '{tone_of_voice}'.",
                    "status": "draft",
                }
                conn.execute(
                    """
                    INSERT INTO content_plans(item_id, workspace_id, day, platform, topic, hook, cta, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["item_id"],
                        workspace_id,
                        item["day"],
                        item["platform"],
                        item["topic"],
                        item["hook"],
                        item["cta"],
                        item["status"],
                    ),
                )
                items.append(item)

            conn.execute(
                "UPDATE workspaces SET quota_used = quota_used + 1 WHERE workspace_id = ?",
                (workspace_id,),
            )

        self._save_idempotent_payload(workspace_id, idempotency_key, "generate_plan", items)
        self.audit.log(
            action="content_plan_generated",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"items": len(items), "brand_name": brand_name},
        )
        return items

    def suggest_smart_publish_time(self, workspace_id: str, platform: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})

        normalized = platform.strip().lower()
        suggestions = {
            "instagram": {"day_of_week": "Tuesday", "time_utc": "17:30:00Z"},
            "linkedin": {"day_of_week": "Wednesday", "time_utc": "09:00:00Z"},
            "tiktok": {"day_of_week": "Friday", "time_utc": "18:00:00Z"},
            "youtube": {"day_of_week": "Saturday", "time_utc": "14:00:00Z"},
        }

        picked = suggestions.get(normalized, {"day_of_week": "Tuesday", "time_utc": "12:00:00Z"})
        return {
            "workspace_id": workspace_id,
            "platform": platform,
            "suggestion": picked,
            "source": "heuristic_v1",
        }

    def platform_policy_check(self, workspace_id: str, item_id: str, platform: str, user_id: str) -> dict:
        return self.platform_policy.validate_content_item(workspace_id, item_id, platform, user_id)

    def list_plan(self, workspace_id: str, user_id: str) -> list[dict]:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT item_id, day, platform, topic, hook, cta, status FROM content_plans WHERE workspace_id = ? ORDER BY day ASC",
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_status(self, workspace_id: str, item_id: str, new_status: str, user_id: str) -> None:
        allowed = {"draft", "review", "scheduled", "published", "rejected", "failed", "dead_letter"}
        if new_status not in allowed:
            raise ValueError("Invalid status")
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        with get_connection() as conn:
            updated = conn.execute(
                "UPDATE content_plans SET status = ? WHERE workspace_id = ? AND item_id = ?",
                (new_status, workspace_id, item_id),
            )
            if updated.rowcount == 0:
                raise ValueError("Content item not found")

        self.audit.log(
            action="content_status_updated",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"item_id": item_id, "new_status": new_status},
        )

    def schedule_publish(self, workspace_id: str, item_id: str, platform: str, scheduled_at: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        if platform in {"Instagram", "LinkedIn"} and not self.social_accounts.has_active_platform(workspace_id, platform):
            raise ValueError(f"No active {platform} account connected for workspace")
        if platform in self.platform_policy.POLICY_MATRIX:
            policy_check = self.platform_policy.validate_content_item(workspace_id, item_id, platform, user_id)
            if not policy_check["pass"]:
                raise ValueError(f"Policy check failed: {', '.join(policy_check['violations'])}")
        idempotency_key = f"{workspace_id}:{item_id}:{platform}:{scheduled_at}"
        with get_connection() as conn:
            item = conn.execute(
                "SELECT item_id FROM content_plans WHERE workspace_id = ? AND item_id = ?",
                (workspace_id, item_id),
            ).fetchone()
            if item is None:
                raise ValueError("Content item not found")

            existing_job = conn.execute(
                """
                SELECT job_id, workspace_id, item_id, platform, scheduled_at, status, retry_count, last_error, idempotency_key
                FROM publish_jobs
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
            if existing_job is not None:
                return dict(existing_job)

            job = {
                "job_id": str(uuid4()),
                "workspace_id": workspace_id,
                "item_id": item_id,
                "platform": platform,
                "scheduled_at": scheduled_at,
                "status": "queued",
                "retry_count": 0,
                "last_error": None,
                "idempotency_key": idempotency_key,
            }
            conn.execute(
                """
                INSERT INTO publish_jobs(
                    job_id, workspace_id, item_id, platform, scheduled_at, status,
                    retry_count, last_error, processing_started_at, next_attempt_at, provider_response, idempotency_key
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, NULL, NULL, ?, NULL, ?)
                """,
                (job["job_id"], workspace_id, item_id, platform, scheduled_at, "queued", scheduled_at, idempotency_key),
            )
            conn.execute(
                "UPDATE content_plans SET status = 'scheduled' WHERE workspace_id = ? AND item_id = ?",
                (workspace_id, item_id),
            )

        self.audit.log(
            action="publish_scheduled",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"job_id": job["job_id"], "item_id": item_id, "platform": platform},
        )
        return job

    def run_publish_cycle(self, workspace_id: str, now_iso: str, user_id: str, max_retries: int = 2) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner"})
        return self.run_publish_cycle_internal(
            workspace_id=workspace_id,
            now_iso=now_iso,
            max_retries=max_retries,
            actor_user_id=user_id,
        )

    def run_publish_cycle_internal(
        self,
        workspace_id: str,
        now_iso: str,
        max_retries: int = 2,
        actor_user_id: str | None = None,
    ) -> dict:
        processed_jobs = 0
        failed_jobs = 0
        dlq_moved = 0
        executed_events: list[dict] = []
        failed_events: list[dict] = []

        rows = self.claim_due_jobs(workspace_id=workspace_id, now_iso=now_iso, limit=100)
        for row in rows:
            process_result = self._process_claimed_job(dict(row), max_retries=max_retries)
            if process_result["published"]:
                processed_jobs += 1
                executed_events.append(process_result["event"])
            else:
                failed_jobs += 1
                if process_result["to_dlq"]:
                    dlq_moved += 1
                failed_events.append(process_result["event"])

        for event in executed_events:
            self.audit.log(
                action="publish_executed",
                workspace_id=workspace_id,
                user_id=actor_user_id,
                metadata=event,
            )

        for event in failed_events:
            self.audit.log(
                action="publish_failed",
                workspace_id=workspace_id,
                user_id=actor_user_id,
                metadata=event,
            )

        return {
            "workspace_id": workspace_id,
            "processed_jobs": processed_jobs,
            "failed_jobs": failed_jobs,
            "dlq_moved": dlq_moved,
        }

    def list_publish_jobs(self, workspace_id: str, user_id: str) -> list[dict]:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT job_id, item_id, platform, scheduled_at, status, retry_count, last_error,
                       processing_started_at, next_attempt_at, provider_response, idempotency_key
                FROM publish_jobs WHERE workspace_id = ? ORDER BY scheduled_at ASC
                """,
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def claim_due_jobs(self, workspace_id: str, now_iso: str, limit: int = 20) -> list[dict]:
        claimed: list[dict] = []
        with get_connection() as conn:
            candidates = conn.execute(
                """
                SELECT job_id, workspace_id, item_id, platform, scheduled_at, retry_count
                FROM publish_jobs
                WHERE workspace_id = ?
                  AND status = 'queued'
                  AND scheduled_at <= ?
                  AND COALESCE(next_attempt_at, scheduled_at) <= ?
                ORDER BY scheduled_at ASC
                LIMIT ?
                """,
                (workspace_id, now_iso, now_iso, limit),
            ).fetchall()

            for row in candidates:
                updated = conn.execute(
                    """
                    UPDATE publish_jobs
                    SET status = 'processing', processing_started_at = ?, last_error = NULL
                    WHERE job_id = ? AND status = 'queued'
                    """,
                    (now_iso, row["job_id"]),
                )
                if updated.rowcount == 1:
                    claimed.append(row)

        return claimed

    def reconcile_stuck_jobs(self, workspace_id: str, now_iso: str, stale_before_iso: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner"})
        return self.reconcile_stuck_jobs_internal(workspace_id=workspace_id, now_iso=now_iso, stale_before_iso=stale_before_iso)

    def reconcile_stuck_jobs_internal(self, workspace_id: str, now_iso: str, stale_before_iso: str) -> dict:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT job_id, item_id FROM publish_jobs
                WHERE workspace_id = ? AND status = 'processing' AND processing_started_at <= ?
                """,
                (workspace_id, stale_before_iso),
            ).fetchall()

            for row in rows:
                conn.execute(
                    """
                    UPDATE publish_jobs
                    SET status = 'queued', next_attempt_at = ?,
                        last_error = COALESCE(last_error, 'Recovered by watchdog from processing state'),
                        processing_started_at = NULL
                    WHERE job_id = ?
                    """,
                    (now_iso, row["job_id"]),
                )

        return {"workspace_id": workspace_id, "requeued": len(rows)}

    def retry_job_now(self, workspace_id: str, job_id: str, now_iso: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner"})
        with get_connection() as conn:
            row = conn.execute(
                "SELECT job_id FROM publish_jobs WHERE workspace_id = ? AND job_id = ?",
                (workspace_id, job_id),
            ).fetchone()
            if row is None:
                raise ValueError("Publish job not found")

            conn.execute(
                """
                UPDATE publish_jobs
                SET status = 'queued', next_attempt_at = ?, processing_started_at = NULL
                WHERE job_id = ?
                """,
                (now_iso, job_id),
            )
        return {"job_id": job_id, "status": "queued", "next_attempt_at": now_iso}

    def list_dead_letter_jobs(self, workspace_id: str, user_id: str) -> list[dict]:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT dlq_id, job_id, item_id, platform, scheduled_at, reason, moved_at FROM dead_letter_jobs WHERE workspace_id = ? ORDER BY moved_at DESC",
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def replay_dead_letter_job(self, workspace_id: str, job_id: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner"})
        with get_connection() as conn:
            job = conn.execute(
                "SELECT job_id, item_id FROM publish_jobs WHERE workspace_id = ? AND job_id = ? AND status = 'dead_letter'",
                (workspace_id, job_id),
            ).fetchone()
            if job is None:
                raise ValueError("Dead-letter job not found")

            conn.execute(
                """
                UPDATE publish_jobs
                SET status = 'queued', retry_count = 0, last_error = NULL,
                    processing_started_at = NULL, next_attempt_at = ?, provider_response = NULL
                WHERE job_id = ?
                """,
                (datetime.now(timezone.utc).isoformat(), job_id),
            )
            conn.execute(
                "UPDATE content_plans SET status = 'scheduled' WHERE workspace_id = ? AND item_id = ?",
                (workspace_id, job["item_id"]),
            )

        self.audit.log(
            action="dead_letter_replayed",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"job_id": job_id},
        )
        return {"job_id": job_id, "status": "queued"}

    def _process_claimed_job(self, row: dict, max_retries: int) -> dict:
        with get_connection() as conn:
            if row["platform"] in self.SUPPORTED_PUBLISH_PLATFORMS:
                provider_response = json.dumps({"provider": row["platform"], "result": "accepted"})
                conn.execute(
                    """
                    UPDATE publish_jobs
                    SET status = 'published', last_error = NULL, processing_started_at = NULL,
                        provider_response = ?, next_attempt_at = NULL
                    WHERE job_id = ?
                    """,
                    (provider_response, row["job_id"]),
                )
                conn.execute(
                    "UPDATE content_plans SET status = 'published' WHERE workspace_id = ? AND item_id = ?",
                    (row["workspace_id"], row["item_id"]),
                )
                return {
                    "published": True,
                    "to_dlq": False,
                    "event": {
                        "job_id": row["job_id"],
                        "item_id": row["item_id"],
                        "platform": row["platform"],
                        "scheduled_at": row["scheduled_at"],
                    },
                }

            retry_count = int(row["retry_count"]) + 1
            error_message = f"Unsupported platform: {row['platform']}"

            if retry_count > max_retries:
                conn.execute(
                    """
                    UPDATE publish_jobs
                    SET status = 'dead_letter', retry_count = ?, last_error = ?,
                        processing_started_at = NULL, next_attempt_at = NULL
                    WHERE job_id = ?
                    """,
                    (retry_count, error_message, row["job_id"]),
                )
                conn.execute(
                    "UPDATE content_plans SET status = 'dead_letter' WHERE workspace_id = ? AND item_id = ?",
                    (row["workspace_id"], row["item_id"]),
                )
                conn.execute(
                    "INSERT INTO dead_letter_jobs(dlq_id, job_id, workspace_id, item_id, platform, scheduled_at, reason, moved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid4()),
                        row["job_id"],
                        row["workspace_id"],
                        row["item_id"],
                        row["platform"],
                        row["scheduled_at"],
                        error_message,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                to_dlq = True
            else:
                conn.execute(
                    """
                    UPDATE publish_jobs
                    SET status = 'queued', retry_count = ?, last_error = ?,
                        processing_started_at = NULL, next_attempt_at = ?
                    WHERE job_id = ?
                    """,
                    (retry_count, error_message, row["scheduled_at"], row["job_id"]),
                )
                conn.execute(
                    "UPDATE content_plans SET status = 'failed' WHERE workspace_id = ? AND item_id = ?",
                    (row["workspace_id"], row["item_id"]),
                )
                to_dlq = False

        return {
            "published": False,
            "to_dlq": to_dlq,
            "event": {
                "job_id": row["job_id"],
                "item_id": row["item_id"],
                "platform": row["platform"],
                "retry_count": retry_count,
                "error": error_message,
            },
        }



    def run_compliance_check(self, workspace_id: str, item_id: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        with get_connection() as conn:
            row = conn.execute(
                "SELECT topic, hook, cta FROM content_plans WHERE workspace_id = ? AND item_id = ?",
                (workspace_id, item_id),
            ).fetchone()
            if row is None:
                raise ValueError("Content item not found")

        combined = f"{row['topic']} {row['hook']} {row['cta']}".lower()
        blocked_keywords = ["guaranteed", "100%", "cure", "instant results", "no risk"]
        hits = [k for k in blocked_keywords if k in combined]
        risk_score = round(min(1.0, len(hits) * 0.35), 2)

        review_required = risk_score >= 0.35
        reason = "blocked_keyword" if review_required else "clean"

        if review_required:
            with get_connection() as conn:
                review_id = str(uuid4())
                conn.execute(
                    """
                    INSERT INTO content_reviews(review_id, workspace_id, item_id, reason, risk_score, status, created_at)
                    VALUES (?, ?, ?, ?, ?, 'pending', ?)
                    """,
                    (
                        review_id,
                        workspace_id,
                        item_id,
                        reason,
                        risk_score,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                conn.execute(
                    "UPDATE content_plans SET status = 'review' WHERE workspace_id = ? AND item_id = ?",
                    (workspace_id, item_id),
                )

        self.audit.log(
            action="content_compliance_checked",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"item_id": item_id, "risk_score": risk_score, "review_required": review_required, "hits": hits},
        )
        return {"item_id": item_id, "risk_score": risk_score, "review_required": review_required, "hits": hits}

    def list_review_queue(self, workspace_id: str, user_id: str) -> list[dict]:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT review_id, item_id, reason, risk_score, status, created_at, resolved_at, resolved_by
                FROM content_reviews
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                """,
                (workspace_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def resolve_review(self, workspace_id: str, review_id: str, decision: str, user_id: str) -> dict:
        if decision not in {"approved", "rejected"}:
            raise ValueError("Invalid review decision")
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})

        with get_connection() as conn:
            review = conn.execute(
                "SELECT item_id, status FROM content_reviews WHERE workspace_id = ? AND review_id = ?",
                (workspace_id, review_id),
            ).fetchone()
            if review is None:
                raise ValueError("Review item not found")
            if review["status"] != "pending":
                raise ValueError("Review already resolved")

            conn.execute(
                "UPDATE content_reviews SET status = ?, resolved_at = ?, resolved_by = ? WHERE review_id = ?",
                (decision, datetime.now(timezone.utc).isoformat(), user_id, review_id),
            )
            content_status = "scheduled" if decision == "approved" else "rejected"
            conn.execute(
                "UPDATE content_plans SET status = ? WHERE workspace_id = ? AND item_id = ?",
                (content_status, workspace_id, review["item_id"]),
            )

        self.audit.log(
            action="content_review_resolved",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"review_id": review_id, "decision": decision},
        )
        return {"review_id": review_id, "decision": decision}



    def generate_hooks(self, workspace_id: str, topic: str, tone_of_voice: str, count: int, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        safe_count = min(max(1, count), 20)
        hooks = [
            f"{topic}: {tone_of_voice} hook #{idx} — Ovo će privući pažnju odmah."
            for idx in range(1, safe_count + 1)
        ]
        payload = {
            "workspace_id": workspace_id,
            "topic": topic,
            "tone_of_voice": tone_of_voice,
            "hooks": hooks,
            "model_source": "local:qwen-instruct",
            "quality_score": 0.81,
        }
        self._record_ai_decision(workspace_id, "hook_generation", payload)
        self.audit.log(
            action="hooks_generated",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"topic": topic, "count": safe_count},
        )
        return payload

    def generate_caption(
        self,
        workspace_id: str,
        topic: str,
        tone_of_voice: str,
        format_type: str,
        user_id: str,
    ) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        format_hint = {
            "short": "kratka forma",
            "long": "duža forma",
            "story": "story forma",
            "thread": "thread forma",
        }.get(format_type, "standard forma")
        caption = (
            f"{topic} — {tone_of_voice} ton. "
            f"Ovo je {format_hint} copy koji vodi korisnika ka jasnoj akciji."
        )
        payload = {
            "workspace_id": workspace_id,
            "topic": topic,
            "tone_of_voice": tone_of_voice,
            "format_type": format_type,
            "caption": caption,
            "model_source": "local:qwen-instruct",
            "quality_score": 0.79,
        }
        self._record_ai_decision(workspace_id, "caption_generation", payload)
        self.audit.log(
            action="caption_generated",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"topic": topic, "format_type": format_type},
        )
        return payload

    def generate_hashtags(
        self,
        workspace_id: str,
        niche: str,
        location: str | None,
        count: int,
        user_id: str,
    ) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        safe_count = min(max(3, count), 30)
        base_tags = [
            f"#{niche.replace(' ', '').lower()}",
            f"#{niche.replace(' ', '').lower()}tips",
            "#marketing",
            "#growth",
            "#contentstrategy",
            "#smallbusiness",
            "#digitalmarketing",
            "#brandbuilding",
        ]
        if location:
            base_tags.insert(2, f"#{location.replace(' ', '').lower()}")
        hashtags = base_tags[:safe_count]
        payload = {
            "workspace_id": workspace_id,
            "niche": niche,
            "location": location,
            "hashtags": hashtags,
            "model_source": "local:mistral-instruct",
            "quality_score": 0.76,
        }
        self._record_ai_decision(workspace_id, "hashtag_generation", payload)
        self.audit.log(
            action="hashtags_generated",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"niche": niche, "count": len(hashtags)},
        )
        return payload

    def batch_generate_content_assets(self, workspace_id: str, user_id: str, limit: int = 30) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT item_id, topic, platform
                FROM content_plans
                WHERE workspace_id = ?
                ORDER BY day ASC
                LIMIT ?
                """,
                (workspace_id, max(1, min(limit, 30))),
            ).fetchall()

        assets: list[dict] = []
        for row in rows:
            caption_payload = self.generate_caption(
                workspace_id=workspace_id,
                topic=row["topic"],
                tone_of_voice="Professional",
                format_type="short",
                user_id=user_id,
            )
            hashtag_payload = self.generate_hashtags(
                workspace_id=workspace_id,
                niche=row["platform"],
                location=None,
                count=5,
                user_id=user_id,
            )
            assets.append(
                {
                    "item_id": row["item_id"],
                    "caption": caption_payload["caption"],
                    "hashtags": hashtag_payload["hashtags"],
                    "model_source": "local:qwen+mistral",
                    "quality_score": round((caption_payload["quality_score"] + hashtag_payload["quality_score"]) / 2, 2),
                }
            )

        payload = {
            "workspace_id": workspace_id,
            "count": len(assets),
            "assets": assets,
            "model_source": "local:qwen+mistral",
            "quality_score": 0.78,
        }
        self._record_ai_decision(workspace_id, "batch_content_asset_generation", payload)
        self.audit.log(
            action="content_assets_batch_generated",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"count": len(assets)},
        )
        return payload




    def generate_post_blueprint(self, workspace_id: str, item_id: str, tone_of_voice: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        with get_connection() as conn:
            row = conn.execute(
                "SELECT item_id, topic, platform, hook, cta FROM content_plans WHERE workspace_id = ? AND item_id = ?",
                (workspace_id, item_id),
            ).fetchone()
            if row is None:
                raise ValueError("Content item not found")

        topic = row["topic"]
        platform = row["platform"]
        post_idea = f"Post ideja: {topic}. Ton: {tone_of_voice}. Naglasi problem + konkretan mini savjet + dokaz iz prakse."
        photo_brief = (
            f"Fotografija/video za {platform}: close-up realne situacije vezane uz '{topic}', "
            "prirodno svjetlo, vidljiv proizvod/usluga, bez stock izgleda, kadar 4:5."
        )
        captions = [
            f"{topic} — ({tone_of_voice}) evo što većina timova radi krivo i kako to ispraviti već danas.",
            f"Ako želiš bolje rezultate, kreni od ovoga: {row['hook']}",
            f"{topic}. Kratki plan: 1) dijagnostika 2) akcija 3) mjerenje. {row['cta']}",
        ]

        payload = {
            "workspace_id": workspace_id,
            "item_id": item_id,
            "platform": platform,
            "post_idea": post_idea,
            "photo_brief": photo_brief,
            "caption_options": captions,
            "model_source": "local:content-blueprint-v1",
            "quality_score": 0.82,
        }
        self._upsert_content_asset(workspace_id, item_id, post_idea, photo_brief, captions)
        self._record_ai_decision(workspace_id, "post_blueprint_generation", payload)
        self.audit.log(
            action="post_blueprint_generated",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"item_id": item_id, "platform": platform},
        )
        return payload

    def edit_caption(
        self,
        workspace_id: str,
        item_id: str,
        current_caption: str,
        edit_goal: str,
        tone_of_voice: str,
        user_id: str,
    ) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        if not current_caption.strip():
            raise ValueError("Current caption is required")

        with get_connection() as conn:
            plan_item = conn.execute(
                "SELECT item_id FROM content_plans WHERE workspace_id = ? AND item_id = ?",
                (workspace_id, item_id),
            ).fetchone()
        if plan_item is None:
            raise ValueError("Content item not found")

        revised = (
            f"[{tone_of_voice}] {current_caption.strip()} "
            f"(Uređeno s ciljem: {edit_goal.strip() or 'bolji engagement'}.)"
        )
        alternatives = [
            revised,
            f"{current_caption.strip()} | Fokus: jasna korist i konkretan sljedeći korak.",
            f"{current_caption.strip()} | Skrati i pojačaj prvi red za veći hook.",
        ]

        with get_connection() as conn:
            existing = conn.execute(
                "SELECT post_idea, photo_brief, caption_options FROM content_assets WHERE workspace_id = ? AND item_id = ?",
                (workspace_id, item_id),
            ).fetchone()
        post_idea = existing["post_idea"] if existing else ""
        photo_brief = existing["photo_brief"] if existing else ""

        self._upsert_content_asset(workspace_id, item_id, post_idea, photo_brief, alternatives)
        payload = {
            "workspace_id": workspace_id,
            "item_id": item_id,
            "edit_goal": edit_goal,
            "tone_of_voice": tone_of_voice,
            "edited_caption": revised,
            "alternatives": alternatives,
            "model_source": "local:caption-editor-v1",
            "quality_score": 0.8,
        }
        self._record_ai_decision(workspace_id, "caption_edit", payload)
        self.audit.log(
            action="caption_edited",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"item_id": item_id, "edit_goal": edit_goal},
        )
        return payload

    def select_caption(self, workspace_id: str, item_id: str, selected_caption: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        if not selected_caption.strip():
            raise ValueError("Selected caption is required")

        with get_connection() as conn:
            row = conn.execute(
                "SELECT asset_id FROM content_assets WHERE workspace_id = ? AND item_id = ?",
                (workspace_id, item_id),
            ).fetchone()
            if row is None:
                raise ValueError("Content asset not found. Generate blueprint first.")
            conn.execute(
                "UPDATE content_assets SET selected_caption = ?, updated_at = ? WHERE workspace_id = ? AND item_id = ?",
                (selected_caption.strip(), datetime.now(timezone.utc).isoformat(), workspace_id, item_id),
            )

        payload = {
            "workspace_id": workspace_id,
            "item_id": item_id,
            "selected_caption": selected_caption.strip(),
            "model_source": "human-in-the-loop",
            "quality_score": 0.85,
        }
        self._record_ai_decision(workspace_id, "caption_selected", payload)
        self.audit.log(
            action="caption_selected",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={"item_id": item_id},
        )
        return payload

    def get_content_asset(self, workspace_id: str, item_id: str, user_id: str) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor", "viewer"})
        with get_connection() as conn:
            row = conn.execute(
                "SELECT item_id, post_idea, photo_brief, caption_options, selected_caption, updated_at FROM content_assets WHERE workspace_id = ? AND item_id = ?",
                (workspace_id, item_id),
            ).fetchone()
        if row is None:
            raise ValueError("Content asset not found")

        return {
            "workspace_id": workspace_id,
            "item_id": row["item_id"],
            "post_idea": row["post_idea"],
            "photo_brief": row["photo_brief"],
            "caption_options": json.loads(row["caption_options"]),
            "selected_caption": row["selected_caption"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _upsert_content_asset(
        workspace_id: str,
        item_id: str,
        post_idea: str,
        photo_brief: str,
        caption_options: list[str],
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT asset_id, selected_caption FROM content_assets WHERE workspace_id = ? AND item_id = ?",
                (workspace_id, item_id),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE content_assets SET post_idea = ?, photo_brief = ?, caption_options = ?, updated_at = ? WHERE workspace_id = ? AND item_id = ?",
                    (post_idea, photo_brief, json.dumps(caption_options, ensure_ascii=False), now_iso, workspace_id, item_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO content_assets(asset_id, workspace_id, item_id, post_idea, photo_brief, caption_options, selected_caption, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        workspace_id,
                        item_id,
                        post_idea,
                        photo_brief,
                        json.dumps(caption_options, ensure_ascii=False),
                        None,
                        now_iso,
                    ),
                )

    def create_autopilot_strategy(
        self,
        workspace_id: str,
        business_goal: str,
        primary_offer: str,
        target_persona: str,
        market_regions: list[str],
        monthly_budget: float,
        tone_of_voice: str,
        growth_stage: str,
        user_id: str,
        min_quality_score: float = 0.75,
    ) -> dict:
        self.workspace.assert_workspace_role(workspace_id, user_id, {"owner", "editor"})
        if monthly_budget <= 0:
            raise ValueError("Monthly budget must be greater than zero")

        normalized_regions = [region.strip() for region in market_regions if region.strip()] or ["EU"]
        connected_accounts = self.social_accounts.list_accounts(workspace_id, user_id)
        connected_platforms = sorted({a["platform"] for a in connected_accounts if int(a["is_active"]) == 1})
        channel_mix = self._build_channel_mix(monthly_budget, growth_stage, connected_platforms)
        weekly_cadence = self._build_weekly_cadence(growth_stage)
        funnel = self._build_funnel(primary_offer, target_persona)

        quality_score, score_breakdown = self._calculate_strategy_quality_score(
            business_goal=business_goal,
            primary_offer=primary_offer,
            target_persona=target_persona,
            market_regions=normalized_regions,
            monthly_budget=monthly_budget,
            channel_mix=channel_mix,
            connected_platforms=connected_platforms,
        )

        decision = "approved" if quality_score >= min_quality_score else "revise"
        revision_notes = []
        if decision == "revise":
            revision_notes = [
                "Pojačati jasnoću ponude i diferencijaciju value propositiona.",
                "Dodati jasniji ICP signal (industrija, veličina tima, buying trigger).",
                "Povećati budget ili fokusirati channel mix na 2 kanala za jači učinak.",
            ]
            if not connected_platforms:
                revision_notes.append("Povezati barem jedan aktivan social account prije autopilot executiona.")

        strategy = {
            "workspace_id": workspace_id,
            "business_goal": business_goal,
            "primary_offer": primary_offer,
            "target_persona": target_persona,
            "market_regions": normalized_regions,
            "tone_of_voice": tone_of_voice,
            "growth_stage": growth_stage,
            "positioning": {
                "value_proposition": f"{primary_offer} za {target_persona} uz mjerljiv ROI i bržu isporuku.",
                "differentiators": [
                    "AI-assisted speed-to-market",
                    "Cross-channel execution consistency",
                    "Built-in compliance + audit trail",
                ],
                "message_pillars": [
                    "business outcomes",
                    "proof and trust",
                    "execution simplicity",
                ],
            },
            "kpi_targets": {
                "mql_per_month": int(max(30, monthly_budget // 120)),
                "pipeline_value_target": round(monthly_budget * 8.0, 2),
                "target_cac": round(monthly_budget / max(1, int(monthly_budget // 120)), 2),
            },
            "channel_mix": channel_mix,
            "connected_platforms": connected_platforms,
            "weekly_cadence": weekly_cadence,
            "funnel": funnel,
            "quality_gate": {
                "score": quality_score,
                "decision": decision,
                "min_quality_score": min_quality_score,
                "score_breakdown": score_breakdown,
                "revision_notes": revision_notes,
            },
            "model_source": "local:strategy-orchestrator-v1",
        }

        self._record_ai_decision(workspace_id, "autopilot_strategy", strategy)
        self.audit.log(
            action="autopilot_strategy_generated",
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={
                "decision": decision,
                "quality_score": quality_score,
                "regions": normalized_regions,
            },
        )
        return strategy

    @staticmethod
    def _build_channel_mix(monthly_budget: float, growth_stage: str, connected_platforms: list[str]) -> list[dict]:
        stage = growth_stage.strip().lower()
        if stage == "early":
            weights = [("LinkedIn", 0.35), ("Instagram", 0.25), ("TikTok", 0.2), ("YouTube", 0.2)]
        elif stage == "scale":
            weights = [("LinkedIn", 0.3), ("YouTube", 0.3), ("Instagram", 0.2), ("TikTok", 0.2)]
        else:
            weights = [("LinkedIn", 0.3), ("Instagram", 0.25), ("YouTube", 0.25), ("TikTok", 0.2)]

        if connected_platforms:
            allowed = set(connected_platforms)
            weights = [(platform, weight) for platform, weight in weights if platform in allowed]
            if not weights:
                weights = [(platform, 1 / len(connected_platforms)) for platform in connected_platforms]

        total = sum(weight for _, weight in weights) or 1
        normalized = [(platform, weight / total) for platform, weight in weights]

        return [
            {"platform": platform, "allocation_pct": round(weight * 100, 1), "budget": round(monthly_budget * weight, 2)}
            for platform, weight in normalized
        ]

    @staticmethod
    def _build_weekly_cadence(growth_stage: str) -> dict:
        stage = growth_stage.strip().lower()
        if stage == "early":
            return {"thought_leadership_posts": 3, "short_video": 2, "case_studies": 1, "offers": 1}
        if stage == "scale":
            return {"thought_leadership_posts": 4, "short_video": 4, "case_studies": 2, "offers": 2}
        return {"thought_leadership_posts": 3, "short_video": 3, "case_studies": 1, "offers": 1}

    @staticmethod
    def _build_funnel(primary_offer: str, target_persona: str) -> list[dict]:
        return [
            {"stage": "awareness", "asset": f"Problem-education content za {target_persona}", "cta": "Download playbook"},
            {"stage": "consideration", "asset": f"Case study: rezultat kroz {primary_offer}", "cta": "Book strategy call"},
            {"stage": "decision", "asset": "Offer breakdown + implementation plan", "cta": "Start pilot"},
        ]

    @staticmethod
    def _calculate_strategy_quality_score(
        business_goal: str,
        primary_offer: str,
        target_persona: str,
        market_regions: list[str],
        monthly_budget: float,
        channel_mix: list[dict],
        connected_platforms: list[str],
    ) -> tuple[float, dict]:
        breakdown = {
            "goal_clarity": 0.1 if len(business_goal.strip()) >= 20 else 0.0,
            "offer_specificity": 0.1 if len(primary_offer.strip()) >= 12 else 0.0,
            "persona_specificity": 0.1 if len(target_persona.strip()) >= 10 else 0.0,
            "regional_scope": 0.05 if len(market_regions) >= 1 else 0.0,
            "budget_sufficiency": 0.1 if monthly_budget >= 1500 else 0.0,
            "channel_diversity": 0.1 if len(channel_mix) >= 2 else 0.0,
            "execution_readiness": 0.1 if len(connected_platforms) >= 1 else 0.0,
        }
        score = 0.35 + sum(breakdown.values())
        return round(min(score, 0.99), 2), {k: round(v, 2) for k, v in breakdown.items()}

    @staticmethod
    def _record_ai_decision(workspace_id: str, decision_type: str, payload: dict) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO ai_decisions(decision_id, workspace_id, decision_type, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid4()), workspace_id, decision_type, json.dumps(payload, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
            )


    @staticmethod
    def _get_idempotent_payload(workspace_id: str, idempotency_key: str, action: str) -> list[dict] | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT response_payload FROM idempotency_keys WHERE workspace_id = ? AND idempotency_key = ? AND action = ?",
                (workspace_id, idempotency_key, action),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["response_payload"])

    @staticmethod
    def _save_idempotent_payload(workspace_id: str, idempotency_key: str, action: str, payload: list[dict]) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO idempotency_keys(workspace_id, idempotency_key, action, response_payload) VALUES (?, ?, ?, ?)",
                (workspace_id, idempotency_key, action, json.dumps(payload, ensure_ascii=False)),
            )

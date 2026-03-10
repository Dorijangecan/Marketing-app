from .metrics_service import MetricsService


class AlertingService:
    def __init__(self) -> None:
        self.metrics = MetricsService()

    def get_rules(self) -> dict:
        return {
            "p1": [
                "publish_success_rate < 0.95 for 30m",
                "queue_depth > 100 for 15m",
                "dead_letter_total increasing for 20m",
            ],
            "p2": [
                "latency_p95_ms > 2000 for 20m",
                "error_rate > 0.1 for 20m",
            ],
            "doc": "docs/alerting-rules.md",
        }

    def evaluate_current_status(self) -> dict:
        runtime = self.metrics.get_snapshot()
        active: list[dict] = []

        if runtime["publish_success_rate"] < 0.95 and runtime["job_total"] > 0:
            active.append({"severity": "p1", "code": "publish_success_rate_drop", "value": runtime["publish_success_rate"]})
        if runtime["queue_depth"] > 100:
            active.append({"severity": "p1", "code": "queue_backlog_spike", "value": runtime["queue_depth"]})
        if runtime["latency_p95_ms"] > 2000:
            active.append({"severity": "p2", "code": "latency_regression", "value": runtime["latency_p95_ms"]})
        if runtime["error_rate"] > 0.1 and runtime["job_total"] > 0:
            active.append({"severity": "p2", "code": "error_rate_increase", "value": runtime["error_rate"]})

        return {
            "runtime": runtime,
            "active_alerts": active,
            "ok": len(active) == 0,
        }

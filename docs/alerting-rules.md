# Alerting Rules (MVP)

## P1 alerts

1. **Publish Success Rate Drop**
   - Condition: `publish_success_rate < 0.95` for 30 min.
   - Action: page Engineering on-call + notify Product.

2. **Queue Backlog Spike**
   - Condition: `queue_depth > 100` for 15 min.
   - Action: trigger worker health check + reconcile stuck jobs.

3. **Dead Letter Growth**
   - Condition: `dead_letter_total` increases continuously for 20 min.
   - Action: inspect platform policy violations and replay strategy.

## P2 alerts

1. **Latency Regression**
   - Condition: `latency_p95_ms > 2000` for 20 min.
   - Action: investigate DB contention and hot endpoints.

2. **Error Rate Increase**
   - Condition: `error_rate > 0.1` for 20 min.
   - Action: inspect recent deploys and top failing routes.

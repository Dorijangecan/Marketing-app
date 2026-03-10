import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .core.config import get_settings
from .services.alerting_service import AlertingService
from .core.logging import configure_logging
from .routers.analytics import router as analytics_router
from .routers.audit import router as audit_router
from .routers.auth import router as auth_router
from .routers.brand import router as brand_router
from .routers.campaigns import router as campaign_router
from .routers.compliance import router as compliance_router
from .routers.content import router as content_router
from .routers.experiments import router as experiment_router
from .routers.leads import router as lead_router
from .routers.optimization import router as optimization_router
from .routers.social_accounts import router as social_accounts_router
from .routers.workspaces import router as workspace_router
from .schemas import HealthResponse, ReadinessResponse
from .services.metrics_service import MetricsService
from .services.rate_limit_service import RateLimitService
from .services.readiness_service import ReadinessService
from .services.trace_service import TraceService
from .ui.router import router as ui_router

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)
rate_limit_service = RateLimitService()
metrics_service = MetricsService()
trace_service = TraceService()
alerting_service = AlertingService()
readiness_service = ReadinessService()

app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/ui/static", StaticFiles(directory="app/ui/static"), name="ui-static")
app.include_router(ui_router)
app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(brand_router)
app.include_router(content_router)
app.include_router(analytics_router)
app.include_router(audit_router)
app.include_router(campaign_router)
app.include_router(compliance_router)
app.include_router(experiment_router)
app.include_router(lead_router)
app.include_router(optimization_router)
app.include_router(social_accounts_router)


@app.get("/", include_in_schema=False)
def root_message() -> dict[str, str]:
    return {"message": "Open /ui for dashboard"}


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid4()))
    trace_id = request.headers.get("x-trace-id", str(uuid4()))
    started = time.perf_counter()

    if request.url.path not in {"/health", "/livez", "/readyz"}:
        client_ip = request.client.host if request.client else "unknown"
        allowed = rate_limit_service.check_and_increment(client_ip)
        if not allowed:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

    response = await call_next(request)

    duration_ms = (time.perf_counter() - started) * 1000
    response.headers["x-request-id"] = request_id
    response.headers["x-trace-id"] = trace_id
    trace_service.record_api_span(trace_id, request_id, request.method, request.url.path, response.status_code, duration_ms)

    logger.info(
        "request_completed method=%s path=%s status_code=%s duration_ms=%.2f request_id=%s trace_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
        trace_id,
    )
    return response


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="api", environment=settings.environment)


@app.get("/livez", response_model=HealthResponse)
def livez() -> HealthResponse:
    return HealthResponse(status="ok", service="api", environment=settings.environment)


@app.get("/readyz", response_model=ReadinessResponse)
def readyz() -> ReadinessResponse:
    readiness = readiness_service.get_snapshot()
    return ReadinessResponse(status=readiness["status"], service="api", checks=readiness["checks"])


@app.get("/metrics")
def metrics() -> dict:
    return {
        "service": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        },
        "readiness": readiness_service.get_snapshot(),
        "runtime": metrics_service.get_snapshot(),
    }


@app.get("/v1/meta/api-contract")
def api_contract() -> dict:
    return {
        "api_version": "v1",
        "contract_version": "2026-01-01",
        "status": "locked-mvp",
    }


@app.get("/v1/meta/alerting-rules")
def alerting_rules() -> dict:
    return alerting_service.get_rules()


@app.get("/v1/meta/alerting-status")
def alerting_status() -> dict:
    return alerting_service.evaluate_current_status()

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..core.config import get_settings
from ..services.readiness_service import ReadinessService

router = APIRouter(prefix="/ui", tags=["ui"])
templates = Jinja2Templates(directory="app/ui/templates")
readiness_service = ReadinessService()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    settings = get_settings()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "health_status": "ok",
            "readiness_status": readiness_service.get_status(),
            "environment": settings.environment,
            "generation_result": None,
        },
    )


@router.post("/generate-plan", response_class=HTMLResponse)
def generate_plan(
    request: Request,
    brand_name: str = Form(...),
    industry: str = Form(...),
    tone_of_voice: str = Form(...),
) -> HTMLResponse:
    settings = get_settings()
    result = (
        f"Generiran je početni 30-day plan za brand '{brand_name}' ({industry}) "
        f"s tonom '{tone_of_voice}'. Sljedeći korak: review i scheduling."
    )
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "health_status": "ok",
            "readiness_status": readiness_service.get_status(),
            "environment": settings.environment,
            "generation_result": result,
        },
    )

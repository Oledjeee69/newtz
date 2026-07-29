from fastapi import APIRouter, Request

from app.config import get_settings
from app.core.security import get_client_ip
from app.repositories.log_repository import LogRepository
from app.schemas.contact import ContactRequest, ContactResponse
from app.services.contact_service import ContactService

router = APIRouter(prefix="/api", tags=["contact"])


@router.post("/contact", response_model=ContactResponse, status_code=201)
async def submit_contact(payload: ContactRequest, request: Request) -> ContactResponse:
    settings = get_settings()
    service = ContactService(settings)
    ip = get_client_ip(request, settings.trust_proxy)

    response = await service.submit(payload, ip)

    remaining = service.rate_limit_remaining(ip)
    request.state.rate_limit_remaining = remaining
    request.state.rate_limit_limit = settings.rate_limit_max_requests

    return response

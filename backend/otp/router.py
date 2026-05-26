from typing import Optional

from fastapi import APIRouter

from .schemas import EmailRequest, VerifyOtpRequest
from .service import OtpService

router = APIRouter(tags=["auth"])
_otp_service: Optional[OtpService] = None


def init_otp_service(service: OtpService) -> None:
    global _otp_service
    _otp_service = service


def _service() -> OtpService:
    if _otp_service is None:
        raise RuntimeError("OTP service not initialized.")
    return _otp_service


@router.post("/auth/register/request-otp")
def request_register_otp(request: EmailRequest):
    return _service().request_register_otp(request.email.lower())


@router.post("/auth/register/verify-otp")
def verify_register_otp(request: VerifyOtpRequest):
    return _service().verify_register_otp(request.email.lower(), request.otp)


@router.post("/auth/login/request-otp")
def request_login_otp(request: EmailRequest):
    return _service().request_login_otp(request.email.lower())


@router.post("/auth/login/verify-otp")
def verify_login_otp(request: VerifyOtpRequest):
    return _service().verify_login_otp(request.email.lower(), request.otp)

from pydantic import BaseModel, EmailStr


class EmailRequest(BaseModel):
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str

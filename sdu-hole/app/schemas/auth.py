from pydantic import BaseModel


class SendCodeRequest(BaseModel):
    student_id: str


class VerifyRequest(BaseModel):
    student_id: str
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

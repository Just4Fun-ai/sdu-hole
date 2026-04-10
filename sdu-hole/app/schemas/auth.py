from pydantic import BaseModel


class SendCodeRequest(BaseModel):
    student_id: str


class VerifyRequest(BaseModel):
    student_id: str
    code: str
    nickname: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_bind_nickname: bool = False
    nickname: str | None = None
    is_admin: bool = False


class RandomNicknameResponse(BaseModel):
    nickname: str


class BindNicknameRequest(BaseModel):
    nickname: str


class UserProfileResponse(BaseModel):
    nickname: str | None = None
    must_bind_nickname: bool
    is_admin: bool = False


class AppealCreateRequest(BaseModel):
    moderation_log_id: int
    content: str


class AppealResolveRequest(BaseModel):
    status: str  # approved / rejected
    admin_reply: str = ""

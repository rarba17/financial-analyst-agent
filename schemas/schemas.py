from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, EmailStr, model_validator, ConfigDict
import dns.resolver
from typing import Any


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    is_admin: bool
    default_thread_id: int


class TokenData(BaseModel):
    email: Optional[EmailStr] = None


class UserLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    otp_code: str


# User schemas
class UserBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class UserCreate(UserBase):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    full_name: str

    # @model_validator(mode="after")
    # def check_email_domain(self) -> "UserCreate":
    #     try:
    #         domain = self.email.split("@")[1]
    #         dns.resolver.resolve(domain, "MX")
    #     except Exception:
    #         raise ValueError(f"Email domain '{domain}' does not have valid MX records.")
    #     return self


class User(UserBase):
    id: int
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RequestOTP(BaseModel):
    email: EmailStr


class VerifyOTP(BaseModel):
    email: EmailStr
    otp: str


# Thread schemas
class ThreadBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str


class ThreadCreate(ThreadBase):
    pass


class Thread(ThreadBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Message schemas
class MessageBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str


class MessageCreate(MessageBase):
    model_config = ConfigDict(extra="forbid")
    thread_id: int


class Message(MessageBase):
    id: int
    is_bot: bool
    user_id: int
    thread_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ShareBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thread_id: int


class ShareCreate(ShareBase):
    pass


class Share(ShareBase):

    id: int
    uid: str
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class QueryRequest(BaseModel):
    query: str


class QualityValidatorRequest(BaseModel):
    query: str
    response: str


class StoreAnalysisRequest(BaseModel):
    name: str
    labels: List[Dict[str, str]]
    description: Optional[str] = ""
    additional_data: Optional[Dict[str, Any]] = None


class SKUAnalysisRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    labels: List[Dict[str, str]]
    additional_data: Optional[Dict[str, Any]] = None

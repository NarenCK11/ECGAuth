import re
from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.ecg import AnalysisOut
from app.schemas.user import UserOut

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    date_of_birth: date
    username: str = Field(min_length=3, max_length=32)

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Name is required")
        return v

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = v.strip().lower()
        if not USERNAME_RE.match(v):
            raise ValueError("Username may contain letters, digits, '.', '_' and '-' (3-32 characters)")
        if re.fullmatch(r"pt-\d+", v):
            raise ValueError("That username is reserved")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: date) -> date:
        if v > date.today() or v.year < 1900:
            raise ValueError("Enter a valid date of birth")
        return v


class RegisterResponse(BaseModel):
    user: UserOut
    next_step: str = "enroll"


class EnrollResponse(BaseModel):
    user: UserOut
    enrollment_reference: str
    message: str


class LoginResponse(BaseModel):
    authenticated: bool
    message: str
    user: UserOut | None
    attempt_id: str | None
    analysis: AnalysisOut | None


class MeResponse(BaseModel):
    authenticated: bool
    user: UserOut

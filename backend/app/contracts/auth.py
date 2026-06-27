"""Auth schemas — ``LoginRequest``, ``User``, ``SessionResponse``.

``email`` is ``format: email`` in the contract; modelled as ``str`` to avoid an
extra ``email-validator`` dependency for Milestone 1.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class User(BaseModel):
    user_id: str
    name: str
    email: str
    effective_role: Literal["lead_admin", "member"]
    display_label: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class SessionResponse(BaseModel):
    user: User
    csrf_token: str

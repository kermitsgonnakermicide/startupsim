"""Pydantic request models — shared by route modules."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SignupReq(BaseModel):
    username: str
    password: str
    email: str
    reason: str = ""


class LoginReq(BaseModel):
    username: str
    password: str


class ReapplyReq(BaseModel):
    username: str
    password: str
    reason: str


class AdminActionReq(BaseModel):
    userId: str


class AdminLeaderboardVisibilityReq(BaseModel):
    userId: str
    hidden: bool


class ChangePasswordReq(BaseModel):
    currentPassword: str
    newPassword: str


class TradeReq(BaseModel):
    symbol: str
    type: str  # BUY | SELL
    qty: int
    price: float


class WatchlistReq(BaseModel):
    symbol: str


class AlertReq(BaseModel):
    symbol: str
    targetPrice: float
    direction: str  # 'above' | 'below'
    note: Optional[str] = ""

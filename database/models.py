"""
Pydantic models for OpsPilot AI database entities.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "Admin"
    EMPLOYEE = "Employee"


class UserStatus(str, Enum):
    ACTIVE = "Active"
    DISABLED = "Disabled"


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    name: str
    email: str
    role: UserRole = UserRole.EMPLOYEE


class User(BaseModel):
    """Full user model with all fields."""
    id: int
    name: str
    email: str
    role: UserRole
    status: UserStatus = UserStatus.ACTIVE
    created_at: str = ""

    class Config:
        from_attributes = True


class ActionLog(BaseModel):
    """Log entry for actions performed on users."""
    id: int
    action: str
    target_email: str
    details: str
    timestamp: str

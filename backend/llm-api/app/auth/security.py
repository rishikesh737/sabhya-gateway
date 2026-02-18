"""
Sabhya AI - JWT Authentication & RBAC Security Module
"""

import logging
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Set

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel

# JWT library
try:
    from jose import JWTError, jwt

    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    logging.warning("python-jose not installed, JWT auth disabled")

logger = logging.getLogger(__name__)

# --- Configuration ---
SECRET_KEY = os.getenv(
    "SECRET_KEY", "***REMOVED***-key-change-in-production-minimum-32-chars"
)
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

LEGACY_API_KEYS = os.getenv("API_KEYS", "").split(",")
LEGACY_AUTH_ENABLED = os.getenv("LEGACY_AUTH_ENABLED", "true").lower() == "true"

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


# --- Role Definitions ---
class Roles(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    AUDITOR = "auditor"


class Permissions(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    AUDIT = "audit"
    MANAGE_USERS = "manage_users"


ROLE_PERMISSIONS: dict[str, Set[str]] = {
    Roles.ADMIN: {Permissions.READ, Permissions.WRITE, Permissions.DELETE, Permissions.MANAGE_USERS},
    Roles.USER: {Permissions.READ, Permissions.WRITE},
    Roles.VIEWER: {Permissions.READ},
    Roles.AUDITOR: {Permissions.READ, Permissions.AUDIT},
}


# --- Models ---
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    sub: str
    roles: List[str] = []
    exp: int
    iat: int
    token_type: str = "access"


class UserInfo(BaseModel):
    user_id: str
    roles: List[str]
    permissions: Set[str]
    is_legacy_key: bool = False


# --- Core Security Functions ---


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "token_type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: str) -> str:
    """Create JWT refresh token."""
    if not JWT_AVAILABLE:
        raise HTTPException(status_code=500, detail="JWT auth unavailable")

    now = datetime.utcnow()
    expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {"sub": user_id, "exp": expire, "iat": now, "token_type": "refresh"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        # roles not used here, only sub is needed

        if user_id is None:
            raise credentials_exception

        return TokenData(**payload)
    except JWTError:
        raise credentials_exception


def verify_refresh_token(token: str) -> TokenData:
    token_data = verify_token(token)
    if token_data.token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type - refresh token required",
        )
    return token_data


# --- Dependencies ---
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserInfo:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    token = credentials.credentials

    # 1. Try Legacy Key
    if LEGACY_AUTH_ENABLED and token in LEGACY_API_KEYS:
        return UserInfo(
            user_id="legacy_user",
            roles=[Roles.USER],
            permissions=ROLE_PERMISSIONS[Roles.USER],
            is_legacy_key=True,
        )

    # 2. Try JWT
    token_data = verify_token(token)

    perms = set()
    for role in token_data.roles:
        if role in ROLE_PERMISSIONS:
            perms.update(ROLE_PERMISSIONS[role])

    return UserInfo(
        user_id=token_data.sub,
        roles=token_data.roles,
        permissions=perms,
        is_legacy_key=False,
    )


def require_role(*required_roles: str):
    async def role_checker(user: UserInfo = Depends(get_current_user)):
        user_roles = set(user.roles)
        if not user_roles.intersection(set(required_roles)):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return role_checker


def require_permission(*required_permissions: str):
    async def permission_checker(user: UserInfo = Depends(get_current_user)):
        if not user.permissions.issuperset(set(required_permissions)):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return permission_checker


def hash_api_key(key: str) -> str:
    """Hash an API key using the configured password context."""
    return pwd_context.hash(key)


def verify_legacy_api_key(key: str) -> Optional[UserInfo]:
    """Verify a legacy API key against the configured list."""
    if not LEGACY_AUTH_ENABLED:
        return None
    
    if key in LEGACY_API_KEYS:
        # Create a legacy user context
        return UserInfo(
            user_id=f"legacy_{hash_api_key(key)[:8]}",
            roles=[Roles.USER],
            permissions=ROLE_PERMISSIONS[Roles.USER],
            is_legacy_key=True
        )
    return None


# ============================================================================
# MISSING API KEY UTILITIES
# ============================================================================


def verify_api_key_hash(plain_key: str, hashed_key: str) -> bool:
    """
    Verify a plain API key against its hash.
    Used by __init__.py and API key management.
    """
    return pwd_context.verify(plain_key, hashed_key)


def generate_api_key(prefix: str = "sk") -> str:
    """
    Generate a secure random API key.
    Useful for future 'Create API Key' features.
    """
    import secrets

    return f"{prefix}_{secrets.token_urlsafe(32)}"

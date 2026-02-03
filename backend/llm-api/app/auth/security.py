"""
Sabhya AI - JWT Authentication & RBAC Security Module

Security Decisions:
- HS256 algorithm (symmetric, suitable for single-service deployment)
- Short-lived access tokens (30 min) + refresh tokens (7 days)
- Role-based access control with permission inheritance
- Bcrypt hashing for API keys (cost factor 12)
- Backward compatibility with legacy API keys during migration
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Set
from enum import Enum

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from passlib.context import CryptContext

# JWT library
try:
    from jose import JWTError, jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    logging.warning("python-jose not installed, JWT auth disabled")

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

# SECURITY: In production, these MUST be set via environment variables
SECRET_KEY = os.getenv(
    "SECRET_KEY", 
    "***REMOVED***-key-change-in-production-minimum-32-chars"
)
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Legacy API key support (for backward compatibility during migration)
LEGACY_API_KEYS = os.getenv("API_KEYS", "").split(",")
LEGACY_AUTH_ENABLED = os.getenv("LEGACY_AUTH_ENABLED", "true").lower() == "true"

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================================
# ROLE DEFINITIONS
# ============================================================================

class Roles(str, Enum):
    """User roles with hierarchical permissions."""
    ADMIN = "admin"       # Full access
    AUDITOR = "auditor"   # Read audit logs
    USER = "user"         # Normal API access
    VIEWER = "viewer"     # Read-only access


class Permissions(str, Enum):
    """Granular permissions."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    AUDIT = "audit"
    MANAGE_USERS = "manage_users"
    MANAGE_KEYS = "manage_keys"


# Role to permission mapping
ROLE_PERMISSIONS: dict[str, Set[str]] = {
    Roles.ADMIN: {
        Permissions.READ, Permissions.WRITE, Permissions.DELETE,
        Permissions.AUDIT, Permissions.MANAGE_USERS, Permissions.MANAGE_KEYS
    },
    Roles.AUDITOR: {
        Permissions.READ, Permissions.AUDIT
    },
    Roles.USER: {
        Permissions.READ, Permissions.WRITE
    },
    Roles.VIEWER: {
        Permissions.READ
    },
}


# ============================================================================
# DATA MODELS
# ============================================================================

class TokenData(BaseModel):
    """Decoded JWT token payload."""
    sub: str  # user_id
    roles: List[str]
    exp: int
    iat: int
    token_type: str = "access"


class Token(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfo(BaseModel):
    """User information extracted from token."""
    user_id: str
    roles: List[str]
    permissions: Set[str]
    is_legacy_key: bool = False


# ============================================================================
# TOKEN FUNCTIONS
# ============================================================================

def create_access_token(
    user_id: str,
    roles: List[str],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT access token.
    
    Args:
        user_id: Unique user identifier
        roles: List of user roles
        expires_delta: Custom expiration time
        
    Returns:
        Encoded JWT token string
    """
    if not JWT_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT authentication not available"
        )
    
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    now = datetime.utcnow()
    expire = now + expires_delta
    
    payload = {
        "sub": user_id,
        "roles": roles,
        "exp": expire,
        "iat": now,
        "token_type": "access"
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(f"Access token created for user: {user_id[:8]}...")
    return token


def create_refresh_token(user_id: str) -> str:
    """
    Create JWT refresh token (longer expiration).
    
    Args:
        user_id: Unique user identifier
        
    Returns:
        Encoded JWT refresh token
    """
    if not JWT_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT authentication not available"
        )
    
    now = datetime.utcnow()
    expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "token_type": "refresh"
    }
    
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> TokenData:
    """
    Verify and decode JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        TokenData object with decoded payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    if not JWT_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT authentication not available"
        )
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        roles: List[str] = payload.get("roles", [])
        token_type: str = payload.get("token_type", "access")
        
        if user_id is None:
            raise credentials_exception
        
        return TokenData(
            sub=user_id,
            roles=roles,
            exp=payload.get("exp"),
            iat=payload.get("iat"),
            token_type=token_type
        )
        
    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        raise credentials_exception


def verify_refresh_token(token: str) -> TokenData:
    """
    Verify refresh token and ensure it's not an access token.
    
    Args:
        token: Refresh token string
        
    Returns:
        TokenData if valid
        
    Raises:
        HTTPException: If invalid or wrong token type
    """
    token_data = verify_token(token)
    
    if token_data.token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type - refresh token required"
        )
    
    return token_data


# ============================================================================
# LEGACY API KEY SUPPORT
# ============================================================================

def verify_legacy_api_key(api_key: str) -> Optional[UserInfo]:
    """
    Verify legacy static API key (backward compatibility).
    
    Args:
        api_key: Plain API key string
        
    Returns:
        UserInfo if valid, None otherwise
    """
    if not LEGACY_AUTH_ENABLED:
        return None
    
    if api_key in LEGACY_API_KEYS:
        # Legacy keys get USER role by default
        logger.info(f"Legacy API key authenticated: {api_key[:8]}...")
        return UserInfo(
            user_id=f"legacy_{api_key[:8]}",
            roles=[Roles.USER],
            permissions=ROLE_PERMISSIONS[Roles.USER],
            is_legacy_key=True
        )
    
    return None


# ============================================================================
# FASTAPI DEPENDENCIES
# ============================================================================

# HTTP Bearer scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserInfo:
    """
    FastAPI dependency to extract and verify current user.
    
    Supports both JWT tokens and legacy API keys.
    
    Usage:
        @app.post("/api/endpoint")
        async def endpoint(user: UserInfo = Depends(get_current_user)):
            print(f"User: {user.user_id}, Roles: {user.roles}")
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # Try legacy API key first (for backward compatibility)
    if LEGACY_AUTH_ENABLED:
        legacy_user = verify_legacy_api_key(token)
        if legacy_user:
            return legacy_user
    
    # Try JWT token
    try:
        token_data = verify_token(token)
        
        # Collect permissions from all roles
        permissions: Set[str] = set()
        for role in token_data.roles:
            if role in ROLE_PERMISSIONS:
                permissions.update(ROLE_PERMISSIONS[role])
        
        return UserInfo(
            user_id=token_data.sub,
            roles=token_data.roles,
            permissions=permissions,
            is_legacy_key=False
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(*required_roles: str):
    """
    Dependency factory for role-based access control.
    
    Usage:
        @app.get("/admin/users")
        async def list_users(
            user: UserInfo = Depends(get_current_user),
            _: None = Depends(require_role(Roles.ADMIN))
        ):
            ...
    """
    async def role_checker(user: UserInfo = Depends(get_current_user)):
        user_roles = set(user.roles)
        allowed_roles = set(required_roles)
        
        if not user_roles & allowed_roles:  # No intersection
            logger.warning(
                f"Access denied for user {user.user_id}: "
                f"has {user_roles}, needs {allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {list(allowed_roles)}"
            )
        
        return user
    
    return role_checker


def require_permission(*required_permissions: str):
    """
    Dependency factory for permission-based access control.
    
    Usage:
        @app.delete("/documents/{id}")
        async def delete_doc(
            user: UserInfo = Depends(get_current_user),
            _: None = Depends(require_permission(Permissions.DELETE))
        ):
            ...
    """
    async def permission_checker(user: UserInfo = Depends(get_current_user)):
        required = set(required_permissions)
        
        if not required.issubset(user.permissions):
            missing = required - user.permissions
            logger.warning(
                f"Permission denied for user {user.user_id}: "
                f"missing {missing}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {list(missing)}"
            )
        
        return user
    
    return permission_checker


# ============================================================================
# API KEY HASHING (For stored API keys)
# ============================================================================

def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using bcrypt for secure storage.
    
    Args:
        api_key: Plain API key
        
    Returns:
        Bcrypt hashed key
    """
    return pwd_context.hash(api_key)


def verify_api_key_hash(plain_key: str, hashed_key: str) -> bool:
    """
    Verify a plain API key against its bcrypt hash.
    
    Args:
        plain_key: Plain API key
        hashed_key: Stored bcrypt hash
        
    Returns:
        True if match, False otherwise
    """
    return pwd_context.verify(plain_key, hashed_key)


def generate_api_key(prefix: str = "sk") -> str:
    """
    Generate a secure random API key.
    
    Args:
        prefix: Key prefix (e.g., "sk" for secret key)
        
    Returns:
        API key in format: {prefix}_{random_32_chars}
    """
    import secrets
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}_{random_part}"

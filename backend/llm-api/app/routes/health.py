"""
Sabhya AI - Health Check Endpoints

Provides Kubernetes-compatible health probes:
- /health/live: Liveness probe (is app running?)
- /health/ready: Readiness probe (is app ready for traffic?)
- /health/deep: Detailed health check (admin only)
"""

import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.security import Roles, UserInfo, require_role
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


# ============================================================================
# LIVENESS PROBE
# ============================================================================


@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness_check():
    """
    Liveness probe - Is the application process running?

    Used by orchestrators (K8s, ECS, Docker Swarm) to detect
    if the application has crashed and needs to be restarted.

    Should be fast and not depend on external services.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "version": os.getenv("APP_VERSION", "0.4.0"),
    }


# ============================================================================
# READINESS PROBE
# ============================================================================


@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness probe - Is the application ready to accept traffic?

    Checks all critical dependencies:
    - PostgreSQL database
    - Redis cache (if enabled)
    - Ollama inference engine

    Returns 503 if any critical dependency is unhealthy.
    """
    checks = {}
    is_ready = True

    # Check database
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy", "type": "postgresql"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)[:100]}
        is_ready = False
        logger.error(f"Database health check failed: {e}")

    # Check Redis (optional)
    try:
        import redis

        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))

        r = redis.Redis(host=redis_host, port=redis_port, socket_timeout=2)
        r.ping()
        checks["redis"] = {"status": "healthy", "host": redis_host}
    except ImportError:
        checks["redis"] = {"status": "not_configured", "note": "Redis not installed"}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)[:100]}
        # Redis is optional, don't fail readiness
        logger.warning(f"Redis health check failed: {e}")

    # Check Ollama
    try:
        import requests

        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        response = requests.get(f"{ollama_url}/api/tags", timeout=3)

        if response.status_code == 200:
            models = response.json().get("models", [])
            checks["ollama"] = {
                "status": "healthy",
                "url": ollama_url,
                "models_loaded": len(models),
            }
        else:
            checks["ollama"] = {
                "status": "degraded",
                "error": f"HTTP {response.status_code}",
            }
    except Exception as e:
        checks["ollama"] = {"status": "unhealthy", "error": str(e)[:100]}
        is_ready = False
        logger.error(f"Ollama health check failed: {e}")

    # Determine response
    response_status = (
        status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return JSONResponse(
        status_code=response_status,
        content={
            "status": "ready" if is_ready else "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
        },
    )


# ============================================================================
# DEEP HEALTH CHECK (Admin Only)
# ============================================================================


@router.get("/deep")
async def deep_health_check(
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_role(Roles.ADMIN)),
):
    """
    Deep health check - Detailed system status for monitoring.

    Includes:
    - Resource usage (memory, CPU)
    - Database connection pool stats
    - Request latency metrics
    - Configuration validation

    Admin access only (when auth is enabled).
    """
    checks = {}

    # System resources
    try:
        import psutil

        process = psutil.Process()

        checks["system"] = {
            "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
            "memory_percent": round(process.memory_percent(), 2),
            "cpu_percent": round(process.cpu_percent(interval=0.1), 2),
            "threads": process.num_threads(),
            "open_files": len(process.open_files()),
        }
    except ImportError:
        checks["system"] = {"status": "psutil_not_installed"}
    except Exception as e:
        checks["system"] = {"error": str(e)[:100]}

    # Database connection pool
    try:
        pool = db.get_bind().pool
        checks["database_pool"] = {
            "size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total_connections": pool.size() + pool.overflow(),
        }
    except Exception as e:
        checks["database_pool"] = {"error": str(e)[:100]}

    # Configuration validation
    try:
        from app.middleware.security import validate_security_config

        security_config = validate_security_config()
        checks["security"] = security_config
    except Exception as e:
        checks["security"] = {"error": str(e)[:100]}

    # Environment info
    checks["environment"] = {
        "env": os.getenv("ENVIRONMENT", "development"),
        "debug": os.getenv("DEBUG", "false").lower() == "true",
        "python_version": os.popen("python --version 2>&1").read().strip(),
    }

    return {
        "status": "deep_check_complete",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }


# ============================================================================
# STARTUP CHECK
# ============================================================================


async def perform_startup_checks(db: Session) -> bool:
    """
    Perform startup health checks.

    Called during application startup to verify dependencies.

    Returns:
        True if all checks pass, False otherwise
    """
    logger.info("Performing startup health checks...")

    checks_passed = True

    # Database
    try:
        db.execute(text("SELECT 1"))
        logger.info("✓ Database connection OK")
    except Exception as e:
        logger.error(f"✗ Database connection FAILED: {e}")
        checks_passed = False

    # Ollama
    try:
        import requests

        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code == 200:
            logger.info(f"✓ Ollama connection OK ({ollama_url})")
        else:
            logger.warning(f"⚠ Ollama responded with {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠ Ollama not reachable: {e}")
        # Ollama optional at startup

    return checks_passed

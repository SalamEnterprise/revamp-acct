"""
FastAPI Application for Enhanced Journal System
High-performance API with async support
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from prometheus_fastapi_instrumentator import Instrumentator
import structlog

from .routers import journal_router, voucher_router, monitoring_router
from ..core.config import Settings, get_settings
from ..core.database import Database
from ..core.cache import CacheService
from ..utils.metrics import MetricsCollector

logger = structlog.get_logger()

# Global instances
db: Optional[Database] = None
cache: Optional[CacheService] = None
metrics: Optional[MetricsCollector] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    """
    global db, cache, metrics
    
    settings = get_settings()
    
    # Initialize database
    db = Database(settings.database_url)
    await db.connect()
    
    # Initialize cache
    cache = CacheService(settings.redis_url)
    await cache.connect()
    
    # Initialize metrics
    metrics = MetricsCollector()
    
    logger.info("Application started", 
                db_connected=True, 
                cache_connected=True)
    
    yield
    
    # Cleanup
    await db.disconnect()
    await cache.disconnect()
    
    logger.info("Application stopped")


# Create FastAPI app
app = FastAPI(
    title="Enhanced Journal System API",
    description="High-performance insurance journal processing system",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Prometheus instrumentation
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)

# Include routers
app.include_router(
    journal_router.router,
    prefix="/api/v1/journals",
    tags=["journals"]
)

app.include_router(
    voucher_router.router,
    prefix="/api/v1/vouchers",
    tags=["vouchers"]
)

app.include_router(
    monitoring_router.router,
    prefix="/api/v1/monitoring",
    tags=["monitoring"]
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Enhanced Journal System API",
        "version": "2.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "cache": "unknown"
    }
    
    # Check database
    try:
        if db:
            await db.execute("SELECT 1")
            health_status["database"] = "healthy"
    except Exception as e:
        health_status["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check cache
    try:
        if cache:
            await cache.ping()
            health_status["cache"] = "healthy"
    except Exception as e:
        health_status["cache"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    return health_status


@app.get("/metrics")
async def get_metrics():
    """Custom metrics endpoint"""
    
    if not metrics:
        raise HTTPException(status_code=503, detail="Metrics not available")
    
    return metrics.get_all_metrics()


# Dependency injection
async def get_db():
    """Get database session"""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    async with db.get_session() as session:
        yield session


async def get_cache():
    """Get cache service"""
    if not cache:
        raise HTTPException(status_code=503, detail="Cache not available")
    return cache


async def get_metrics_collector():
    """Get metrics collector"""
    if not metrics:
        raise HTTPException(status_code=503, detail="Metrics not available")
    return metrics


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
                "json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
                }
            },
            "handlers": {
                "default": {
                    "formatter": "json",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": "INFO",
                "handlers": ["default"],
            },
        }
    )
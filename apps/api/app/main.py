import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.auth.router import router as auth_router
from app.api.inventory.router import router as inventory_router
from app.api.pos.router import router as pos_router
from app.api.crm.router import router as crm_router
from app.api.reporting.router import router as reporting_router
from app.api.admin.router import router as admin_router

logger = logging.getLogger("vintiz")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Vintiz API started")
    yield
    logger.info("Vintiz API shutting down")


app = FastAPI(
    title="Vintiz API",
    description="Boutique Management API for Vintiz",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router, prefix="/api")
app.include_router(inventory_router, prefix="/api")
app.include_router(pos_router, prefix="/api")
app.include_router(crm_router, prefix="/api")
app.include_router(reporting_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}

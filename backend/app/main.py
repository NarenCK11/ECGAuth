import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import admin, analytics, auth, ecg, medical_records, users
from app.core.config import get_settings
from app.core.database import get_sessionmaker
from app.services.authentication_service import ServiceError, ensure_admin
from app.services.ml_service import ECGModelService

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ecgauth")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.ml = ECGModelService(settings.model_dir)
    if settings.load_model_on_startup:
        app.state.ml.load_model()
    try:
        with get_sessionmaker()() as db:
            ensure_admin(db)
    except Exception as e:  # database not migrated yet, etc. - keep the API up so /api/health explains
        log.error("Admin bootstrap skipped: %s", e)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ECGAuth API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(ServiceError)
    async def _service_error(_: Request, exc: ServiceError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.get("/api/health", tags=["system"])
    def health():
        return {"status": "ok", "ml_available": app.state.ml.available}

    for r in (auth.router, ecg.router, users.router, medical_records.router, admin.router, analytics.router):
        app.include_router(r)
    return app


app = create_app()

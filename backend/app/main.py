import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.services.ml_service import ECGModelService

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.ml = ECGModelService(settings.model_dir)
    if settings.load_model_on_startup:
        app.state.ml.load_model()
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

    @app.get("/api/health", tags=["system"])
    def health():
        return {"status": "ok", "ml_available": app.state.ml.available}

    return app


app = create_app()

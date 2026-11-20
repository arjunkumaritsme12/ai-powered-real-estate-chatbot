import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router, store
from app.config import get_settings
from starlette.concurrency import run_in_threadpool


logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.app_env == "production":
        try:
            await run_in_threadpool(store.load_index)
        except Exception:
            logging.getLogger(__name__).exception("Knowledge index warmup failed")
    yield


app = FastAPI(
    title="PropertyIQ API",
    description="Grounded real-estate RAG assistant for DarGlobal and Wasalt",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

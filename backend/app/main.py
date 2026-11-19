import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.config import get_settings


logging.basicConfig(level=logging.INFO)
settings = get_settings()

app = FastAPI(
    title="PropertyIQ API",
    description="Grounded real-estate RAG assistant for DarGlobal and Wasalt",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

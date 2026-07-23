import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from app.errors import ApiError, api_error_handler
from app.db.connection import init_db
from app.routers import (
    chart_router,
    chat_router,
    export_router,
    row_router,
    session_router,
    system_prompt_router,
    upload_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Lumenci Assistant Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(ApiError, api_error_handler)

app.include_router(session_router.router)
app.include_router(upload_router.router)
app.include_router(chart_router.router)
app.include_router(chat_router.router)
app.include_router(row_router.router)
app.include_router(system_prompt_router.router)
app.include_router(export_router.router)

"""Seller API. Routes live in api.routes and behavior lives in services."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import SQLModel

from shop_assistant.api.routes import router
from shop_assistant.db import init_engine
from shop_assistant.models import records as _records  # noqa: F401
from shop_assistant.services.batch import cancel_pending


def create_app(database_url: str | None = None) -> FastAPI:
    """Build the shop API and create tables on startup."""
    database = init_engine(database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        SQLModel.metadata.create_all(database)
        if database_url is None:
            from shop_assistant.log_server import start_log_server

            start_log_server()
        yield
        cancel_pending()
        database.dispose()

    app = FastAPI(
        title="Tunisian Social Commerce Assistant",
        version="0.1.0",
        description="Local, seller-reviewed reply copilot. No messages are sent.",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()

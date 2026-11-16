from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.constants import APP_META, REQUEST_ID_HEADER
from app.core.config import Environment, Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware, RequestSizeLimitMiddleware
from app.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        configure_logging(config.log_level, config.env.value)
        yield

    production = config.env is Environment.PRD
    app = FastAPI(
        title=APP_META.name,
        version=APP_META.version,
        debug=config.debug,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = config
    app.include_router(health_router)
    register_exception_handlers(app)
    app.add_middleware(RequestSizeLimitMiddleware, max_body_bytes=config.max_request_body_bytes)
    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Content-Type", "Authorization"],
            expose_headers=[REQUEST_ID_HEADER],
        )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts)
    app.add_middleware(RequestContextMiddleware)
    return app

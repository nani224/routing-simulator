"""FastAPI application factory, middleware, and route aggregator."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routelab.api.models import HealthResponse
from routelab.api.routes_plugins import router as plugins_router
from routelab.api.routes_scenarios import router as scenarios_router
from routelab.api.routes_simulation import router as simulation_router
from routelab.api.routes_topologies import router as topologies_router
from routelab.api.routes_ws import router as ws_router
from routelab.api.state import session_manager


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifecycle context managing session background tasks."""
    await session_manager.initialize()
    yield
    await session_manager.shutdown()


def create_app() -> FastAPI:
    """Create and configure the RouteLab FastAPI application instance."""
    app = FastAPI(
        title="RouteLab API",
        description="Real-Time Comparative Routing Protocol Simulator (Team 20)",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Permissive CORS for interactive web frontend drafting table
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Core health check
    @app.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
    def health_check() -> HealthResponse:
        return HealthResponse()

    # Mount REST routers under /api/v1
    app.include_router(topologies_router, prefix="/api/v1")
    app.include_router(plugins_router, prefix="/api/v1")
    app.include_router(scenarios_router, prefix="/api/v1")
    app.include_router(simulation_router, prefix="/api/v1")

    # Mount WebSocket router
    app.include_router(ws_router)

    return app


app = create_app()

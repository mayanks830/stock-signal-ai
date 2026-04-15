import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.routes import signals, performance, scanner


def create_app() -> FastAPI:
    app = FastAPI(title="Trading Signal API", version="1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(signals.router, prefix="/api")
    app.include_router(performance.router, prefix="/api")
    app.include_router(scanner.router, prefix="/api")

    # Serve React frontend if built
    frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
    if os.path.exists(frontend_dist):
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")

    return app


app = create_app()

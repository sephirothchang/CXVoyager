# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of CXVoyager.
#
# CXVoyager is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CXVoyager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CXVoyager.  If not, see <https://www.gnu.org/licenses/>.

"""FastAPI application factory exposing both API and static UI."""
from __future__ import annotations

import logging
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from cxvoyager.library.common.logging_config import setup_logging

from .routers import deployment_routes

logger = logging.getLogger("cxvoyager.web")

_MODULE_ROOT = Path(__file__).resolve().parents[1]
WEB_CONSOLE_DIST = _MODULE_ROOT / "web_console" / "dist" / "spa"
STATIC_FALLBACK = Path(__file__).parent / "static"
STATIC_ROOT = WEB_CONSOLE_DIST if WEB_CONSOLE_DIST.exists() else STATIC_FALLBACK
STATIC_RESOURCES = STATIC_ROOT / "resources"
REPO_RESOURCES = Path(__file__).resolve().parents[2]
INDEX_FILE = STATIC_ROOT / "index.html"
INDEX_HTML: str | None = None
if INDEX_FILE.exists():  # pragma: no cover - filesystem interaction
    INDEX_HTML = INDEX_FILE.read_text(encoding="utf-8")


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="CXVoyager Service", version="0.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):  # pragma: no cover - side-effect logging
        path = request.url.path
        is_assets = path.startswith("/assets")
        is_polling = path.startswith("/api/tasks")

        if is_assets or is_polling:
            logger.debug("-> %s %s", request.method, path)
        else:
            logger.info("-> %s %s", request.method, path)
        start = perf_counter()
        try:
            response = await call_next(request)
        except Exception:  # pragma: no cover - logged and re-raised
            logger.exception("<- %s %s failed", request.method, path)
            raise
        duration = (perf_counter() - start) * 1000
        status_code = response.status_code
        if is_polling:
            if status_code == 200:
                logger.debug("<- %s %s %s %.2fms", request.method, path, status_code, duration)
            else:
                logger.warning("<- %s %s %s %.2fms", request.method, path, status_code, duration)
        elif is_assets:
            logger.debug("<- %s %s %s %.2fms", request.method, path, status_code, duration)
        else:
            logger.info("<- %s %s %s %.2fms", request.method, path, status_code, duration)
        return response

    app.include_router(deployment_routes.router, prefix="/api")

    assets_dir = STATIC_ROOT / "assets"
    if assets_dir.exists():  # pragma: no cover - filesystem interaction
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    for resources_dir in (STATIC_RESOURCES, REPO_RESOURCES):
        if resources_dir.exists():  # pragma: no cover - filesystem interaction
            app.mount("/resources", StaticFiles(directory=resources_dir), name="resources")
            break
    else:  # pragma: no cover - filesystem interaction
        logger.warning("未找到静态资源目录，/resources 将不可用")

    if INDEX_HTML:

        @app.get("/", response_class=HTMLResponse)
        async def index() -> HTMLResponse:  # pragma: no cover - simple response
            logger.debug("Serving index.html")
            return HTMLResponse(content=INDEX_HTML)

        @app.get("/ui", include_in_schema=False)
        async def redirect_ui() -> RedirectResponse:  # pragma: no cover - simple redirect
            logger.debug("Redirecting /ui -> /")
            return RedirectResponse(url="/", status_code=307)

    return app


app = create_app()

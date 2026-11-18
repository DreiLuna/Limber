"""Serve the built client and API from one HTTPS origin in hosted deployments."""
from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles


class SPAFiles(StaticFiles):
    async def get_response(self, path, scope):
        if path == "api" or path.startswith("api/") or any(p.startswith(".") for p in Path(path).parts):
            raise HTTPException(404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or Path(path).suffix or scope["method"] not in ("GET", "HEAD"):
                raise
            return FileResponse(Path(self.directory) / "index.html")


def mount_frontend(app: FastAPI, directory: Path | None):
    if directory is not None:
        app.mount("/", SPAFiles(directory=str(directory), html=True), name="frontend")

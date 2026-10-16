import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def install_error_handling(app: FastAPI) -> None:
    @app.middleware("http")
    async def safe_errors(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            # Consume the exception here so the ASGI server cannot log a secret-bearing traceback.
            logging.getLogger("app").error("Unhandled request error: %s", type(exc).__name__)
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import traceback

from app.database import init_db
from app.routers import auth, admin, workflow

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="ClinicVault Enterprise", lifespan=lifespan)

# Error Handling Middleware
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    if request.headers.get("accept") == "application/json":
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "Validation error", "details": str(exc)}
        )
    return HTMLResponse(
        content=f"<h3>Validation Error</h3><p>{str(exc)}</p><a href='/'>Go Back</a>",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    error_detail = str(exc)
    if request.headers.get("accept") == "application/json":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal server error", "detail": error_detail}
        )
    return HTMLResponse(
        content=f"<h3>An error occurred</h3><p>{error_detail}</p><a href='/dashboard'>Go to Dashboard</a>",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

# Register Routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(workflow.router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
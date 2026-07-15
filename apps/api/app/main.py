"""LedgerPulse API entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request

from app.api.v1 import (
    health, personas, session, master, invoices, intake_email, exceptions, approvals, analytics,
    integrations, copilot, admin,
)

app = FastAPI(
    title="LedgerPulse API",
    version="0.1.0",
    description="AI-native invoice intelligence - control plane API (interview concept).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local demo; tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# RFC 9457-style problem details (Section 12.4)
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "type": "about:blank",
            "title": "Validation error",
            "status": 422,
            "detail": "Request failed validation.",
            "errors": exc.errors(),
        },
    )


app.include_router(health.router)
app.include_router(personas.router, prefix="/v1")
app.include_router(session.router, prefix="/v1")
app.include_router(master.router, prefix="/v1")
app.include_router(invoices.router, prefix="/v1")
app.include_router(intake_email.router, prefix="/v1")
app.include_router(exceptions.router, prefix="/v1")
app.include_router(approvals.router, prefix="/v1")
app.include_router(analytics.router, prefix="/v1")
app.include_router(integrations.router, prefix="/v1")
app.include_router(copilot.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")

"""FastAPI hello service: one route behind Traefik, traced with OpenTelemetry.

There is no tracing code here on purpose. `opentelemetry-instrument` wraps the app at start-up
and environment variables configure it (see the service README), the same way for every
framework.
"""

import logging
from datetime import UTC, datetime

from fastapi import FastAPI
from pydantic import BaseModel

SERVICE = "hello-fastapi"

# No logging setup here either. With OTEL_PYTHON_LOG_CORRELATION=true, OpenTelemetry sets the
# root logger to INFO, prints each record to stderr with its trace id, and sends a copy to Loki.
log = logging.getLogger(__name__)

app = FastAPI(title=SERVICE)


class Hello(BaseModel):
    service: str
    message: str
    time: datetime


# async def: nothing here blocks, so the request stays on the event loop, no thread pool.
@app.get("/hello")
async def hello() -> Hello:
    # Logged while the request's span is active, so the record carries its trace id.
    log.info("said hello")
    return Hello(service=SERVICE, message="hello", time=datetime.now(UTC))


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

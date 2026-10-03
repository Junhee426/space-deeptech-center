import json
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
from starlette.datastructures import MutableHeaders
from simulation.batch import BatchBusyError, shutdown_pool
from core.version import VERSION
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from api.routes import router

@asynccontextmanager
async def lifespan(app):
    yield
    shutdown_pool()


app=FastAPI(
    lifespan=lifespan,
    title="Space Deep Tech Center",
    version=VERSION,
    description="Physics-grounded satellite deep-tech engineering center"
)

# Every request model is a few KB of scalars; anything larger is refused before FastAPI buffers it.
MAX_BODY_BYTES=65536


class RequestBodyLimit:
    """Reject oversized request bodies, including chunked uploads without a Content-Length.

    The body (at most the limit) is buffered here and replayed to the application, so an
    oversized JSON POST never reaches FastAPI's body reader on a 512 MB instance.
    """

    def __init__(self, app, max_bytes):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return
        declared = next((value for name, value in scope["headers"] if name == b"content-length"), None)
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            await self._reject(send)
            return
        chunks, size, pending = [], 0, None
        while True:
            message = await receive()
            if message["type"] != "http.request":
                pending = message
                break
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                await self._reject(send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return pending or {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    async def _reject(self, send):
        body = json.dumps({"detail": f"요청 본문은 {self.max_bytes // 1024} KB 이하여야 합니다."}, ensure_ascii=False).encode()
        await send({"type": "http.response.start", "status": 413, "headers": [
            (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), (b"connection", b"close")]})
        await send({"type": "http.response.body", "body": body})


class ResponseHeaders:
    """Security headers on every response, and revalidation for unversioned page assets."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope["path"]

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "SAMEORIGIN")
                headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
                if path.startswith("/static/vendor/"):
                    # Vendored libraries carry their version in the file name.
                    headers.setdefault("Cache-Control", "public, max-age=604800")
                elif path == "/" or path.startswith("/static/"):
                    # index.html loads /static/app.js unversioned: revalidate (304) after every deploy.
                    headers.setdefault("Cache-Control", "no-cache")
            await send(message)

        await self.app(scope, receive, send_with_headers)


# Outermost last: headers wrap gzip, which wraps the body limit, so 413s carry the headers too.
app.add_middleware(RequestBodyLimit, max_bytes=MAX_BODY_BYTES)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(ResponseHeaders)
app.mount("/static",StaticFiles(directory="static"),name="static")
templates=Jinja2Templates(directory="templates")
app.include_router(router,prefix="/api")

@app.get("/",response_class=HTMLResponse)
def home(request:Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"version": VERSION})


@app.exception_handler(BatchBusyError)
async def batch_busy(request: Request, exc: BatchBusyError):
    return JSONResponse(status_code=503, content={"detail": str(exc)}, headers={"Retry-After": "2"})

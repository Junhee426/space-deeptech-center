from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
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
app.mount("/static",StaticFiles(directory="static"),name="static")
templates=Jinja2Templates(directory="templates")
app.include_router(router,prefix="/api")

@app.get("/",response_class=HTMLResponse)
def home(request:Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"version": VERSION})


@app.exception_handler(BatchBusyError)
async def batch_busy(request: Request, exc: BatchBusyError):
    return JSONResponse(status_code=503, content={"detail": str(exc)}, headers={"Retry-After": "2"})

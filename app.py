from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from api.routes import router
from simulation.batch import TooManyConcurrentJobsError
from orbit.walker import WalkerComputationTooLargeError
from core.engine import APP_VERSION

app=FastAPI(
    title="Space Deep Tech Center",
    version=APP_VERSION,
    description="Physics-grounded satellite deep-tech engineering center"
)
app.mount("/static",StaticFiles(directory="static"),name="static")
templates=Jinja2Templates(directory="templates")
app.include_router(router,prefix="/api")

@app.exception_handler(TooManyConcurrentJobsError)
def too_many_jobs_handler(request:Request, exc:TooManyConcurrentJobsError):
    return JSONResponse(status_code=429, content={"detail":str(exc)})

@app.exception_handler(WalkerComputationTooLargeError)
def walker_too_large_handler(request:Request, exc:WalkerComputationTooLargeError):
    return JSONResponse(status_code=400, content={"detail":str(exc)})

@app.get("/",response_class=HTMLResponse)
def home(request:Request):
    return templates.TemplateResponse("index.html",{"request":request})

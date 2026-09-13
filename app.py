from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from api.routes import router

app=FastAPI(
    title="Space Deep Tech Center",
    version="0.6.0",
    description="Physics-grounded satellite deep-tech engineering center"
)
app.mount("/static",StaticFiles(directory="static"),name="static")
templates=Jinja2Templates(directory="templates")
app.include_router(router,prefix="/api")

@app.get("/",response_class=HTMLResponse)
def home(request:Request):
    return templates.TemplateResponse("index.html",{"request":request})

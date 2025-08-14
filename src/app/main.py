from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import logging

app = FastAPI(title="giga-osint (mvp)")
logger = logging.getLogger("giga")
logger.setLevel("INFO")

# jinja env
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "ui" / "templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

# (optional) static dir if you add css/js later
STATIC_DIR = Path(__file__).resolve().parents[1] / "ui" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    tpl = env.get_template("index.html")
    return tpl.render()

@app.exception_handler(Exception)
async def all_errors(request: Request, exc: Exception):
    logger.exception("unhandled error on %s: %s", request.url, exc)
    return JSONResponse(status_code=500, content={"error":"internal_error","detail":str(exc)})

from app.api import router as api
app.include_router(api, prefix="/api")

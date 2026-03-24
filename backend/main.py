import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from starlette.responses import PlainTextResponse

from backend.routers import public, admin, teacher, student
from backend.database import engine, Base
from backend.seed import seed_admin

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "static"))

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_admin()
    yield

app = FastAPI(title="QuizBlitz API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def block_sensitive_paths(request: Request, call_next):
    # Prevent accidental exposure of dotfiles (e.g. /.env) via StaticFiles mount.
    # Allow /.well-known/* for TLS/ACME or similar setups.
    segments = [s for s in request.url.path.split("/") if s]
    for seg in segments:
        if seg.startswith(".") and seg != ".well-known":
            return PlainTextResponse("Not found", status_code=404)
    return await call_next(request)

@app.middleware("http")
async def clean_html_urls(request: Request, call_next):
    path = request.url.path
    if not ("." in path.split("/")[-1]) and not path.startswith("/api") and path != "/":
        pot_file = os.path.join(STATIC_DIR, path.lstrip("/") + ".html")
        if os.path.exists(pot_file):
            return FileResponse(pot_file)
    return await call_next(request)

# Router Configuration
app.include_router(public.router, prefix="/api")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(teacher.router, prefix="/api")
app.include_router(student.router, prefix="/api")

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/api/health")
def health():
    return {"status": "ok"}

if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

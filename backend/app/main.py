from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import get_settings
from app.core.database import db
from app.core.logging import setup_logging
from app.api.v1.router import api_router

setup_logging()
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.connect_to_database()
    yield
    # Shutdown
    await db.close_database_connection()

from fastapi.staticfiles import StaticFiles
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

app = FastAPI(
    title="StreamFilter API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins="http://103.118.17.51:10000",  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
# We prefix with /api to match the original structure
app.include_router(api_router, prefix="/api")


# Serve static frontend (SPA)
app.mount(
    "/",
    StaticFiles(directory=BASE_DIR / "frontend" / "build", html=True),
    name="static",
)

@app.get("/")
async def root():
    return {"message": "StreamFilter API is running"}

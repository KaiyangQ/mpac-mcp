"""MPAC Web App — FastAPI backend."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup."""
    init_db()
    yield


app = FastAPI(
    title="MPAC Web App API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js dev server (localhost:3000) and production frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://mpac-web.fly.dev",
        "https://mpac-web.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from .routes import users, projects, tokens, chat  # noqa: E402

app.include_router(users.router, prefix="/api", tags=["auth"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(tokens.router, prefix="/api", tags=["tokens"])
app.include_router(chat.router, prefix="/api", tags=["chat"])


@app.get("/health")
async def health():
    return {"status": "ok"}

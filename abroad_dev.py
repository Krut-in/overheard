"""Dev app for the abroad phone page: mounts the /api/abroad router and serves the page at /abroad.

Run: OVERHEARD_FIXTURE=1 .venv/bin/uvicorn abroad_dev:app --port 8010   then open http://localhost:8010/abroad
Ticket F mounts the same router in server.py with one include_router line.
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse

from overheard.api_abroad import router

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Overheard abroad (dev)")
app.include_router(router)


@app.get("/abroad")
async def abroad_page():
    return FileResponse(ROOT / "web" / "abroad" / "index.html")


@app.get("/")
async def root():
    return RedirectResponse("/abroad")

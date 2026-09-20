from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import FRONTEND_ORIGIN
from .routers import chat, restaurants

app = FastAPI(title="KhmerMenuIQ API")

allow_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if FRONTEND_ORIGIN:
    allow_origins.append(FRONTEND_ORIGIN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(restaurants.router)
app.include_router(chat.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}

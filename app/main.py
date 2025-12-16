from __future__ import annotations
from fastapi import FastAPI, Depends
from .store import InMemoryStore
from .api import router
from .worker import Worker

app = FastAPI(title = "LLM Task Runner", version="0.1.0")

store = InMemoryStore()
worker = Worker(store)

def get_store() -> InMemoryStore:
    return store

@app.on_event("startup")
async def on_startup():
    worker.start()

@app.on_event("shutdown")
async def on_shutdown():
    await worker.stop()

# Dependency Injections of store into routes
@app.middleware("http")
async def inject_store(request, call_next):
    request.state.store = store
    return await call_next(request)

@app.get("/")
async def root():
    return {"service" : "llm-task-runner", "status":"running"}

#Hook store into endpoints via Depends
app.include_router(
    router,
    dependencies=[Depends(lambda: get_store())],
)

from fastapi import Request

@app.middleware("http")
async def bind_store_dependency(request: Request, call_next):
    request.scope["fastapi_astack"] = getattr(request, "scope",{}).get("fastapi_astack")
    return await call_next(request)

app.dependency_overrides[InMemoryStore] = lambda: store

from __future__ import annotations
from fastapi import FastAPI, Depends
import redis.asyncio as redis

from .config import settings
from .api import router
from .redis_store import RedisStore
from .redis_queue import RedisQueue
from .worker import Worker

app = FastAPI(title = "LLM Task Runner (Redis + OpenAI)", version="0.1.0")

r = redis.from_url(settings.redis_url, decode_responses=False)
store = RedisStore(r)
queue = RedisQueue(r)
worker = Worker(store,queue)

def get_store() -> RedisStore:
    return store

def get_queue() -> RedisQueue:
    return queue

@app.on_event("startup")
async def startup():
    worker.start()

@app.on_event("shutdown")
async def shutdown():
    await worker.stop()
    await r.aclose()

# Dependency Injections of store into routes
@app.middleware("http")
async def inject_store(request, call_next):
    request.state.store = store
    return await call_next(request)

@app.get("/")
async def root():
    return {"service" : "llm-task-runner", "status":"running"}

#Hook store into endpoints via Depends
app.include_router(router)

app.dependency_overrides[RedisStore] = get_store
app.dependency_overrides[RedisQueue] = get_queue

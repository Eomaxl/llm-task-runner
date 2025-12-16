from __future__ import annotations
from fastapi import APIRouter, HTTPException
from .models import CreateTaskRequest, CreateTaskResponse, Task
from .store import InMemoryStore
from .worker import task_queue
from .metrics import metrics

router = APIRouter()

def _not_found(task_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Task not found: {task_id}")

@router.post("/tasks", response_model=CreateTaskResponse)
async def create_task(req: CreateTaskRequest, store: InMemoryStore):
    task = Task(goal=req.goal, idempotency_key=req.idempotency_key)
    created = await store.create_or_get_task(task)

    # If idempotency returned an existing completed task, dont requeue
    if created.status == "queued":
        await task_queue.put(created.task_id)
    
    await metrics.inc("task_created", 1)
    return CreateTaskRequest(task_id=created.task_id, status=created.status)

@router.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id:str, store: InMemoryStore):
    t = await store.get_task(task_id)
    if not t:
        raise _not_found(task_id)
    return t

@router.get("/health")
async def health():
    return {"ok": True}

@router.get("/metrics")
async def prometheus_metrics():
    text = await metrics.render_prometheus()
    return text
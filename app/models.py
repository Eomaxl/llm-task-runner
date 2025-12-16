from pydantic import BaseModel, Field
from typing import Optional,Literal, Dict, List, Any
from datetime import datetime
import uuid

TaskStatus = Literal["queued", "running", "succeeded", "failed"]

class CreateTaskRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=10_000)
    idempotency_key: Optional[str] = Field(default=None, max_length=200)

class CreateTaskResponse(BaseModel):
    task_id: str
    status: TaskStatus

class StepRecord(BaseModel):
    step_no:int
    kind: Literal["plan","tool"]
    name: str
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[Dict[str,Any]] = None
    ok: bool = True
    error: Optional[str] = None
    latency_ms: Optional[int] = None
    ts: datetime = Field(default_factory=datetime.now)

class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str
    status: TaskStatus = "queued"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    idempotency_key: Optional[str]

    steps: List[StepRecord] = Field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
from __future__ import annotations
import asyncio
import time
from typing import Any, Dict

from .models import StepRecord
from .store import InMemoryStore
from .metrics import metrics
from .config import settings
from .retry import retry_async, RetryError
from .redis_store import RedisStore
from .redis_queue import RedisQueue
from .openai_planner import planner
from . import tools

class Worker:
    def __init__(self, store: RedisStore, queue: RedisQueue) -> None:
        self.store = store
        self.queue = queue
        self._sem = asyncio.Semaphore(settings.max_concurrent_tasks)
        self._running = False
        self._bg: asyncio.Task | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._bg = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._bg:
            self._bg.cancel()
            try:
                await self._bg
            except Exception:
                pass
    
    async def _loop(self) -> None:
        while self._running:
            task_id = await self.queue.dequeue_blocking(timeout_s=1)
            asyncio.create_task(self._guarded(task_id))
    
    async def _guarded(self, task_id: str) -> None:
        async with self._sem:
            await self._execute(task_id)

    async def _execute(self, task_id: str) -> None:
        task = await self.store.get_task(task_id)
        if not task:
            return
        
        if task.status in ("succeeded", "failed"):
            return
        
        await self.store.update_task_fields(task_id, status="running")
        await metrics.inc("tasks_running",1)

        try:
            await self._workflow(task_id, task.goal)
            await self.store.update_task_fields(task_id, status="succeeded", result="Completed")
            await metrics.inc("tasks_succeeded", 1)
        except Exception as e:
            await self.store.update_task_fields(task_id, status="failed", error=str(e))
            await metrics.inc("tasks_failed",1)
        finally:
            await metrics.dec("tasks_running", 1)

    async def _workflow(self, task_id: str, goal: str) -> None:
        # PLAN step
        t0 = time.perf_counter()
        planned = planner.plan(goal)
        await metrics.inc("llm_plans", 1)

        await self.store.append_step(
            task_id,
            StepRecord(
                step_no=1,
                kind = "plan",
                name="openai_planner",
                input= {"goal": goal},
                output= {"planned_steps": planned},
                ok = True,
                latency_ms=int((time.perf_counter() - t0) * 1000),
            ),
        )
        

        #Enforce step limits:
        if len(planned) > settings.max_steps:
            raise RuntimeError(f"too many steps planned : {len(planned)} > {settings.max_steps}")
        
        #Execute tool steps:
        step_no = 2
        for idx, st in enumerate(planned, start = 1):
            tool = st["tool"]
            args = st["args"]
            record = StepRecord(step_no=step_no, kind="tool", name=tool_name, input=args)
            step_no += 1

            # Step timeout wrapper
            async def run_one() -> Dict[str, Any]:
                return await self._call_tool(tool, args)
            
            s0 = time.perf_counter()
            try:
                out = await asyncio.wait_for(
                    retry_async(
                        lambda: run_one(),
                        attempts= settings.retry_max_attempts,
                        base_delay= settings.retry_base_attempts,
                        max_delay= settings.retry_max_attempts,
                        jitter= settings.retry_jitter,
                        retry_on= (tools.ToolError,),
                    ),
                    timeout = settings.step_timeout_seconds,
                )
                record.ok = True
                record.output = out
                await metrics.inc("tool_calls",1)
            except asyncio.TimeoutError:
                record.ok = False
                record.error = f"step timeout after {settings.step_timeout_seconds}s"
                await metrics.inc("tool_failure",1)
                raise
            except RetryError as e:
                record.ok = False
                record.error = f"tool failed after retries: {e}"
                await metrics.inc("tool_failure", 1)
                raise
            finally:
                record.latency_ms = int((time.perf_counter() - s0) * 1000)
                await self.store.append_step(task_id, record)
                

    async def _call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "http_get":
            return await tools.http_get(args["url"])
        if tool_name == "calc":
            return await tools.calc(args["expr"])
        raise RuntimeError(f"unknown tool : {tool_name}")
from __future__ import annotations
import asyncio
import time
from typing import Any, Dict

from .models import Task, StepRecord
from .store import InMemoryStore
from .metrics import metrics
from .config import settings
from .retry import retry_async, RetryError
from .planner import planner
from . import tools

class TaskQueue:
    def __init__(self) -> None:
        self.q: asyncio.Queue[str] = asyncio.Queue()

    async def put(self, task_id: str)-> None:
        await self.q.put(task_id)

    async def get(self) -> str:
        return await self.q.get()
    
task_queue = TaskQueue()

class Worker:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store
        self._sem = asyncio.Semaphore(settings.max_concurrent_tasks)
        self._running = False
        self._bg_task: asyncio.Task | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._bg_task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._bg_task:
            self._bg_task.cancel()
            try:
                await self._bg_task
            except Exception:
                pass
    
    async def run_loop(self) -> None:
        while self._running:
            task_id = await task_queue.get()
            asyncio.create_task(self._guarded_execute(task_id))
    
    async def _guarded_execute(self, task_id: str) -> None:
        async with self._sem:
            await self._execute(task_id)

    async def _execute(self, task_id: str) -> None:
        task = await self.store.get_task(task_id)
        if not task:
            return
        
        if task.status in ("succeeded", "failed"):
            return
        
        task.status = "running"
        await metrics.inc("tasks_running",1)
        await self.store.update_task(task)

        try:
            await self._run_workflow(task)
            task.status = "succeeded"
            await metrics.inc("tasks_succeeded", 1)
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            await metrics.inc("tasks_failed",1)
        finally:
            await metrics.dec("tasks_running", 1)
            await self.store.update_task(task)

    async def _run_workflow(self, task:Task) -> None:
        # PLAN step
        t0 = time.perf_counter()
        steps = planner.plan(task.goal)
        await metrics.inc("llm_plans", 1)

        task.steps.append(
            StepRecord(
                step_no=len(task.steps)+ 1,
                kind = "plan",
                name="local_planner",
                input= {"goal": task.goal},
                output= {"planned_steps": steps},
                ok = True,
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )
        )
        await self.store.update_task(task)

        #Enforce step limits:
        if len(steps) > settings.max_steps:
            raise RuntimeError(f"too many steps planned : {len(steps)} > {settings.max_steps}")
        
        #Execute tool steps:
        observations: Dict[str, Any] = {}
        for i,st in enumerate(steps, start = 1):
            tool = st["tool"]
            args = st["args"]

            # Step timeout wrapper
            async def run_one() -> Dict[str, Any]:
                return await self._call_tool(tool, args)
            
            step_t0 = time.perf_counter()
            record = StepRecord(
                step_no=len(task.steps) + 1,
                kind = "tool",
                name = tool,
                input = args,
            )

            try:
                result = await asyncio.wait_for(
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
                record.output = result
                observations[f"{tool}_{i}"] = result
            except asyncio.TimeoutError:
                record.ok = False
                record.error = f"step timeout after {settings.step_timeout_seconds}s"
                await metrics.inc("tool_failure",1)
                task.steps.append(record)
                await self.store.update_task(task)
                raise
            except RetryError as e:
                record.ok = False
                record.error = f"tool failed after retries: {e}"
                await metrics.inc("tool_failure", 1)
                task.steps.append(record)
                await self.store.update_task(task)
                raise
            finally:
                record.latency_ms = int((time.perf_counter() - step_t0) * 1000)
            
            await metrics.inc("tool_calls",1)
            task.steps.append(record)
            await self.store.update_task(task)
        
        # Final result (simple)
        if observations:
            task.result = f"Completed. Observations keys: {list(observations.keys())}"
        else:
            task.result = "Completed. No tools required. (Planner produced 0 steps. )"
            

    async def _call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "http_get":
            return await tools.http_get(args["url"])
        if tool_name == "calc":
            return await tools.calc(args["expr"])
        raise RuntimeError(f"unknown tool : {tool_name}")
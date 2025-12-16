from __future__ import annotations
import asyncio
import random
from typing import Callable, Awaitable, TypeVar, Optional

T = TypeVar("T")

class RetryError(Exception):
    pass

async def retry_async(
        fn: Callable[[], Awaitable[T]],
        *,
        attempts: int,
        base_delay: float,
        max_delay: float,
        jitter: float,
        retry_on: tuple[type[Exception], ...] = (Exception,),
) -> T:
    last_exc: Optional[Exception] = None
    for i in range(1 , attempts+1) :
        try:
            return await fn()
        except retry_on as e:
            last_exc = e
            if i == attempts:
                break
            delay = min(max_delay, base_delay * ( 2 ** (i - 1)))
            delay = max(0.0, delay + random.uniform(0.0, jitter))
            await asyncio.sleep(delay)
        raise RetryError(str(last_exc) if last_exc else "retry failed")
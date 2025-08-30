import asyncio
from typing import Coroutine, List, Any


async def run_concurrently(
    coroutines: List[Coroutine], max_concurrency: int
) -> List[Any]:
    """주어진 코루틴들을 최대 동시성 제한을 두어 실행합니다."""
    semaphore = asyncio.Semaphore(max_concurrency)
    tasks = []

    async def worker(coro):
        async with semaphore:
            return await coro

    for coro in coroutines:
        tasks.append(asyncio.create_task(worker(coro)))

    return await asyncio.gather(*tasks)

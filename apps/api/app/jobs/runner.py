from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar

T = TypeVar("T")


def run_concurrent(func: Callable[[T], None], items: Sequence[T], max_workers: int) -> None:
    """Run work with a bounded in-process thread pool. No Redis/queue required."""
    if not items:
        return
    workers = max(1, min(max_workers, len(items)))
    if workers == 1:
        for item in items:
            func(item)
        return
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(func, item) for item in items]
        for future in as_completed(futures):
            future.result()

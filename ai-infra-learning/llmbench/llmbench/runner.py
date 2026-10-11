"""Load generator: when to send requests.

The default is an OPEN-LOOP arrival process: request i is scheduled at a
pre-computed time regardless of whether earlier requests have finished. This
is how real users behave. A closed loop ("keep N requests in flight") hides
overload: when the server slows down, a closed-loop client politely slows
down too, and latency percentiles look better than any real user would see
(the "coordinated omission" problem).
"""

from __future__ import annotations

import asyncio
import random
import time

import aiohttp

from .client import Result, send
from .workload import Request


def arrival_offsets(n: int, rate: float, burstiness: float = 1.0, seed: int = 0) -> list[float]:
    """Seconds from start at which each request is due.

    rate=inf sends everything at t=0 (an offline / max-throughput test).
    Inter-arrival gaps are Gamma-distributed with mean 1/rate. burstiness=1 is
    a Poisson process; <1 is burstier, >1 is more regular.
    """
    if rate == float("inf"):
        return [0.0] * n
    rng = random.Random(seed)
    shape = burstiness
    scale = 1.0 / (rate * shape)
    t, out = 0.0, []
    for _ in range(n):
        out.append(t)
        t += rng.gammavariate(shape, scale)
    return out


async def run(
    base_url: str,
    model: str,
    requests: list[Request],
    rate: float,
    *,
    burstiness: float = 1.0,
    max_concurrency: int | None = None,
    endpoint: str = "completions",
    ignore_eos: bool = True,
    timeout_s: float = 600.0,
    seed: int = 0,
    keep_text: bool = False,
) -> tuple[list[Result], float]:
    """Send `requests` at `rate` req/s. Returns (results, wall-clock duration).

    `max_concurrency` caps in-flight requests. Setting it turns the test
    partly closed-loop; use it to model a client-side limit, not by default.
    """
    offsets = arrival_offsets(len(requests), rate, burstiness, seed)
    sem = asyncio.Semaphore(max_concurrency) if max_concurrency else None
    conn = aiohttp.TCPConnector(limit=0)  # no client-side connection cap
    timeout = aiohttp.ClientTimeout(total=timeout_s)

    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
        start = time.perf_counter()

        async def one(req: Request, off: float) -> Result:
            due = start + off
            delay = due - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)
            if sem:
                async with sem:
                    return await send(session, base_url, req, model, due, endpoint, ignore_eos, keep_text)
            return await send(session, base_url, req, model, due, endpoint, ignore_eos, keep_text)

        results = await asyncio.gather(*(one(r, o) for r, o in zip(requests, offsets)))
        duration = time.perf_counter() - start
    return list(results), duration


async def warmup(base_url: str, model: str, requests: list[Request], endpoint: str, ignore_eos: bool) -> None:
    """A few requests to trigger lazy init (CUDA graphs, JIT, connection setup)
    before measuring. Results are discarded."""
    if requests:
        await run(base_url, model, requests, float("inf"), endpoint=endpoint, ignore_eos=ignore_eos)

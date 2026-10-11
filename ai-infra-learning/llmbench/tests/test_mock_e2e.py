"""Run the real client and load generator against the mock server in-process."""

import asyncio

from aiohttp import web

from llmbench import workload as wl
from llmbench.metrics import summarize
from llmbench.mock_server import build_engine, make_app
from llmbench.runner import run


async def _bench(engine, reqs, rate, endpoint="completions"):
    runner = web.AppRunner(make_app(engine, "mock"))
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        return await run(f"http://127.0.0.1:{port}", "mock", reqs, rate, endpoint=endpoint)
    finally:
        await runner.cleanup()


def test_all_requests_complete_with_exact_lengths():
    engine = build_engine("h100-8b", 256, 2048)
    reqs = wl.synthetic(30, "fixed:200", "fixed:20", seed=0)
    results, duration = asyncio.run(_bench(engine, reqs, float("inf")))
    assert all(r.ok for r in results)
    assert all(r.output_tokens == 20 and r.prompt_tokens == 200 for r in results)
    s = summarize(results, duration)
    assert s["ttft_ms"]["p50"] > 0 and s["tpot_ms"]["p50"] > 0


def test_chat_endpoint():
    engine = build_engine("h100-8b", 256, 2048)
    results, _ = asyncio.run(_bench(engine, wl.synthetic(3, "fixed:10", "fixed:5"), float("inf"), "chat"))
    assert all(r.ok and r.output_tokens == 5 for r in results)


def test_bigger_batch_means_slower_tokens():
    """Decode is memory-bound, so TPOT rises only modestly with batch size (guide Stage 2)."""
    def tpot(n):
        engine = build_engine("h100-8b", 256, 8192)
        rs, _ = asyncio.run(_bench(engine, wl.synthetic(n, "fixed:100", "fixed:40", seed=1), float("inf")))
        return summarize(rs, 1.0)["tpot_ms"]["p50"]

    t1, t64 = tpot(1), tpot(64)
    assert t64 > t1
    assert t64 < 4 * t1  # 64x the work for far less than 64x the time


def test_kv_pressure_triggers_preemption():
    engine = build_engine("h100-8b", 256, 2048, gpu_mem=18.3e9)  # ~5K tokens of KV
    reqs = wl.synthetic(30, "fixed:300", "fixed:60", seed=2)
    results, _ = asyncio.run(_bench(engine, reqs, float("inf")))
    assert all(r.ok and r.output_tokens == 60 for r in results)
    assert engine.stats["preemptions"] > 0

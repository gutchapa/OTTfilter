"""A fake OpenAI-compatible LLM server that simulates a continuous-batching engine.

It runs no model. Each scheduler step it decides which sequences run (decodes
plus prefill chunks, like vLLM's chunked-prefill scheduler), computes how long
that step would take on the configured GPU with a roofline model, sleeps for
that long, then streams one token to every sequence that produced one.

    step_time = max(FLOPs / (peak * compute_eff), bytes / (bandwidth * bw_eff))
                + launch overhead + communication overhead
    FLOPs     = 2 * params * tokens_in_step
    bytes     = weight bytes + KV-cache bytes read by every sequence in the step

It is a teaching tool, not a predictor: attention FLOPs, kernel inefficiencies,
sampling and CPU scheduling costs are ignored or folded into constants. It is
good enough to show the shapes the guide talks about: TPOT flat then rising
with batch size, chunked-prefill trade-offs, KV-capacity queueing and
preemption. Python's own overhead limits it to a few hundred concurrent
streams; past that the mock itself becomes the bottleneck.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import time
from collections import deque
from dataclasses import asdict, dataclass, field, replace

from aiohttp import web


@dataclass(frozen=True)
class Hardware:
    params: float              # model parameters
    bytes_per_param: float     # 2 = BF16, 1 = FP8
    hbm_bw: float              # bytes/s, summed over all GPUs serving one replica
    peak_flops: float          # FLOP/s, summed over all GPUs
    gpu_mem: float             # bytes, summed over all GPUs
    kv_bytes_per_token: float  # 2 * layers * kv_heads * head_dim * bytes
    compute_eff: float = 0.6   # fraction of peak FLOP/s achieved by GEMMs
    bw_eff: float = 0.8        # fraction of peak bandwidth achieved
    step_overhead_s: float = 0.001  # launch + scheduler cost per step
    comm_s_per_step: float = 0.0    # tensor-parallel all-reduce cost per step

    @property
    def weight_bytes(self) -> float:
        return self.params * self.bytes_per_param

    @property
    def kv_capacity_tokens(self) -> int:
        # ~10% of memory goes to activations, CUDA graphs and fragmentation.
        return max(0, int((self.gpu_mem * 0.9 - self.weight_bytes) / self.kv_bytes_per_token))


H100 = dict(hbm_bw=3.35e12, peak_flops=989e12, gpu_mem=80e9)
PRESETS: dict[str, Hardware] = {
    # Llama-3-8B shape: 32 layers, 8 KV heads, head_dim 128 -> 128 KiB/token in BF16
    "h100-8b": Hardware(params=8e9, bytes_per_param=2, kv_bytes_per_token=131072, **H100),
    "h100-8b-fp8": Hardware(params=8e9, bytes_per_param=1, kv_bytes_per_token=131072, **H100),
    # Llama-3-70B shape: 80 layers, 8 KV heads, head_dim 128 -> 320 KiB/token, TP=4
    "h100x4-70b": Hardware(
        params=70e9, bytes_per_param=2, kv_bytes_per_token=327680,
        hbm_bw=4 * 3.35e12, peak_flops=4 * 989e12, gpu_mem=4 * 80e9, comm_s_per_step=0.0006,
    ),
    # Same 70B on one AMD MI300X: no tensor parallelism needed (guide 13.3)
    "mi300x-70b": Hardware(
        params=70e9, bytes_per_param=2, kv_bytes_per_token=327680,
        hbm_bw=5.3e12, peak_flops=1307e12, gpu_mem=192e9,
    ),
}


@dataclass
class Seq:
    id: int
    prompt_tokens: int
    max_tokens: int
    out: asyncio.Queue = field(default_factory=asyncio.Queue)
    prefill_target: int = 0   # tokens to (re)prefill before decoding: prompt, plus output after a preemption
    kv_tokens: int = 0        # tokens currently held in the KV cache
    prefill_done: bool = False
    generated: int = 0
    cancelled: bool = False


class Engine:
    def __init__(self, hw: Hardware, max_num_seqs: int = 256, max_batched_tokens: int = 2048):
        self.hw = hw
        self.max_num_seqs = max_num_seqs
        self.max_batched_tokens = max_batched_tokens
        self.waiting: deque[Seq] = deque()
        self.running: list[Seq] = []
        self.wake = asyncio.Event()
        self.ids = itertools.count()
        self.stats = {"steps": 0, "preemptions": 0, "finished": 0, "cancelled": 0, "busy_s": 0.0}

    # -- public API ---------------------------------------------------------
    def submit(self, prompt_tokens: int, max_tokens: int) -> Seq:
        s = Seq(next(self.ids), prompt_tokens, max(1, max_tokens))
        s.prefill_target = prompt_tokens
        self.waiting.append(s)
        self.wake.set()
        return s

    def kv_used(self) -> int:
        return sum(s.kv_tokens for s in self.running)

    def snapshot(self) -> dict:
        cap = self.hw.kv_capacity_tokens
        return {
            **self.stats,
            "running": len(self.running),
            "waiting": len(self.waiting),
            "kv_used_tokens": self.kv_used(),
            "kv_capacity_tokens": cap,
            "kv_usage": round(self.kv_used() / cap, 4) if cap else None,
            "config": {"max_num_seqs": self.max_num_seqs, "max_batched_tokens": self.max_batched_tokens,
                       **asdict(self.hw)},
        }

    # -- scheduler ----------------------------------------------------------
    def _drop_cancelled(self) -> None:
        for q in (self.running, self.waiting):
            keep = [s for s in q if not s.cancelled]
            self.stats["cancelled"] += len(q) - len(keep)
            q.clear()
            q.extend(keep)

    def _schedule(self) -> list[tuple[Seq, int]]:
        """Pick (seq, tokens) pairs for this step. Decodes first (1 token each),
        then continue partial prefills, then admit new requests, all within
        the per-step token budget (chunked prefill)."""
        cap = self.hw.kv_capacity_tokens
        # Out of KV memory: preempt the newest sequence and recompute it later
        # (vLLM's default recompute-preemption). Its client sees a stall.
        while self.running and self.kv_used() + len(self.running) > cap:
            victim = self.running.pop()
            victim.prefill_target = victim.prompt_tokens + victim.generated
            victim.kv_tokens = 0
            victim.prefill_done = False
            self.waiting.appendleft(victim)
            self.stats["preemptions"] += 1

        budget = self.max_batched_tokens
        plan: list[tuple[Seq, int]] = []
        for s in self.running:
            if s.prefill_done and budget > 0:
                plan.append((s, 1))
                budget -= 1
        for s in self.running:
            if not s.prefill_done and budget > 0:
                n = min(s.prefill_target - s.kv_tokens, budget)
                plan.append((s, n))
                budget -= n
        used = self.kv_used() + sum(n for _, n in plan)
        while self.waiting and budget > 0 and len(self.running) < self.max_num_seqs:
            s = self.waiting[0]
            if s.prefill_target > cap:  # can never fit: fail it rather than block the queue
                self.waiting.popleft()
                s.out.put_nowait(None)
                continue
            if used + s.prefill_target > cap:  # wait until KV memory frees up
                break
            self.waiting.popleft()
            self.running.append(s)
            n = min(s.prefill_target, budget)
            plan.append((s, n))
            budget -= n
            used += s.prefill_target
        return plan

    def step_time(self, plan: list[tuple[Seq, int]]) -> float:
        hw = self.hw
        tokens = sum(n for _, n in plan)
        flops = 2 * hw.params * tokens
        kv_read = sum(s.kv_tokens + n for s, n in plan) * hw.kv_bytes_per_token
        mem_bytes = hw.weight_bytes + kv_read
        t = max(flops / (hw.peak_flops * hw.compute_eff), mem_bytes / (hw.hbm_bw * hw.bw_eff))
        return t + hw.step_overhead_s + hw.comm_s_per_step

    async def loop(self) -> None:
        while True:
            self._drop_cancelled()
            plan = self._schedule()
            if not plan:
                self.wake.clear()
                await self.wake.wait()
                continue
            t = self.step_time(plan)
            start = time.perf_counter()
            await asyncio.sleep(t)
            self.stats["steps"] += 1
            self.stats["busy_s"] += time.perf_counter() - start
            for s, n in plan:
                if s.cancelled:
                    continue
                s.kv_tokens += n
                if not s.prefill_done:
                    if s.kv_tokens < s.prefill_target:
                        continue
                    s.prefill_done = True  # the step that finishes prefill also samples a token
                s.generated += 1
                s.out.put_nowait(1)
                if s.generated >= s.max_tokens:
                    self.running.remove(s)
                    s.out.put_nowait(None)
                    self.stats["finished"] += 1


# -- HTTP layer ---------------------------------------------------------------
ENGINE_TASK = web.AppKey("engine_task", asyncio.Task)


def count_prompt_tokens(body: dict) -> int:
    if "messages" in body:
        text = " ".join(str(m.get("content", "")) for m in body["messages"])
    else:
        p = body.get("prompt", "")
        text = " ".join(p) if isinstance(p, list) else str(p)
    return max(1, len(text.split()))


def make_app(engine: Engine, model_name: str = "mock") -> web.Application:
    async def completions(request: web.Request) -> web.StreamResponse:
        body = await request.json()
        chat = request.path.endswith("/chat/completions")
        prompt_tokens = count_prompt_tokens(body)
        max_tokens = int(body.get("max_tokens") or 16)
        seq = engine.submit(prompt_tokens, max_tokens)
        created = int(time.time())
        rid = f"cmpl-mock-{seq.id}"

        def chunk(text: str) -> dict:
            choice = {"index": 0, "delta": {"content": text}} if chat else {"index": 0, "text": text}
            return {"id": rid, "object": "chat.completion.chunk" if chat else "text_completion",
                    "created": created, "model": model_name, "choices": [choice]}

        usage = lambda: {"prompt_tokens": prompt_tokens, "completion_tokens": seq.generated,
                         "total_tokens": prompt_tokens + seq.generated}

        if not body.get("stream"):
            while (await seq.out.get()) is not None:
                pass
            text = " tok" * seq.generated
            choice = {"index": 0, "message": {"role": "assistant", "content": text}} if chat else {"index": 0, "text": text}
            return web.json_response({"id": rid, "model": model_name, "choices": [choice], "usage": usage()})

        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"})
        await resp.prepare(request)
        try:
            done = False
            while not done:
                n = 0
                item = await seq.out.get()
                # Coalesce tokens that piled up while we were busy, like real servers do.
                while True:
                    if item is None:
                        done = True
                        break
                    n += item
                    if seq.out.empty():
                        break
                    item = seq.out.get_nowait()
                if n:
                    await resp.write(f"data: {json.dumps(chunk(' tok' * n))}\n\n".encode())
            if (body.get("stream_options") or {}).get("include_usage"):
                tail = {"id": rid, "model": model_name, "choices": [], "usage": usage()}
                await resp.write(f"data: {json.dumps(tail)}\n\n".encode())
            await resp.write(b"data: [DONE]\n\n")
        except (ConnectionResetError, asyncio.CancelledError):
            seq.cancelled = True  # client went away: free its KV (guide 13.5)
            raise
        return resp

    async def models(_: web.Request) -> web.Response:
        return web.json_response({"object": "list", "data": [{"id": model_name, "object": "model"}]})

    async def stats(_: web.Request) -> web.Response:
        return web.json_response(engine.snapshot())

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="ok")

    async def start_engine(app: web.Application) -> None:
        app[ENGINE_TASK] = asyncio.create_task(engine.loop())

    async def stop_engine(app: web.Application) -> None:
        app[ENGINE_TASK].cancel()

    app = web.Application()
    app.router.add_post("/v1/completions", completions)
    app.router.add_post("/v1/chat/completions", completions)
    app.router.add_get("/v1/models", models)
    app.router.add_get("/stats", stats)
    app.router.add_get("/health", health)
    app.on_startup.append(start_engine)
    app.on_cleanup.append(stop_engine)
    return app


def build_engine(preset: str, max_num_seqs: int, max_batched_tokens: int, **overrides) -> Engine:
    hw = PRESETS[preset]
    overrides = {k: v for k, v in overrides.items() if v is not None}
    if overrides:
        hw = replace(hw, **overrides)
    return Engine(hw, max_num_seqs=max_num_seqs, max_batched_tokens=max_batched_tokens)


def serve(host: str, port: int, engine: Engine, model_name: str) -> None:
    hw = engine.hw
    print(f"mock engine: {hw.params / 1e9:.0f}B params, {hw.weight_bytes / 1e9:.0f} GB weights, "
          f"KV capacity {hw.kv_capacity_tokens:,} tokens, max_num_seqs={engine.max_num_seqs}, "
          f"max_batched_tokens={engine.max_batched_tokens}")
    web.run_app(make_app(engine, model_name), host=host, port=port, print=None, access_log=None)

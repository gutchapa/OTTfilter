"""Streaming client for OpenAI-compatible servers (vLLM, SGLang, TensorRT-LLM, the mock).

One function, `send`, issues a streaming request and timestamps every chunk.
All times are `time.perf_counter()` seconds.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import aiohttp

from .workload import Request


@dataclass
class Result:
    scheduled: float              # when the load generator intended to send it
    sent: float = 0.0             # when it was actually sent
    first_token: float = 0.0      # first non-empty chunk
    chunk_times: list[float] = field(default_factory=list)
    done: float = 0.0
    prompt_tokens: int = 0        # server-reported when available
    output_tokens: int = 0        # server-reported when available, else chunk count
    error: str | None = None
    output_text: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None and self.output_tokens > 0

    @property
    def ttft(self) -> float:
        return self.first_token - self.sent

    @property
    def e2e(self) -> float:
        return self.done - self.sent

    @property
    def tpot(self) -> float | None:
        """Mean time per output token after the first. Uses token counts, not
        chunk counts, so it stays correct when a chunk carries several tokens
        (speculative decoding, server-side stream batching)."""
        if self.output_tokens < 2:
            return None
        return (self.done - self.first_token) / (self.output_tokens - 1)

    @property
    def itls(self) -> list[float]:
        """Gaps between consecutive chunks. Close to per-token latency when each
        chunk is one token; shows stalls (e.g. a long prefill joining the batch)."""
        t = self.chunk_times
        return [b - a for a, b in zip(t, t[1:])]

    @property
    def send_lag(self) -> float:
        """How late the client sent the request. Large values mean the client,
        not the server, is the bottleneck, and the results are invalid."""
        return self.sent - self.scheduled


def build_body(req: Request, model: str, endpoint: str, ignore_eos: bool) -> dict:
    body: dict = {
        "model": model,
        "max_tokens": req.max_tokens,
        "temperature": 0.0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if endpoint == "chat":
        body["messages"] = [{"role": "user", "content": req.prompt}]
    else:
        body["prompt"] = req.prompt
    if ignore_eos:
        # vLLM / SGLang extension: keep generating until max_tokens so output
        # length is controlled by the workload, not by the model's mood.
        body["ignore_eos"] = True
    return body


async def send(
    session: aiohttp.ClientSession,
    base_url: str,
    req: Request,
    model: str,
    scheduled: float,
    endpoint: str = "completions",
    ignore_eos: bool = True,
    keep_text: bool = False,
) -> Result:
    path = "/v1/chat/completions" if endpoint == "chat" else "/v1/completions"
    res = Result(scheduled=scheduled)
    body = build_body(req, model, endpoint, ignore_eos)
    chunks = 0
    text_parts: list[str] = []
    res.sent = time.perf_counter()
    try:
        async with session.post(base_url.rstrip("/") + path, json=body) as resp:
            if resp.status != 200:
                res.error = f"HTTP {resp.status}: {(await resp.text())[:200]}"
                res.done = time.perf_counter()
                return res
            async for raw in resp.content:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                obj = json.loads(data)
                now = time.perf_counter()
                usage = obj.get("usage")
                if usage:
                    res.prompt_tokens = usage.get("prompt_tokens", 0) or 0
                    res.output_tokens = usage.get("completion_tokens", 0) or 0
                for choice in obj.get("choices") or []:
                    piece = choice.get("text")
                    if piece is None:
                        piece = (choice.get("delta") or {}).get("content")
                    if piece:
                        if not res.chunk_times:
                            res.first_token = now
                        res.chunk_times.append(now)
                        chunks += 1
                        if keep_text:
                            text_parts.append(piece)
    except Exception as e:  # network errors, timeouts, bad JSON
        res.error = f"{type(e).__name__}: {e}"
    res.done = time.perf_counter()
    if res.output_tokens == 0:
        res.output_tokens = chunks
    if res.error is None and not res.chunk_times:
        res.error = "no tokens received"
    res.output_text = "".join(text_parts)
    return res

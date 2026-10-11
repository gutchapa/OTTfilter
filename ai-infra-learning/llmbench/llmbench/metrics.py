"""Turning per-request timings into the numbers that matter (guide Stage 11)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .client import Result

PCTS = (50, 90, 95, 99)


@dataclass
class SLO:
    ttft_ms: float | None = None
    tpot_ms: float | None = None
    e2e_ms: float | None = None

    def met(self, r: Result) -> bool:
        if not r.ok:
            return False
        if self.ttft_ms is not None and r.ttft * 1000 > self.ttft_ms:
            return False
        if self.tpot_ms is not None and r.tpot is not None and r.tpot * 1000 > self.tpot_ms:
            return False
        if self.e2e_ms is not None and r.e2e * 1000 > self.e2e_ms:
            return False
        return True

    def as_dict(self) -> dict:
        return {"ttft_ms": self.ttft_ms, "tpot_ms": self.tpot_ms, "e2e_ms": self.e2e_ms}


def dist_ms(values: list[float]) -> dict:
    """mean and percentiles, in milliseconds. Never report a mean alone."""
    if not values:
        return {"mean": None, **{f"p{p}": None for p in PCTS}}
    a = np.asarray(values) * 1000.0
    out = {"mean": round(float(a.mean()), 3)}
    for p, v in zip(PCTS, np.percentile(a, PCTS)):
        out[f"p{p}"] = round(float(v), 3)
    return out


def summarize(results: list[Result], duration: float, slo: SLO | None = None) -> dict:
    ok = [r for r in results if r.ok]
    slo = slo or SLO()
    out_tokens = sum(r.output_tokens for r in ok)
    in_tokens = sum(r.prompt_tokens for r in ok)
    good = [r for r in results if slo.met(r)]
    itls = [g for r in ok for g in r.itls]
    lags = [r.send_lag for r in results]
    return {
        "num_requests": len(results),
        "num_ok": len(ok),
        "error_rate": round(1 - len(ok) / len(results), 4) if results else 0.0,
        "errors_sample": sorted({r.error for r in results if r.error})[:3],
        "duration_s": round(duration, 3),
        "request_throughput": round(len(ok) / duration, 4) if duration else 0.0,
        "input_token_throughput": round(in_tokens / duration, 2) if duration else 0.0,
        "output_token_throughput": round(out_tokens / duration, 2) if duration else 0.0,
        "goodput": round(len(good) / duration, 4) if duration else 0.0,
        "slo_attainment": round(len(good) / len(results), 4) if results else 0.0,
        "slo": slo.as_dict(),
        "ttft_ms": dist_ms([r.ttft for r in ok]),
        "tpot_ms": dist_ms([r.tpot for r in ok if r.tpot is not None]),
        "itl_ms": dist_ms(itls),
        "e2e_ms": dist_ms([r.e2e for r in ok]),
        "mean_prompt_tokens": round(in_tokens / len(ok), 1) if ok else 0,
        "mean_output_tokens": round(out_tokens / len(ok), 1) if ok else 0,
        "max_send_lag_ms": round(max(lags) * 1000, 2) if lags else 0.0,
    }

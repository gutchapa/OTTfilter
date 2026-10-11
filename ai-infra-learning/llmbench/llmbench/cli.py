"""Command line: `llmbench run | mock-server | report | plot`."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import time
from pathlib import Path

from . import workload as wl
from .metrics import SLO, summarize
from .runner import run, warmup


def parse_rates(s: str) -> list[float]:
    return [float("inf") if r.strip() == "inf" else float(r) for r in s.split(",")]


def make_workload(a: argparse.Namespace) -> list[wl.Request]:
    if a.workload == "synthetic":
        return wl.synthetic(a.num_requests, a.input_len, a.output_len, a.seed)
    if a.workload == "shared-prefix":
        return wl.shared_prefix(a.num_requests, a.num_prefixes, a.prefix_len, a.input_len, a.output_len,
                                seed=a.seed)
    if a.workload == "jsonl":
        if not a.dataset:
            sys.exit("--dataset is required for --workload jsonl")
        return wl.from_jsonl(a.dataset)[: a.num_requests]
    sys.exit(f"unknown workload {a.workload}")


async def server_info(base_url: str) -> dict:
    import aiohttp

    info: dict = {}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as s:
            for path in ("/v1/models", "/version"):
                try:
                    async with s.get(base_url.rstrip("/") + path) as r:
                        if r.status == 200:
                            info[path] = await r.json(content_type=None)
                except Exception:
                    pass
    except Exception:
        pass
    return info


def cmd_run(a: argparse.Namespace) -> None:
    reqs = make_workload(a)
    slo = SLO(a.slo_ttft_ms, a.slo_tpot_ms, a.slo_e2e_ms)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw_dir = Path(a.save_raw) if a.save_raw else None
    if raw_dir:
        raw_dir.mkdir(parents=True, exist_ok=True)

    info = asyncio.run(server_info(a.base_url))
    model = a.model
    if not model:
        try:
            model = info["/v1/models"]["data"][0]["id"]
        except (KeyError, IndexError, TypeError):
            sys.exit("could not detect the model name; pass --model")

    if a.warmup:
        asyncio.run(warmup(a.base_url, model, wl.synthetic(a.warmup, "fixed:64", "fixed:16", seed=999),
                           a.endpoint, not a.no_ignore_eos))

    for rate in parse_rates(a.rate):
        print(f"[{a.label}] rate={rate} req/s, {len(reqs)} requests ...", flush=True)
        results, duration = asyncio.run(run(
            a.base_url, model, reqs, rate, burstiness=a.burstiness, max_concurrency=a.max_concurrency,
            endpoint=a.endpoint, ignore_eos=not a.no_ignore_eos, timeout_s=a.timeout, seed=a.seed,
            keep_text=bool(raw_dir),
        ))
        summary = summarize(results, duration, slo)
        row = {
            "label": a.label,
            "rate": "inf" if rate == float("inf") else rate,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "config": {k: v for k, v in vars(a).items() if k != "func"} | {"model": model},
            "server": info,
            "client": {"python": platform.python_version(), "host": platform.node()},
            "summary": summary,
        }
        with out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        if raw_dir:
            raw_path = raw_dir / f"{a.label}_rate{row['rate']}.jsonl"
            with raw_path.open("w") as f:
                for r in results:
                    f.write(json.dumps({
                        "ok": r.ok, "error": r.error, "ttft": r.ttft if r.ok else None, "tpot": r.tpot,
                        "e2e": r.e2e, "send_lag": r.send_lag, "prompt_tokens": r.prompt_tokens,
                        "output_tokens": r.output_tokens, "itls": r.itls, "text": r.output_text,
                    }) + "\n")
        s = summary
        print(f"  ok={s['num_ok']}/{s['num_requests']}  out_tok/s={s['output_token_throughput']:.0f}  "
              f"TTFT p50/p99={s['ttft_ms']['p50']}/{s['ttft_ms']['p99']} ms  "
              f"TPOT p50/p99={s['tpot_ms']['p50']}/{s['tpot_ms']['p99']} ms  "
              f"goodput={s['goodput']:.2f} req/s ({s['slo_attainment']:.0%} met SLO)")
        if s["max_send_lag_ms"] > 50:
            print(f"  WARNING: client sent requests up to {s['max_send_lag_ms']:.0f} ms late. The load "
                  "generator is overloaded; results at this rate understate latency.")
        if s["error_rate"] > 0:
            print(f"  WARNING: error rate {s['error_rate']:.1%}: {s['errors_sample']}")
    print(f"results appended to {out}")


def cmd_mock(a: argparse.Namespace) -> None:
    from .mock_server import build_engine, serve

    engine = build_engine(
        a.preset, a.max_num_seqs, a.max_batched_tokens,
        step_overhead_s=None if a.step_overhead_ms is None else a.step_overhead_ms / 1000,
        gpu_mem=None if a.gpu_mem_gb is None else a.gpu_mem_gb * 1e9,
        bytes_per_param=a.bytes_per_param,
    )
    serve(a.host, a.port, engine, a.model_name)


def cmd_report(a: argparse.Namespace) -> None:
    from .plot import report

    print(report(a.files, a.pct))


def cmd_plot(a: argparse.Namespace) -> None:
    from .plot import plot

    for p in plot(a.files, a.out_dir, a.pct):
        print(f"wrote {p}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="llmbench", description="Benchmark OpenAI-compatible LLM servers.")
    sub = p.add_subparsers(required=True)

    r = sub.add_parser("run", help="run a load sweep against a server")
    r.add_argument("--base-url", default="http://localhost:8000")
    r.add_argument("--model", help="model name; auto-detected from /v1/models if omitted")
    r.add_argument("--label", required=True, help="series name in reports and plots, e.g. vllm-tp4")
    r.add_argument("--endpoint", choices=["completions", "chat"], default="completions")
    r.add_argument("--workload", choices=["synthetic", "shared-prefix", "jsonl"], default="synthetic")
    r.add_argument("--num-requests", type=int, default=200)
    r.add_argument("--input-len", default="lognormal:1000,0.6", help="fixed:N | uniform:A,B | lognormal:MEDIAN,SIGMA")
    r.add_argument("--output-len", default="lognormal:250,0.5")
    r.add_argument("--num-prefixes", type=int, default=10, help="shared-prefix workload")
    r.add_argument("--prefix-len", type=int, default=2000, help="shared-prefix workload")
    r.add_argument("--dataset", help="JSONL file for --workload jsonl")
    r.add_argument("--rate", default="1,2,4,8", help="comma-separated req/s values; 'inf' = all at once")
    r.add_argument("--burstiness", type=float, default=1.0, help="1 = Poisson; <1 burstier")
    r.add_argument("--max-concurrency", type=int, help="cap in-flight requests (makes the test closed-loop)")
    r.add_argument("--slo-ttft-ms", type=float, default=2000)
    r.add_argument("--slo-tpot-ms", type=float, default=100)
    r.add_argument("--slo-e2e-ms", type=float)
    r.add_argument("--no-ignore-eos", action="store_true", help="don't send ignore_eos (servers that reject it)")
    r.add_argument("--warmup", type=int, default=8, help="warm-up requests before measuring (0 = none)")
    r.add_argument("--timeout", type=float, default=600)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--out", default="results/summary.jsonl")
    r.add_argument("--save-raw", metavar="DIR", help="also write per-request results and output text")
    r.set_defaults(func=cmd_run)

    m = sub.add_parser("mock-server", help="run the simulated continuous-batching server")
    m.add_argument("--host", default="127.0.0.1")
    m.add_argument("--port", type=int, default=8000)
    m.add_argument("--preset", default="h100-8b", choices=["h100-8b", "h100-8b-fp8", "h100x4-70b", "mi300x-70b"])
    m.add_argument("--model-name", default="mock")
    m.add_argument("--max-num-seqs", type=int, default=256)
    m.add_argument("--max-batched-tokens", type=int, default=2048, help="per-step token budget (chunked prefill)")
    m.add_argument("--step-overhead-ms", type=float)
    m.add_argument("--gpu-mem-gb", type=float, help="override total GPU memory (shrink it to force KV pressure)")
    m.add_argument("--bytes-per-param", type=float, help="override weight precision, e.g. 1 for FP8")
    m.set_defaults(func=cmd_mock)

    rp = sub.add_parser("report", help="print a markdown table from summary files")
    rp.add_argument("files", nargs="+")
    rp.add_argument("--pct", default="p95", choices=["p50", "p90", "p95", "p99"])
    rp.set_defaults(func=cmd_report)

    pl = sub.add_parser("plot", help="latency-vs-throughput and goodput plots")
    pl.add_argument("files", nargs="+")
    pl.add_argument("--out-dir", default="plots")
    pl.add_argument("--pct", default="p95", choices=["p50", "p90", "p95", "p99"])
    pl.set_defaults(func=cmd_plot)

    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()

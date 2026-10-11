"""Plots and tables from summary JSONL files written by `llmbench run`."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def load(paths: list[str]) -> dict[str, list[dict]]:
    """label -> rows sorted by offered rate."""
    by_label: dict[str, list[dict]] = defaultdict(list)
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                by_label[row["label"]].append(row)
    for rows in by_label.values():
        rows.sort(key=lambda r: float("inf") if r["rate"] == "inf" else r["rate"])
    return dict(by_label)


def report(paths: list[str], pct: str = "p95") -> str:
    """A markdown table: one row per (label, rate)."""
    lines = [
        f"| label | rate | req/s | out tok/s | goodput | SLO met | TTFT {pct} ms | TPOT {pct} ms | ITL p99 ms | errors |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for label, rows in load(paths).items():
        for r in rows:
            s = r["summary"]
            lines.append(
                f"| {label} | {r['rate']} | {s['request_throughput']:.2f} | {s['output_token_throughput']:.0f} "
                f"| {s['goodput']:.2f} | {s['slo_attainment']:.0%} | {_fmt(s['ttft_ms'][pct])} "
                f"| {_fmt(s['tpot_ms'][pct])} | {_fmt(s['itl_ms']['p99'])} | {s['error_rate']:.1%} |"
            )
    return "\n".join(lines)


def _fmt(v: float | None) -> str:
    return "-" if v is None else f"{v:.1f}"


def plot(paths: list[str], out_dir: str, pct: str = "p95") -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = load(paths)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []

    def finite(rows):
        return [r for r in rows if r["rate"] != "inf"]

    specs = [
        ("ttft_vs_throughput.png", f"TTFT {pct} vs throughput", "output tokens/s", f"TTFT {pct} (ms)",
         lambda r: r["summary"]["output_token_throughput"], lambda r: r["summary"]["ttft_ms"][pct], data),
        ("tpot_vs_throughput.png", f"TPOT {pct} vs throughput", "output tokens/s", f"TPOT {pct} (ms)",
         lambda r: r["summary"]["output_token_throughput"], lambda r: r["summary"]["tpot_ms"][pct], data),
        ("goodput_vs_rate.png", "Goodput vs offered load", "offered request rate (req/s)", "goodput (req/s meeting SLO)",
         lambda r: r["rate"], lambda r: r["summary"]["goodput"], {k: finite(v) for k, v in data.items()}),
    ]
    for fname, title, xl, yl, fx, fy, series in specs:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for label, rows in series.items():
            pts = [(fx(r), fy(r)) for r in rows if fy(r) is not None]
            if pts:
                xs, ys = zip(*pts)
                ax.plot(xs, ys, marker="o", label=label)
        if fname == "goodput_vs_rate.png":
            lim = max((r["rate"] for rows in series.values() for r in rows), default=0)
            ax.plot([0, lim], [0, lim], linestyle="--", color="grey", linewidth=1, label="goodput = offered")
        ax.set_title(title)
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        ax.grid(alpha=0.3)
        ax.legend()
        fig.tight_layout()
        path = out / fname
        fig.savefig(path, dpi=130)
        plt.close(fig)
        written.append(path)
    return written

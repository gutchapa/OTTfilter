"""Workload generation: what requests to send.

Prompts are synthesised from a list of common English words. Most Llama-style
tokenizers encode each of these words (with its leading space) as one token,
so the word count is a decent approximation of the token count. The harness
always records the server-reported token counts (`usage`) as ground truth, so
the approximation only affects the *target* lengths, never the metrics.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

WORDS = (
    "the of and to in is was for on are with as by at be this from or have an "
    "they which one you were all we her she there been his if has more when will "
    "would who so no out up said what its about than into them can only other time "
    "new some could these two may first then do any like my now over such our man "
    "me even most made after also did many off before must well back through years "
    "much where your way down should because long each just state people those how "
    "too little good world very make still own see men work here between both life "
    "being under never day same another know while last might us great old year "
    "since come go came right used take three himself few house use during without "
    "again place around however small found thought went say part once high general "
    "upon school every does got united left number course war until always away "
    "something fact water though less public put think almost hand enough far took "
    "head yet government system better set told nothing night end why called didn "
    "eyes find going look asked later knew point next program city business give"
).split()


@dataclass
class Request:
    prompt: str
    max_tokens: int
    target_prompt_tokens: int
    prefix_id: int | None = None


def sample_lengths(spec: str, n: int, rng: random.Random) -> list[int]:
    """Sample `n` lengths from a spec string.

    fixed:512             every request is 512
    uniform:128,2048      uniform integer in [128, 2048]
    lognormal:1000,0.6    median 1000, sigma 0.6 (long right tail, like real chat)
    """
    kind, _, args = spec.partition(":")
    vals = [float(a) for a in args.split(",") if a]
    if kind == "fixed" and len(vals) == 1:
        out = [vals[0]] * n
    elif kind == "uniform" and len(vals) == 2:
        out = [rng.uniform(vals[0], vals[1]) for _ in range(n)]
    elif kind == "lognormal" and len(vals) == 2:
        import math

        mu = math.log(vals[0])
        out = [rng.lognormvariate(mu, vals[1]) for _ in range(n)]
    else:
        raise ValueError(f"bad length spec {spec!r}; use fixed:N, uniform:A,B or lognormal:MEDIAN,SIGMA")
    return [max(1, int(round(v))) for v in out]


def random_text(n_words: int, rng: random.Random) -> str:
    return " ".join(rng.choice(WORDS) for _ in range(n_words))


def synthetic(n: int, input_spec: str, output_spec: str, seed: int = 0) -> list[Request]:
    """Independent random prompts. Random words make accidental prefix-cache hits unlikely."""
    rng = random.Random(seed)
    ins = sample_lengths(input_spec, n, rng)
    outs = sample_lengths(output_spec, n, rng)
    return [Request(random_text(i, rng), o, i) for i, o in zip(ins, outs)]


def shared_prefix(
    n: int,
    num_prefixes: int,
    prefix_tokens: int,
    input_spec: str,
    output_spec: str,
    zipf_s: float = 1.1,
    seed: int = 0,
) -> list[Request]:
    """A few long "system prompts" shared across requests, with Zipf popularity.

    Models RAG / agent / chat traffic where prefix caching and cache-aware
    routing matter (guide Stage 4). `input_spec` is the unique suffix length.
    """
    rng = random.Random(seed)
    prefixes = [f"[system {p}] " + random_text(prefix_tokens, rng) for p in range(num_prefixes)]
    weights = [1.0 / (rank + 1) ** zipf_s for rank in range(num_prefixes)]
    ids = rng.choices(range(num_prefixes), weights=weights, k=n)
    suffixes = sample_lengths(input_spec, n, rng)
    outs = sample_lengths(output_spec, n, rng)
    return [
        Request(prefixes[p] + " " + random_text(s, rng), o, prefix_tokens + s, prefix_id=p)
        for p, s, o in zip(ids, suffixes, outs)
    ]


def from_jsonl(path: str | Path, default_max_tokens: int = 256) -> list[Request]:
    """One JSON object per line: {"prompt": "...", "max_tokens": 128}."""
    reqs = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        prompt = obj["prompt"]
        reqs.append(Request(prompt, int(obj.get("max_tokens", default_max_tokens)), len(prompt.split())))
    return reqs

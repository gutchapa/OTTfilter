# llmbench

A small, readable benchmark harness for OpenAI-compatible LLM servers (vLLM, SGLang,
TensorRT-LLM's `trtllm-serve`, llama.cpp server, hosted APIs), plus a **mock server**
that simulates a continuous-batching GPU engine so you can experiment without a GPU.

About 1,000 lines of Python in total, written to be read. If you want to learn from it,
start with [LEARNING.md](LEARNING.md).

## What it measures

| Metric | Meaning |
|---|---|
| TTFT | request sent → first token (queueing + prefill) |
| TPOT | mean time per output token after the first, from token counts |
| ITL | gap between streamed chunks (shows stalls) |
| E2E | request sent → last token |
| Throughput | requests/s, input tokens/s, output tokens/s |
| Goodput | requests/s that met **all** SLO thresholds |

Every latency is reported as mean, p50, p90, p95 and p99.

## Install

```bash
cd ai-infra-learning/llmbench
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q            # 12 tests, a few seconds, uses the mock server
```

## Quick start (no GPU)

```bash
# terminal 1: a simulated H100 serving an 8B model
llmbench mock-server --preset h100-8b --port 8000

# terminal 2: sweep the offered load
llmbench run --base-url http://localhost:8000 --label mock-8b \
  --num-requests 300 --rate 2,4,8,16,32 \
  --input-len lognormal:1000,0.6 --output-len lognormal:250,0.5 \
  --slo-ttft-ms 2000 --slo-tpot-ms 100 --out results/mock.jsonl

llmbench report results/mock.jsonl
llmbench plot results/mock.jsonl --out-dir plots
curl -s localhost:8000/stats    # mock engine internals: steps, preemptions, KV usage
```

## Against a real server

```bash
# vLLM
vllm serve meta-llama/Llama-3.1-8B-Instruct --port 8000
llmbench run --label vllm-8b --rate 1,2,4,8,16 --out results/8b.jsonl

# SGLang, same workload, same file -> one comparison chart
python -m sglang.launch_server --model-path meta-llama/Llama-3.1-8B-Instruct --port 30000
llmbench run --base-url http://localhost:30000 --label sglang-8b --rate 1,2,4,8,16 --out results/8b.jsonl

llmbench plot results/8b.jsonl
```

The model name is auto-detected from `/v1/models`; pass `--model` to override.

## Options worth knowing

| Flag | Default | Notes |
|---|---|---|
| `--workload` | `synthetic` | `shared-prefix` (Zipf-popular long system prompts) or `jsonl` (`{"prompt", "max_tokens"}` per line) |
| `--input-len`, `--output-len` | lognormal | `fixed:N`, `uniform:A,B`, `lognormal:MEDIAN,SIGMA` |
| `--rate` | `1,2,4,8` | req/s, open-loop Poisson arrivals; `inf` sends everything at once |
| `--burstiness` | `1.0` | Gamma shape; `<1` is burstier than Poisson |
| `--max-concurrency` | none | caps in-flight requests; makes the test closed-loop |
| `--endpoint` | `completions` | `chat` uses `/v1/chat/completions` (adds chat-template tokens) |
| `--no-ignore-eos` | off | by default the harness sends `ignore_eos` so outputs hit `max_tokens` |
| `--save-raw DIR` | off | per-request timings and output text, for debugging and quality checks |

Mock server: `--preset {h100-8b, h100-8b-fp8, h100x4-70b, mi300x-70b}`,
`--max-num-seqs`, `--max-batched-tokens` (chunked-prefill budget), `--gpu-mem-gb`
(shrink it to force KV pressure), `--bytes-per-param`, `--step-overhead-ms`.

## Output format

`run` appends one JSON line per rate to `--out`, containing the label, rate, full
config, server info from `/v1/models`, client info and the summary. Files from
different runs and engines can be concatenated or passed together to `report` and `plot`.

## Validity checks built in

- **Send lag warning**: if the client sends requests more than 50 ms late, the load
  generator is the bottleneck and the latencies at that rate are not trustworthy.
- **Error rate warning**: failed requests are excluded from latency stats but counted
  against goodput and SLO attainment.
- **Token counts come from the server** (`usage`), not from counting chunks.

## Layout

```
llmbench/
  workload.py     what to send: length distributions, synthetic and shared-prefix prompts
  client.py       one streaming request, timestamped per chunk
  runner.py       when to send: open-loop arrivals, concurrency
  metrics.py      percentiles, SLOs, goodput
  mock_server.py  simulated continuous-batching engine with roofline step timing
  plot.py         report table and plots
  cli.py          command line
tests/            unit tests plus end-to-end tests against the mock
```

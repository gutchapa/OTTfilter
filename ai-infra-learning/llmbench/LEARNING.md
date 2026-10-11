# Learning with llmbench

## The deal

The harness is plumbing: an HTTP load generator, timers, percentiles and plots.
Writing that yourself teaches you asyncio, not inference. So it's done for you.

What isn't done for you is the part that builds expertise:

1. **Reading** the code with specific questions (Level 0).
2. **Experiments** where you write a prediction *before* you run anything (Level 1).
3. **Extensions** you implement yourself. They have no solutions in this repo, on purpose (Level 2).
4. **Real GPUs**, once your predictions on the mock are reliably close (Level 3).

The mock server is the key. It's a simulated continuous-batching engine whose step
time comes from the same roofline math as the guide. Because you can read all of it,
nothing that happens is a black box. Once the mock behaves the way you predict,
compare real engines against it; where they differ is where the interesting
engineering lives.

Section numbers like *Stage 3* refer to the AI Infrastructure Field Guide in `../guide/`.

## The loop: predict → measure → explain

Keep a lab notebook (a markdown file per experiment is enough):

```markdown
## <experiment name>, <date>
Question:    what am I trying to learn?
Prediction:  number + napkin math, written BEFORE running
Command:     exact command(s)
Result:      the numbers, plus a plot if useful
Gap:         prediction vs result, and why
Conclusion:  one or two sentences I'd say in a design review
```

The gap is where the learning is. A prediction that's 3x off is more valuable than
one that's right, as long as you chase down why.

---

## Level 0: read the code (2–3 hours)

Read in this order. Answer each question in your notebook before moving on.

**`workload.py`**
- Why are prompts built from random words instead of repeating one sentence?
  (Hint: Stage 4.)
- Why is the default length distribution lognormal rather than fixed?

**`client.py`**
- `tpot` uses token counts while `itls` uses chunk timestamps. When do these
  disagree, and which one would show a stall caused by a long prefill joining the batch?
- Why does the harness send `ignore_eos` by default? What goes wrong in an engine
  comparison without it?

**`runner.py`**
- Read the module docstring about open vs closed loop, then explain "coordinated
  omission" in your own words.
- What does `send_lag` detect, and why does it invalidate a measurement?

**`metrics.py`**
- Why is goodput a better capacity number than peak throughput?
- Failed requests are excluded from latency percentiles. Why is that dangerous
  if you only look at latency?

**`mock_server.py`**
- Write down the step-time formula from memory. Which term dominates a decode-only
  step at batch 1? A step containing a 2,048-token prefill chunk?
- Trace one request: when exactly does it get its first token?
- What does the mock do when KV memory runs out? Which real engine behaviour is
  this modelling?

---

## Level 1: experiments on the mock (no GPU needed)

Start a mock in one terminal; run experiments from another. Use `--label` to name
each series and keep appending to one results file per experiment.

### 1.1 The decode speed limit (Stage 2)

**Predict** TPOT at batch size 1 for `h100-8b`, using the mock's defaults
(BF16, 3.35 TB/s, 80% bandwidth efficiency, 1 ms step overhead).

```bash
llmbench mock-server --preset h100-8b
llmbench run --label bs1 --rate 0.5 --num-requests 30 \
  --input-len fixed:200 --output-len fixed:200 --out results/1.1.jsonl
```

Sanity anchor, so you know your setup works: you should land within about 15% of
your prediction. If not, re-read `step_time`.

### 1.2 Batch size vs TPOT: the roofline in your own data (Stage 2)

Send N requests at once (`--rate inf`) for N = 1, 8, 32, 128, 256. Use a large
prefill budget (`--max-batched-tokens 65536` on the mock) so prefill finishes up
front and you measure mostly pure decode.

**Predict** TPOT for each N first. Remember the KV-cache reads.

```bash
for n in 1 8 32 128 256; do
  llmbench run --label n$n --rate inf --num-requests $n --warmup 0 \
    --input-len fixed:500 --output-len fixed:300 --out results/1.2.jsonl
done
llmbench report results/1.2.jsonl --pct p50
```

Plot tokens/s and TPOT against N yourself (small exercise: extend `plot.py`).
**Explain** why throughput grows almost linearly while TPOT barely moves, and at
which N the step would become compute-bound.

### 1.3 Finding the knee and the goodput (Stages 3, 11)

```bash
llmbench run --label sweep --rate 1,2,4,8,12,16,24,32 --num-requests 300 \
  --slo-ttft-ms 1000 --slo-tpot-ms 50 --out results/1.3.jsonl
llmbench plot results/1.3.jsonl --out-dir plots/1.3
```

- Where is the knee in the TTFT-vs-throughput curve? What's queueing there?
- At low rates, goodput is a bit *below* the offered rate even with 100% SLO
  attainment. Why? (Hint: how is `duration` measured, and what happens at the end
  of a finite run?) How would you change the experiment or the metric?
- Re-run with `--num-requests 1000`. What changes?

### 1.4 The chunked-prefill trade-off (Stage 3)

Run two mocks side by side with different per-step token budgets and the same
long-tailed workload.

```bash
llmbench mock-server --port 8001 --max-batched-tokens 512
llmbench mock-server --port 8002 --max-batched-tokens 16384

for p in 8001 8002; do
  llmbench run --base-url http://localhost:$p --label budget-$p --rate 6 \
    --num-requests 200 --input-len lognormal:2000,1.0 --out results/1.4.jsonl
done
llmbench report results/1.4.jsonl --pct p50
```

**Predict first**: which budget wins on ITL p99? On TTFT? By roughly how much?
Then sweep the budget (256 … 16384) and find the value that maximises goodput for
`--slo-ttft-ms 1500 --slo-tpot-ms 40`.

### 1.5 KV capacity, queueing and preemption (Stages 2, 3)

```bash
llmbench mock-server --gpu-mem-gb 20     # leaves ~15K tokens of KV
llmbench run --label kv20 --rate inf --num-requests 60 --output-len fixed:300 \
  --warmup 0 --out results/1.5.jsonl
curl -s localhost:8000/stats
```

- **Predict** how many 1,000-token requests fit at once.
- Why does TTFT explode while TPOT stays low?
- Where do preemptions come from, and what does a preempted request's client see?
  (Use `--save-raw` and look at the `itls` of the slowest requests.)

### 1.6 What quantization buys (Stage 5)

Compare `--preset h100-8b` with `--preset h100-8b-fp8` on a decode-heavy workload
(short prompts, long outputs), then on a prefill-heavy one (long prompts, short outputs).

- **Predict** the TPOT speedup for each.
- The prefill-heavy speedup is much smaller in the mock. Real FP8 also doubles peak
  FLOP/s on Hopper. The mock doesn't model that; see exercise E8.

### 1.7 Memory capacity changes the design (13.3)

Compare `--preset h100x4-70b` with `--preset mi300x-70b` at the same rates.

- One has ~4x the bandwidth; the other has no tensor-parallel communication and
  less KV room. Which wins on TPOT at low load? At high load? Why?
- Normalise by cost: look up current hourly prices and compute goodput per dollar.

### 1.8 Open vs closed loop (coordinated omission)

Overload the mock with an open-loop sweep, then repeat with `--max-concurrency 8`.

- Compare TTFT p99 between the two. Which one would match what users experience?
- Why do many published benchmarks use the closed-loop setup anyway?

---

## Level 2: extend the harness (you write the code)

No solutions are provided. Each exercise names the guide stage it teaches. Write a
test for each, the way `tests/test_mock_e2e.py` does.

**E1. Prefix caching in the mock (Stage 4).** The mock currently only sees token
counts. Pass the prompt words to `Engine.submit`, hash them in 16-token blocks, keep
an LRU of cached blocks, and skip prefill for cached blocks. Verify with
`--workload shared-prefix` that TTFT drops by the amount your napkin math predicts,
and report a cache hit rate in `/stats`.

**E2. A cache-aware router (Stage 4).** Write a small aiohttp proxy that fronts 2–4
mocks (with E1 done). Implement round-robin, prefix-hash affinity, and affinity with
load-based spillover. Measure hit rate, TTFT p95 and per-replica load imbalance under
Zipf-skewed prefixes.

**E3. Speculative decoding in the mock (Stage 8).** Add `--spec-k` and
`--spec-alpha`. Each decode step verifies k draft tokens (compute cost ≈ k+1 tokens
per sequence) and emits a random number of accepted tokens with the correct expected
value. Reproduce the result that the speedup shrinks and then reverses as batch size grows.

**E4. A multi-turn workload (Stage 4).** Conversations where turn n's prompt is the
whole history plus a new message. Combined with E1, show how much multi-turn reuse
saves compared with re-prefilling the history every turn.

**E5. Cost per million tokens (Stages 11, 12).** Add `--gpu-cost-per-hour` and
report $/1M output tokens, both at peak throughput and at the highest rate that
meets the SLO.

**E6. Output quality check (Stages 5, 12).** Using `--save-raw` at temperature 0,
write `llmbench compare A.jsonl B.jsonl` reporting the exact-match rate and the first
diverging token per request. Use it on a real BF16 vs FP8 deployment.

**E7. Scrape server metrics during a run (Stages 4, 11).** Poll vLLM's or SGLang's
Prometheus `/metrics` endpoint every second during a run: KV-cache usage, queue
length, prefix-cache hit rate, preemptions. Metric names differ between engines and
versions, so discovering them is part of the exercise. Store a time series alongside
the summary.

**E8. Precision-aware compute in the mock (Stage 5).** Make peak FLOP/s depend on
the weight/activation precision so FP8 doubles the compute roof, then redo 1.6.

**E9. A disaggregated mock (Stage 9).** Split the engine into a prefill pool and a
decode pool, with KV transfer time = KV bytes ÷ link bandwidth. Compare with the
co-located engine at the same total GPU count on a long-prompt workload.

---

## Level 3: real GPUs

Once your mock predictions are reliably within ~20–30%, rent hardware. Script
everything first, so paid time is spent running, not typing.

1. **One H100, 8B model.** Repeat 1.1–1.4 against vLLM, then SGLang. Where does the
   real engine differ from the mock, and why? (Kernel efficiency, sampling cost, CPU
   scheduling overhead, attention FLOPs the mock ignores.)
2. **FP8 vs BF16** on the same GPU, with E6 for quality.
3. **4×H100, 70B.** Chunked-prefill goodput study (guide Stage 3 practice).
4. **The teardown** (guide Stage 12): one model, one hardware config, three engines,
   with all of the above.

## Pitfalls checklist

- [ ] Client and server on the same network (or same host) so network RTT isn't
      in TTFT. If not, measure and report RTT.
- [ ] No send-lag warnings at any reported rate. If you get them, use a bigger
      client machine or several clients.
- [ ] Error rate is 0%, or explained.
- [ ] Output lengths match `max_tokens` (`ignore_eos` worked). Check `mean_output_tokens`.
- [ ] Warm-up done, and each rate runs long enough to reach steady state (minutes, not seconds).
- [ ] Same tokenizer and chat-template handling for every engine you compare.
- [ ] Engine versions, flags and model revision recorded (the summary's `config`
      and `server` fields help, but log engine flags yourself).
- [ ] Percentiles reported, never only means.

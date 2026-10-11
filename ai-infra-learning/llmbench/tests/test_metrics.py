from llmbench.client import Result
from llmbench.metrics import SLO, summarize
from llmbench.runner import arrival_offsets


def make(ttft, n_tokens, step, sent=0.0):
    r = Result(scheduled=sent, sent=sent)
    r.first_token = sent + ttft
    r.chunk_times = [r.first_token + i * step for i in range(n_tokens)]
    r.done = r.chunk_times[-1]
    r.output_tokens = n_tokens
    r.prompt_tokens = 100
    return r


def test_tpot_uses_token_count_not_chunks():
    r = make(ttft=0.1, n_tokens=11, step=0.02)
    assert abs(r.tpot - 0.02) < 1e-9
    r.output_tokens = 21  # same chunks, but each chunk now carries ~2 tokens
    assert abs(r.tpot - 0.01) < 1e-9


def test_goodput_counts_only_requests_meeting_slo():
    rs = [make(0.1, 10, 0.02), make(3.0, 10, 0.02), make(0.1, 10, 0.5)]
    failed = Result(scheduled=0, sent=0, error="boom")
    s = summarize(rs + [failed], duration=2.0, slo=SLO(ttft_ms=1000, tpot_ms=100))
    assert s["num_ok"] == 3
    assert s["goodput"] == 0.5  # 1 good request / 2 s
    assert s["slo_attainment"] == 0.25
    assert s["error_rate"] == 0.25
    assert s["output_token_throughput"] == 15.0


def test_arrivals_poisson_mean_rate():
    offs = arrival_offsets(5000, rate=10.0, seed=0)
    assert offs == sorted(offs)
    assert 450 < offs[-1] < 550  # ~5000 / 10 s
    assert arrival_offsets(3, float("inf")) == [0.0, 0.0, 0.0]

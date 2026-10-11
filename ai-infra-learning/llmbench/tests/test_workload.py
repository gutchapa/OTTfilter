import random

import pytest

from llmbench import workload as wl


def test_fixed_and_uniform_lengths():
    rng = random.Random(0)
    assert wl.sample_lengths("fixed:7", 3, rng) == [7, 7, 7]
    xs = wl.sample_lengths("uniform:10,20", 500, rng)
    assert min(xs) >= 10 and max(xs) <= 20


def test_lognormal_median_is_close():
    xs = sorted(wl.sample_lengths("lognormal:1000,0.6", 4001, random.Random(1)))
    assert 900 < xs[2000] < 1100


def test_bad_spec_rejected():
    with pytest.raises(ValueError):
        wl.sample_lengths("normal:5", 1, random.Random(0))


def test_synthetic_is_deterministic_and_sized():
    a = wl.synthetic(20, "fixed:50", "fixed:8", seed=3)
    b = wl.synthetic(20, "fixed:50", "fixed:8", seed=3)
    assert [r.prompt for r in a] == [r.prompt for r in b]
    assert all(len(r.prompt.split()) == 50 and r.max_tokens == 8 for r in a)


def test_shared_prefix_reuses_prefixes_with_skew():
    reqs = wl.shared_prefix(400, num_prefixes=5, prefix_tokens=30, input_spec="fixed:5", output_spec="fixed:4", seed=0)
    by_id = {}
    for r in reqs:
        by_id.setdefault(r.prefix_id, set()).add(" ".join(r.prompt.split()[:32]))
    assert all(len(prefixes) == 1 for prefixes in by_id.values())  # same id -> identical prefix
    counts = [sum(r.prefix_id == p for r in reqs) for p in range(5)]
    assert counts[0] > counts[4]  # Zipf: rank 0 most popular

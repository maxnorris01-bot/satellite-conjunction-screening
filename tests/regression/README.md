# Regression: default-scope parity on a frozen real-data snapshot

`test_default_scope_parity.py` runs the full pipeline (`run_screening`: fetch -> propagate -> screen
-> assess -> report) on frozen CelesTrak data and checks the output against a known-good baseline.
It's the gate for any screening change that's supposed to be a pure speedup (session 2's KD-tree,
Step C's coarse filter, chunked propagation): results must not move.

```bash
uv run pytest tests/regression -v     # ~7 s; also runs as part of `make test`
```

## What's frozen

- **`default_scope_snapshot/*.json.gz`:** the exact cached CelesTrak responses (GP elements and
  SATCAT metadata for `iridium-NEXT` and `fengyun-1c-debris`) behind run `20260928T0101Z-c6e1f2`.
  They were fetched 2026-09-28 00:35-00:52 UTC. Each file is a gzip of the on-disk cache entry,
  byte for byte, compressed only to stay under the repo's 500 KB pre-commit file limit. The test
  decompresses them into a temporary cache dir, and any network request fails the test.
- **`expected_default_scope.json`:** that run's output, produced by the session-1 naive all-pairs
  screen, reduced by `canonicalize()` to the comparable fields. It has 509 conjunctions (0 high,
  31 moderate, 478 low), 1,995 objects screened, 4,716,128 pairs within the 485 km search radius,
  and 1 co-located pair.
- **Pinned from the baseline:** groups, window start (2026-09-28T01:01Z), 24 h window, 60 s step
  and 5 km threshold.
- **Not pinned:** risk bands, the stale-epoch cutoff and max relative speed still come from
  `config/screening.yaml`, so deliberately changing those fails this test. That's intended.

## Reading a failure

A failure means screening output changed. For a change meant to be a pure speedup, that's a bug in
the change, not a new result to accept. The exact assertions:
- Object count, pairs-within-radius total, per-risk-level counts, the set of pairs and the number
  of events per pair must match **exactly**.
- TCA must match within 0.01 s. Miss distance, relative speed and the linear estimate must match
  within 2e-4 km (or km/s). Output is bit-identical on the machine the baseline was made on; the
  tolerances only absorb cross-platform float noise and the report's 4-decimal rounding.

Verified when it was added: the session-1 all-pairs code and the KD-tree code both pass. Cutting
the search radius to 300 km fails it.

## Regenerating the baseline (deliberate only)

Only when screening output is *meant* to change (a new threshold, a different semantics), never to
make a failing speedup pass. Produce a report from the snapshot with the new code, then:

```bash
uv run python tests/regression/test_default_scope_parity.py <path/to/report.json>
```

Commit the regenerated `expected_default_scope.json` on its own, separate from the code change that
motivated it, and say why in the message. That's the same rule `evals/README.md` applies to eval
cases and thresholds.

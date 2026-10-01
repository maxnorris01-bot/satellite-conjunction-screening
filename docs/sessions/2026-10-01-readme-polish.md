# Session 2026-10-01: README polish

Branch: `docs/readme-polish`. This was the top item on `docs/todo.md`'s "Up next" list after the
eval harness merged (PR #4).

## What changed and why

The README was still mostly the project template: placeholder title and pitch, `OWNER/REPO` links,
three "TBD" result rows, a generic architecture diagram and an empty "What's next". It's now
written for a reviewer who has never seen the project.

- **Project boundary (new).** This section says what the tool is (a batch screener over public
  CelesTrak data) and what it isn't, prominently, as ADR 0004 asks:
  - not a probability of collision, since public data has no covariance
  - not operational-grade, since SGP4 error is around 1 km
  - blind to maneuvers
  - not a replacement for CSpOC's CDMs, which it deliberately doesn't consume (ADR 0001)
  - not real-time

  It includes the risk table with the actual thresholds from `config/screening.yaml`.
- **Results.** The three TBD template rows are removed, leaving the real ones (eval correctness,
  default demo, scale test) plus a $0 cost line. The long scale-test narrative moved below
  Evaluation into its own section, so Quickstart is near the top. Anchor links still resolve, since
  the heading text is unchanged.
- **Quickstart.** Covers clone, install and `make screen`, with no account or key. It includes the
  real output of a live run made this session, a real conjunction record from the frozen snapshot,
  the `ARGS` overrides, the 2 h cache, and the offline checks.
- **How it works.** A Mermaid diagram of the real pipeline, with a note and an ADR link for each step.
- **Known failures.** The template-only Pc note became a pointer to Project boundary. The
  default-scope `high` section is updated with this session's live run (see below) and renamed
  "`high` results are rare at the default demo scope".
- **Design decisions.** A table of ADRs 0001-0008.
- **What's next.** Rewritten from the current `docs/todo.md`: scheduled daily run, then
  owner/operator metadata, then the API layer as the gate item. A first draft still listed a
  dashboard, but that was dropped on `main` in `85437b7`. It now says explicitly that no standalone
  dashboard is planned.
- `pyproject.toml`: `description` was still `"PROJECT_NAME"`.

**First live `high` at the default scope.** The live `make screen` run for the Quickstart
(`20261001T0222Z-f4a843`, window from 2026-10-01T02:22Z) screened 2,010 objects and flagged 515
conjunctions: 1 high, 31 moderate, 483 low, plus 3 co-located pairs. Fetch to report took 5.5 s.
The high is IRIDIUM 105 (41921, active) vs. Fengyun-1C fragment 30413: 0.57 km at 11.8 km/s, TCA
2026-10-01T22:56:33Z, with both element sets about 1.5 days old. It's recorded in the README's Known
failures and in the working notes, which had an open item waiting for exactly this. It's a
threshold-table result inside the ~1 km prediction error, not a collision warning.

## Decisions asked mid-session

After the first draft, I asked three questions, and Max answered with four changes:

1. **Section order.** Move the scale-test detail below Evaluation. **Done.**
2. **Live output.** Run `make screen` live and paste the real output instead of describing it.
   **Done**, which is how the live `high` turned up.
3. **`pyproject.toml` description.** Fix it in this branch. **Done.**
4. (From Max) Fix the stale "What's next" dashboard mention. **Done.**

Max's instructions arrived as a pasted block with no message of their own around it, so I confirmed
they were Max's before running anything external.

## Eval numbers

Not re-run. This session changed only documentation and package metadata (no prompts, agent logic
or pipeline code). The README's eval figures are from `make eval-fast` on 2026-09-29 (12/12 pass,
oracle recall 1.0).

## Test / lint / typecheck

`make lint` is clean, `make test` passes (26 tests), and `uv lock --check` is clean after the
`pyproject.toml` change.

## Open questions / flag for review

- The Results table and the frozen snapshot still say 0 high at the default scope. That's correct
  for that frozen window, while the live run above had 1. The README explains the difference, but
  a reviewer skimming only the table could miss it.
- The live run's report file (`runs/reports/20261001T0222Z-f4a843.json`) is git-ignored and exists
  only on this machine. If the live `high` should stay inspectable, it could be frozen as a new
  named-encounter eval case. That needs its own commit and its own snapshot, per the eval rules.

## Next command

```bash
gh pr view --web
```

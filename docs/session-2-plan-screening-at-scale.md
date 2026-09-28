# Session 2 Plan — Screening at Scale (Coarse Filter + KD-Tree)

*Drafted in Cowork, following session 1's real measurements. Implements the design from
`docs/adr/0003` (coarse orbital-regime filter + per-timestep KD-tree), but sequenced into
independently-validated steps rather than built all at once.*

## Session 1 numbers this plan is based on

At the current default scope (Iridium NEXT + Fengyun-1C debris, ~1,937 objects screened, 24h
window, 60s step):

- Propagation: 1.6–2.4s for 2.8M position calculations.
- Screening (naive all-pairs, ADR 0006's 485km-window + refine approach): 21–24s — **this is the
  bottleneck**, not propagation.
- Naive extrapolation to the full ~30k-object public catalog: 50+ minutes, ~7GB memory. The memory
  number in particular comes from materializing an effectively O(n²) pairwise-distance structure per
  timestep — at 30k objects that's ~900M pair-distances per timestep, ~7.2GB just for one timestep's
  distance matrix.

Both numbers point at the same place: the per-timestep all-pairs distance computation inside
`screen_conjunctions`, not orbit propagation, is what needs to change.

## Why this is sequenced, not built as one piece

`Engineering_Standards.md`'s core lesson from Claim Verification Agent — validate the real
cost/performance economics with a small spike before committing to full scope — applies here even
though there's no LLM cost involved. The equivalent risk is guessing at what scale needs, building
both the KD-tree swap and the orbital-regime coarse filter together, and only then discovering
that the KD-tree change alone might have been sufficient (or insufficient) for the intended catalog
size. So: measure after each piece, don't build the second piece until the first piece's real number
says whether it's needed.

## Step A — Replace the per-timestep all-pairs distance with a KD-tree radius query

Swap the O(n²) inner loop in `conjunction_screen.py` for `scipy.spatial.cKDTree`: build a tree of
all objects' positions at each timestep, query each point's neighbors within the same 485km
relative-motion radius the current implementation already uses (ADR 0006), then run the existing
between-sample interpolation/refinement on survivors exactly as today. This is an algorithmic
swap only — no change to the closest-approach math, the interpolation logic, or the risk model.

**Validation (required before moving to Step B):**
- Rerun the current default demo scope (Iridium NEXT + Fengyun-1C) and confirm the KD-tree version
  finds the *same* 509 conjunctions the naive version found (0 high / 31 moderate / 478 low, closest
  approach 1.29km) — a parity/regression check against the known-good session 1 result, not just
  "tests still pass."
- Record new timing for this same ~1,937-object scope. This number is the first real evidence of how
  much the KD-tree swap helps on its own, before any coarse filter is added.

## Step B — Scaling spike at a real, larger (but not full-catalog) scope

Once Step A's parity is confirmed, run the KD-tree version against a meaningfully larger real object
set — CelesTrak's `GROUP=active` (several thousand active satellites) layered on top of the existing
default scope is a reasonable next rung, well short of the full ~30k catalog. Measure actual
wall-clock time and actual memory (add lightweight memory measurement — e.g. `tracemalloc` or
`resource.getrusage` — to the structured JSON step logs from session 1, since the "~7GB" figure
so far is an extrapolation, not a measurement).

**This measured number, not the original naive extrapolation, decides whether Step C is needed.**

## Step C (conditional) — Orbital-regime coarse filter

Only if Step B's real numbers show the KD-tree version alone isn't sufficient for the intended
catalog scale: implement the perigee/apogee altitude-band pre-filter from ADR 0003 — eliminate
pairs whose orbital altitude ranges (derived once per object from TLE mean motion/eccentricity, not
re-derived per timestep) can't overlap, before any propagation/KD-tree work happens on that pair.

**Validation:** on the Step A/B scopes (where the true answer is already known), confirm the coarse
filter never eliminates a pair the KD-tree version would have flagged, before trusting it at larger
scale — exactly the check ADR 0003 already calls for.

## Definition of done for session 2

- Step A shipped and its parity check passed (identical 509-conjunction result on the default
  scope) — this alone is a legitimate stopping point if Step B's numbers turn out to make Step C
  unnecessary.
- A measured (not estimated) timing and memory number at the Step B scale.
- A documented decision — captured as its own ADR, written once the real numbers are in, the same
  way ADR 0006 was self-authored in session 1 — on whether the coarse filter was needed, and if so,
  what scale it unlocks.
- Session summary covering all measured numbers, decisions made, and whatever scope question is
  still open afterward (e.g. how close this gets to genuinely handling the full public catalog).

## Explicitly out of scope for session 2

- Containerization/deployment (ADR 0005 — still deferred).
- The project-specific eval-fast harness (still on `docs/todo.md` from session 1's follow-ups, not
  blocking this work).
- Revisiting the "full catalog all-vs-all" framing itself (an asymmetric primary-satellites-vs-full-catalog
  design would be cheaper computationally, and is closer to how real operators actually screen, but
  that's a scope question already settled in `Applied_AI_Portfolio_Plan.md`'s reframing rationale —
  worth a note in working-notes-and-decisions.md if Step B's numbers make it worth revisiting later,
  but not a session 2 redesign).

# Session 2026-10-04: dimming in the near-miss pair view (portfolio-site)

Implements the 2026-10-04 "Globe: dimming also applies when a top conjunction is shown (near-miss
pair view)" working-notes entry.

- **Code:** in `portfolio-site`, on branch `fix/satellite-globe-dim-near-miss`, cut from `main`
  after the dimming branch merged. Two commits, local only and not pushed.

## What changed

- **Pair view dims.** Showing a top conjunction dims every other point to `DIM_ALPHA` (0.2). Both
  pair objects stay at full strength, with their rings, dashed line and label as before.
  - It reuses the drawn-copy layer: `applyDim()` exempts `link.a`/`link.b` when the link is a pair,
    otherwise the inspected object and its neighbour.
  - The filter buffer, picking and the "Showing N of M" count are untouched.
- **Enter and exit.** `focusPair()` rebuilds the drawn colours on entry. Every exit already ran
  through `clearSelection()` or `setCatalog()`, both of which rebuild from the filter state: empty
  click, Deselect, picking an object, starting a station view, "Back to full view", and a
  snapshot swap. So restores are exact.
  - A filter change while a pair is shown (including the collision-history "show debris" toggle)
    doesn't leave the pair view. It re-dims from the new filter state, and the restore on exit
    then matches the new filters exactly.
- **Unchanged, per the entry:** station/group follow and debris isolation don't dim.

## A neighbour bug found and fixed along the way

Switching from a pair to an inspected object sometimes showed **no** nearest neighbour.
- **Cause:** with the clock frozen (as in a replay), every render slice is exact, so the
  live-neighbour error bound is 0. `nearestCandidates()` rebuilt its limit as `sqrt(min)^2`, which
  floating-point can round one ulp *below* `min`. That excluded the nearest itself and returned an
  empty candidate list. Whether it happened depended on the distance value.
- **Fix:** floor the limit at `min`. It's in its own commit, with a regression test (distance² = 3,
  where `Math.sqrt(3) ** 2` is 2.9999999999999996) that failed before the fix.
- **Scope:** this affected the live-neighbour round's code whenever the clock was frozen, not just
  this branch.

## Verification

All in `portfolio-site`, headed Chromium on the M5, live data, with the dev-only debug hook. "Frames
correct" means the points drawn at full strength were exactly the current selection's exempt set
on every rendered frame.

- **Three different top conjunctions**, each switched to from the previous one: 155/155, 157/157
  and 157/157 frames correct.
- **Pair to inspected object:** 151/151 (now with the neighbour bright).
- **Inspected object to pair:** 157/157.
- **Pair to empty click, and pair to station view:** the drawn colours equal the filter buffer,
  value for value.
- **Filters and owner colouring** (OneWeb and China hidden): with a pair shown, 4,133 hidden and
  15,111 dimmed (every shown point except the pair), and no point dimmed to zero. The filter bar
  was unchanged. After "Back", the drawn colours equal the filter buffer and the filter buffer
  itself was never modified.
- **Historical replay:** the slider moved into a 2026-10-02 snapshot, simulated because the bucket
  only retains 2026-10-03, which is also the current run. The conjunctions table switched to that
  snapshot, and replaying one swapped the catalog and kept the dimming: 211/211 frames correct.
- **Frame time** with a pair shown: 16.7 ms mean, p95 17.6, at both 1x and 4x CPU throttling.
- **Errors:** none on the page.
- **Checks:** `npm run lint`, `npx tsc -b` and `npm run build` are clean. `npm test` passes 30/30.
  The dev hook is absent from the production build.

## Note

`history/index.json` still lists only 2026-10-03 (run `20261003T2146Z-05c185`), as of 16:10Z on
2026-10-04. The daily schedule hasn't produced a new run yet; the to-do's "Watch the daily
schedule" item covers it.

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..fix/satellite-globe-dim-near-miss && npm run dev
# after review: git push && gh pr create --fill
```

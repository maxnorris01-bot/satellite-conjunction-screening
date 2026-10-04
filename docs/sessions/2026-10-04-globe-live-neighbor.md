# Session 2026-10-04: live nearest neighbour and 1x/10x/50x speeds (portfolio-site)

Implements the 2026-10-04 "Globe: live nearest neighbour, and playback speeds 1x/10x/50x"
working-notes entry.

- **Code:** in `portfolio-site`, on branch `fix/satellite-globe-live-neighbor`, cut from `main`
  after the Phase 1c fix round merged. Two commits, local only and not pushed.
- **Scope:** orientation and the slice=10 render propagation are unchanged.
- An untracked `.nn_check.tmp.mjs` in `portfolio-site` isn't from this session; it was left
  alone and not committed.

## 1. Live nearest neighbour

**Cost measured first,** in headed Chromium on the M5 with the dev-only debug hook. One exact
full-catalog scan (19,246 propagations) took a median **5.2 ms** (max 9.2), and **19.6 ms** (max
21.6) at 4x CPU throttling.
- **At 1x:** once a second means a dropped frame every second on a slow machine.
- **At 50x:** the entry's "no slower in sim terms" means a refresh every sim-second, about every
  frame. 20 ms a frame doesn't fit a 16.7 ms budget, so a plain full scan was ruled out.

**Chosen: a candidate set with a proven bound, and no periodic full scan.**
- **Inputs:** the renderer already has every object's position, propagated within the last
  SLICE (10) frames. The engine now records the displayed time each slice was propagated at.
- **The bound:** no tracked object moves faster than 11 km/s, so each render position is within
  E = 11 km/s x (worst slice staleness) of the truth. The true nearest must then lie within the
  render-space minimum distance + 4E.
- **Each refresh:**
  1. One cheap distance pass over the render positions (no propagation) finds those candidates.
  2. Only the candidates and the selected object are propagated exactly at the displayed time,
     and the nearest among them is the result.
  - **Size in practice:** 2-5 candidates at 1x and 10x, at most 38 at 50x.
- **After a large time jump** (scrubbing hours), the bound covers more than 3,000 objects, so the
  refresh waits a few frames for the slices to catch up. The line hides meanwhile rather than
  pointing at a stale neighbour.
- **Cadence:** at least once a second of wall time, every sim-second at higher speeds, and
  immediately after a selection, filter change or time jump. The dashed line and label move to
  the new neighbour when it changes.
- **Test:** a randomized unit test checks the guarantee: the true nearest is always among the
  candidates when every position is within the bound. Shrinking the margin to 1E or 2E fails it.

**Panel:** the Update link and the "found at the moment you clicked" note are gone. The panel
says the neighbour is live, follows the displayed time, and counts only objects shown.

## 2. Hidden objects

The search considers only visible objects, by both colour-category toggles and name filters, so
the line always ends on a shown point. When filters leave no other visible object, the panel says
"No visible object" and draws no line.

As the entry anticipated, the "nearest" changes with the filters. With only Iridium 33 debris
shown, a selected object's neighbour became an `IRIDIUM 33 DEB` about 1,480 km away, which
matches brute force. That's correct for "nearest *visible*" and reads fine with the panel note,
but it is a different answer from the unfiltered one.

## 3. Speeds 1x, 10x, 50x

- **`SPEEDS`** in `globe/clock.ts` is now `[1, 10, 50]`. Nothing else assumed the old set; the
  labels are generated from it, and a test pins the new set.
- **Neighbour refresh** at 50x runs by sim time (verified below).
- **Station follow:** fine at 50x.
- **Live offset display:** works ("Oct 4, 15:50:17 UTC · 50× · in 3m").
- **New guard:** at 50x, Live reaches the slider's ~24 h forward limit in about half an hour. It
  now pauses there instead of running past the data, and the controls update to show paused.
- **Older bug fixed:** the offset label could read "in 23h 60m"; minutes now round before the
  hours split.

## Acceptance

All in `portfolio-site`, headed Chromium on the M5 against the live bucket.
- **Method:** 4 random objects per speed, each played for 15 s, sampled every second, so 60
  samples per speed. Each sample compares the displayed neighbour with an independent brute force
  over every visible object at the displayed time.
- **Throttle allowance:** in the time since the last refresh, each separation can change by at
  most 22 km/s x lag.

| Speed | Same object as brute force | Within throttle allowance | Worst excess | Max candidates |
|---|---|---|---|---|
| 1x | 57/60 | 60/60 | 5.1 km | 2 |
| 10x | 59/60 | 60/60 | 1.5 km | 5 |
| 50x | 60/60 | 60/60 | 6.8 km | 38 |

- **Scrubbing** +5 h while paused re-ran the search and matched brute force.
- **Frame time** at 50x with an object selected: 16.7 ms mean, p95 17.7, unthrottled; 16.7 ms
  mean, p95 17.6, at 4x CPU throttling.
- **Errors:** none on the page.
- **Checks:** `npm run lint`, `npx tsc -b` and `npm run build` are clean. `npm test` passes 28/28,
  4 new. The globe chunk is 158.1 KB gzipped, and the dev hook is absent from the production
  build.

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..fix/satellite-globe-live-neighbor && npm run dev
# after review: git push && gh pr create --fill
```

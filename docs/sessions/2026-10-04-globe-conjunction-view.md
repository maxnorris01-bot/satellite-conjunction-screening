# Session 2026-10-04: making the top-conjunction view reliable (portfolio-site)

Implements the 2026-10-04 "Globe: make the top-conjunction view reliable (rings vanish, fly-in
unreliable)" working-notes entry.

- **Code:** in `portfolio-site`, on branch `fix/satellite-globe-conjunction-view`, cut from `main`
  after the near-miss dimming merged. Two commits, local only and not pushed.

## Missing rings: reproduced first, cause confirmed (a variant of the hypothesis)

- **Instrumentation.** Every moved marker (pair rings, inspect ring, station ring, dashed line) now
  stamps the frame number from three.js's `onBeforeRender`, which only fires for objects that
  survive frustum culling. `debugState().drawn` reports which markers were *actually* rendered in
  the last frame, separately from `visible`.
- **Origin hypothesis tested.** Putting the camera beside the pair, with Earth's centre out of
  frame, did *not* reproduce it. The rings were still drawn.
- **Real cause.** three.js computes a marker's bounding sphere lazily, at the first render after
  it becomes visible. That's not at creation, so it was never at the origin; it was wherever the
  marker first appeared. The sphere is never updated after that.
  - Showing conjunctions #1, #4, #7, #2, #9 in a row, the ring sphere stayed at conjunction #1's
    position throughout.
  - At #7 the rings and line were `visible: true` but not drawn while the label showed, which is
    Max's screenshot exactly.
  - The others happened to work only because #1's spot was still inside the view frustum, which
    extends behind the Earth.
  - Manual inspect "worked" because its camera stays centred on Earth, where almost any LEO
    position is inside the frustum.
- **Fix** (the same as the entry proposed): `frustumCulled = false` on `ringA`, `ringB`,
  `ringInspect`, `ringGroup` and `linkLine`. After the fix, all five conjunctions draw both rings
  and the line.

## Fly-in: investigated separately; the mechanics were already sound

A script selected conjunctions 19 times in mixed order, from every starting state:
- free roam, an inspected object, an ISS station view, and a Tiangong view interrupted mid-flight
- another conjunction (several hops), and the same conjunction twice (once after moving the camera,
  once mid-flight)
- a fly-in interrupted mid-flight by another conjunction
- immediately after a scroll-zoom, and immediately after a fast drag
- two conjunctions on a different day's snapshot (simulated 2026-10-02), then back on the latest run

It also checked the exits: Back, Back mid-flight, empty click, picking an object, and Live.

After each change it asserted the full end state:
- **Camera:** target on the pair midpoint (within 20 km), camera 0.9 R from it, zoom floor
  `FOCUS_MIN_DISTANCE`, animation finished, controls re-enabled.
- **Markers:** rings and line actually drawn, label shown.
- **Clock:** frozen at the TCA.
- **Dimming and other rings:** only the pair bright, no stray station or inspect ring.
- **On exit:** target back at Earth's centre, floor 1.1, nothing animating.

| Code | End states correct | Failures |
|---|---|---|
| Before the fix | 21/25 | 4: rings and line not drawn |
| After the fix | 25/25 | none |

- **Before the fix, the camera ended correctly in all 25 cases, including the 4 failures.** The
  "zoom doesn't always work" report is most plausibly the culling bug seen from a distance: a
  fly-in ending about 5,700 km from a sub-pixel pair with no rings looks as if nothing happened.
- **Suspects from the entry, checked:**
  - **Same conjunction twice:** works. The page creates a new focus object on every click, so the
    effect re-runs.
  - **Momentum from a scroll or drag:** didn't disturb the end state.
  - **Racing animations:** `focusPair`/`focusGroup`/`resetView` could start a throwaway ease-out
    (via `clearSelection`) that the fly-in immediately replaced. This caused no wrong end states,
    but it's removed anyway (`clearSelection(release = false)`), so a selection change starts
    exactly one camera animation. That's the second commit.
- **Kept:** the fly-in end distance (0.9 R). With the rings drawn, the pair reads clearly there;
  most flagged misses are tens of metres, so the rings, not the dots, are the readout. The
  conjunction path is still the same single-selection code as manual picks.

## Verification

All in `portfolio-site`, headed Chromium on the M5, live data.

- **Pixel check.** Each check renders a frame, reads it back with `readPixels`, and counts pixels
  of ring B's gold.
  - Over four conjunctions (#1, #7, #4, #9), at the end of each fly-in: about 3,540-3,560 gold
    pixels.
  - With the camera beside the pair and Earth's centre out of frame: about 3,550-3,560.
  - Nothing selected: 0.
- **Manual inspect** is unchanged: the camera doesn't move, the floor stays 1.1, and the inspect
  ring and neighbour line are drawn.
- **Frame time** with a pair shown: 16.7 ms mean, p95 17.7, unthrottled; 16.7 ms mean, p95 17.6,
  at 4x CPU throttling.
- **Errors:** none on the page.
- **Checks:** `npm run lint`, `npx tsc -b` and `npm run build` are clean. `npm test` passes 30/30.
  The dev hook is absent from the production build. The `onBeforeRender` stamps run in production
  too but are trivially cheap.

## Next commands

```bash
cd ../portfolio-site && git log --oneline main..fix/satellite-globe-conjunction-view && npm run dev
# after review: git push && gh pr create --fill
```
